import json, gevent, time, sys, hashlib
from Config import config
from Site import SiteManager
from Debug import Debug
from util import QueryJson
from Plugin import PluginManager

@PluginManager.acceptPlugins
class UiWebsocket(object):
	def __init__(self, ws, site, server, user):
		self.ws = ws
		self.site = site
		self.user = user
		self.log = site.log
		self.server = server
		self.next_message_id = 1
		self.waiting_cb = {} # Waiting for callback. Key: message_id, Value: function pointer
		self.channels = [] # Channels joined to
		self.sending = False # Currently sending to client
		self.send_queue = [] # Messages to send to client


	# Start listener loop
	def start(self):
		ws = self.ws
		if self.site.address == config.homepage and not self.site.page_requested: # Add open fileserver port message or closed port error to homepage at first request after start
			if config.ip_external: 
				self.site.notifications.append(["done", "Congratulation, your port <b>"+str(config.fileserver_port)+"</b> is opened. <br>You are full member of ZeroNet network!", 10000])
			elif config.ip_external == False:
				self.site.notifications.append(["error", "Your network connection is restricted. Please, open <b>"+str(config.fileserver_port)+"</b> port <br>on your router to become full member of ZeroNet network.", 0])
		self.site.page_requested = True # Dont add connection notification anymore

		for notification in self.site.notifications: # Send pending notification messages
			self.cmd("notification", notification)
		self.site.notifications = []
		while True:
			try:
				message = ws.receive()
				if message:
					self.handleRequest(message)
			except Exception, err:
				if err.message != 'Connection is already closed':
					if config.debug: # Allow websocket errors to appear on /Debug 
						import sys
						sys.modules["main"].DebugHook.handleError() 
					self.log.error("WebSocket error: %s" % Debug.formatException(err))
				return "Bye."


	# Event in a channel
	def event(self, channel, *params):
		if channel in self.channels: # We are joined to channel
			if channel == "siteChanged":
				site = params[0] # Triggerer site
				site_info = self.formatSiteInfo(site)
				if len(params) > 1 and params[1]: # Extra data
					site_info.update(params[1])
				self.cmd("setSiteInfo", site_info)


	# Send response to client (to = message.id)
	def response(self, to, result):
		self.send({"cmd": "response", "to": to, "result": result})


	# Send a command
	def cmd(self, cmd, params={}, cb = None):
		self.send({"cmd": cmd, "params": params}, cb)


	# Encode to json and send message
	def send(self, message, cb = None):
		message["id"] = self.next_message_id # Add message id to allow response
		self.next_message_id += 1
		if cb: # Callback after client responsed
			self.waiting_cb[message["id"]] = cb
		if self.sending: return # Already sending 
		self.send_queue.append(message)
		try:
			while self.send_queue:
				self.sending = True
				message = self.send_queue.pop(0)
				self.ws.send(json.dumps(message))
				self.sending = False
		except Exception, err:
			self.log.debug("Websocket send error: %s" % Debug.formatException(err))


	# Handle incoming messages
	def handleRequest(self, data):
		req = json.loads(data)

		cmd = req.get("cmd")
		params = req.get("params")
		permissions = self.site.settings["permissions"]
		if req["id"] >= 1000000: # Its a wrapper command, allow admin commands
			permissions = permissions[:] 
			permissions.append("ADMIN")

		if cmd == "response": # It's a response to a command
			return self.actionResponse(req["to"], req["result"])
		elif cmd == "ping":
			func = self.actionPing
		elif cmd == "channelJoin":
			func = self.actionChannelJoin
		elif cmd == "siteInfo":
			func = self.actionSiteInfo
		elif cmd == "serverInfo":
			func = self.actionServerInfo
		elif cmd == "siteUpdate":
			func = self.actionSiteUpdate
		elif cmd == "sitePublish":
			func = self.actionSitePublish
		elif cmd == "fileWrite":
			func = self.actionFileWrite
		elif cmd == "fileGet":
			func = self.actionFileGet
		elif cmd == "fileQuery":
			func = self.actionFileQuery
		elif cmd == "dbQuery":
			func = self.actionDbQuery
		# Admin commands
		elif cmd == "sitePause" and "ADMIN" in permissions:
			func = self.actionSitePause
		elif cmd == "siteResume" and "ADMIN" in permissions:
			func = self.actionSiteResume
		elif cmd == "siteDelete" and "ADMIN" in permissions:
			func = self.actionSiteDelete
		elif cmd == "siteList" and "ADMIN" in permissions:
			func = self.actionSiteList
		elif cmd == "siteSetLimit" and "ADMIN" in permissions:
			func = self.actionSiteSetLimit
		elif cmd == "channelJoinAllsite" and "ADMIN" in permissions:
			func = self.actionChannelJoinAllsite
		elif cmd == "serverUpdate" and "ADMIN" in permissions:
			func = self.actionServerUpdate
		else:
			func_name = "action" + cmd[0].upper() + cmd[1:]
			func = getattr(self, func_name, None)
			if not func: # Unknown command
				self.response(req["id"], "Unknown command: %s" % cmd)
				return

		# Support calling as named, unnamed paramters and raw first argument too
		if type(params) is dict:
			func(req["id"], **params)
		elif type(params) is list:
			func(req["id"], *params)
		else:
			func(req["id"], params)


	# - Actions -

	# Do callback on response {"cmd": "response", "to": message_id, "result": result}
	def actionResponse(self, to, result):
		if to in self.waiting_cb:
			self.waiting_cb[to](result) # Call callback function
		else:
			self.log.error("Websocket callback not found: %s, %s" % (to, result))


	# Send a simple pong answer
	def actionPing(self, to):
		self.response(to, "pong")


	# Format site info
	def formatSiteInfo(self, site, create_user=True):
		content = site.content_manager.contents.get("content.json")
		if content: # Remove unnecessary data transfer
			content = content.copy()
			content["files"] = len(content.get("files", {}))
			content["includes"] = len(content.get("includes", {}))
			if "sign" in content: del(content["sign"])
			if "signs" in content: del(content["signs"])

		settings = site.settings.copy()
		del settings["wrapper_key"] # Dont expose wrapper key
		del settings["auth_key"] # Dont send auth key twice

		ret = {
			"auth_key": self.site.settings["auth_key"], # Obsolete, will be removed
			"auth_key_sha512": hashlib.sha512(self.site.settings["auth_key"]).hexdigest()[0:64], # Obsolete, will be removed
			"auth_address": self.user.getAuthAddress(site.address, create=create_user),
			"address": site.address,
			"settings": settings,
			"content_updated": site.content_updated,
			"bad_files": len(site.bad_files),
			"size_limit": site.getSizeLimit(),
			"next_size_limit": site.getNextSizeLimit(),
			"peers": site.settings.get("peers", len(site.peers)),
			"started_task_num": site.worker_manager.started_task_num,
			"tasks": len(site.worker_manager.tasks),
			"workers": len(site.worker_manager.workers),
			"content": content
		}
		if site.settings["serving"] and content: ret["peers"] += 1 # Add myself if serving
		return ret


	# Send site details
	def actionSiteInfo(self, to):
		ret = self.formatSiteInfo(self.site)
		self.response(to, ret)


	# Join to an event channel
	def actionChannelJoin(self, to, channel):
		if channel not in self.channels:
			self.channels.append(channel)


	def formatServerInfo(self):
		return {
			"ip_external": bool(config.ip_external),
			"platform": sys.platform,
			"fileserver_ip": config.fileserver_ip,
			"fileserver_port": config.fileserver_port,
			"ui_ip": config.ui_ip,
			"ui_port": config.ui_port,
			"version": config.version,
			"debug": config.debug,
			"plugins": PluginManager.plugin_manager.plugin_names
		}


	# Server variables
	def actionServerInfo(self, to):
		ret = self.formatServerInfo()
		self.response(to, ret)


	def actionSitePublish(self, to, privatekey=None, inner_path="content.json"):
		site = self.site
		if not inner_path.endswith("content.json"): # Find the content.json first
			inner_path = site.content_manager.getFileInfo(inner_path)["content_inner_path"]

		if not site.settings["own"] and self.user.getAuthAddress(self.site.address) not in self.site.content_manager.getValidSigners(inner_path): 
			return self.response(to, "Forbidden, you can only modify your own sites")
		if not privatekey: # Get privatekey from users.json
			privatekey = self.user.getAuthPrivatekey(self.site.address)

		# Signing
		site.content_manager.loadContent(add_bad_files=False) # Reload content.json, ignore errors to make it up-to-date
		signed = site.content_manager.sign(inner_path, privatekey) # Sign using private key sent by user
		if signed:
			if inner_path == "content_json": self.cmd("notification", ["done", "Private key correct, content signed!", 5000]) # Display message for 5 sec
		else:
			self.cmd("notification", ["error", "Content sign failed: invalid private key."])
			self.response(to, "Site sign failed")
			return
		site.content_manager.loadContent(add_bad_files=False) # Load new content.json, ignore errors

		# Publishing
		if not site.settings["serving"]: # Enable site if paused
			site.settings["serving"] = True
			site.saveSettings()
			site.announce()

		published = site.publish(5, inner_path) # Publish to 5 peer

		if published>0: # Successfuly published
			self.cmd("notification", ["done", "Content published to %s peers." % published, 5000])
			self.response(to, "ok")
			site.updateWebsocket() # Send updated site data to local websocket clients
		else:
			if len(site.peers) == 0:
				self.cmd("notification", ["info", "No peers found, but your content is ready to access."])
				self.response(to, "No peers found, but your content is ready to access.")
			else:
				self.cmd("notification", ["error", "Content publish failed."])
				self.response(to, "Content publish failed.")


	# Write a file to disk
	def actionFileWrite(self, to, inner_path, content_base64):
		if not self.site.settings["own"] and self.user.getAuthAddress(self.site.address) not in self.site.content_manager.getValidSigners(inner_path):
			return self.response(to, "Forbidden, you can only modify your own files")

		try:
			import base64
			content = base64.b64decode(content_base64)
			self.site.storage.write(inner_path, content)
		except Exception, err:
			return self.response(to, "Write error: %s" % err)

		if inner_path.endswith("content.json"):
			self.site.content_manager.loadContent(inner_path, add_bad_files=False)

		return self.response(to, "ok")

	
	# Find data in json files
	def actionFileQuery(self, to, dir_inner_path, query):
		# s = time.time()
		dir_path = self.site.storage.getPath(dir_inner_path)
		rows = list(QueryJson.query(dir_path, query))
		# self.log.debug("FileQuery %s %s done in %s" % (dir_inner_path, query, time.time()-s))
		return self.response(to, rows)
	

	# Sql query
	def actionDbQuery(self, to, query, params=None):
		rows = []
		try:
			res = self.site.storage.query(query, params)
		except Exception, err: # Response the error to client
			return self.response(to, {"error": str(err)})
		# Convert result to dict
		for row in res:
			rows.append(dict(row))
		return self.response(to, rows)


	# Return file content
	def actionFileGet(self, to, inner_path):
		try:
			self.site.needFile(inner_path, priority=1)
			body = self.site.storage.read(inner_path)
		except:
			body = None
		return self.response(to, body)


	# - Admin actions -
	
	# List all site info
	def actionSiteList(self, to):
		ret = []
		SiteManager.site_manager.load() # Reload sites
		for site in self.server.sites.values():
			if not site.content_manager.contents.get("content.json"): continue # Broken site
			ret.append(self.formatSiteInfo(site, create_user=False)) # Dont generate the auth_address on listing
		self.response(to, ret)


	# Join to an event channel on all sites
	def actionChannelJoinAllsite(self, to, channel):
		if channel not in self.channels: # Add channel to channels
			self.channels.append(channel)

		for site in self.server.sites.values(): # Add websocket to every channel
			if self not in site.websockets:
				site.websockets.append(self)


	# Update site content.json
	def actionSiteUpdate(self, to, address):
		site = self.server.sites.get(address)
		if site and (site.address == self.site.address or "ADMIN" in self.site.settings["permissions"]):
			gevent.spawn(site.update)
		else:
			self.response(to, {"error": "Unknown site: %s" % address})


	# Pause site serving
	def actionSitePause(self, to, address):
		site = self.server.sites.get(address)
		if site:
			site.settings["serving"] = False
			site.saveSettings()
			site.updateWebsocket()
			site.worker_manager.stopWorkers()
		else:
			self.response(to, {"error": "Unknown site: %s" % address})


	# Resume site serving
	def actionSiteResume(self, to, address):
		site = self.server.sites.get(address)
		if site:
			site.settings["serving"] = True
			site.saveSettings()
			gevent.spawn(site.update)
			time.sleep(0.001) # Wait for update thread starting
			site.updateWebsocket()
		else:
			self.response(to, {"error": "Unknown site: %s" % address})


	def actionSiteDelete(self, to, address):
		site = self.server.sites.get(address)
		if site:
			site.settings["serving"] = False
			site.saveSettings()
			site.worker_manager.running = False
			site.worker_manager.stopWorkers()
			site.storage.deleteFiles()
			SiteManager.site_manager.delete(address)
			site.updateWebsocket()
		else:
			self.response(to, {"error": "Unknown site: %s" % address})


	def actionSiteSetLimit(self, to, size_limit):
		self.site.settings["size_limit"] = size_limit
		self.site.saveSettings()
		self.response(to, "Site size limit changed to %sMB" % size_limit)
		self.site.download()


	def actionServerUpdate(self, to):
		import sys
		self.cmd("updating")
		sys.modules["main"].update_after_shutdown = True
		sys.modules["main"].file_server.stop()
		sys.modules["main"].ui_server.stop()


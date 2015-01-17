import json, gevent, time, sys, hashlib
from Config import config
from Site import SiteManager
from Debug import Debug

class UiWebsocket:
	def __init__(self, ws, site, server):
		self.ws = ws
		self.site = site
		self.log = site.log
		self.server = server
		self.next_message_id = 1
		self.waiting_cb = {} # Waiting for callback. Key: message_id, Value: function pointer
		self.channels = [] # Channels joined to


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
						sys.modules["src.main"].DebugHook.handleError() 
					self.log.error("WebSocket error: %s" % Debug.formatException(err))
				return "Bye."


	# Event in a channel
	def event(self, channel, *params):
		if channel in self.channels: # We are joined to channel
			if channel == "siteChanged":
				site = params[0] # Triggerer site
				site_info = self.siteInfo(site)
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
		try:
			self.ws.send(json.dumps(message))
			if cb: # Callback after client responsed
				self.waiting_cb[message["id"]] = cb
		except Exception, err:
			self.log.debug("Websocket send error: %s" % Debug.formatException(err))


	# Handle incoming messages
	def handleRequest(self, data):
		req = json.loads(data)
		cmd = req["cmd"]
		permissions = self.site.settings["permissions"]
		if cmd == "response":
			self.actionResponse(req)
		elif cmd == "ping":
			self.actionPing(req["id"])
		elif cmd == "channelJoin":
			self.actionChannelJoin(req["id"], req["params"])
		elif cmd == "siteInfo":
			self.actionSiteInfo(req["id"], req["params"])
		elif cmd == "serverInfo":
			self.actionServerInfo(req["id"], req["params"])
		elif cmd == "siteUpdate":
			self.actionSiteUpdate(req["id"], req["params"])
		# Admin commands
		elif cmd == "sitePause" and "ADMIN" in permissions:
			self.actionSitePause(req["id"], req["params"])
		elif cmd == "siteResume" and "ADMIN" in permissions:
			self.actionSiteResume(req["id"], req["params"])
		elif cmd == "siteList" and "ADMIN" in permissions:
			self.actionSiteList(req["id"], req["params"])
		elif cmd == "channelJoinAllsite" and "ADMIN" in permissions:
			self.actionChannelJoinAllsite(req["id"], req["params"])
		# Unknown command
		else:
			self.response(req["id"], "Unknown command: %s" % cmd)


	# - Actions -

	# Do callback on response {"cmd": "response", "to": message_id, "result": result}
	def actionResponse(self, req):
		if req["to"] in self.waiting_cb:
			self.waiting_cb(req["result"]) # Call callback function
		else:
			self.log.error("Websocket callback not found: %s" % req)


	# Send a simple pong answer
	def actionPing(self, to):
		self.response(to, "pong")


	# Format site info
	def siteInfo(self, site):
		ret = {
			"auth_id": self.site.settings["auth_key"][0:10],
			"auth_id_md5": hashlib.md5(self.site.settings["auth_key"][0:10]).hexdigest(),
			"address": site.address,
			"settings": site.settings,
			"content_updated": site.content_updated,
			"bad_files": site.bad_files.keys(),
			"last_downloads": site.last_downloads,
			"peers": len(site.peers),
			"tasks": [task["inner_path"] for task in site.worker_manager.tasks],
			"content": site.content
		}
		if site.settings["serving"] and site.content: ret["peers"] += 1 # Add myself if serving
		return ret


	# Send site details
	def actionSiteInfo(self, to, params):
		ret = self.siteInfo(self.site)
		self.response(to, ret)


	# Join to an event channel
	def actionChannelJoin(self, to, params):
		if params["channel"] not in self.channels:
			self.channels.append(params["channel"])


	# Server variables
	def actionServerInfo(self, to, params):
		ret = {
			"ip_external": bool(config.ip_external),
			"platform": sys.platform,
			"fileserver_ip": config.fileserver_ip,
			"fileserver_port": config.fileserver_port,
			"ui_ip": config.ui_ip,
			"ui_port": config.ui_port,
			"version": config.version,
			"debug": config.debug
		}
		self.response(to, ret)


	# - Admin actions -
	
	# List all site info
	def actionSiteList(self, to, params):
		ret = []
		SiteManager.load() # Reload sites
		for site in self.server.sites.values():
			if not site.content: continue # Broken site
			ret.append(self.siteInfo(site))
		self.response(to, ret)


	# Join to an event channel on all sites
	def actionChannelJoinAllsite(self, to, params):
		if params["channel"] not in self.channels: # Add channel to channels
			self.channels.append(params["channel"])

		for site in self.server.sites.values(): # Add websocket to every channel
			if self not in site.websockets:
				site.websockets.append(self)


	# Update site content.json
	def actionSiteUpdate(self, to, params):
		address = params.get("address")
		site = self.server.sites.get(address)
		if site and (site.address == self.site.address or "ADMIN" in self.site.settings["permissions"]):
			gevent.spawn(site.update)
		else:
			self.response(to, {"error": "Unknown site: %s" % address})


	# Pause site serving
	def actionSitePause(self, to, params):
		address = params.get("address")
		site = self.server.sites.get(address)
		if site:
			site.settings["serving"] = False
			site.saveSettings()
			site.updateWebsocket()
		else:
			self.response(to, {"error": "Unknown site: %s" % address})


	# Resume site serving
	def actionSiteResume(self, to, params):
		address = params.get("address")
		site = self.server.sites.get(address)
		if site:
			site.settings["serving"] = True
			site.saveSettings()
			gevent.spawn(site.update)
			time.sleep(0.001) # Wait for update thread starting
			site.updateWebsocket()
		else:
			self.response(to, {"error": "Unknown site: %s" % address})

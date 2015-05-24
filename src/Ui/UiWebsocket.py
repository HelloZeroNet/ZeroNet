import json, gevent, time, sys, hashlib
from Config import config
from Site import SiteManager
from Debug import Debug
from util import QueryJson, RateLimit
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
			if sys.modules["main"].file_server.port_opened == True: 
				self.site.notifications.append(["done", "Congratulation, your port <b>"+str(config.fileserver_port)+"</b> is opened. <br>You are full member of ZeroNet network!", 10000])
			elif sys.modules["main"].file_server.port_opened == False:
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

		admin_commands = ("sitePause", "siteResume", "siteDelete", "siteList", "siteSetLimit", "channelJoinAllsite", "serverUpdate", "certSet")

		if cmd == "response": # It's a response to a command
			return self.actionResponse(req["to"], req["result"])
		elif cmd in admin_commands and "ADMIN" not in permissions: # Admin commands
			return self.response(req["id"], "You don't have permission to run %s" % cmd)
		else: # Normal command
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


	# Format site info
	def formatSiteInfo(self, site, create_user=True):
		content = site.content_manager.contents.get("content.json")
		if content: # Remove unnecessary data transfer
			content = content.copy()
			content["files"] = len(content.get("files", {}))
			content["includes"] = len(content.get("includes", {}))
			if "sign" in content: del(content["sign"])
			if "signs" in content: del(content["signs"])
			if "signers_sign" in content: del(content["signers_sign"])

		settings = site.settings.copy()
		del settings["wrapper_key"] # Dont expose wrapper key
		del settings["auth_key"] # Dont send auth key twice

		ret = {
			"auth_key": self.site.settings["auth_key"], # Obsolete, will be removed
			"auth_key_sha512": hashlib.sha512(self.site.settings["auth_key"]).hexdigest()[0:64], # Obsolete, will be removed
			"auth_address": self.user.getAuthAddress(site.address, create=create_user),
			"cert_user_id": self.user.getCertUserId(site.address),
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


	def formatServerInfo(self):
		return {
			"ip_external": bool(sys.modules["main"].file_server.port_opened),
			"platform": sys.platform,
			"fileserver_ip": config.fileserver_ip,
			"fileserver_port": config.fileserver_port,
			"ui_ip": config.ui_ip,
			"ui_port": config.ui_port,
			"version": config.version,
			"rev": config.rev,
			"debug": config.debug,
			"plugins": PluginManager.plugin_manager.plugin_names
		}


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


	# Send site details
	def actionSiteInfo(self, to, file_status = None):
		ret = self.formatSiteInfo(self.site)
		if file_status: # Client queries file status
			if self.site.storage.isFile(file_status): # File exits, add event done
				ret["event"] = ("file_done", file_status)
		self.response(to, ret)


	# Join to an event channel
	def actionChannelJoin(self, to, channel):
		if channel not in self.channels:
			self.channels.append(channel)


	# Server variables
	def actionServerInfo(self, to):
		ret = self.formatServerInfo()
		self.response(to, ret)


	def actionSitePublish(self, to, privatekey=None, inner_path="content.json"):
		site = self.site
		extend = {} # Extended info for signing
		if not inner_path.endswith("content.json"): # Find the content.json first
			file_info = site.content_manager.getFileInfo(inner_path)
			inner_path = file_info["content_inner_path"]
			if "cert_signers" in file_info: # Its an user dir file
				cert = self.user.getCert(self.site.address)
				extend["cert_auth_type"] = cert["auth_type"]
				extend["cert_user_id"] = self.user.getCertUserId(site.address)
				extend["cert_sign"] = cert["cert_sign"]


		if not site.settings["own"] and self.user.getAuthAddress(self.site.address) not in self.site.content_manager.getValidSigners(inner_path): 
			return self.response(to, "Forbidden, you can only modify your own sites")
		if not privatekey: # Get privatekey from users.json
			privatekey = self.user.getAuthPrivatekey(self.site.address)

		# Signing
		site.content_manager.loadContent(add_bad_files=False) # Reload content.json, ignore errors to make it up-to-date
		signed = site.content_manager.sign(inner_path, privatekey, extend=extend) # Sign using private key sent by user
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


		event_name = "publish %s %s" % (site.address, inner_path)
		thread = RateLimit.callAsync(event_name, 7, site.publish, 5, inner_path) # Only publish once in 7 second to 5 peers
		notification = "linked" not in dir(thread) # Only display notification on first callback
		thread.linked = True
		thread.link(lambda thread: self.cbSitePublish(to, thread, notification)) # At the end callback with request id and thread


	# Callback of site publish
	def cbSitePublish(self, to, thread, notification=True):
		site = self.site
		published = thread.value
		if published>0: # Successfuly published
			if notification: self.cmd("notification", ["done", "Content published to %s peers." % published, 5000])
			self.response(to, "ok")
			if notification: site.updateWebsocket() # Send updated site data to local websocket clients
		else:
			if len(site.peers) == 0:
				if notification: self.cmd("notification", ["info", "No peers found, but your content is ready to access."])
				self.response(to, "No peers found, but your content is ready to access.")
			else:
				if notification: self.cmd("notification", ["error", "Content publish failed."])
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

		self.response(to, "ok")

		# Send sitechanged to other local users
		for ws in self.site.websockets:
			if ws != self:
				ws.event("siteChanged", self.site, {"event": ["file_done", inner_path]})
		

	
	# Find data in json files
	def actionFileQuery(self, to, dir_inner_path, query):
		# s = time.time()
		dir_path = self.site.storage.getPath(dir_inner_path)
		rows = list(QueryJson.query(dir_path, query))
		# self.log.debug("FileQuery %s %s done in %s" % (dir_inner_path, query, time.time()-s))
		return self.response(to, rows)
	

	# Sql query
	def actionDbQuery(self, to, query, params=None, wait_for=None):
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
	def actionFileGet(self, to, inner_path, required=True):
		try:
			if required: self.site.needFile(inner_path, priority=1)
			body = self.site.storage.read(inner_path)
		except:
			body = None
		return self.response(to, body)


	def actionFileRules(self, to, inner_path):
		rules = self.site.content_manager.getRules(inner_path)
		if inner_path.endswith("content.json"):
			content = self.site.content_manager.contents.get(inner_path)
			if content:
				rules["current_size"] = len(json.dumps(content)) + sum([file["size"] for file in content["files"].values()])
			else:
				rules["current_size"] = 0
		return self.response(to, rules)


	# Add certificate to user
	def actionCertAdd(self, to, domain, auth_type, auth_user_name, cert):
		try:
			res = self.user.addCert(self.user.getAuthAddress(self.site.address), domain, auth_type, auth_user_name, cert)
			if res == True:
				self.cmd("notification", ["done", "New certificate added: <b>%s/%s@%s</b>." % (auth_type, auth_user_name, domain)])
				self.response(to, "ok")
			else:
				self.response(to, "Not changed")
		except Exception, err:
			self.response(to, {"error": err.message})


	# Select certificate for site
	def actionCertSelect(self, to, accepted_domains=[]):
		accounts = []
		accounts.append(["", "Unique to site", ""]) # Default option
		active = "" # Make it active if no other option found

		# Add my certs
		auth_address = self.user.getAuthAddress(self.site.address) # Current auth address
		for domain, cert in self.user.certs.items():
			if auth_address == cert["auth_address"]: 
				active = domain
			title = cert["auth_user_name"]+"@"+domain
			if domain in accepted_domains:
				accounts.append([domain, title, ""])
			else:
				accounts.append([domain, title, "disabled"])


		# Render the html
		body = "<span style='padding-bottom: 5px; display: inline-block'>Select account you want to use in this site:</span>"
		# Accounts
		for domain, account, css_class in accounts:
			if domain == active:
				css_class += " active" # Currently selected option
				title = "<b>%s</b> <small>(currently selected)</small>" % account
			else:
				title = "<b>%s</b>" % account
			body += "<a href='#Select+account' class='select select-close cert %s' title='%s'>%s</a>" % (css_class, domain, title)
		# More avalible  providers
		more_domains = [domain for domain in accepted_domains if domain not in self.user.certs] # Domainains we not displayed yet
		if more_domains:
			# body+= "<small style='margin-top: 10px; display: block'>Accepted authorization providers by the site:</small>"
			body+= "<div style='background-color: #F7F7F7; margin-right: -30px'>"
			for domain in more_domains:
				body += "<a href='/%s' onclick='wrapper.gotoSite(this)' target='_blank' class='select'><small style='float: right; margin-right: 40px; margin-top: -1px'>Register &raquo;</small>%s</a>" % (domain, domain)
			body+= "</div>"
			
		body += """
			<script>
			 $(".notification .select.cert").on("click", function() {
			 	$(".notification .select").removeClass('active')
			 	wrapper.ws.cmd('certSet', [this.title])
			 	return false
			 })
			</script>
		"""

		# Send the notification
		self.cmd("notification", ["ask", body])


	# Set certificate that used for authenticate user for site
	def actionCertSet(self, to, domain):
		self.user.setCert(self.site.address, domain)
		self.site.updateWebsocket(cert_changed=domain)


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
			gevent.spawn(site.update, announce=True)
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
		self.cmd("updating")
		sys.modules["main"].update_after_shutdown = True
		sys.modules["main"].file_server.stop()
		sys.modules["main"].ui_server.stop()


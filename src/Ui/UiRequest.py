import time, re, os, mimetypes, json, cgi
from Config import config
from Site import SiteManager
from User import UserManager
from Ui.UiWebsocket import UiWebsocket

status_texts = {
	200: "200 OK",
	400: "400 Bad Request",
	403: "403 Forbidden",
	404: "404 Not Found",
}



class UiRequest:
	def __init__(self, server = None):
		if server:
			self.server = server
			self.log = server.log
		self.get = {} # Get parameters
		self.env = {} # Enviroment settings
		self.user = UserManager.getCurrent()
		self.start_response = None # Start response function


	# Call the request handler function base on path
	def route(self, path):
		if config.ui_restrict and self.env['REMOTE_ADDR'] != config.ui_restrict: # Restict Ui access by ip
			return self.error403()

		if path == "/":
			return self.actionIndex()
		elif path == "/favicon.ico":
			return self.actionFile("src/Ui/media/img/favicon.ico")
		# Media
		elif path.startswith("/uimedia/"):
			return self.actionUiMedia(path)
		elif path.startswith("/media"):
			return self.actionSiteMedia(path) 
		# Websocket
		elif path == "/Websocket":
			return self.actionWebsocket()
		# Debug
		elif path == "/Debug" and config.debug:
			return self.actionDebug()
		elif path == "/Console" and config.debug:
			return self.actionConsole()
		elif path == "/Stats":
			return self.actionStats()
		# Test
		elif path == "/Test/Websocket":
			return self.actionFile("Data/temp/ws_test.html")
		elif path == "/Test/Stream":
			return self.actionTestStream()
		# Site media wrapper
		else:
			return self.actionWrapper(path)


	# Get mime by filename
	def getContentType(self, file_name):
		content_type = mimetypes.guess_type(file_name)[0]
		if not content_type: 
			if file_name.endswith("json"): # Correct json header
				content_type = "application/json"
			else:
				content_type = "application/octet-stream"
		return content_type


	# Send response headers
	def sendHeader(self, status=200, content_type="text/html", extra_headers=[]):
		if content_type == "text/html": content_type = "text/html; charset=utf-8"
		headers = []
		headers.append(("Version", "HTTP/1.1"))
		headers.append(("Access-Control-Allow-Origin", "*")) # Allow json access
		headers.append(("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept")) # Allow json access
		headers.append(("Cache-Control", "no-cache, no-store, private, must-revalidate, max-age=0")) # No caching at all
		#headers.append(("Cache-Control", "public, max-age=604800")) # Cache 1 week
		headers.append(("Content-Type", content_type))
		for extra_header in extra_headers:
			headers.append(extra_header)
		self.start_response(status_texts[status], headers)


	# Renders a template
	def render(self, template_path, *args, **kwargs):
		#template = SimpleTemplate(open(template_path), lookup=[os.path.dirname(template_path)])
		#yield str(template.render(*args, **kwargs).encode("utf8"))
		template = open(template_path).read().decode("utf8")
		yield template.format(**kwargs).encode("utf8")


	# - Actions -

	# Redirect to an url
	def actionRedirect(self, url):
		self.start_response('301 Redirect', [('Location', url)])
		yield "Location changed: %s" % url


	def actionIndex(self):
		return self.actionRedirect("/"+config.homepage)


	# Render a file from media with iframe site wrapper
	def actionWrapper(self, path):
		if "." in path and not path.endswith(".html"): return self.actionSiteMedia("/media"+path) # Only serve html files with frame
		if self.get.get("wrapper") == "False": return self.actionSiteMedia("/media"+path) # Only serve html files with frame
		if self.env.get("HTTP_X_REQUESTED_WITH"): return self.error403() # No ajax allowed on wrapper

		match = re.match("/(?P<site>[A-Za-z0-9]+)(?P<inner_path>/.*|$)", path)
		if match:
			inner_path = match.group("inner_path").lstrip("/")
			if not inner_path: inner_path = "index.html" # If inner path defaults to index.html

			site = self.server.sites.get(match.group("site"))
			if site and site.content_manager.contents.get("content.json") and (not site.getReachableBadFiles() or site.settings["own"]): # Its downloaded or own
				title = site.content_manager.contents["content.json"]["title"]
			else:
				title = "Loading %s..." % match.group("site")
				site = SiteManager.need(match.group("site")) # Start download site
				if not site: return self.error404(path)

			self.sendHeader(extra_headers=[("X-Frame-Options", "DENY")])

			# Wrapper variable inits
			query_string = ""
			body_style = ""
			meta_tags = ""

			if self.env.get("QUERY_STRING"): query_string = "?"+self.env["QUERY_STRING"]
			if site.content_manager.contents.get("content.json") : # Got content.json
				content = site.content_manager.contents["content.json"]
				if content.get("background-color"): 
					body_style += "background-color: "+cgi.escape(site.content_manager.contents["content.json"]["background-color"], True)+";"
				if content.get("viewport"):
					meta_tags += '<meta name="viewport" id="viewport" content="%s">' % cgi.escape(content["viewport"], True)

			return self.render("src/Ui/template/wrapper.html", 
				inner_path=inner_path, 
				address=match.group("site"), 
				title=title, 
				body_style=body_style,
				meta_tags=meta_tags,
				query_string=query_string,
				wrapper_key=site.settings["wrapper_key"],
				permissions=json.dumps(site.settings["permissions"]),
				show_loadingscreen=json.dumps(not os.path.isfile(site.getPath(inner_path))),
				homepage=config.homepage
			)

		else: # Bad url
			return self.error404(path)


	# Serve a media for site
	def actionSiteMedia(self, path):
		path = path.replace("/index.html/", "/") # Base Backward compatibility fix
		
		match = re.match("/media/(?P<site>[A-Za-z0-9]+)/(?P<inner_path>.*)", path)

		referer = self.env.get("HTTP_REFERER")
		if referer: # Only allow same site to receive media
			referer = re.sub("http://.*?/", "/", referer) # Remove server address
			referer = referer.replace("/media", "") # Media
			if not referer.startswith("/"+match.group("site")): return self.error403() # Referer not starts same address as requested path

		if match: # Looks like a valid path
			file_path = "data/%s/%s" % (match.group("site"), match.group("inner_path"))
			allowed_dir = os.path.abspath("data/%s" % match.group("site")) # Only files within data/sitehash allowed
			if ".." in file_path or not os.path.dirname(os.path.abspath(file_path)).startswith(allowed_dir): # File not in allowed path
				return self.error403()
			else:
				if config.debug and file_path.split("/")[-1].startswith("all."): # When debugging merge *.css to all.css and *.js to all.js
					site = self.server.sites.get(match.group("site"))
					if site.settings["own"]:
						from Debug import DebugMedia
						DebugMedia.merge(file_path)
				if os.path.isfile(file_path): # File exits
					return self.actionFile(file_path)
				else: # File not exits, try to download
					site = SiteManager.need(match.group("site"), all_file=False)
					self.sendHeader(content_type=self.getContentType(file_path)) # ?? Get Exception without this
					result = site.needFile(match.group("inner_path"), priority=1) # Wait until file downloads
					return self.actionFile(file_path)

		else: # Bad url
			return self.error404(path)


	# Serve a media for ui
	def actionUiMedia(self, path):
		match = re.match("/uimedia/(?P<inner_path>.*)", path)
		if match: # Looks like a valid path
			file_path = "src/Ui/media/%s" % match.group("inner_path")
			allowed_dir = os.path.abspath("src/Ui/media") # Only files within data/sitehash allowed
			if ".." in file_path or not os.path.dirname(os.path.abspath(file_path)).startswith(allowed_dir): # File not in allowed path
				return self.error403()
			else:
				if config.debug and match.group("inner_path").startswith("all."): # When debugging merge *.css to all.css and *.js to all.js
					from Debug import DebugMedia
					DebugMedia.merge(file_path)
				return self.actionFile(file_path)
		else: # Bad url
			return self.error400()


	# Stream a file to client
	def actionFile(self, file_path, block_size = 64*1024):
		if os.path.isfile(file_path):
			# Try to figure out content type by extension
			content_type = self.getContentType(file_path)

			self.sendHeader(content_type = content_type) # TODO: Dont allow external access: extra_headers=[("Content-Security-Policy", "default-src 'unsafe-inline' data: http://localhost:43110 ws://localhost:43110")]
			if self.env["REQUEST_METHOD"] != "OPTIONS":
				file = open(file_path, "rb")
				while 1:
					try:
						block = file.read(block_size)
						if block:
							yield block
						else:
							raise StopIteration
					except StopIteration:
						file.close()
						break
		else: # File not exits
			yield self.error404(file_path)


	# On websocket connection
	def actionWebsocket(self):
		ws = self.env.get("wsgi.websocket")
		if ws:
			wrapper_key = self.get["wrapper_key"]
			# Find site by wrapper_key
			site = None
			for site_check in self.server.sites.values():
				if site_check.settings["wrapper_key"] == wrapper_key: site = site_check

			if site: # Correct wrapper key
				ui_websocket = UiWebsocket(ws, site, self.server, self.user)
				site.websockets.append(ui_websocket) # Add to site websockets to allow notify on events
				ui_websocket.start()
				for site_check in self.server.sites.values(): # Remove websocket from every site (admin sites allowed to join other sites event channels)
					if ui_websocket in site_check.websockets:
						site_check.websockets.remove(ui_websocket)
				return "Bye."
			else: # No site found by wrapper key
				self.log.error("Wrapper key not found: %s" % wrapper_key)
				return self.error403()
		else:
			start_response("400 Bad Request", []) 
			return "Not a websocket!"


	# Debug last error
	def actionDebug(self):
		# Raise last error from DebugHook
		import sys
		last_error = sys.modules["src.main"].DebugHook.last_error
		if last_error:
			raise last_error[0], last_error[1], last_error[2]
		else:
			self.sendHeader()
			yield "No error! :)"


	# Just raise an error to get console
	def actionConsole(self):
		import sys
		sites = self.server.sites
		main = sys.modules["src.main"]
		raise Exception("Here is your console")


	def actionStats(self):
		import gc, sys
		from greenlet import greenlet
		greenlets = [obj for obj in gc.get_objects() if isinstance(obj, greenlet)]
		self.sendHeader()
		main = sys.modules["src.main"]

		yield "<pre>"
		yield "Connections (%s):<br>" % len(main.file_server.connections)
		for connection in main.file_server.connections:
			yield "%s: %s %s<br>" % (connection.protocol, connection.ip, connection.zmq_sock)

		yield "Greenlets (%s):<br>" % len(greenlets)
		for thread in greenlets:
			yield " - %s<br>" % cgi.escape(repr(thread))
		yield "</pre>"


	# - Tests -

	def actionTestStream(self):
		self.sendHeader()
		yield " "*1080 # Overflow browser's buffer
		yield "He"
		time.sleep(1)
		yield "llo!"
		yield "Running websockets: %s" % len(self.server.websockets)
		self.server.sendMessage("Hello!")


	# - Errors -

	# Send bad request error
	def error400(self):
		self.sendHeader(400)
		return "Bad Request"


	# You are not allowed to access this
	def error403(self):
		self.sendHeader(403)
		return "Forbidden"


	# Send file not found error
	def error404(self, path = None):
		self.sendHeader(404)
		return "Not Found: %s" % path

	# - Reload for eaiser developing -
	def reload(self):
		import imp
		global UiWebsocket
		UiWebsocket = imp.load_source("UiWebsocket", "src/Ui/UiWebsocket.py").UiWebsocket
		UserManager.reload()
		self.user = UserManager.getCurrent()

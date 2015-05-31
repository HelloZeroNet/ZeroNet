import time, re, os, mimetypes, json, cgi
from Config import config
from Site import SiteManager
from User import UserManager
from Plugin import PluginManager
from Ui.UiWebsocket import UiWebsocket

status_texts = {
	200: "200 OK",
	400: "400 Bad Request",
	403: "403 Forbidden",
	404: "404 Not Found",
	500: "500 Internal Server Error",
}


@PluginManager.acceptPlugins
class UiRequest(object):
	def __init__(self, server, get, env, start_response):
		if server:
			self.server = server
			self.log = server.log
		self.get = get # Get parameters
		self.env = env # Enviroment settings
		self.start_response = start_response # Start response function
		self.user = None


	# Call the request handler function base on path
	def route(self, path):
		if config.ui_restrict and self.env['REMOTE_ADDR'] not in config.ui_restrict: # Restict Ui access by ip
			return self.error403()

		path = re.sub("^http://zero[/]+", "/", path) # Remove begining http://zero/ for chrome extension
		path = re.sub("^http://", "/", path) # Remove begining http for chrome extension .bit access

		if path == "/":
			return self.actionIndex()
		elif path.endswith("favicon.ico"):
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
		# Site media wrapper
		else:
			body = self.actionWrapper(path)
			if body:
				return body
			else:
				func = getattr(self, "action"+path.lstrip("/"), None) # Check if we have action+request_path function
				if func:
					return func()
				else:
					return self.error404(path)


	# The request is proxied by chrome extension
	def isProxyRequest(self):
		return self.env["PATH_INFO"].startswith("http://")


	def isAjaxRequest(self):
		return self.env.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"


	# Get mime by filename
	def getContentType(self, file_name):
		content_type = mimetypes.guess_type(file_name)[0]
		if not content_type: 
			if file_name.endswith("json"): # Correct json header
				content_type = "application/json"
			else:
				content_type = "application/octet-stream"
		return content_type


	# Returns: <dict> Cookies based on self.env
	def getCookies(self):
		raw_cookies = self.env.get('HTTP_COOKIE')
		if raw_cookies:
			cookies = cgi.parse_qsl(raw_cookies)
			return {key.strip(): val for key, val in cookies}
		else:
			return {}


	def getCurrentUser(self):
		if self.user: return self.user # Cache
		self.user = UserManager.user_manager.get() # Get user
		if not self.user:
			self.user = UserManager.user_manager.create()
		return self.user


	# Send response headers
	def sendHeader(self, status=200, content_type="text/html", extra_headers=[]):
		if content_type == "text/html": content_type = "text/html; charset=utf-8"
		headers = []
		headers.append(("Version", "HTTP/1.1"))
		headers.append(("Access-Control-Allow-Origin", "*")) # Allow json access
		if self.env["REQUEST_METHOD"] == "OPTIONS":
			headers.append(("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept")) # Allow json access

		if (self.env["REQUEST_METHOD"] == "OPTIONS" or not self.isAjaxRequest()) and status == 200 and (content_type == "text/css" or content_type.startswith("application") or self.env["REQUEST_METHOD"] == "OPTIONS" or content_type.startswith("image")): # Cache Css, Js, Image files for 10min
			headers.append(("Cache-Control", "public, max-age=600")) # Cache 10 min
		else: # Images, Css, Js
			headers.append(("Cache-Control", "no-cache, no-store, private, must-revalidate, max-age=0")) # No caching at all
		#headers.append(("Cache-Control", "public, max-age=604800")) # Cache 1 week
		headers.append(("Content-Type", content_type))
		for extra_header in extra_headers:
			headers.append(extra_header)
		return self.start_response(status_texts[status], headers)


	# Renders a template
	def render(self, template_path, *args, **kwargs):
		#template = SimpleTemplate(open(template_path), lookup=[os.path.dirname(template_path)])
		#yield str(template.render(*args, **kwargs).encode("utf8"))
		template = open(template_path).read().decode("utf8")
		return template.format(**kwargs).encode("utf8")


	# - Actions -

	# Redirect to an url
	def actionRedirect(self, url):
		self.start_response('301 Redirect', [('Location', url)])
		yield "Location changed: %s" % url


	def actionIndex(self):
		return self.actionRedirect("/"+config.homepage)


	# Render a file from media with iframe site wrapper
	def actionWrapper(self, path, extra_headers=None):
		if not extra_headers: extra_headers = []
		if self.get.get("wrapper") == "False": return self.actionSiteMedia("/media"+path) # Only serve html files with frame

		match = re.match("/(?P<address>[A-Za-z0-9\._-]+)(?P<inner_path>/.*|$)", path)
		if match:
			address = match.group("address")
			inner_path = match.group("inner_path").lstrip("/")
			if "." in inner_path and not inner_path.endswith(".html"): return self.actionSiteMedia("/media"+path) # Only serve html files with frame
			if self.env.get("HTTP_X_REQUESTED_WITH"): return self.error403("Ajax request not allowed to load wrapper") # No ajax allowed on wrapper

			file_inner_path = inner_path
			if not file_inner_path: file_inner_path = "index.html" # If inner path defaults to index.html

			if not inner_path and not path.endswith("/"): inner_path = address+"/" # Fix relative resources loading if missing / end of site address
			inner_path = re.sub(".*/(.+)", "\\1", inner_path) # Load innerframe relative to current url

			site = SiteManager.site_manager.get(address)

			if site and site.content_manager.contents.get("content.json") and (not site.getReachableBadFiles() or site.settings["own"]): # Its downloaded or own
				title = site.content_manager.contents["content.json"]["title"]
			else:
				title = "Loading %s..." % address
				site = SiteManager.site_manager.need(address) # Start download site
					
				if not site: return False

			#extra_headers.append(("X-Frame-Options", "DENY"))

			self.sendHeader(extra_headers=extra_headers[:])

			# Wrapper variable inits
			query_string = ""
			body_style = ""
			meta_tags = ""

			if self.env.get("QUERY_STRING"): query_string = "?"+self.env["QUERY_STRING"]+"&wrapper=False"
			else: query_string = "?wrapper=False"

			if self.isProxyRequest(): # Its a remote proxy request
				server_url = "http://%s:%s" % (self.env["SERVER_NAME"], self.env["SERVER_PORT"])
				homepage = "http://zero/"+config.homepage
			else: # Use relative path
				server_url = ""
				homepage = "/"+config.homepage

			if site.content_manager.contents.get("content.json") : # Got content.json
				content = site.content_manager.contents["content.json"]
				if content.get("background-color"): 
					body_style += "background-color: "+cgi.escape(site.content_manager.contents["content.json"]["background-color"], True)+";"
				if content.get("viewport"):
					meta_tags += '<meta name="viewport" id="viewport" content="%s">' % cgi.escape(content["viewport"], True)

			return self.render("src/Ui/template/wrapper.html", 
				server_url=server_url,
				inner_path=inner_path, 
				file_inner_path=file_inner_path, 
				address=address, 
				title=title, 
				body_style=body_style,
				meta_tags=meta_tags,
				query_string=query_string,
				wrapper_key=site.settings["wrapper_key"],
				permissions=json.dumps(site.settings["permissions"]),
				show_loadingscreen=json.dumps(not site.storage.isFile(file_inner_path)),
				rev=config.rev,
				homepage=homepage
			)

		else: # Bad url
			return False


	# Returns if media request allowed from that referer
	def isMediaRequestAllowed(self, site_address, referer):
		referer_path = re.sub("http[s]{0,1}://.*?/", "/", referer).replace("/media", "") # Remove site address
		return referer_path.startswith("/"+site_address)


	# Serve a media for site
	def actionSiteMedia(self, path):
		path = path.replace("/index.html/", "/") # Base Backward compatibility fix
		if path.endswith("/"): path = path+"index.html"
		
		match = re.match("/media/(?P<address>[A-Za-z0-9\._-]+)/(?P<inner_path>.*)", path)

		referer = self.env.get("HTTP_REFERER")
		if referer and match: # Only allow same site to receive media
			if not self.isMediaRequestAllowed(match.group("address"), referer):
				return self.error403("Media referrer error") # Referrer not starts same address as requested path				

		if match: # Looks like a valid path
			address = match.group("address")
			file_path = "%s/%s/%s" % (config.data_dir, address, match.group("inner_path"))
			allowed_dir = os.path.abspath("%s/%s" % (config.data_dir, address)) # Only files within data/sitehash allowed
			data_dir = os.path.abspath("data") # No files from data/ allowed
			if ".." in file_path or not os.path.dirname(os.path.abspath(file_path)).startswith(allowed_dir) or allowed_dir == data_dir: # File not in allowed path
				return self.error403()
			else:
				if config.debug and file_path.split("/")[-1].startswith("all."): # When debugging merge *.css to all.css and *.js to all.js
					site = self.server.sites.get(address)
					if site.settings["own"]:
						from Debug import DebugMedia
						DebugMedia.merge(file_path)
				if os.path.isfile(file_path): # File exits
					#self.sendHeader(content_type=self.getContentType(file_path)) # ?? Get Exception without this
					return self.actionFile(file_path)
				else: # File not exits, try to download
					site = SiteManager.site_manager.need(address, all_file=False)
					result = site.needFile(match.group("inner_path"), priority=1) # Wait until file downloads
					if result:
						#self.sendHeader(content_type=self.getContentType(file_path))
						return self.actionFile(file_path)
					else:
						self.log.debug("File not found: %s" % match.group("inner_path"))
						return self.error404(match.group("inner_path"))

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
				user = self.getCurrentUser()
				if not user:
					self.log.error("No user found")
					return self.error403()
				ui_websocket = UiWebsocket(ws, site, self.server, user)
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
		last_error = sys.modules["main"].DebugHook.last_error
		if last_error:
			raise last_error[0], last_error[1], last_error[2]
		else:
			self.sendHeader()
			return "No error! :)"


	# Just raise an error to get console
	def actionConsole(self):
		import sys
		sites = self.server.sites
		main = sys.modules["main"]
		raise Exception("Here is your console")


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
	def error403(self, message="Forbidden"):
		self.sendHeader(403)
		return message


	# Send file not found error
	def error404(self, path = None):
		self.sendHeader(404)
		return "Not Found: %s" % path.encode("utf8")


	# Internal server error
	def error500(self, message = ":("):
		self.sendHeader(500)
		return "<h1>Server error</h1>%s" % cgi.escape(message)


# - Reload for eaiser developing -
#def reload():
	#import imp, sys
	#global UiWebsocket
	#UiWebsocket = imp.load_source("UiWebsocket", "src/Ui/UiWebsocket.py").UiWebsocket
	#reload(sys.modules["User.UserManager"])
	#UserManager.reloadModule()
	#self.user = UserManager.user_manager.getCurrent()

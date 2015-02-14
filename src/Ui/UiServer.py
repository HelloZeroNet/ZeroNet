from gevent import monkey; monkey.patch_all(thread = False)
import logging, time, cgi, string, random
from gevent.pywsgi import WSGIServer
from gevent.pywsgi import WSGIHandler
from lib.geventwebsocket.handler import WebSocketHandler
from Ui import UiRequest
from Site import SiteManager
from Config import config
from Debug import Debug

# Skip websocket handler if not necessary
class UiWSGIHandler(WSGIHandler):
	def __init__(self, *args, **kwargs):
		super(UiWSGIHandler, self).__init__(*args, **kwargs)
		self.ws_handler = WebSocketHandler(*args, **kwargs)


	def run_application(self):
		if "HTTP_UPGRADE" in self.environ: # Websocket request
			self.ws_handler.__dict__ = self.__dict__ # Match class variables
			self.ws_handler.run_application()
		else: # Standard HTTP request
			#print self.application.__class__.__name__
			try:
				return super(UiWSGIHandler, self).run_application()
			except Exception, err:
				logging.debug("UiWSGIHandler error: %s" % err)


class UiServer:
	def __init__(self):
		self.ip = config.ui_ip
		self.port = config.ui_port
		if self.ip == "*": self.ip = "" # Bind all
		#self.sidebar_websockets = [] # Sidebar websocket connections
		#self.auth_key = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(12)) # Global admin auth key
		self.sites = SiteManager.list()
		self.log = logging.getLogger(__name__)
		
		self.ui_request = UiRequest(self)


	# Handle WSGI request
	def handleRequest(self, env, start_response):
		path = env["PATH_INFO"]
		self.ui_request.env = env
		self.ui_request.start_response = start_response
		if env.get("QUERY_STRING"):
			self.ui_request.get = dict(cgi.parse_qsl(env['QUERY_STRING']))
		else:
			self.ui_request.get = {}
		return self.ui_request.route(path)


	# Reload the UiRequest class to prevent restarts in debug mode
	def reload(self):
		import imp
		self.ui_request = imp.load_source("UiRequest", "src/Ui/UiRequest.py").UiRequest(self)
		self.ui_request.reload()


	# Bind and run the server
	def start(self):
		handler = self.handleRequest

		if config.debug:
			# Auto reload UiRequest on change
			from Debug import DebugReloader
			DebugReloader(self.reload)

			# Werkzeug Debugger
			try:
				from werkzeug.debug import DebuggedApplication
				handler = DebuggedApplication(self.handleRequest, evalex=True)
			except Exception, err:
				self.log.info("%s: For debugging please download Werkzeug (http://werkzeug.pocoo.org/)" % err)
				from Debug import DebugReloader
		self.log.write = lambda msg: self.log.debug(msg.strip()) # For Wsgi access.log
		self.log.info("--------------------------------------")
		self.log.info("Web interface: http://%s:%s/" % (config.ui_ip, config.ui_port))
		self.log.info("--------------------------------------")

		if config.open_browser:
			logging.info("Opening browser: %s...", config.open_browser)
			import webbrowser
			if config.open_browser == "default_browser":
				browser = webbrowser.get()
			else:
				browser = webbrowser.get(config.open_browser)
			browser.open("http://%s:%s" % (config.ui_ip, config.ui_port), new=2) 

		WSGIServer((self.ip, self.port), handler, handler_class=UiWSGIHandler, log=self.log).serve_forever()

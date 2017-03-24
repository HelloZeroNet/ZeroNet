import logging
import time
import cgi
import socket
import sys
import gevent

from gevent.pywsgi import WSGIServer
from gevent.pywsgi import WSGIHandler
from lib.geventwebsocket.handler import WebSocketHandler

from UiRequest import UiRequest
from Site import SiteManager
from Config import config
from Debug import Debug


# Skip websocket handler if not necessary
class UiWSGIHandler(WSGIHandler):

    def __init__(self, *args, **kwargs):
        self.server = args[2]
        super(UiWSGIHandler, self).__init__(*args, **kwargs)
        self.args = args
        self.kwargs = kwargs

    def run_application(self):
        if "HTTP_UPGRADE" in self.environ:  # Websocket request
            try:
                ws_handler = WebSocketHandler(*self.args, **self.kwargs)
                ws_handler.__dict__ = self.__dict__  # Match class variables
                ws_handler.run_application()
            except Exception, err:
                logging.error("UiWSGIHandler websocket error: %s" % Debug.formatException(err))
                if config.debug:  # Allow websocket errors to appear on /Debug
                    import sys
                    sys.modules["main"].DebugHook.handleError()
        else:  # Standard HTTP request
            try:
                super(UiWSGIHandler, self).run_application()
            except Exception, err:
                logging.error("UiWSGIHandler error: %s" % Debug.formatException(err))
                if config.debug:  # Allow websocket errors to appear on /Debug
                    import sys
                    sys.modules["main"].DebugHook.handleError()

    def handle(self):
        # Save socket to be able to close them properly on exit
        self.server.sockets[self.client_address] = self.socket
        super(UiWSGIHandler, self).handle()
        del self.server.sockets[self.client_address]


class UiServer:

    def __init__(self):
        self.ip = config.ui_ip
        self.port = config.ui_port
        if self.ip == "*":
            self.ip = ""  # Bind all
        self.wrapper_nonces = []
        self.site_manager = SiteManager.site_manager
        self.sites = SiteManager.site_manager.list()
        self.log = logging.getLogger(__name__)

    # After WebUI started
    def afterStarted(self):
        from util import Platform
        Platform.setMaxfilesopened(config.max_files_opened)

    # Handle WSGI request
    def handleRequest(self, env, start_response):
        path = env["PATH_INFO"]
        if env.get("QUERY_STRING"):
            get = dict(cgi.parse_qsl(env['QUERY_STRING']))
        else:
            get = {}
        ui_request = UiRequest(self, get, env, start_response)
        if config.debug:  # Let the exception catched by werkezung
            return ui_request.route(path)
        else:  # Catch and display the error
            try:
                return ui_request.route(path)
            except Exception, err:
                logging.debug("UiRequest error: %s" % Debug.formatException(err))
                return ui_request.error500("Err: %s" % Debug.formatException(err))

    # Reload the UiRequest class to prevent restarts in debug mode
    def reload(self):
        global UiRequest
        import imp
        import sys
        reload(sys.modules["User.UserManager"])
        reload(sys.modules["Ui.UiWebsocket"])
        UiRequest = imp.load_source("UiRequest", "src/Ui/UiRequest.py").UiRequest
        # UiRequest.reload()

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
        self.log.write = lambda msg: self.log.debug(msg.strip())  # For Wsgi access.log
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
            url = "http://%s:%s/%s" % (config.ui_ip if config.ui_ip != "*" else "127.0.0.1", config.ui_port, config.homepage)
            gevent.spawn_later(0.3, browser.open, url, new=2)

        self.server = WSGIServer((self.ip.replace("*", ""), self.port), handler, handler_class=UiWSGIHandler, log=self.log)
        self.server.sockets = {}
        self.afterStarted()
        try:
            self.server.serve_forever()
        except Exception, err:
            self.log.error("Web interface bind error, must be running already, exiting.... %s" % err)
            sys.modules["main"].file_server.stop()
        self.log.debug("Stopped.")

    def stop(self):
        self.log.debug("Stopping...")
        # Close WS sockets
        if "clients" in dir(self.server):
            for client in self.server.clients.values():
                client.ws.close()
        # Close http sockets
        sock_closed = 0
        for sock in self.server.sockets.values():
            try:
                sock.send("bye")
                sock.shutdown(socket.SHUT_RDWR)
                # sock._sock.close()
                # sock.close()
                sock_closed += 1
            except Exception, err:
                self.log.debug("Http connection close error: %s" % err)
        self.log.debug("Socket closed: %s" % sock_closed)
        time.sleep(0.1)

        self.server.socket.close()
        self.server.stop()
        time.sleep(1)
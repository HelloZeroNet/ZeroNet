import logging
import time
import urllib
import socket
import gevent

from gevent.pywsgi import WSGIServer
from lib.gevent_ws import WebSocketHandler

from .UiRequest import UiRequest
from Site import SiteManager
from Config import config
from Debug import Debug
import importlib


# Skip websocket handler if not necessary
class UiWSGIHandler(WebSocketHandler):

    def __init__(self, *args, **kwargs):
        self.server = args[2]
        super(UiWSGIHandler, self).__init__(*args, **kwargs)
        self.args = args
        self.kwargs = kwargs

    def handleError(self, err):
        if config.debug:  # Allow websocket errors to appear on /Debug
            import main
            main.DebugHook.handleError()
        else:
            ui_request = UiRequest(self.server, {}, self.environ, self.start_response)
            block_gen = ui_request.error500("UiWSGIHandler error: %s" % Debug.formatExceptionMessage(err))
            for block in block_gen:
                self.write(block)

    def run_application(self):
        err_name = "UiWSGIHandler websocket" if "HTTP_UPGRADE" in self.environ else "UiWSGIHandler"
        try:
            super(UiWSGIHandler, self).run_application()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as err:
            logging.warning("%s connection error: %s" % (err_name, err))
        except Exception as err:
            logging.warning("%s error: %s" % (err_name, Debug.formatException(err)))
            self.handleError(err)

    def handle(self):
        # Save socket to be able to close them properly on exit
        self.server.sockets[self.client_address] = self.socket
        super(UiWSGIHandler, self).handle()
        del self.server.sockets[self.client_address]


class UiServer:
    def __init__(self):
        self.ip = config.ui_ip
        self.port = config.ui_port
        self.running = False
        if self.ip == "*":
            self.ip = "0.0.0.0"  # Bind all
        if config.ui_host:
            self.allowed_hosts = set(config.ui_host)
        elif config.ui_ip == "127.0.0.1":
            # IP Addresses are inherently allowed as they are immune to DNS
            # rebinding attacks.
            self.allowed_hosts = set(["zero", "localhost:%s" % config.ui_port])
            # "URI producers and normalizers should omit the port component and
            # its ':' delimiter if port is empty or if its value would be the
            # same as that of the scheme's default."
            # Source: https://tools.ietf.org/html/rfc3986#section-3.2.3
            # As a result, we need to support portless hosts if port 80 is in
            # use.
            if config.ui_port == 80:
                self.allowed_hosts.update(["localhost"])
        else:
            self.allowed_hosts = set([])
        self.allowed_ws_origins = set()

        self.wrapper_nonces = []
        self.add_nonces = []
        self.websockets = []
        self.site_manager = SiteManager.site_manager
        self.sites = SiteManager.site_manager.list()
        self.log = logging.getLogger(__name__)
        config.error_logger.onNewRecord = self.handleErrorLogRecord

    def handleErrorLogRecord(self, record):
        self.updateWebsocket(log_event=record.levelname)

    # After WebUI started
    def afterStarted(self):
        from util import Platform
        Platform.setMaxfilesopened(config.max_files_opened)

    # Handle WSGI request
    def handleRequest(self, env, start_response):
        path = bytes(env["PATH_INFO"], "raw-unicode-escape").decode("utf8")
        if env.get("QUERY_STRING"):
            get = dict(urllib.parse.parse_qsl(env['QUERY_STRING']))
        else:
            get = {}
        ui_request = UiRequest(self, get, env, start_response)
        if config.debug:  # Let the exception catched by werkezung
            return ui_request.route(path)
        else:  # Catch and display the error
            try:
                return ui_request.route(path)
            except Exception as err:
                logging.debug("UiRequest error: %s" % Debug.formatException(err))
                return ui_request.error500("Err: %s" % Debug.formatException(err))

    # Reload the UiRequest class to prevent restarts in debug mode
    def reload(self):
        global UiRequest
        import imp
        import sys
        importlib.reload(sys.modules["User.UserManager"])
        importlib.reload(sys.modules["Ui.UiWebsocket"])
        UiRequest = imp.load_source("UiRequest", "src/Ui/UiRequest.py").UiRequest
        # UiRequest.reload()

    # Bind and run the server
    def start(self):
        self.running = True
        handler = self.handleRequest

        if config.debug:
            # Auto reload UiRequest on change
            from Debug import DebugReloader
            DebugReloader.watcher.addCallback(self.reload)

            # Werkzeug Debugger
            try:
                from werkzeug.debug import DebuggedApplication
                handler = DebuggedApplication(self.handleRequest, evalex=True)
            except Exception as err:
                self.log.info("%s: For debugging please download Werkzeug (http://werkzeug.pocoo.org/)" % err)
                from Debug import DebugReloader
        self.log.write = lambda msg: self.log.debug(msg.strip())  # For Wsgi access.log
        self.log.info("--------------------------------------")
        if ":" in config.ui_ip:
            self.log.info("Web interface: http://[%s]:%s/" % (config.ui_ip, config.ui_port))
        else:
            self.log.info("Web interface: http://%s:%s/" % (config.ui_ip, config.ui_port))
        self.log.info("--------------------------------------")

        if config.open_browser and config.open_browser != "False":
            logging.info("Opening browser: %s...", config.open_browser)
            import webbrowser
            try:
                if config.open_browser == "default_browser":
                    browser = webbrowser.get()
                else:
                    browser = webbrowser.get(config.open_browser)
                url = "http://%s:%s/%s" % (config.ui_ip if config.ui_ip != "*" else "127.0.0.1", config.ui_port, config.homepage)
                gevent.spawn_later(0.3, browser.open, url, new=2)
            except Exception as err:
                print("Error starting browser: %s" % err)

        self.server = WSGIServer((self.ip, self.port), handler, handler_class=UiWSGIHandler, log=self.log)
        self.server.sockets = {}
        self.afterStarted()
        try:
            self.server.serve_forever()
        except Exception as err:
            self.log.error("Web interface bind error, must be running already, exiting.... %s" % err)
            import main
            main.file_server.stop()
        self.log.debug("Stopped.")

    def stop(self):
        self.log.debug("Stopping...")
        # Close WS sockets
        if "clients" in dir(self.server):
            for client in list(self.server.clients.values()):
                client.ws.close()
        # Close http sockets
        sock_closed = 0
        for sock in list(self.server.sockets.values()):
            try:
                sock.send(b"bye")
                sock.shutdown(socket.SHUT_RDWR)
                # sock._sock.close()
                # sock.close()
                sock_closed += 1
            except Exception as err:
                self.log.debug("Http connection close error: %s" % err)
        self.log.debug("Socket closed: %s" % sock_closed)
        time.sleep(0.1)
        if config.debug:
            from Debug import DebugReloader
            DebugReloader.watcher.stop()

        self.server.socket.close()
        self.server.stop()
        self.running = False
        time.sleep(1)

    def updateWebsocket(self, **kwargs):
        if kwargs:
            param = {"event": list(kwargs.items())[0]}
        else:
            param = None

        for ws in self.websockets:
            ws.event("serverChanged", param)

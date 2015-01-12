import re

from .protocols.base import BaseProtocol
from .exceptions import WebSocketError


class WebSocketApplication(object):
    protocol_class = BaseProtocol

    def __init__(self, ws):
        self.protocol = self.protocol_class(self)
        self.ws = ws

    def handle(self):
        self.protocol.on_open()

        while True:
            try:
                message = self.ws.receive()
            except WebSocketError:
                self.protocol.on_close()
                break

            self.protocol.on_message(message)

    def on_open(self, *args, **kwargs):
        pass

    def on_close(self, *args, **kwargs):
        pass

    def on_message(self, message, *args, **kwargs):
        self.ws.send(message, **kwargs)

    @classmethod
    def protocol_name(cls):
        return cls.protocol_class.PROTOCOL_NAME


class Resource(object):
    def __init__(self, apps=None):
        self.apps = apps if apps else []

    def _app_by_path(self, environ_path):
        # Which app matched the current path?

        for path, app in self.apps.iteritems():
            if re.match(path, environ_path):
                return app

    def app_protocol(self, path):
        app = self._app_by_path(path)

        if hasattr(app, 'protocol_name'):
            return app.protocol_name()
        else:
            return ''

    def __call__(self, environ, start_response):
        environ = environ
        current_app = self._app_by_path(environ['PATH_INFO'])

        if current_app is None:
            raise Exception("No apps defined")

        if 'wsgi.websocket' in environ:
            ws = environ['wsgi.websocket']
            current_app = current_app(ws)
            current_app.ws = ws  # TODO: needed?
            current_app.handle()

            return None
        else:
            return current_app(environ, start_response)

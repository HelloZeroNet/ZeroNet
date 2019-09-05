import json
import threading
import traceback
import xmlrpclib

from Singleton import Singleton
from Config import config

@Singleton
class BMAPI(object):
    thrdata = None
    def __init__(self):
        self.thrdata = threading.local()
        self.connect()

    def check_connection(self):
        if not (hasattr(self.thrdata, 'con') and self.thrdata.con is not None):
            self.connect()
        return self.thrdata.con

    def connect(self):
        try:
            self.thrdata.con = xmlrpclib.ServerProxy(
                    'http://' +
                    config.bitmessage_username + ':' +
                    config.bitmessage_password + '@' +
                    config.bitmessage_host + ':' +
                    config.bitmessage_port + '/')
        except:
            traceback.print_exc()
        try:
            response = self.thrdata.con.add(2, 2)
        except:
            self.thrdata.con = None
            traceback.print_exc()
        if self.thrdata.con is not None:
            return self.thrdata.con
        return False

    def disconnect(self):
        self.thrdata.con = None

    def conn(self):
        return self.check_connection()

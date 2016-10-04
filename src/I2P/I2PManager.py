import logging

from gevent.coros import RLock
from gevent.server import StreamServer
from gevent.pool import Pool
from httplib import HTTPConnection
import urllib2

from i2p import socket
from i2p.datatypes import Destination

from Config import config
from Site import SiteManager
from Debug import Debug


class I2PHTTPConnection(HTTPConnection):
    def __init__(self, i2p_manager, site_address, *args, **kwargs):
        HTTPConnection.__init__(self, *args, **kwargs)
        self.i2p_manager = i2p_manager
        self.site_address = site_address
        self._create_connection = self._create_i2p_connection

    def _create_i2p_connection(self, address, timeout=60,
                               source_address=None):
        return self.i2p_manager.createSocket(self.site_address, *address)

class I2PHTTPHandler(urllib2.HTTPHandler):
    def __init__(self, i2p_manager, site_address, *args, **kwargs):
        urllib2.HTTPHandler.__init__(self, *args, **kwargs)
        self.i2p_manager = i2p_manager
        self.site_address = site_address

    def http_open(self, req):
        return self.do_open(self._createI2PHTTPConnection, req)

    def _createI2PHTTPConnection(self, *args, **kwargs):
        return I2PHTTPConnection(self.i2p_manager, self.site_address, *args, **kwargs)

class I2PManager:
    def __init__(self, fileserver_handler=None):
        self.dest_conns = {}  # Destination: SAM connection
        self.dest_servs = {} # Destination: StreamServer
        self.site_dests = {}  # Site address: Destination
        self.log = logging.getLogger("I2PManager")
        self.start_dests = None
        self.lock = RLock()

        if config.i2p == "disable":
            self.enabled = False
            self.start_dests = False
            self.status = "Disabled"
        else:
            self.enabled = True
            self.status = "Waiting"

        if fileserver_handler:
            self.fileserver_handler = fileserver_handler
        else:
            self.fileserver_handler = lambda self, sock, addr: None

        self.sam_ip, self.sam_port = config.i2p_sam.split(":")
        self.sam_port = int(self.sam_port)

        # Test SAM port
        if config.i2p != "disable":
            try:
                assert self.connect(), "No connection"
                self.log.debug("I2P SAM port %s check ok" % config.i2p_sam)
            except Exception, err:
                self.log.debug("I2P SAM port %s check error: %s" % (config.i2p_sam, err))
                self.enabled = False

    def connect(self):
        if not self.enabled:
            return False
        self.site_dests = {}
        self.dest_conns = {}
        self.dest_servs = {}

        self.log.debug("Connecting to %s:%s" % (self.sam_ip, self.sam_port))
        with self.lock:
            try:
                socket.checkAPIConnection((self.sam_ip, self.sam_port))
                self.status = u"Connected"
                return True
            except Exception, err:
                self.status = u"Error (%s)" % err
                self.log.error("I2P SAM connect error: %s" % Debug.formatException(err))
                self.enabled = False
                return False

    def disconnect(self):
        for server in self.dest_servs:
            server.stop()
        self.dest_conns = {}
        self.dest_servs = {}

    def startDests(self):
        if self.enabled:
            self.log.debug("Start Destinations")
            self.start_dests = True

    def addDest(self, site_address=None):
        sock = socket.socket(socket.AF_I2P, socket.SOCK_STREAM,
                             samaddr=(self.sam_ip, self.sam_port))
        try:
            sock.setblocking(0)
            sock.bind(None, site_address) # Transient Destination, tied to site address
            sock.listen()
            server = StreamServer(
                sock, self.fileserver_handler, spawn=Pool(1000)
            )
            server.start()
            dest = sock.getsockname()
            self.dest_conns[dest] = sock
            self.dest_servs[dest] = server
            self.status = u"OK (%s Destinations running)" % len(self.dest_conns)
            SiteManager.peer_blacklist.append((dest.base64()+".i2p", 0))
            return dest
        except Exception, err:
            self.status = u"SESSION CREATE error (%s)" % err
            self.log.error("I2P SESSION CREATE error: %s" % Debug.formatException(err))
            return False

    def delDest(self, dest):
        if dest in self.dest_servs:
            self.dest_servs[dest].stop()
            del self.dest_conns[dest]
            del self.dest_servs[dest]
            self.status = "OK (%s Destinations running)" % len(self.dest_conns)
            return True
        else:
            self.status = u"Tried to delete non-existent Destination"
            self.log.error("I2P error: Tried to delete non-existent")
            self.disconnect()
            return False

    def getDest(self, site_address):
        with self.lock:
            if not self.enabled:
                return None
            if self.start_dests:  # Different Destination for every site
                dest = self.site_dests.get(site_address)
            else:  # Same Destination for every site
                dest = self.site_dests.get("global")
                site_address = "global"
            if not dest:
                self.site_dests[site_address] = self.addDest(site_address)
                dest = self.site_dests[site_address]
                self.log.debug("Created new Destination for %s: %s" % (site_address, dest))
            return dest

    def getPrivateDest(self, addr):
        dest = addr if isinstance(addr, Destination) else getDest(addr)
        return self.dest_conns[dest].getPrivateDest()

    def createSocket(self, site_address, dest, port):
        if not self.enabled:
            return False
        if dest.endswith(".i2p") and not dest.endswith(".b32.i2p"):
            dest = Destination(raw=dest[:-4], b64=True)
        self.log.debug("Creating new socket to %s:%s" %
                       (dest.base32() if isinstance(dest, Destination) else dest, port))
        sock = socket.socket(socket.AF_I2P, socket.SOCK_STREAM,
                             samaddr=(self.sam_ip, self.sam_port))
        sock.connect((dest, int(port)), site_address)
        return sock

    def lookup(self, name):
        return socket.lookup(name, (self.sam_ip, self.sam_port))

    def urlopen(self, site_address, url, timeout):
        handler = I2PHTTPHandler(self, site_address)
        opener = urllib2.build_opener(handler)
        return opener.open(url, timeout=50)

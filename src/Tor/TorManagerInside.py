import logging
import socket

from Config import config
from Crypt import CryptRsa


class TorManagerInside:
    def __init__(self, tor_hidden_services_fname):
        self.privatekeys = {}  # Onion: Privatekey
        self.site_onions = {}  # Site address: Onion
        self.log = logging.getLogger("TorManagerInside")

        self.ip, self.port = config.tor_controller.split(":")
        self.port = int(self.port)

        self.hss = self.readHiddenServices(tor_hidden_services_fname)
        self.hs_current = 0
        self.hs_insufficient_warning = False

        self.enabled = True
        self.start_onions = True
        self.status = u"OK (%s onion running)" % len(self.hss)

    def readHiddenServices(self, fname):
        with open(fname) as f:
            lines = f.readlines()
        hss = []
        hs = []
        for line in lines:
            hs.append(line.strip('\n'))
            if len(hs) == 2:
                hss.append(hs)
                hs = []
        return hss
        
    def getPrivatekey(self, address):
        return self.privatekeys[address]

    def getPublickey(self, address):
        return CryptRsa.privatekeyToPublickey(self.privatekeys[address])

    def getOnion(self, site_address):
        onion = self.site_onions.get(site_address)
        if onion:
            return onion
        if self.hs_current == len(self.hss):
            self.hs_current = 0
            if not self.hs_insufficient_warning:
                print "Warning: Insufficient number of onions supplied (%u), will reuse for the site %s and for the further sites" % (len(self.hss), site_address)
                self.hs_insufficient_warning = True

        hs_info = self.hss[self.hs_current]
        self.hs_current = self.hs_current + 1
        onion = hs_info[0].replace(".onion", "")
        self.site_onions[site_address] = onion
        self.privatekeys[onion] = hs_info[1]
        self.log.debug("Using the next hidden service for %s: %s" % (site_address, onion))
        return onion

    def createSocket(self, onion, port):
        self.log.debug("Creating new socket to %s:%s" % (onion, port))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((onion, int(port)))
        return sock

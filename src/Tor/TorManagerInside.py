import logging
import socket
import random
import sys

from Config import config
from Crypt import CryptRsa
from Site import SiteManager

# TorManagerInside is the version of TorManager reduced to the needs of the Tor-connected VM.

class TorManagerInside:
    def __init__(self, tor_hidden_services_fname):
        self.privatekeys = {}  # Onion: Privatekey
        self.site_onions = {}  # Site address: Onion
        self.onion_sites = {}  # Onion: Site address
        self.log = logging.getLogger("TorManagerInside")

        self.ip, self.port = config.tor_controller.split(":")
        self.port = int(self.port)

        self.hss_all = self.reshuffleList(self.readHiddenServices(tor_hidden_services_fname))
        self.hss_unused = self.hss_all[:]

        # Add our onions to the black list
        for hs in self.hss_all:
            SiteManager.peer_blacklist.append((hs[0], config.fileserver_port))

        self.enabled = True
        self.start_onions = True
        self.updateStatus()

    def readHiddenServices(self, fname):
        with open(fname) as f:
            lines = f.readlines()
        hss = []
        hs = []
        phase = 'O'
        onion = ""
        key = ""
        for line in lines:
            line = line.strip('\n')
            if line == "":
                continue
            if phase == 'O':
                if not line.endswith(".onion"):
                    sys.exit("Onion address is expected in the hidden services file, got the line >%s<" % line)
                onion = line
                phase = 'H'
            elif phase == 'H':
                if line != "-----BEGIN RSA PRIVATE KEY-----":
                    sys.exit("Key header is expected in the hidden services file, got the line >%s<" % line)
                phase = 'K'
            elif phase == 'K':
                if line != "-----END RSA PRIVATE KEY-----":
                    key = key+line
                else:
                    hss.append([onion, key])
                    key = ""
                    phase = 'O'
        if phase != 'O':
            sys.exit("Unexpected end of the hidden services file")
        return hss

    def reshuffleList(self, lst):
        idxs = range(0, len(lst))
        shuf = []
        while len(idxs) > 0:
            n = random.randrange(0, len(idxs))
            shuf.append(lst[idxs[n]])
            del idxs[n]
        return shuf

    def updateStatus(self):
        self.status = u"OK (%s onion used of %s available)" % (len(self.onion_sites), len(self.hss_all))
        
    def getPrivatekey(self, address):
        return self.privatekeys[address]

    def getPublickey(self, address):
        return CryptRsa.privatekeyToPublickey(self.privatekeys[address])

    def haveOnionsAvailable(self):
        return len(self.hss_unused) > 0

    def numOnions(self):
        return len(self.hss_all)

    def getOnion(self, site_address):
        onion = self.site_onions.get(site_address)
        if onion:
            return onion
        if len(self.hss_unused) == 0:
            sys.exit("TorManager ran out of onions (%u onions were supplied)" % len(self.hss_all))
        hs_info = self.hss_unused[0]
        del self.hss_unused[0]
        onion = hs_info[0].replace(".onion", "")
        self.site_onions[site_address] = onion
        self.onion_sites[onion] = site_address
        self.privatekeys[onion] = hs_info[1]
        self.log.debug("Using the next onion for the site %s: %s.onion" % (site_address, onion))
        self.updateStatus()
        return onion

    def delSiteOnion(self, site_address, onion):
        self.log.debug("Deleting the site %s, recycling its onion %s.onion" % (site_address, onion))
        self.hss_unused.append([onion+".onion", self.privatekeys[onion]])
        del self.privatekeys[onion]
        del self.site_onions[site_address]
        del self.onion_sites[onion]
        self.updateStatus()
        return True

    def delOnion(self, onion):
        site_address = self.onion_sites[onion]
        return self.delSiteOnion(site_address, onion)
        
    def delSite(self, site_address):
        onion = self.site_onions[site_address]
        return self.delSiteOnion(site_address, onion)

    def createSocket(self, onion, port):
        self.log.debug("Creating new socket to %s:%s" % (onion, port))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((onion, int(port)))
        return sock

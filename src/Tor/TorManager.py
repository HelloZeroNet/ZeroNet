import logging
import re
import socket
import binascii
import sys
import os
import time

import gevent
import subprocess
import atexit

from Config import config
from Crypt import CryptRsa
from Site import SiteManager
from lib.PySocks import socks
try:
    from gevent.coros import RLock
except:
    from gevent.lock import RLock
from util import helper
from Debug import Debug


class TorManager:
    def __init__(self, fileserver_ip=None, fileserver_port=None):
        self.privatekeys = {}  # Onion: Privatekey
        self.site_onions = {}  # Site address: Onion
        self.tor_exe = "tools/tor/tor.exe"
        self.tor_process = None
        self.log = logging.getLogger("TorManager")
        self.start_onions = None
        self.conn = None
        self.lock = RLock()

        if config.tor == "disable":
            self.enabled = False
            self.start_onions = False
            self.status = "Disabled"
        else:
            self.enabled = True
            self.status = "Waiting"

        if fileserver_port:
            self.fileserver_port = fileserver_port
        else:
            self.fileserver_port = config.fileserver_port

        self.ip, self.port = config.tor_controller.split(":")
        self.port = int(self.port)

        self.proxy_ip, self.proxy_port = config.tor_proxy.split(":")
        self.proxy_port = int(self.proxy_port)

        # Test proxy port
        if config.tor != "disable":
            try:
                assert self.connect(), "No connection"
                self.log.debug("Tor proxy port %s check ok" % config.tor_proxy)
            except Exception, err:
                self.log.debug("Tor proxy port %s check error: %s" % (config.tor_proxy, err))
                self.enabled = False
                # Change to self-bundled Tor ports
                from lib.PySocks import socks
                self.port = 49051
                self.proxy_port = 49050
                socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", self.proxy_port)
                if os.path.isfile(self.tor_exe):  # Already, downloaded: sync mode
                    self.startTor()
                else:  # Not downloaded yet: Async mode
                    gevent.spawn(self.startTor)

    def startTor(self):
        if sys.platform.startswith("win"):
            try:
                if not os.path.isfile(self.tor_exe):
                    self.downloadTor()

                self.log.info("Starting Tor client %s..." % self.tor_exe)
                tor_dir = os.path.dirname(self.tor_exe)
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                self.tor_process = subprocess.Popen(r"%s -f torrc" % self.tor_exe, cwd=tor_dir, close_fds=True, startupinfo=startupinfo)
                for wait in range(1,10):  # Wait for startup
                    time.sleep(wait * 0.5)
                    self.enabled = True
                    if self.connect():
                        break
                # Terminate on exit
                atexit.register(self.stopTor)
            except Exception, err:
                self.log.error("Error starting Tor client: %s" % Debug.formatException(err))
                self.enabled = False
        return False

    def stopTor(self):
        self.log.debug("Stopping...")
        try:
            self.tor_process.terminate()
        except Exception, err:
            self.log.error("Error stopping Tor: %s" % err)

    def downloadTor(self):
        self.log.info("Downloading Tor...")
        # Check Tor webpage for link
        download_page = helper.httpRequest("https://www.torproject.org/download/download.html").read()
        download_url = re.search('href="(.*?tor.*?win32.*?zip)"', download_page).group(1)
        if not download_url.startswith("http"):
            download_url = "https://www.torproject.org/download/" + download_url

        # Download Tor client
        self.log.info("Downloading %s" % download_url)
        data = helper.httpRequest(download_url, as_file=True)
        data_size = data.tell()

        # Handle redirect
        if data_size < 1024 and "The document has moved" in data.getvalue():
            download_url = re.search('href="(.*?tor.*?win32.*?zip)"', data.getvalue()).group(1)
            data = helper.httpRequest(download_url, as_file=True)
            data_size = data.tell()

        if data_size > 1024:
            import zipfile
            zip = zipfile.ZipFile(data)
            self.log.info("Unpacking Tor")
            for inner_path in zip.namelist():
                if ".." in inner_path:
                    continue
                dest_path = inner_path
                dest_path = re.sub("^Data/Tor/", "tools/tor/data/", dest_path)
                dest_path = re.sub("^Data/", "tools/tor/data/", dest_path)
                dest_path = re.sub("^Tor/", "tools/tor/", dest_path)
                dest_dir = os.path.dirname(dest_path)
                if dest_dir and not os.path.isdir(dest_dir):
                    os.makedirs(dest_dir)

                if dest_dir != dest_path.strip("/"):
                    data = zip.read(inner_path)
                    if not os.path.isfile(dest_path):
                        open(dest_path, 'wb').write(data)
        else:
            self.log.error("Bad response from server: %s" % data.getvalue())
            return False

    def connect(self):
        if not self.enabled:
            return False
        self.site_onions = {}
        self.privatekeys = {}

        if "socket_noproxy" in dir(socket):  # Socket proxy-patched, use non-proxy one
            conn = socket.socket_noproxy(socket.AF_INET, socket.SOCK_STREAM)
        else:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.log.debug("Connecting to %s:%s" % (self.ip, self.port))
        try:
            with self.lock:
                conn.connect((self.ip, self.port))

                # Auth cookie file
                res_protocol = self.send("PROTOCOLINFO", conn)
                cookie_match = re.search('COOKIEFILE="(.*?)"', res_protocol)
                if cookie_match:
                    cookie_file = cookie_match.group(1).decode("string-escape")
                    auth_hex = binascii.b2a_hex(open(cookie_file, "rb").read())
                    res_auth = self.send("AUTHENTICATE %s" % auth_hex, conn)
                elif config.tor_password:
                    res_auth = self.send('AUTHENTICATE "%s"' % config.tor_password, conn)
                else:
                    res_auth = self.send("AUTHENTICATE", conn)

                assert "250 OK" in res_auth, "Authenticate error %s" % res_auth

                # Version 0.2.7.5 required because ADD_ONION support
                res_version = self.send("GETINFO version", conn)
                version = re.search('version=([0-9\.]+)', res_version).group(1)
                assert float(version.replace(".", "0", 2)) >= 207.5, "Tor version >=0.2.7.5 required, found: %s" % version

                self.status = u"Connected (%s)" % res_auth
                self.conn = conn
        except Exception, err:
            self.conn = None
            self.status = u"Error (%s)" % err
            self.log.error("Tor controller connect error: %s" % Debug.formatException(err))
            self.enabled = False
        return self.conn

    def disconnect(self):
        self.conn.close()
        self.conn = None

    def startOnions(self):
        if self.enabled:
            self.log.debug("Start onions")
            self.start_onions = True

    # Get new exit node ip
    def resetCircuits(self):
        res = self.request("SIGNAL NEWNYM")
        if "250 OK" not in res:
            self.status = u"Reset circuits error (%s)" % res
            self.log.error("Tor reset circuits error: %s" % res)

    def addOnion(self):
        res = self.request("ADD_ONION NEW:RSA1024 port=%s" % self.fileserver_port)
        match = re.search("ServiceID=([A-Za-z0-9]+).*PrivateKey=RSA1024:(.*?)[\r\n]", res, re.DOTALL)
        if match:
            onion_address, onion_privatekey = match.groups()
            self.privatekeys[onion_address] = onion_privatekey
            self.status = u"OK (%s onion running)" % len(self.privatekeys)
            SiteManager.peer_blacklist.append((onion_address + ".onion", self.fileserver_port))
            return onion_address
        else:
            self.status = u"AddOnion error (%s)" % res
            self.log.error("Tor addOnion error: %s" % res)
            return False

    def delOnion(self, address):
        res = self.request("DEL_ONION %s" % address)
        if "250 OK" in res:
            del self.privatekeys[address]
            self.status = "OK (%s onion running)" % len(self.privatekeys)
            return True
        else:
            self.status = u"DelOnion error (%s)" % res
            self.log.error("Tor delOnion error: %s" % res)
            self.disconnect()
            return False

    def request(self, cmd):
        with self.lock:
            if not self.enabled:
                return False
            if not self.conn:
                if not self.connect():
                    return ""
            return self.send(cmd)

    def send(self, cmd, conn=None):
        if not conn:
            conn = self.conn
        self.log.debug("> %s" % cmd)
        back = ""
        for retry in range(2):
            try:
                conn.sendall("%s\r\n" % cmd)
                while not back.endswith("250 OK\r\n"):
                    back += conn.recv(1024 * 64).decode("utf8", "ignore")
                break
            except Exception, err:
                self.log.error("Tor send error: %s, reconnecting..." % err)
                self.disconnect()
                time.sleep(1)
                self.connect()
                back = None
        self.log.debug("< %s" % back.strip())
        return back

    def getPrivatekey(self, address):
        return self.privatekeys[address]

    def getPublickey(self, address):
        return CryptRsa.privatekeyToPublickey(self.privatekeys[address])

    def getOnion(self, site_address):
        with self.lock:
            if not self.enabled:
                return None
            if self.start_onions:  # Different onion for every site
                onion = self.site_onions.get(site_address)
            else:  # Same onion for every site
                onion = self.site_onions.get("global")
                site_address = "global"
            if not onion:
                self.site_onions[site_address] = self.addOnion()
                onion = self.site_onions[site_address]
                self.log.debug("Created new hidden service for %s: %s" % (site_address, onion))
            return onion

    def createSocket(self, onion, port):
        if not self.enabled:
            return False
        self.log.debug("Creating new socket to %s:%s" % (onion, port))
        if config.tor == "always":  # Every socket is proxied by default
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((onion, int(port)))
        else:
            sock = socks.socksocket()
            sock.set_proxy(socks.SOCKS5, self.proxy_ip, self.proxy_port)
            sock.connect((onion, int(port)))
        return sock

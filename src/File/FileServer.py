import logging
import urllib2
import re
import time

import gevent

import util
from Config import config
from FileRequest import FileRequest
from Site import SiteManager
from Debug import Debug
from Connection import ConnectionServer
from util import UpnpPunch


class FileServer(ConnectionServer):

    def __init__(self, ip=config.fileserver_ip, port=config.fileserver_port):
        ConnectionServer.__init__(self, ip, port, self.handleRequest)
        if config.ip_external:  # Ip external defined in arguments
            self.port_opened = True
            SiteManager.peer_blacklist.append((config.ip_external, self.port))  # Add myself to peer blacklist
        else:
            self.port_opened = None  # Is file server opened on router
        self.sites = {}
        self.last_request = time.time()
        self.files_parsing = {}

    # Handle request to fileserver
    def handleRequest(self, connection, message):
        if config.verbose:
            if "params" in message:
                self.log.debug(
                    "FileRequest: %s %s %s %s" %
                    (str(connection), message["cmd"], message["params"].get("site"), message["params"].get("inner_path"))
                )
            else:
                self.log.debug("FileRequest: %s %s" % (str(connection), message["cmd"]))
        req = FileRequest(self, connection)
        req.route(message["cmd"], message.get("req_id"), message.get("params"))
        if not self.has_internet:
            self.has_internet = True
            self.onInternetOnline()

    def onInternetOnline(self):
        self.log.info("Internet online")
        gevent.spawn(self.checkSites, check_files=False, force_port_check=True)

    # Reload the FileRequest class to prevent restarts in debug mode
    def reload(self):
        global FileRequest
        import imp
        FileRequest = imp.load_source("FileRequest", "src/File/FileRequest.py").FileRequest

    # Try to open the port using upnp
    def openport(self, port=None, check=True):
        if not port:
            port = self.port
        if self.port_opened:
            return True  # Port already opened
        if check:  # Check first if its already opened
            time.sleep(1)  # Wait for port open
            if self.testOpenport(port, use_alternative=False)["result"] is True:
                return True  # Port already opened

        if config.tor == "always":  # Port opening won't work in Tor mode
            return False

        self.log.info("Trying to open port using UpnpPunch...")
        try:
            upnp_punch = UpnpPunch.open_port(self.port, 'ZeroNet')
            upnp_punch = True
        except Exception, err:
            self.log.error("UpnpPunch run error: %s" % Debug.formatException(err))
            upnp_punch = False

        if upnp_punch and self.testOpenport(port)["result"] is True:
            return True

        self.log.info("Upnp mapping failed :( Please forward port %s on your router to your ipaddress" % port)
        return False

    # Test if the port is open
    def testOpenport(self, port=None, use_alternative=True):
        if not port:
            port = self.port
        back = self.testOpenportPortchecker(port)
        if back["result"] is not True and use_alternative:  # If no success try alternative checker
            return self.testOpenportCanyouseeme(port)
        else:
            return back

    def testOpenportPortchecker(self, port=None):
        self.log.info("Checking port %s using portchecker.co..." % port)
        try:
            data = urllib2.urlopen("http://portchecker.co/check", "port=%s" % port, timeout=20.0).read()
            message = re.match('.*<div id="results-wrapper">(.*?)</div>', data, re.DOTALL).group(1)
            message = re.sub("<.*?>", "", message.replace("<br>", " ").replace("&nbsp;", " ").strip())  # Strip http tags
        except Exception, err:
            message = "Error: %s" % Debug.formatException(err)
            data = ""

        if "closed" in message or "Error" in message:
            if config.tor != "always":
                self.log.info("[BAD :(] Port closed: %s" % message)
            if port == self.port:
                self.port_opened = False  # Self port, update port_opened status
                match = re.match(".*targetIP.*?value=\"(.*?)\"", data, re.DOTALL)  # Try find my external ip in message
                if match:  # Found my ip in message
                    config.ip_external = match.group(1)
                    SiteManager.peer_blacklist.append((config.ip_external, self.port))  # Add myself to peer blacklist
                else:
                    config.ip_external = False
            return {"result": False, "message": message}
        else:
            self.log.info("[OK :)] Port open: %s" % message)
            if port == self.port:  # Self port, update port_opened status
                self.port_opened = True
                match = re.match(".*targetIP.*?value=\"(.*?)\"", data, re.DOTALL)  # Try find my external ip in message
                if match:  # Found my ip in message
                    config.ip_external = match.group(1)
                    SiteManager.peer_blacklist.append((config.ip_external, self.port))  # Add myself to peer blacklist
                else:
                    config.ip_external = False
            return {"result": True, "message": message}

    def testOpenportCanyouseeme(self, port=None):
        self.log.info("Checking port %s using canyouseeme.org..." % port)
        try:
            data = urllib2.urlopen("http://www.canyouseeme.org/", "port=%s" % port, timeout=20.0).read()
            message = re.match('.*<p style="padding-left:15px">(.*?)</p>', data, re.DOTALL).group(1)
            message = re.sub("<.*?>", "", message.replace("<br>", " ").replace("&nbsp;", " "))  # Strip http tags
        except Exception, err:
            message = "Error: %s" % Debug.formatException(err)

        if "Error" in message:
            if config.tor != "always":
                self.log.info("[BAD :(] Port closed: %s" % message)
            if port == self.port:
                self.port_opened = False  # Self port, update port_opened status
                match = re.match(".*?([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", message)  # Try find my external ip in message
                if match:  # Found my ip in message
                    config.ip_external = match.group(1)
                    SiteManager.peer_blacklist.append((config.ip_external, self.port))  # Add myself to peer blacklist
                else:
                    config.ip_external = False
            return {"result": False, "message": message}
        else:
            self.log.info("[OK :)] Port open: %s" % message)
            if port == self.port:  # Self port, update port_opened status
                self.port_opened = True
                match = re.match(".*?([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", message)  # Try find my external ip in message
                if match:  # Found my ip in message
                    config.ip_external = match.group(1)
                    SiteManager.peer_blacklist.append((config.ip_external, self.port))  # Add myself to peer blacklist
                else:
                    config.ip_external = False
            return {"result": True, "message": message}

    # Set external ip without testing
    def setIpExternal(self, ip_external):
        logging.info("Setting external ip without testing: %s..." % ip_external)
        config.ip_external = ip_external
        self.port_opened = True

    # Check site file integrity
    def checkSite(self, site, check_files=True):
        if site.settings["serving"]:
            site.announce(mode="startup")  # Announce site to tracker
            site.update(check_files=check_files)  # Update site's content.json and download changed files
            site.sendMyHashfield()
            site.updateHashfield()
            if len(site.peers) > 5:  # Keep active connections if site having 5 or more peers
                site.needConnections()

    # Check sites integrity
    @util.Noparallel()
    def checkSites(self, check_files=True, force_port_check=False):
        self.log.debug("Checking sites...")
        sites_checking = False
        if self.port_opened is None or force_port_check:  # Test and open port if not tested yet
            if len(self.sites) <= 2:  # Don't wait port opening on first startup
                sites_checking = True
                for address, site in self.sites.items():
                    gevent.spawn(self.checkSite, site, check_files)

            self.openport()
            if self.port_opened is False:
                self.tor_manager.startOnions()

        if not sites_checking:
            for address, site in self.sites.items():  # Check sites integrity
                gevent.spawn(self.checkSite, site, check_files)  # Check in new thread
                time.sleep(2)  # Prevent too quick request

    def trackersFileReloader(self):
        while 1:
            config.loadTrackersFile()
            time.sleep(60)

    # Announce sites every 20 min
    def announceSites(self):
        import gc
        if config.trackers_file:
            gevent.spawn(self.trackersFileReloader)
        while 1:
            # Sites health care every 20 min
            for address, site in self.sites.items():
                if not site.settings["serving"]:
                    continue
                if site.peers:
                    site.announcePex()

                # Retry failed files
                if site.bad_files:
                    site.retryBadFiles()

                site.cleanupPeers()

                # In passive mode keep 5 active peer connection to get the updates
                if self.port_opened is False:
                    site.needConnections()

                time.sleep(2)  # Prevent too quick request

            site = None
            gc.collect()  # Implicit garbage collection

            # Find new peers
            for tracker_i in range(len(config.trackers)):
                time.sleep(60 * 20 / len(config.trackers))  # Query all trackers one-by-one in 20 minutes evenly distributed
                for address, site in self.sites.items():
                    if not site.settings["serving"]:
                        continue
                    site.announce(mode="update", pex=False)
                    if site.settings["own"]:  # Check connections more frequently on own sites to speed-up first connections
                        site.needConnections()
                    site.sendMyHashfield(3)
                    site.updateHashfield(1)
                    time.sleep(2)

    # Detects if computer back from wakeup
    def wakeupWatcher(self):
        last_time = time.time()
        while 1:
            time.sleep(30)
            if time.time() - max(self.last_request, last_time) > 60 * 3:  # If taken more than 3 minute then the computer was in sleep mode
                self.log.info(
                    "Wakeup detected: time warp from %s to %s (%s sleep seconds), acting like startup..." %
                    (last_time, time.time(), time.time() - last_time)
                )
                self.checkSites(check_files=False, force_port_check=True)
            last_time = time.time()

    # Bind and start serving sites
    def start(self, check_sites=True):
        self.sites = SiteManager.site_manager.list()
        self.log = logging.getLogger("FileServer")

        if config.debug:
            # Auto reload FileRequest on change
            from Debug import DebugReloader
            DebugReloader(self.reload)

        if check_sites:  # Open port, Update sites, Check files integrity
            gevent.spawn(self.checkSites)

        thread_announce_sites = gevent.spawn(self.announceSites)
        thread_wakeup_watcher = gevent.spawn(self.wakeupWatcher)

        ConnectionServer.start(self)

        # thread_wakeup_watcher.kill(exception=Debug.Notify("Stopping FileServer"))
        # thread_announce_sites.kill(exception=Debug.Notify("Stopping FileServer"))
        self.log.debug("Stopped.")

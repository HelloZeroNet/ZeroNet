import random
import time
import hashlib
import urllib
import urllib2
import struct
import socket
import re
import collections

from lib import bencode
from lib.subtl.subtl import UdpTrackerClient
from lib.PySocks import socks
from lib.PySocks import sockshandler
import gevent

from Plugin import PluginManager
from Config import config
from Debug import Debug
from util import helper
import util


class AnnounceError(Exception):
    pass

global_stats = collections.defaultdict(lambda: collections.defaultdict(int))


@PluginManager.acceptPlugins
class SiteAnnouncer(object):
    def __init__(self, site):
        self.site = site
        self.stats = {}
        self.fileserver_port = config.fileserver_port
        self.peer_id = self.site.connection_server.peer_id
        self.last_tracker_id = random.randint(0, 10)
        self.time_last_announce = 0

    def getTrackers(self):
        return config.trackers

    def getSupportedTrackers(self):
        trackers = self.getTrackers()
        if config.disable_udp or config.trackers_proxy != "disable":
            trackers = [tracker for tracker in trackers if not tracker.startswith("udp://")]

        if not self.site.connection_server.tor_manager.enabled:
            trackers = [tracker for tracker in trackers if ".onion" not in tracker]

        if "ipv6" not in self.site.connection_server.supported_ip_types:
            trackers = [tracker for tracker in trackers if helper.getIpType(self.getAddressParts(tracker)["ip"]) != "ipv6"]

        return trackers

    def getAnnouncingTrackers(self, mode):
        trackers = self.getSupportedTrackers()

        if trackers and (mode == "update" or mode == "more"):  # Only announce on one tracker, increment the queried tracker id
            self.last_tracker_id += 1
            self.last_tracker_id = self.last_tracker_id % len(trackers)
            trackers_announcing = [trackers[self.last_tracker_id]]  # We only going to use this one
        else:
            trackers_announcing = trackers

        return trackers_announcing

    def getOpenedServiceTypes(self):
        back = []
        # Type of addresses they can reach me
        if config.trackers_proxy == "disable":
            for ip_type, opened in self.site.connection_server.port_opened.items():
                if opened:
                    back.append(ip_type)
        if self.site.connection_server.tor_manager.start_onions:
            back.append("onion")
        return back

    @util.Noparallel(blocking=False)
    def announce(self, force=False, mode="start", pex=True):
        if time.time() - self.time_last_announce < 30 and not force:
            return  # No reannouncing within 30 secs
        if force:
            self.site.log.debug("Force reannounce in mode %s" % mode)

        self.fileserver_port = config.fileserver_port
        self.time_last_announce = time.time()

        trackers = self.getAnnouncingTrackers(mode)

        if config.verbose:
            self.site.log.debug("Tracker announcing, trackers: %s" % trackers)

        errors = []
        slow = []
        s = time.time()
        threads = []
        num_announced = 0

        for tracker in trackers:  # Start announce threads
            tracker_stats = global_stats[tracker]
            # Reduce the announce time for trackers that looks unreliable
            if tracker_stats["num_error"] > 5 and tracker_stats["time_request"] > time.time() - 60 * min(30, tracker_stats["num_error"]):
                if config.verbose:
                    self.site.log.debug("Tracker %s looks unreliable, announce skipped (error: %s)" % (tracker, tracker_stats["num_error"]))
                continue
            thread = gevent.spawn(self.announceTracker, tracker, mode=mode)
            threads.append(thread)
            thread.tracker = tracker

        time.sleep(0.01)
        self.updateWebsocket(trackers="announcing")

        gevent.joinall(threads, timeout=20)  # Wait for announce finish

        for thread in threads:
            if thread.value is None:
                continue
            if thread.value is not False:
                if thread.value > 1.0:  # Takes more than 1 second to announce
                    slow.append("%.2fs %s" % (thread.value, thread.tracker))
                num_announced += 1
            else:
                if thread.ready():
                    errors.append(thread.tracker)
                else:  # Still running
                    slow.append("30s+ %s" % thread.tracker)

        # Save peers num
        self.site.settings["peers"] = len(self.site.peers)

        if len(errors) < len(threads):  # At least one tracker finished
            if len(trackers) == 1:
                announced_to = trackers[0]
            else:
                announced_to = "%s/%s trackers" % (num_announced, len(threads))
            if mode != "update" or config.verbose:
                self.site.log.debug(
                    "Announced in mode %s to %s in %.3fs, errors: %s, slow: %s" %
                    (mode, announced_to, time.time() - s, errors, slow)
                )
        else:
            if len(threads) > 1:
                self.site.log.error("Announce to %s trackers in %.3fs, failed" % (len(threads), time.time() - s))
            if len(threads) == 1 and mode != "start":  # Move to next tracker
                self.site.log.debug("Tracker failed, skipping to next one...")
                gevent.spawn_later(1.0, self.announce, force=force, mode=mode, pex=pex)

        self.updateWebsocket(trackers="announced")

        if pex:
            self.updateWebsocket(pex="announcing")
            if mode == "more":  # Need more peers
                self.announcePex(need_num=10)
            else:
                self.announcePex()

            self.updateWebsocket(pex="announced")

    def getTrackerHandler(self, protocol):
        if protocol == "udp":
            handler = self.announceTrackerUdp
        elif protocol == "http":
            handler = self.announceTrackerHttp
        elif protocol == "https":
            handler = self.announceTrackerHttps
        else:
            handler = None
        return handler

    def getAddressParts(self, tracker):
        if "://" not in tracker or not re.match("^[A-Za-z0-9:/\\.#-]+$", tracker):
            return None
        protocol, address = tracker.split("://", 1)
        try:
            ip, port = address.rsplit(":", 1)
        except ValueError as err:
            ip = address
            port = 80
            if protocol.startswith("https"):
                port = 443
        back = {}
        back["protocol"] = protocol
        back["address"] = address
        back["ip"] = ip
        back["port"] = port
        return back

    def announceTracker(self, tracker, mode="start", num_want=10):
        s = time.time()
        address_parts = self.getAddressParts(tracker)
        if not address_parts:
            self.site.log.warning("Tracker %s error: Invalid address" % tracker.decode("utf8", "ignore"))
            return False

        if tracker not in self.stats:
            self.stats[tracker] = {"status": "", "num_request": 0, "num_success": 0, "num_error": 0, "time_request": 0, "time_last_error": 0}

        last_status = self.stats[tracker]["status"]
        self.stats[tracker]["status"] = "announcing"
        self.stats[tracker]["time_request"] = time.time()
        global_stats[tracker]["time_request"] = time.time()
        if config.verbose:
            self.site.log.debug("Tracker announcing to %s (mode: %s)" % (tracker, mode))
        if mode == "update":
            num_want = 10
        else:
            num_want = 30

        handler = self.getTrackerHandler(address_parts["protocol"])
        error = None
        try:
            if handler:
                peers = handler(address_parts["address"], mode=mode, num_want=num_want)
            else:
                raise AnnounceError("Unknown protocol: %s" % address_parts["protocol"])
        except Exception, err:
            self.site.log.warning("Tracker %s announce failed: %s in mode %s" % (tracker, str(err).decode("utf8", "ignore"), mode))
            error = err

        if error:
            self.stats[tracker]["status"] = "error"
            self.stats[tracker]["time_status"] = time.time()
            self.stats[tracker]["last_error"] = str(err).decode("utf8", "ignore")
            self.stats[tracker]["time_last_error"] = time.time()
            self.stats[tracker]["num_error"] += 1
            self.stats[tracker]["num_request"] += 1
            global_stats[tracker]["num_request"] += 1
            global_stats[tracker]["num_error"] += 1
            self.updateWebsocket(tracker="error")
            return False

        if peers is None:  # Announce skipped
            self.stats[tracker]["time_status"] = time.time()
            self.stats[tracker]["status"] = last_status
            return None

        self.stats[tracker]["status"] = "announced"
        self.stats[tracker]["time_status"] = time.time()
        self.stats[tracker]["num_success"] += 1
        self.stats[tracker]["num_request"] += 1
        global_stats[tracker]["num_request"] += 1
        global_stats[tracker]["num_error"] = 0

        if peers is True:  # Announce success, but no peers returned
            return time.time() - s

        # Adding peers
        added = 0
        for peer in peers:
            if peer["port"] == 1:  # Some trackers does not accept port 0, so we send port 1 as not-connectable
                peer["port"] = 0
            if not peer["port"]:
                continue  # Dont add peers with port 0
            if self.site.addPeer(peer["addr"], peer["port"], source="tracker"):
                added += 1

        if added:
            self.site.worker_manager.onPeers()
            self.site.updateWebsocket(peers_added=added)

        if config.verbose:
            self.site.log.debug(
                "Tracker result: %s://%s (found %s peers, new: %s, total: %s)" %
                (address_parts["protocol"], address_parts["address"], len(peers), added, len(self.site.peers))
            )
        return time.time() - s

    def announceTrackerUdp(self, tracker_address, mode="start", num_want=10):
        s = time.time()
        if config.disable_udp:
            raise AnnounceError("Udp disabled by config")
        if config.trackers_proxy != "disable":
            raise AnnounceError("Udp trackers not available with proxies")

        ip, port = tracker_address.split("/")[0].split(":")
        tracker = UdpTrackerClient(ip, int(port))
        if helper.getIpType(ip) in self.getOpenedServiceTypes():
            tracker.peer_port = self.fileserver_port
        else:
            tracker.peer_port = 0
        tracker.connect()
        if not tracker.poll_once():
            raise AnnounceError("Could not connect")
        tracker.announce(info_hash=hashlib.sha1(self.site.address).hexdigest(), num_want=num_want, left=431102370)
        back = tracker.poll_once()
        if not back:
            raise AnnounceError("No response after %.0fs" % (time.time() - s))
        elif type(back) is dict and "response" in back:
            peers = back["response"]["peers"]
        else:
            raise AnnounceError("Invalid response: %r" % back)

        return peers

    def httpRequest(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
            'Accept-Encoding': 'none',
            'Accept-Language': 'en-US,en;q=0.8',
            'Connection': 'keep-alive'
        }

        req = urllib2.Request(url, headers=headers)

        if config.trackers_proxy == "tor":
            tor_manager = self.site.connection_server.tor_manager
            handler = sockshandler.SocksiPyHandler(socks.SOCKS5, tor_manager.proxy_ip, tor_manager.proxy_port)
            opener = urllib2.build_opener(handler)
            return opener.open(req, timeout=50)
        elif config.trackers_proxy == "disable":
            return urllib2.urlopen(req, timeout=25)
        else:
            proxy_ip, proxy_port = config.trackers_proxy.split(":")
            handler = sockshandler.SocksiPyHandler(socks.SOCKS5, proxy_ip, int(proxy_port))
            opener = urllib2.build_opener(handler)
            return opener.open(req, timeout=50)

    def announceTrackerHttps(self, *args, **kwargs):
        kwargs["protocol"] = "https"
        return self.announceTrackerHttp(*args, **kwargs)

    def announceTrackerHttp(self, tracker_address, mode="start", num_want=10, protocol="http"):
        tracker_ip, tracker_port = tracker_address.rsplit(":", 1)
        if helper.getIpType(tracker_ip) in self.getOpenedServiceTypes():
            port = self.fileserver_port
        else:
            port = 1
        params = {
            'info_hash': hashlib.sha1(self.site.address).digest(),
            'peer_id': self.peer_id, 'port': port,
            'uploaded': 0, 'downloaded': 0, 'left': 431102370, 'compact': 1, 'numwant': num_want,
            'event': 'started'
        }

        url = protocol + "://" + tracker_address + "?" + urllib.urlencode(params)

        s = time.time()
        response = None
        # Load url
        if config.tor == "always" or config.trackers_proxy != "disable":
            timeout = 60
        else:
            timeout = 30

        with gevent.Timeout(timeout, False):  # Make sure of timeout
            req = self.httpRequest(url)
            response = req.read()
            req.fp._sock.recv = None  # Hacky avoidance of memory leak for older python versions
            req.close()
            req = None

        if not response:
            raise AnnounceError("No response after %.0fs" % (time.time() - s))

        # Decode peers
        try:
            peer_data = bencode.decode(response)["peers"]
            response = None
            peer_count = len(peer_data) / 6
            peers = []
            for peer_offset in xrange(peer_count):
                off = 6 * peer_offset
                peer = peer_data[off:off + 6]
                addr, port = struct.unpack('!LH', peer)
                peers.append({"addr": socket.inet_ntoa(struct.pack('!L', addr)), "port": port})
        except Exception as err:
            raise AnnounceError("Invalid response: %r (%s)" % (response, err))

        return peers

    @util.Noparallel(blocking=False)
    def announcePex(self, query_num=2, need_num=5):
        peers = self.site.getConnectedPeers()
        if len(peers) == 0:  # Wait 3s for connections
            time.sleep(3)
            peers = self.site.getConnectedPeers()

        if len(peers) == 0:  # Small number of connected peers for this site, connect to any
            peers = self.site.peers.values()
            need_num = 10

        random.shuffle(peers)
        done = 0
        total_added = 0
        for peer in peers:
            num_added = peer.pex(need_num=need_num)
            if num_added is not False:
                done += 1
                total_added += num_added
                if num_added:
                    self.site.worker_manager.onPeers()
                    self.site.updateWebsocket(peers_added=num_added)
            if done == query_num:
                break
        self.site.log.debug("Pex result: from %s peers got %s new peers." % (done, total_added))

    def updateWebsocket(self, **kwargs):
        if kwargs:
            param = {"event": kwargs.items()[0]}
        else:
            param = None

        for ws in self.site.websockets:
            ws.event("announcerChanged", self.site, param)

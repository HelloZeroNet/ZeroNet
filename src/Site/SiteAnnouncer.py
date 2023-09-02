import random
import time
import hashlib
import logging
import re
import collections

import gevent

from Plugin import PluginManager
from Config import config
from Debug import Debug
from util import helper
from greenlet import GreenletExit
import util
from util import CircularIterator


class AnnounceError(Exception):
    pass

global_stats = collections.defaultdict(lambda: collections.defaultdict(int))


@PluginManager.acceptPlugins
class SiteAnnouncer(object):
    def __init__(self, site):
        self.site = site
        self.log = logging.getLogger("Site:%s SiteAnnouncer" % self.site.address_short)

        self.stats = {}
        self.fileserver_port = config.fileserver_port
        self.peer_id = self.site.connection_server.peer_id
        self.tracker_circular_iterator = CircularIterator()
        self.time_last_announce = 0
        self.supported_tracker_count = 0

    # Returns connection_server rela
    # Since 0.8.0
    @property
    def connection_server(self):
        return self.site.connection_server

    def getTrackers(self):
        return config.trackers

    def getSupportedTrackers(self):
        trackers = self.getTrackers()

        if not self.connection_server.tor_manager.enabled:
            trackers = [tracker for tracker in trackers if ".onion" not in tracker]

        trackers = [tracker for tracker in trackers if self.getAddressParts(tracker)]  # Remove trackers with unknown address

        if "ipv6" not in self.connection_server.supported_ip_types:
            trackers = [tracker for tracker in trackers if self.connection_server.getIpType(self.getAddressParts(tracker)["ip"]) != "ipv6"]

        return trackers

    # Returns a cached value of len(self.getSupportedTrackers()), which can be
    # inacurate.
    # To be used from Site for estimating available tracker count.
    def getSupportedTrackerCount(self):
        return self.supported_tracker_count

    def shouldTrackerBeTemporarilyIgnored(self, tracker, mode, force):
        if not tracker:
            return True

        if force:
            return False

        now = time.time()

        # Throttle accessing unresponsive trackers
        tracker_stats = global_stats[tracker]
        delay = min(30 * tracker_stats["num_error"], 60 * 10)
        time_announce_allowed = tracker_stats["time_request"] + delay
        if now < time_announce_allowed:
            return True

        return False

    def getAnnouncingTrackers(self, mode, force):
        trackers = self.getSupportedTrackers()

        self.supported_tracker_count = len(trackers)

        if trackers and (mode == "update" or mode == "more"):

            # Choose just 2 trackers to announce to

            trackers_announcing = []

            # One is the next in sequence

            self.tracker_circular_iterator.resetSuccessiveCount()
            while 1:
                tracker = self.tracker_circular_iterator.next(trackers)
                if not self.shouldTrackerBeTemporarilyIgnored(tracker, mode, force):
                    trackers_announcing.append(tracker)
                    break
                if self.tracker_circular_iterator.isWrapped():
                    break

            # And one is just random

            shuffled_trackers = random.sample(trackers, len(trackers))
            for tracker in shuffled_trackers:
                if tracker in trackers_announcing:
                    continue
                if not self.shouldTrackerBeTemporarilyIgnored(tracker, mode, force):
                    trackers_announcing.append(tracker)
                    break
        else:
            trackers_announcing = [
                tracker for tracker in trackers
                if not self.shouldTrackerBeTemporarilyIgnored(tracker, mode, force)
            ]

        return trackers_announcing

    def getOpenedServiceTypes(self):
        back = []
        # Type of addresses they can reach me
        if config.trackers_proxy == "disable" and config.tor != "always":
            for ip_type, opened in list(self.connection_server.port_opened.items()):
                if opened:
                    back.append(ip_type)
        if self.connection_server.tor_manager.start_onions:
            back.append("onion")
        return back

    @util.Noparallel()
    def announce(self, force=False, mode="start", pex=True):
        if not self.site.isServing():
            return

        if time.time() - self.time_last_announce < 30 and not force:
            return  # No reannouncing within 30 secs

        self.log.debug("announce: force=%s, mode=%s, pex=%s" % (force, mode, pex))

        self.fileserver_port = config.fileserver_port
        self.time_last_announce = time.time()

        trackers = self.getAnnouncingTrackers(mode, force)
        self.log.debug("Chosen trackers: %s" % trackers)
        self.announceToTrackers(trackers, force=force, mode=mode)

        if pex:
            self.announcePex()

    def getTrackerHandler(self, protocol):
        return None

    def getAddressParts(self, tracker):
        if "://" not in tracker or not re.match("^[A-Za-z0-9:/\\.#-]+$", tracker):
            return None
        protocol, address = tracker.split("://", 1)
        if ":" in address:
            ip, port = address.rsplit(":", 1)
        else:
            ip = address
            if protocol.startswith("https"):
                port = 443
            else:
                port = 80
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
            self.log.warning("Tracker %s error: Invalid address" % tracker)
            return False

        if tracker not in self.stats:
            self.stats[tracker] = {"status": "", "num_request": 0, "num_success": 0, "num_error": 0, "time_request": 0, "time_last_error": 0}

        last_status = self.stats[tracker]["status"]
        self.stats[tracker]["status"] = "announcing"
        self.stats[tracker]["time_request"] = time.time()
        global_stats[tracker]["time_request"] = time.time()
        if config.verbose:
            self.log.debug("Tracker announcing to %s (mode: %s)" % (tracker, mode))
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
        except Exception as err:
            self.log.warning("Tracker %s announce failed: %s in mode %s" % (tracker, Debug.formatException(err), mode))
            error = err

        if error:
            self.stats[tracker]["status"] = "error"
            self.stats[tracker]["time_status"] = time.time()
            self.stats[tracker]["last_error"] = str(error)
            self.stats[tracker]["time_last_error"] = time.time()
            if self.connection_server.has_internet:
                self.stats[tracker]["num_error"] += 1
            self.stats[tracker]["num_request"] += 1
            global_stats[tracker]["num_request"] += 1
            if self.connection_server.has_internet:
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
            self.log.debug(
                "Tracker result: %s://%s (found %s peers, new: %s, total: %s)" %
                (address_parts["protocol"], address_parts["address"], len(peers), added, len(self.site.peers))
            )
        return time.time() - s

    def announceToTrackers(self, trackers, force=False, mode="start"):
        errors = []
        slow = []
        s = time.time()
        threads = []
        num_announced = 0

        for tracker in trackers:  # Start announce threads
            thread = self.site.greenlet_manager.spawn(self.announceTracker, tracker, mode=mode)
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
                self.log.debug(
                    "Announced in mode %s to %s in %.3fs, errors: %s, slow: %s" %
                    (mode, announced_to, time.time() - s, errors, slow)
                )
        else:
            if len(threads) > 1:
                self.log.error("Announce to %s trackers in %.3fs, failed" % (len(threads), time.time() - s))
            if len(threads) > 1 and mode != "start":  # Move to next tracker
                self.log.debug("Tracker failed, skipping to next one...")
                self.site.greenlet_manager.spawnLater(5.0, self.announce, force=force, mode=mode, pex=False)

        self.updateWebsocket(trackers="announced")

    @util.Noparallel(blocking=False)
    def announcePex(self, query_num=2, need_num=10, establish_connections=True):
        peers = []
        try:
            peer_count = 20 + query_num * 2

            # Wait for some peers to connect
            for _ in range(5):
                if not self.site.isServing():
                    return
                peers = self.site.getConnectedPeers(only_fully_connected=True)
                if len(peers) > 0:
                    break
                time.sleep(2)

            if len(peers) < peer_count and establish_connections:
                # Small number of connected peers for this site, connect to any
                peers = list(self.site.getRecentPeers(peer_count))

            if len(peers) > 0:
                self.updateWebsocket(pex="announcing")

            random.shuffle(peers)
            done = 0
            total_added = 0
            for peer in peers:
                if not establish_connections and not peer.isConnected():
                    continue
                num_added = peer.pex(need_num=need_num)
                if num_added is not False:
                    done += 1
                    total_added += num_added
                    if num_added:
                        self.site.worker_manager.onPeers()
                        self.site.updateWebsocket(peers_added=num_added)
                if done == query_num:
                    break
                time.sleep(0.1)
            self.log.debug("Pex result: from %s peers got %s new peers." % (done, total_added))
        finally:
            if len(peers) > 0:
                self.updateWebsocket(pex="announced")

    def updateWebsocket(self, **kwargs):
        if kwargs:
            param = {"event": list(kwargs.items())[0]}
        else:
            param = None

        for ws in self.site.websockets:
            ws.event("announcerChanged", self.site, param)

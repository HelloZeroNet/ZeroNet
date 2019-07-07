import random
import time
import hashlib
import re
import collections

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
            for ip_type, opened in list(self.site.connection_server.port_opened.items()):
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
            self.site.log.warning("Tracker %s error: Invalid address" % tracker)
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
        except Exception as err:
            self.site.log.warning("Tracker %s announce failed: %s in mode %s" % (tracker, Debug.formatException(err), mode))
            error = err

        if error:
            self.stats[tracker]["status"] = "error"
            self.stats[tracker]["time_status"] = time.time()
            self.stats[tracker]["last_error"] = str(error)
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

    @util.Noparallel(blocking=False)
    def announcePex(self, query_num=2, need_num=5):
        peers = self.site.getConnectedPeers()
        if len(peers) == 0:  # Wait 3s for connections
            time.sleep(3)
            peers = self.site.getConnectedPeers()

        if len(peers) == 0:  # Small number of connected peers for this site, connect to any
            peers = list(self.site.peers.values())
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
            param = {"event": list(kwargs.items())[0]}
        else:
            param = None

        for ws in self.site.websockets:
            ws.event("announcerChanged", self.site, param)

import random
import time
import os
import logging
import json
import atexit
import re

import gevent

from Config import config
from Plugin import PluginManager
from util import helper


class TrackerStorage(object):
    def __init__(self):
        self.site_announcer = None
        self.log = logging.getLogger("TrackerStorage")

        self.working_tracker_time_interval = 60 * 60
        self.tracker_down_time_interval = 60 * 60
        self.tracker_discover_time_interval = 5 * 60

        self.working_shared_trackers_limit_per_protocol = {}
        self.working_shared_trackers_limit_per_protocol["other"] = 2

        self.file_path = "%s/trackers.json" % config.data_dir
        self.load()
        self.time_discover = 0.0
        self.time_success = 0.0
        atexit.register(self.save)

    def initTrackerLimitForProtocol(self):
        for s in re.split("[,;]", config.working_shared_trackers_limit_per_protocol):
            x = s.split("=", 1)
            if len(x) == 1:
                x = ["other", x[0]]
            try:
                self.working_shared_trackers_limit_per_protocol[x[0]] = int(x[1])
            except ValueError:
                pass
        self.log.debug("Limits per protocol: %s" % self.working_shared_trackers_limit_per_protocol)

    def getTrackerLimitForProtocol(self, protocol):
        l = self.working_shared_trackers_limit_per_protocol
        return l.get(protocol, l.get("other"))

    def setSiteAnnouncer(self, site_announcer):
        if self.site_announcer:
            return
        self.site_announcer = site_announcer
        self.initTrackerLimitForProtocol()
        self.recheckValidTrackers()

    def isTrackerAddressValid(self, tracker_address):
        if not self.site_announcer: # Not completely initialized, skip check
            return True

        address_parts = self.site_announcer.getAddressParts(tracker_address)
        if not address_parts:
            self.log.debug("Invalid tracker address: %s" % tracker_address)
            return False

        handler = self.site_announcer.getTrackerHandler(address_parts["protocol"])
        if not handler:
            self.log.debug("Invalid tracker address: Unknown protocol %s: %s" % (address_parts["protocol"], tracker_address))
            return False

        return True

    def recheckValidTrackers(self):
        trackers = self.getTrackers()
        for address, tracker in list(trackers.items()):
            if not self.isTrackerAddressValid(address):
                del trackers[address]

    def getNormalizedTrackerProtocol(self, tracker_address):
        if not self.site_announcer:
            return None

        address_parts = self.site_announcer.getAddressParts(tracker_address)
        if not address_parts:
            return None

        protocol = address_parts["protocol"]
        if protocol == "https":
            protocol = "http"

        return protocol

    def getSupportedProtocols(self):
        if not self.site_announcer:
            return None

        supported_trackers = self.site_announcer.getSupportedTrackers()

        # If a tracker is in our list, but is absent from the results of getSupportedTrackers(),
        # it seems to be supported by software, but forbidden by the settings or network configuration.
        # We check and remove thoose trackers here, since onTrackerError() is never emitted for them.
        trackers = self.getTrackers()
        for tracker_address, tracker in list(trackers.items()):
            t = max(trackers[tracker_address]["time_added"],
                    trackers[tracker_address]["time_success"])
            if tracker_address not in supported_trackers and t < time.time() - self.tracker_down_time_interval:
                self.log.debug("Tracker %s looks unused, removing." % tracker_address)
                del trackers[tracker_address]

        protocols = set()
        for tracker_address in supported_trackers:
            protocol = self.getNormalizedTrackerProtocol(tracker_address)
            if not protocol:
                continue
            protocols.add(protocol)

        protocols = list(protocols)

        self.log.debug("Supported tracker protocols: %s" % protocols)

        return protocols

    def getDefaultFile(self):
        return {"shared": {}}

    def onTrackerFound(self, tracker_address, type="shared", my=False):
        if not self.isTrackerAddressValid(tracker_address):
            return False

        trackers = self.getTrackers(type)
        added = False
        if tracker_address not in trackers:
            trackers[tracker_address] = {
                "time_added": time.time(),
                "time_success": 0,
                "latency": 99.0,
                "num_error": 0,
                "my": False
            }
            self.log.debug("New tracker found: %s" % tracker_address)
            added = True

        trackers[tracker_address]["time_found"] = time.time()
        trackers[tracker_address]["my"] = my
        return added

    def onTrackerSuccess(self, tracker_address, latency):
        trackers = self.getTrackers()
        if tracker_address not in trackers:
            return False

        trackers[tracker_address]["latency"] = latency
        trackers[tracker_address]["time_success"] = time.time()
        trackers[tracker_address]["num_error"] = 0

        self.time_success = time.time()

    def onTrackerError(self, tracker_address):
        trackers = self.getTrackers()
        if tracker_address not in trackers:
            return False

        trackers[tracker_address]["time_error"] = time.time()
        trackers[tracker_address]["num_error"] += 1

        if self.time_success < time.time() - self.tracker_down_time_interval / 2:
            # Don't drop trackers from the list, if there haven't been any successful announces recently.
            # There may be network connectivity issues.
            return

        protocol = self.getNormalizedTrackerProtocol(tracker_address) or ""

        nr_working_trackers_for_protocol = len(self.getTrackersPerProtocol(working_only=True).get(protocol, []))
        nr_working_trackers = len(self.getWorkingTrackers())

        error_limit = 30
        if nr_working_trackers_for_protocol >= self.getTrackerLimitForProtocol(protocol):
            error_limit = 10
            if nr_working_trackers >= config.working_shared_trackers_limit:
                error_limit = 5

        if trackers[tracker_address]["num_error"] > error_limit and trackers[tracker_address]["time_success"] < time.time() - self.tracker_down_time_interval:
            self.log.debug("Tracker %s looks down, removing." % tracker_address)
            del trackers[tracker_address]

    def isTrackerWorking(self, tracker_address, type="shared"):
        trackers = self.getTrackers(type)
        tracker = trackers[tracker_address]
        if not tracker:
            return False

        if tracker["time_success"] > time.time() - self.working_tracker_time_interval:
            return True

        return False

    def getTrackers(self, type="shared"):
        return self.file_content.setdefault(type, {})

    def getTrackersPerProtocol(self, type="shared", working_only=False):
        if not self.site_announcer:
            return None

        trackers = self.getTrackers(type)

        trackers_per_protocol = {}
        for tracker_address in trackers:
            protocol = self.getNormalizedTrackerProtocol(tracker_address)
            if not protocol:
                continue
            if not working_only or self.isTrackerWorking(tracker_address, type=type):
                trackers_per_protocol.setdefault(protocol, []).append(tracker_address)

        return trackers_per_protocol

    def getWorkingTrackers(self, type="shared"):
        trackers = {
            key: tracker for key, tracker in self.getTrackers(type).items()
            if self.isTrackerWorking(key, type)
        }
        return trackers

    def getFileContent(self):
        if not os.path.isfile(self.file_path):
            open(self.file_path, "w").write("{}")
            return self.getDefaultFile()
        try:
            return json.load(open(self.file_path))
        except Exception as err:
            self.log.error("Error loading trackers list: %s" % err)
            return self.getDefaultFile()

    def load(self):
        self.file_content = self.getFileContent()

        trackers = self.getTrackers()
        self.log.debug("Loaded %s shared trackers" % len(trackers))
        for address, tracker in list(trackers.items()):
            tracker["num_error"] = 0
        self.recheckValidTrackers()

    def save(self):
        s = time.time()
        helper.atomicWrite(self.file_path, json.dumps(self.file_content, indent=2, sort_keys=True).encode("utf8"))
        self.log.debug("Saved in %.3fs" % (time.time() - s))

    def enoughWorkingTrackers(self, type="shared"):
        supported_protocols = self.getSupportedProtocols()
        if not supported_protocols:
            return False

        trackers_per_protocol = self.getTrackersPerProtocol(type="shared", working_only=True)
        if not trackers_per_protocol:
            return False

        total_nr = 0

        for protocol in supported_protocols:
            trackers = trackers_per_protocol.get(protocol, [])
            if len(trackers) < self.getTrackerLimitForProtocol(protocol):
                self.log.debug("Not enough working trackers for protocol %s: %s < %s" % (
                    protocol, len(trackers), self.getTrackerLimitForProtocol(protocol)))
                return False
            total_nr += len(trackers)

        if total_nr < config.working_shared_trackers_limit:
            self.log.debug("Not enough working trackers: %s < %s" % (
                total_nr, config.working_shared_trackers_limit))
            return False

        return True

    def discoverTrackers(self, peers):
        if self.enoughWorkingTrackers(type="shared"):
            return False

        self.log.debug("Discovering trackers from %s peers..." % len(peers))

        s = time.time()
        num_success = 0
        for peer in peers:
            if peer.connection and peer.connection.handshake.get("rev", 0) < 3560:
                continue  # Not supported

            res = peer.request("getTrackers")
            if not res or "error" in res:
                continue

            num_success += 1

            random.shuffle(res["trackers"])
            for tracker_address in res["trackers"]:
                if type(tracker_address) is bytes:  # Backward compatibilitys
                    tracker_address = tracker_address.decode("utf8")
                added = self.onTrackerFound(tracker_address)
                if added:  # Only add one tracker from one source
                    break

        if not num_success and len(peers) < 20:
            self.time_discover = 0.0

        if num_success:
            self.save()

        self.log.debug("Trackers discovered from %s/%s peers in %.3fs" % (num_success, len(peers), time.time() - s))


if "tracker_storage" not in locals():
    tracker_storage = TrackerStorage()


@PluginManager.registerTo("SiteAnnouncer")
class SiteAnnouncerPlugin(object):
    def getTrackers(self):
        tracker_storage.setSiteAnnouncer(self)
        if tracker_storage.time_discover < time.time() - tracker_storage.tracker_discover_time_interval:
            tracker_storage.time_discover = time.time()
            gevent.spawn(tracker_storage.discoverTrackers, self.site.getConnectedPeers())
        trackers = super(SiteAnnouncerPlugin, self).getTrackers()
        shared_trackers = list(tracker_storage.getTrackers("shared").keys())
        if shared_trackers:
            return trackers + shared_trackers
        else:
            return trackers

    def announceTracker(self, tracker, *args, **kwargs):
        tracker_storage.setSiteAnnouncer(self)
        res = super(SiteAnnouncerPlugin, self).announceTracker(tracker, *args, **kwargs)
        if res:
            latency = res
            tracker_storage.onTrackerSuccess(tracker, latency)
        elif res is False:
            tracker_storage.onTrackerError(tracker)

        return res


@PluginManager.registerTo("FileRequest")
class FileRequestPlugin(object):
    def actionGetTrackers(self, params):
        shared_trackers = list(tracker_storage.getWorkingTrackers("shared").keys())
        random.shuffle(shared_trackers)
        self.response({"trackers": shared_trackers})


@PluginManager.registerTo("FileServer")
class FileServerPlugin(object):
    def portCheck(self, *args, **kwargs):
        res = super(FileServerPlugin, self).portCheck(*args, **kwargs)
        if res and not config.tor == "always" and "Bootstrapper" in PluginManager.plugin_manager.plugin_names:
            for ip in self.ip_external_list:
                my_tracker_address = "zero://%s:%s" % (ip, config.fileserver_port)
                tracker_storage.onTrackerFound(my_tracker_address, my=True)
        return res


@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("AnnounceShare plugin")
        group.add_argument('--working_shared_trackers_limit', help='Stop discovering new shared trackers after this number of shared trackers reached (total)', default=10, type=int, metavar='limit')
        group.add_argument('--working_shared_trackers_limit_per_protocol', help='Stop discovering new shared trackers after this number of shared trackers reached per each supported protocol', default="zero=5,other=2", metavar='limit')

        return super(ConfigPlugin, self).createArguments()

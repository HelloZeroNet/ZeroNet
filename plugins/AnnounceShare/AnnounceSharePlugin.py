import time
import os
import logging
import json
import atexit

import gevent

from Config import config
from Plugin import PluginManager
from util import helper


class TrackerStorage(object):
    def __init__(self):
        self.log = logging.getLogger("TrackerStorage")
        self.file_path = "%s/trackers.json" % config.data_dir
        self.load()
        self.time_discover = 0.0
        atexit.register(self.save)

    def getDefaultFile(self):
        return {"shared": {}}

    def onTrackerFound(self, tracker_address, type="shared", my=False):
        if not tracker_address.startswith("zero://"):
            return False

        trackers = self.getTrackers()
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

    def onTrackerError(self, tracker_address):
        trackers = self.getTrackers()
        if tracker_address not in trackers:
            return False

        trackers[tracker_address]["time_error"] = time.time()
        trackers[tracker_address]["num_error"] += 1

        if len(self.getWorkingTrackers()) >= config.working_shared_trackers_limit:
            error_limit = 5
        else:
            error_limit = 30
        error_limit

        if trackers[tracker_address]["num_error"] > error_limit and trackers[tracker_address]["time_success"] < time.time() - 60 * 60:
            self.log.debug("Tracker %s looks down, removing." % tracker_address)
            del trackers[tracker_address]

    def getTrackers(self, type="shared"):
        return self.file_content.setdefault(type, {})

    def getWorkingTrackers(self, type="shared"):
        trackers = {
            key: tracker for key, tracker in self.getTrackers(type).items()
            if tracker["time_success"] > time.time() - 60 * 60
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
            if not address.startswith("zero://"):
                del trackers[address]

    def save(self):
        s = time.time()
        helper.atomicWrite(self.file_path, json.dumps(self.file_content, indent=2, sort_keys=True).encode("utf8"))
        self.log.debug("Saved in %.3fs" % (time.time() - s))

    def discoverTrackers(self, peers):
        if len(self.getWorkingTrackers()) > config.working_shared_trackers_limit:
            return False
        s = time.time()
        num_success = 0
        for peer in peers:
            if peer.connection and peer.connection.handshake.get("rev", 0) < 3560:
                continue  # Not supported

            res = peer.request("getTrackers")
            if not res or "error" in res:
                continue

            num_success += 1
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
        if tracker_storage.time_discover < time.time() - 5 * 60:
            tracker_storage.time_discover = time.time()
            gevent.spawn(tracker_storage.discoverTrackers, self.site.getConnectedPeers())
        trackers = super(SiteAnnouncerPlugin, self).getTrackers()
        shared_trackers = list(tracker_storage.getTrackers("shared").keys())
        if shared_trackers:
            return trackers + shared_trackers
        else:
            return trackers

    def announceTracker(self, tracker, *args, **kwargs):
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
        group.add_argument('--working_shared_trackers_limit', help='Stop discovering new shared trackers after this number of shared trackers reached', default=5, type=int, metavar='limit')

        return super(ConfigPlugin, self).createArguments()

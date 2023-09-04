import time
import os
import logging
import json
import atexit
import re

import gevent

from Config import config
from Debug import Debug
from Plugin import PluginManager
from util import helper

class TrackerList(object):
    def __init__(self):
        self.log = logging.getLogger("TrackerList")
        self.tracker_storage = None
        self.last_rescan_time = 0.0
        self.last_rescan_failed = False

    def parse_list(self, data):
        for line in data.splitlines():
            line = line.strip()

            if not line:
                continue

            if re.match("^udp://", line):
                line = re.sub("/announce$", "", line)

            if self.tracker_storage.onTrackerFound(line):
                self.log.info("Added tracker: %s" % line)

    def do_rescan(self):
        url = config.tracker_list_url
        response = None

        self.log.info("Rescanning: %s" % url)

        try:
            # FIXME: add support of reading from ZeroNet URLs
            if re.match("^http(s)?://", url):
                req = helper.httpRequest(url)
                response = req.read().decode("utf8")
                req.close()
                req = None
            else:
                response = open(url, 'r').read().decode("utf8")
        except Exception as err:
            self.log.error("Error reading %s: %s" % (url, err))
            self.last_rescan_failed = True

        if response:
            self.parse_list(response);
            self.last_rescan_failed = False

    def reload(self):
        rescan_interval = config.tracker_list_rescan_interval
        if self.last_rescan_failed:
            rescan_interval = rescan_interval / 2

        if self.last_rescan_time > time.time() - rescan_interval:
            return

        self.last_rescan_time = time.time()

        if "tracker_storage" not in locals():
            try:
                if "TrackerShare" in PluginManager.plugin_manager.plugin_names:
                    from TrackerShare.TrackerSharePlugin import tracker_storage
                    self.tracker_storage = tracker_storage
                elif "AnnounceShare" in PluginManager.plugin_manager.plugin_names:
                    from AnnounceShare.AnnounceSharePlugin import tracker_storage
                    self.tracker_storage = tracker_storage
            except Exception as err:
                self.log.error("%s" % Debug.formatException(err))

        if self.tracker_storage:
            gevent.spawn(self.do_rescan)


if "tracker_list" not in locals():
    tracker_list = TrackerList()


@PluginManager.registerTo("SiteAnnouncer")
class SiteAnnouncerPlugin(object):
    def announceTracker(self, tracker, *args, **kwargs):
        tracker_list.reload()
        return super(SiteAnnouncerPlugin, self).announceTracker(tracker, *args, **kwargs)


@PluginManager.registerTo("FileServer")
class FileServerPlugin(object):
    def portCheck(self, *args, **kwargs):
        res = super(FileServerPlugin, self).portCheck(*args, **kwargs)
        tracker_list.reload()
        return res


@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("TrackerList plugin")
        group.add_argument('--tracker_list_url', help='URL of local file path, where the list of additional trackers is located', default='https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all_ip.txt', metavar='url')
        group.add_argument('--tracker_list_rescan_interval', help='Interval in seconds between rescans of the list of additional trackers', default=60 * 60, type=int, metavar='interval')

        return super(ConfigPlugin, self).createArguments()

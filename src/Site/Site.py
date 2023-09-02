import os
import json
import logging
import re
import time
import random
import sys
import hashlib
import itertools
import collections
import base64

import gevent
import gevent.pool
import gevent.lock

import util
from Config import config
from Peer import Peer
from Worker import WorkerManager
from Debug import Debug
from Content import ContentManager
from .SiteStorage import SiteStorage
from Crypt import CryptHash
from util import helper
from util import Diff
from util import GreenletManager
from Plugin import PluginManager
from File import FileServer
from .SiteAnnouncer import SiteAnnouncer
from . import SiteManager
from . import SiteHelpers

def lerp(val_min, val_max, scale):
    return scale * (val_max - val_min) + val_min

class ScaledTimeoutHandler:
    def __init__(self, val_min, val_max, handler=None, scaler=None):
        self.val_min = val_min
        self.val_max = val_max
        self.timestamp = 0
        self.handler = handler
        self.scaler = scaler
        self.log = logging.getLogger("ScaledTimeoutHandler")

    def isExpired(self, scale):
        interval = lerp(self.val_min, self.val_max, scale)
        expired_at = self.timestamp + interval
        now = time.time()
        expired = (now > expired_at)
        if expired:
            self.log.debug(
                "Expired: [%d..%d]: scale=%f, interval=%f",
                self.val_min, self.val_max, scale, interval)
        return expired

    def done(self):
        self.timestamp = time.time()

    def run(self, *args, **kwargs):
        do_run = kwargs["force"] or self.isExpired(self.scaler())
        if do_run:
            result = self.handler(*args, **kwargs)
            if result:
                self.done()
            return result
        else:
            return None

class BackgroundPublisher:
    def __init__(self, site, published=[], limit=5, inner_path="content.json", diffs={}):
        self.site = site
        self.threads = gevent.pool.Pool(None)
        self.inner_path = inner_path
        self.stages = [
            {
                "interval": ScaledTimeoutHandler(60, 60),
                "max_tries": 2,
                "tries": 0,
                "limit": 0,
                "done": False
            },
            {
                "interval": ScaledTimeoutHandler(60 * 10, 60 * 10),
                "max_tries": 5,
                "tries": 0,
                "limit": 0,
                "done": False
            }
        ]
        self.reinit(published=published, limit=limit, diffs=diffs)

    def reinit(self, published=[], limit=5, diffs={}):
        self.threads.kill()
        self.published = published
        self.diffs = diffs

        i = 0
        for stage in self.stages:
            stage["nr"] = i
            stage["limit"] = limit * (2 + i)
            stage["tries"] = 0
            stage["done"] = False
            stage["thread"] = None
            if i > 0:
                stage["interval"].done()
            i += 1

    def isStageComplete(self, stage):
        if not stage["done"]:
            stage["done"] = len(self.published) >= stage["limit"]
        if not stage["done"]:
            stage["done"] =  stage["tries"] >= stage["max_tries"]
        return stage["done"]

    def isComplete(self):
        for stage in self.stages:
            if not self.isStageComplete(stage):
                return False
        return True

    def process(self):
        for stage in self.stages:
            if not self.isStageComplete(stage):
                self.processStage(stage)
                break
        return self.isComplete()

    def processStage(self, stage):
        if not stage["interval"].isExpired(0):
            return

        if len(self.site.peers) < stage["limit"]:
            self.site.announce(mode="more")

        if not stage["thread"]:
            peers = list(self.site.peers.values())
            random.shuffle(peers)
            stage["thread"] = self.threads.spawn(self.site.publisher,
                self.inner_path, peers, self.published, stage["limit"], diffs=self.diffs, max_retries=1)

        stage["tries"] += 1
        stage["interval"].done()

        self.site.log.info("Background publisher: Stage #%s: %s published to %s/%s peers",
            stage["nr"], self.inner_path, len(self.published), stage["limit"])

    def finalize(self):
        self.threads.kill()
        self.site.log.info("Background publisher: Published %s to %s peers", self.inner_path, len(self.published))


@PluginManager.acceptPlugins
class Site(object):

    def __init__(self, address, allow_create=True, settings=None):
        self.address = str(re.sub("[^A-Za-z0-9]", "", address))  # Make sure its correct address
        self.address_hash = hashlib.sha256(self.address.encode("ascii")).digest()
        self.address_sha1 = hashlib.sha1(self.address.encode("ascii")).digest()
        self.address_short = "%s..%s" % (self.address[:6], self.address[-4:])  # Short address for logging
        self.log = logging.getLogger("Site:%s" % self.address_short)
        self.addEventListeners()

        self.periodic_maintenance_handlers = [
            ScaledTimeoutHandler(
                config.site_announce_interval_max * 60,
                config.site_announce_interval_min * 60,
                handler=self.periodicMaintenanceHandler_announce,
                scaler=self.getAnnounceRating),
            ScaledTimeoutHandler(
                config.site_peer_check_interval_max * 60,
                config.site_peer_check_interval_min * 60,
                handler=self.periodicMaintenanceHandler_peer_check,
                scaler=self.getAnnounceRating),
            ScaledTimeoutHandler(
                config.site_update_check_interval_max * 60,
                config.site_update_check_interval_min * 60,
                handler=self.periodicMaintenanceHandler_general,
                scaler=self.getActivityRating)
        ]

        self.background_publishers = {}
        self.background_publishers_lock = gevent.lock.RLock()

        # FZS = forced zero "since"
        self.fzs_range = 20
        self.fzs_interval = 30 * 60
        self.fzs_count = random.randint(0, self.fzs_range / 4)
        self.fzs_timestamp = 0

        ##############################################
        self.connection_server = None
        if "main" in sys.modules:  # import main has side-effects, breaks tests
            import main
            if "file_server" in dir(main):  # Use global file server by default if possible
                self.connection_server = main.file_server
            else:
                main.file_server = FileServer()
                self.connection_server = main.file_server
        else:
            self.connection_server = FileServer()
        ##############################################

        self.content = None  # Load content.json
        self.peers = {}  # Key: ip:port, Value: Peer.Peer
        self.peers_recent = collections.deque(maxlen=150)
        self.peer_blacklist = SiteManager.peer_blacklist  # Ignore this peers (eg. myself)
        self.greenlet_manager = GreenletManager.GreenletManager(self.connection_server.site_pool)  # Running greenlets
        self.worker_manager = WorkerManager(self)  # Handle site download from other peers
        self.bad_files = {}  # SHA check failed files, need to redownload {"inner.content": 1} (key: file, value: failed accept)
        self.content_updated = None  # Content.js update time
        self.last_online_update = 0
        self.startup_announce_done = 0
        self.notifications = []  # Pending notifications displayed once on page load [error|ok|info, message, timeout]
        self.page_requested = False  # Page viewed in browser
        self.websockets = []  # Active site websocket connections

        self.loadSettings(settings)  # Load settings from sites.json
        self.storage = SiteStorage(self, allow_create=allow_create)  # Save and load site files
        self.content_manager = ContentManager(self)
        self.content_manager.loadContents()  # Load content.json files

        self.announcer = SiteAnnouncer(self)  # Announce and get peer list from other nodes

        self.peer_connector = SiteHelpers.PeerConnector(self) # Connect more peers in background by request
        self.persistent_peer_req = None # The persistent peer requirement, managed by maintenance handler

        if not self.settings.get("wrapper_key"):  # To auth websocket permissions
            self.settings["wrapper_key"] = CryptHash.random()
            self.log.debug("New wrapper key: %s" % self.settings["wrapper_key"])

        if not self.settings.get("ajax_key"):  # To auth websocket permissions
            self.settings["ajax_key"] = CryptHash.random()
            self.log.debug("New ajax key: %s" % self.settings["ajax_key"])

    def __str__(self):
        return "Site %s" % self.address_short

    def __repr__(self):
        return "<%s>" % self.__str__()

    # Load site settings from data/sites.json
    def loadSettings(self, settings=None):
        if not settings:
            settings = json.load(open("%s/sites.json" % config.data_dir)).get(self.address)
        if settings:
            self.settings = settings
            if "check_files_timestamp" not in settings:
                settings["check_files_timestamp"] = 0
            if "verify_files_timestamp" not in settings:
                settings["verify_files_timestamp"] = 0
            if "cache" not in settings:
                settings["cache"] = {}
            if "size_files_optional" not in settings:
                settings["size_optional"] = 0
            if "optional_downloaded" not in settings:
                settings["optional_downloaded"] = 0
            if "downloaded" not in settings:
                settings["downloaded"] = settings.get("added")
            self.bad_files = settings["cache"].get("bad_files", {})
            settings["cache"]["bad_files"] = {}
            # Give it minimum 10 tries after restart
            for inner_path in self.bad_files:
                self.bad_files[inner_path] = min(self.bad_files[inner_path], 20)
        else:
            self.settings = {
                "check_files_timestamp": 0,
                "verify_files_timestamp": 0,
                "own": False,
                "serving": True,
                "permissions": [],
                "cache": {"bad_files": {}},
                "size_files_optional": 0,
                "added": int(time.time()),
                "downloaded": None,
                "optional_downloaded": 0,
                "size_optional": 0
            }  # Default
            if config.download_optional == "auto":
                self.settings["autodownloadoptional"] = True

        # Add admin permissions to homepage
        if self.address in (config.homepage, config.updatesite) and "ADMIN" not in self.settings["permissions"]:
            self.settings["permissions"].append("ADMIN")

        return

    # Save site settings to data/sites.json
    def saveSettings(self):
        if not SiteManager.site_manager.sites:
            SiteManager.site_manager.sites = {}
        if not SiteManager.site_manager.sites.get(self.address):
            SiteManager.site_manager.sites[self.address] = self
            SiteManager.site_manager.load(False)
        SiteManager.site_manager.saveDelayed()

    # Returns True if any site-related activity should be interrupted
    # due to connection server being stopped or site being deleted
    def isStopping(self):
        return self.connection_server.stopping or self.settings.get("deleting", False)

    # Returns False if any network activity for the site should not happen
    def isServing(self):
        if self.connection_server.isOfflineMode():
            return False
        elif self.isStopping():
            return False
        else:
            return self.settings["serving"]

    # Spawns a thread that will be waited for on server being stopped (and killed after a timeout).
    # Short cut to self.greenlet_manager.spawn()
    def spawn(self, *args, **kwargs):
        thread = self.greenlet_manager.spawn(*args, **kwargs)
        return thread

    # Spawns a thread that will be waited for on server being stopped (and killed after a timeout).
    # Short cut to self.greenlet_manager.spawnLater()
    def spawnLater(self, *args, **kwargs):
        thread = self.greenlet_manager.spawnLater(*args, **kwargs)
        return thread

    def checkSendBackLRU(self, peer, inner_path, remote_modified):
        return SiteManager.site_manager.checkSendBackLRU(self, peer, inner_path, remote_modified)

    def addToSendBackLRU(self, peer, inner_path, modified):
        return SiteManager.site_manager.addToSendBackLRU(self, peer, inner_path, modified)

    def getSettingsCache(self):
        back = {}
        back["bad_files"] = self.bad_files
        back["hashfield"] = base64.b64encode(self.content_manager.hashfield.tobytes()).decode("ascii")
        return back

    # Max site size in MB
    def getSizeLimit(self):
        return self.settings.get("size_limit", int(config.size_limit))

    def isFileVerificationExpired(self, check_files_interval, verify_files_interval):
        now = time.time()
        check_files_timestamp = self.settings.get("check_files_timestamp", 0)
        verify_files_timestamp = self.settings.get("verify_files_timestamp", 0)

        if check_files_interval is None:
            check_files_expiration = now + 1
        else:
            check_files_expiration = check_files_timestamp + check_files_interval

        if verify_files_interval is None:
            verify_files_expiration = now + 1
        else:
            verify_files_expiration = verify_files_timestamp + verify_files_interval

        if verify_files_expiration < now:
            return "verify"

        if check_files_expiration < now:
            return "check"

        return False

    # Next size limit based on current size
    def getNextSizeLimit(self):
        size_limits = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000]
        size = self.settings.get("size", 0)
        for size_limit in size_limits:
            if size * 1.2 < size_limit * 1024 * 1024:
                return size_limit
        return 999999

    def isAddedRecently(self):
        return time.time() - self.settings.get("added", 0) < 60 * 60 * 24

    # Download all files from content.json
    def downloadContent(self, inner_path, download_files=True, peer=None, check_modifications=False, diffs={}):
        s = time.time()
        if config.verbose:
            self.log.debug(
                "DownloadContent %s: Started. (download_files: %s, check_modifications: %s, diffs: %s)..." %
                (inner_path, download_files, check_modifications, diffs.keys())
            )

        if not inner_path.endswith("content.json"):
            return False

        found = self.needFile(inner_path, update=self.bad_files.get(inner_path))
        content_inner_dir = helper.getDirname(inner_path)
        if not found:
            self.log.debug("DownloadContent %s: Download failed, check_modifications: %s" % (inner_path, check_modifications))
            if check_modifications:  # Download failed, but check modifications if its succed later
                self.onFileDone.once(lambda file_name: self.checkModifications(0), "check_modifications")
            return False  # Could not download content.json

        if config.verbose:
            self.log.debug("DownloadContent got %s" % inner_path)
            sub_s = time.time()

        changed, deleted = self.content_manager.loadContent(inner_path, load_includes=False)

        if config.verbose:
            self.log.debug("DownloadContent %s: loadContent done in %.3fs" % (inner_path, time.time() - sub_s))

        if inner_path == "content.json":
            self.saveSettings()

        if peer:  # Update last received update from peer to prevent re-sending the same update to it
            peer.last_content_json_update = self.content_manager.contents[inner_path]["modified"]

        # Verify size limit
        if inner_path == "content.json":
            site_size_limit = self.getSizeLimit() * 1024 * 1024
            content_size = len(json.dumps(self.content_manager.contents[inner_path], indent=1)) + sum([file["size"] for file in list(self.content_manager.contents[inner_path].get("files", {}).values()) if file["size"] >= 0])  # Size of new content
            if site_size_limit < content_size:
                # Not enought don't download anything
                self.log.debug("DownloadContent Size limit reached (site too big please increase limit): %.2f MB > %.2f MB" % (content_size / 1024 / 1024, site_size_limit / 1024 / 1024))
                return False

        # Start download files
        file_threads = []
        if download_files:
            for file_relative_path in list(self.content_manager.contents[inner_path].get("files", {}).keys()):
                file_inner_path = content_inner_dir + file_relative_path

                # Try to diff first
                diff_success = False
                diff_actions = diffs.get(file_relative_path)
                if diff_actions and self.bad_files.get(file_inner_path):
                    try:
                        s = time.time()
                        new_file = Diff.patch(self.storage.open(file_inner_path, "rb"), diff_actions)
                        new_file.seek(0)
                        time_diff = time.time() - s

                        s = time.time()
                        diff_success = self.content_manager.verifyFile(file_inner_path, new_file)
                        time_verify = time.time() - s

                        if diff_success:
                            s = time.time()
                            new_file.seek(0)
                            self.storage.write(file_inner_path, new_file)
                            time_write = time.time() - s

                            s = time.time()
                            self.onFileDone(file_inner_path)
                            time_on_done = time.time() - s

                            self.log.debug(
                                "DownloadContent Patched successfully: %s (diff: %.3fs, verify: %.3fs, write: %.3fs, on_done: %.3fs)" %
                                (file_inner_path, time_diff, time_verify, time_write, time_on_done)
                            )
                    except Exception as err:
                        self.log.debug("DownloadContent Failed to patch %s: %s" % (file_inner_path, err))
                        diff_success = False

                if not diff_success:
                    # Start download and dont wait for finish, return the event
                    res = self.needFile(file_inner_path, blocking=False, update=self.bad_files.get(file_inner_path), peer=peer)
                    if res is not True and res is not False:  # Need downloading and file is allowed
                        file_threads.append(res)  # Append evt

            # Optionals files
            if inner_path == "content.json":
                self.spawn(self.updateHashfield)

            for file_relative_path in list(self.content_manager.contents[inner_path].get("files_optional", {}).keys()):
                file_inner_path = content_inner_dir + file_relative_path
                if file_inner_path not in changed and not self.bad_files.get(file_inner_path):
                    continue
                if not self.isDownloadable(file_inner_path):
                    continue
                # Start download and dont wait for finish, return the event
                res = self.pooledNeedFile(
                    file_inner_path, blocking=False, update=self.bad_files.get(file_inner_path), peer=peer
                )
                if res is not True and res is not False:  # Need downloading and file is allowed
                    file_threads.append(res)  # Append evt

        # Wait for includes download
        include_threads = []
        for file_relative_path in list(self.content_manager.contents[inner_path].get("includes", {}).keys()):
            file_inner_path = content_inner_dir + file_relative_path
            include_thread = self.spawn(self.downloadContent, file_inner_path, download_files=download_files, peer=peer)
            include_threads.append(include_thread)

        if config.verbose:
            self.log.debug("DownloadContent %s: Downloading %s includes..." % (inner_path, len(include_threads)))
        gevent.joinall(include_threads)
        if config.verbose:
            self.log.debug("DownloadContent %s: Includes download ended" % inner_path)

        if check_modifications:  # Check if every file is up-to-date
            self.checkModifications(0)

        if config.verbose:
            self.log.debug("DownloadContent %s: Downloading %s files, changed: %s..." % (inner_path, len(file_threads), len(changed)))
        gevent.joinall(file_threads)
        if config.verbose:
            self.log.debug("DownloadContent %s: ended in %.3fs (tasks left: %s)" % (
                inner_path, time.time() - s, len(self.worker_manager.tasks)
            ))


        # If no file tasks have been started, worker_manager.checkComplete()
        # never called. So call it explicitly.
        self.greenlet_manager.spawn(self.worker_manager.checkComplete)

        return True

    # Return bad files with less than 3 retry
    def getReachableBadFiles(self):
        if not self.bad_files:
            return False
        return [bad_file for bad_file, retry in self.bad_files.items() if retry < 3]

    # Retry download bad files
    def retryBadFiles(self, force=False):
        self.checkBadFiles()

        self.log.debug("Retry %s bad files" % len(self.bad_files))
        content_inner_paths = []
        file_inner_paths = []

        for bad_file, tries in list(self.bad_files.items()):
            if force or random.randint(0, min(40, tries)) < 4:  # Larger number tries = less likely to check every 15min
                if bad_file.endswith("content.json"):
                    content_inner_paths.append(bad_file)
                else:
                    file_inner_paths.append(bad_file)

        if content_inner_paths:
            self.pooledDownloadContent(content_inner_paths, only_if_bad=True)

        if file_inner_paths:
            self.pooledDownloadFile(file_inner_paths, only_if_bad=True)

    def checkBadFiles(self):
        for bad_file in list(self.bad_files.keys()):
            file_info = self.content_manager.getFileInfo(bad_file)
            if bad_file.endswith("content.json"):
                if file_info is False and bad_file != "content.json":
                    del self.bad_files[bad_file]
                    self.log.debug("No info for file: %s, removing from bad_files" % bad_file)
            else:
                if file_info is False or not file_info.get("size"):
                    del self.bad_files[bad_file]
                    self.log.debug("No info or size for file: %s, removing from bad_files" % bad_file)

    # Download all files of the site
    @util.Noparallel(blocking=False)
    def download(self, check_size=False, blind_includes=False, retry_bad_files=True):
        if not self.connection_server:
            self.log.debug("No connection server found, skipping download")
            return False

        s = time.time()
        self.log.debug(
            "Start downloading, bad_files: %s, check_size: %s, blind_includes: %s, isAddedRecently: %s" %
            (self.bad_files, check_size, blind_includes, self.isAddedRecently())
        )

        if self.isAddedRecently():
            self.spawn(self.announce, mode="start", force=True)
        else:
            self.spawn(self.announce, mode="update")

        if check_size:  # Check the size first
            valid = self.downloadContent("content.json", download_files=False)  # Just download content.json files
            if not valid:
                return False  # Cant download content.jsons or size is not fits

        # Download everything
        valid = self.downloadContent("content.json", check_modifications=blind_includes)

        if retry_bad_files:
            self.onComplete.once(lambda: self.retryBadFiles(force=True))
        self.log.debug("Download done in %.3fs" % (time.time() - s))

        return valid

    def pooledDownloadContent(self, inner_paths, pool_size=100, only_if_bad=False):
        self.log.debug("New downloadContent pool: len: %s, only if bad: %s" % (len(inner_paths), only_if_bad))
        self.worker_manager.started_task_num += len(inner_paths)
        pool = gevent.pool.Pool(pool_size)
        num_skipped = 0
        site_size_limit = self.getSizeLimit() * 1024 * 1024
        for inner_path in inner_paths:
            if not only_if_bad or inner_path in self.bad_files:
                pool.spawn(self.downloadContent, inner_path)
            else:
                num_skipped += 1
            self.worker_manager.started_task_num -= 1
            if self.settings["size"] > site_size_limit * 0.95:
                self.log.warning("Site size limit almost reached, aborting downloadContent pool")
                for aborted_inner_path in inner_paths:
                    if aborted_inner_path in self.bad_files:
                        del self.bad_files[aborted_inner_path]
                self.worker_manager.removeSolvedFileTasks(mark_as_good=False)
                break
        pool.join()
        self.log.debug("Ended downloadContent pool len: %s, skipped: %s" % (len(inner_paths), num_skipped))

    def pooledDownloadFile(self, inner_paths, pool_size=100, only_if_bad=False):
        self.log.debug("New downloadFile pool: len: %s, only if bad: %s" % (len(inner_paths), only_if_bad))
        self.worker_manager.started_task_num += len(inner_paths)
        pool = gevent.pool.Pool(pool_size)
        num_skipped = 0
        for inner_path in inner_paths:
            if not only_if_bad or inner_path in self.bad_files:
                pool.spawn(self.needFile, inner_path, update=True)
            else:
                num_skipped += 1
            self.worker_manager.started_task_num -= 1
        self.log.debug("Ended downloadFile pool len: %s, skipped: %s" % (len(inner_paths), num_skipped))

    # Update worker, try to find client that supports listModifications command
    def updater(self, peers_try, queried, need_queries, since):
        threads = []
        while 1:
            if not peers_try or len(queried) >= need_queries:  # Stop after 3 successful query
                break
            peer = peers_try.pop(0)

            if peer in queried:
                continue

            if config.verbose:
                self.log.debug("CheckModifications: Trying to get updates from: %s Left: %s" % (peer, peers_try))

            res = None
            with gevent.Timeout(20, exception=False):
                res = peer.listModified(since)

            if not res or "modified_files" not in res:
                continue  # Failed query

            queried.append(peer)


            modified_contents = []
            send_back = []
            send_back_limit = config.send_back_limit
            send_back_skipped = 0
            peer_modified_files = res["modified_files"]
            my_modified_files = self.content_manager.listModified(since)

            inner_paths = itertools.chain(peer_modified_files.keys(), my_modified_files.keys())
            seen_inner_paths = {}
            for inner_path in inner_paths:  # Check if the peer has newer files than we have
                if seen_inner_paths.get(inner_path, False):
                    continue
                seen_inner_paths[inner_path] = True

                peer_modified = int(peer_modified_files.get(inner_path, 0))
                my_modified = int(my_modified_files.get(inner_path, 0))

                diff = peer_modified - my_modified
                if diff == 0:
                    continue
                has_newer = diff > 0
                has_older = diff < 0

                if inner_path not in self.bad_files and not self.content_manager.isArchived(inner_path, peer_modified):
                    if has_newer: # We don't have this file or we have older version
                        modified_contents.append(inner_path)
                        self.bad_files[inner_path] = self.bad_files.get(inner_path, 1)
                    if has_older: # The remote peer doesn't have this file or it has older version
                        if self.checkSendBackLRU(peer, inner_path, peer_modified):
                            send_back_skipped += 1
                        else:
                            send_back.append(inner_path)

            inner_paths = None
            seen_inner_paths = None

            if modified_contents:
                self.log.info("CheckModifications: %s new modified files from %s" % (len(modified_contents), peer))
                modified_contents.sort(key=lambda inner_path: 0 - peer_modified_files[inner_path])  # Download newest first
                for inner_path in modified_contents:
                    self.log.info("CheckModifications:     %s: %s > %s" % (
                        inner_path, peer_modified_files.get(inner_path, 0), my_modified_files.get(inner_path, 0)
                    ))
                t = self.spawn(self.pooledDownloadContent, modified_contents, only_if_bad=True)
                threads.append(t)

            if send_back:
                self.log.info("CheckModifications: %s has older versions of %s files" % (peer, len(send_back)))
                if len(send_back) > send_back_limit:
                    self.log.info("CheckModifications: choosing %s random files to publish back" % (send_back_limit))
                    random.shuffle(send_back)
                    send_back = send_back[0:send_back_limit]
                for inner_path in send_back:
                    self.log.info("CheckModifications:     %s: %s < %s" % (
                        inner_path, peer_modified_files.get(inner_path, 0), my_modified_files.get(inner_path, 0)
                    ))
                    self.spawn(self.publisher, inner_path, [peer], [], 1, save_to_send_back_lru=True)

            if send_back_skipped:
                self.log.info("CheckModifications: %s has older versions of %s files, skipped according to send back LRU" % (peer, send_back_skipped))

        self.log.debug("CheckModifications: Waiting for %s pooledDownloadContent" % len(threads))
        gevent.joinall(threads)

    # We need, with some rate, to perform the full check of modifications,
    # "since the beginning of time", instead of the partial one.
    def getForcedZeroSince(self):
        now = time.time()
        if self.fzs_timestamp + self.fzs_interval > now:
            return False
        self.fzs_count -= 1
        if self.fzs_count < 1:
            self.fzs_count = random.randint(0, self.fzs_range)
            self.fzs_timestamp = now
            return True
        return False

    # Check modified content.json files from peers and add modified files to bad_files
    # Return: Successfully queried peers [Peer, Peer...]
    def checkModifications(self, since=None):
        s = time.time()
        peers_try = []  # Try these peers
        queried = []  # Successfully queried from these peers
        peer_limit = 10
        updater_limit = 3
        need_queries = 3

        # Wait for peers
        if not self.peers:
            self.announce(mode="update")
            for wait in range(10):
                time.sleep(5 + wait)
                self.log.debug("CheckModifications: Waiting for peers...")
                if self.peers:
                    break

        if since is None:
            if self.getForcedZeroSince():
                since = 0
            else:
                margin = 60 * 60 * 24
                since = self.settings.get("modified", margin) - margin

        if since == 0:
            peer_limit *= 4
            need_queries *= 4

        peers_try = self.getConnectedPeers() + self.getConnectablePeers(peer_limit)

        self.log.debug(
            "CheckModifications: Trying to get listModifications from %s peers, %s connected, since: %s" %
            (len(peers_try), len(self.getConnectedPeers()), since)
        )

        updaters = []
        for i in range(updater_limit):
            updaters.append(self.spawn(self.updater, peers_try, queried, need_queries, since))

        for r in range(10):
            gevent.joinall(updaters, timeout=5+r)
            if len(queried) >= need_queries or len(peers_try) == 0:
                break
            self.log.debug("CheckModifications: Waiting... (%s) succesfully queried: %s, left: %s" %
                (r + 1, len(queried), len(peers_try)))

        self.log.debug("CheckModifications: Queried listModifications from %s peers in %.3fs since %s" % (
            len(queried), time.time() - s, since))
        time.sleep(0.1)
        return queried

    def invalidateUpdateTime(self, invalid_interval):
        a, b = invalid_interval
        if b is None:
            b = time.time()
        if a is None:
            a = b
        if a <= self.last_online_update and self.last_online_update <= b:
            self.last_online_update = 0
            self.log.debug("Update time invalidated")

    def isUpdateTimeValid(self):
        if not self.last_online_update:
            return False
        expirationThreshold = 60 * 60 * 6
        return self.last_online_update > time.time() - expirationThreshold

    def refreshUpdateTime(self, valid=True):
        if valid:
            self.last_online_update = time.time()
        else:
            self.last_online_update = 0

    # Update content.json from peers and download changed files
    # Return: None
    @util.Noparallel()
    def update(self, announce=False, check_files=False, verify_files=False, since=None):
        online = self.connection_server.isInternetOnline()

        self.content_manager.loadContent("content.json", load_includes=False)  # Reload content.json
        self.content_updated = None  # Reset content updated time
        if verify_files:
            check_files = True

        if verify_files:
            self.updateWebsocket(verifying=True)
        elif check_files:
            self.updateWebsocket(checking=True)

        if check_files:
            if verify_files:
                self.storage.updateBadFiles(quick_check=False) # Full-featured checksum verification
            else:
                self.storage.updateBadFiles(quick_check=True) # Quick check and mark bad files based on file size
            # Don't update the timestamps in case of the application being shut down,
            # so we can make another try next time.
            if not self.isStopping():
                self.settings["check_files_timestamp"] = time.time()
                if verify_files:
                    self.settings["verify_files_timestamp"] = time.time()

        if verify_files:
            self.updateWebsocket(verified=True)
        elif check_files:
            self.updateWebsocket(checked=True)

        if not self.isServing():
            return False

        if announce:
            self.updateWebsocket(updating=True)
            self.announce(mode="update", force=True)

        reqs = [
            self.peer_connector.newReq(4, 4, 30),
            self.peer_connector.newReq(2, 2, 60),
            self.peer_connector.newReq(1, 1, 120)
        ]
        nr_connected_peers = self.waitForPeers(reqs);
        if nr_connected_peers < 1:
            return

        self.updateWebsocket(updating=True)

        # Remove files that no longer in content.json
        self.checkBadFiles()

        # Full update, we can reset bad files
        if check_files and since == 0:
            self.bad_files = {}

        queried = self.checkModifications(since)

        changed, deleted = self.content_manager.loadContent("content.json", load_includes=False)

        if self.bad_files:
            self.log.debug("Bad files: %s" % self.bad_files)
            self.spawn(self.retryBadFiles, force=True)

        if len(queried) == 0:
            # Failed to query modifications
            self.content_updated = False
        else:
            self.content_updated = time.time()

        self.sendMyHashfield()
        self.updateHashfield()

        online = online and self.connection_server.isInternetOnline()
        self.refreshUpdateTime(valid=online)

        self.updateWebsocket(updated=True)

    # To be called from FileServer
    @util.Noparallel(queue=True, ignore_args=True)
    def update2(self, check_files=False, verify_files=False):
        self.update(check_files=check_files, verify_files=verify_files)

    # Update site by redownload all content.json
    def redownloadContents(self):
        # Download all content.json again
        content_threads = []
        for inner_path in list(self.content_manager.contents.keys()):
            content_threads.append(self.needFile(inner_path, update=True, blocking=False))

        self.log.debug("Waiting %s content.json to finish..." % len(content_threads))
        gevent.joinall(content_threads)

    # Publish worker
    def publisher(self, inner_path, peers, published, limit, diffs={}, event_done=None, cb_progress=None, max_retries=2, save_to_send_back_lru=False):
        file_size = self.storage.getSize(inner_path)
        content_json_modified = self.content_manager.contents[inner_path]["modified"]
        body = self.storage.read(inner_path)

        while 1:
            if not peers or len(published) >= limit:
                if event_done:
                    event_done.set(True)
                break  # All peers done, or published engouht
            peer = peers.pop()
            if peer in published:
                continue
            if peer.last_content_json_update == content_json_modified:
                self.log.debug("%s already received this update for %s, skipping" % (peer, inner_path))
                continue

            if peer.connection and peer.connection.last_ping_delay:  # Peer connected
                # Timeout: 5sec + size in kb + last_ping
                timeout = 5 + int(file_size / 1024) + peer.connection.last_ping_delay
            else:  # Peer not connected
                # Timeout: 10sec + size in kb
                timeout = 10 + int(file_size / 1024)
            result = {"exception": "Timeout"}

            for retry in range(max_retries):
                try:
                    with gevent.Timeout(timeout, False):
                        result = peer.publish(self.address, inner_path, body, content_json_modified, diffs)
                    if result:
                        break
                except Exception as err:
                    self.log.error("Publish error: %s" % Debug.formatException(err))
                    result = {"exception": Debug.formatException(err)}

            # We add to the send back lru not only on success, but also on errors.
            # Some peers returns None. (Why?)
            # Anyway, we tried our best in delivering possibly lost updates.
            if save_to_send_back_lru:
                self.addToSendBackLRU(peer, inner_path, content_json_modified)

            if result and "ok" in result:
                published.append(peer)
                if cb_progress and len(published) <= limit:
                    cb_progress(len(published), limit)
                self.log.info("[OK] %s: %s %s/%s" % (peer.key, result["ok"], len(published), limit))
            else:
                if result == {"exception": "Timeout"}:
                    peer.onConnectionError("Publish timeout")
                self.log.info("[FAILED] %s: %s" % (peer.key, result))
            time.sleep(0.01)

    def addBackgroundPublisher(self, published=[], limit=5, inner_path="content.json", diffs={}):
        with self.background_publishers_lock:
            if self.background_publishers.get(inner_path, None):
                background_publisher = self.background_publishers[inner_path]
                background_publisher.reinit(published=published, limit=limit, diffs=diffs)
            else:
                background_publisher = BackgroundPublisher(self, published=published, limit=limit, inner_path=inner_path, diffs=diffs)
                self.background_publishers[inner_path] = background_publisher

            self.spawn(background_publisher.process)

    def processBackgroundPublishers(self):
        with self.background_publishers_lock:
            for inner_path, background_publisher in list(self.background_publishers.items()):
                background_publisher.process()
                if background_publisher.isComplete():
                    background_publisher.finalize()
                    del self.background_publishers[inner_path]

    def getPeersForForegroundPublishing(self, limit):
        # Wait for some peers to appear
        reqs = [
            self.peer_connector.newReq(limit, limit / 2, 10), # some of them...
            self.peer_connector.newReq(1, 1, 60) # or at least one...
        ]
        self.waitForPeers(reqs, update_websocket=False)

        peers = self.getConnectedPeers()
        random.shuffle(peers)

        # Prefer newer clients.
        # Trying to deliver foreground updates to the latest version clients,
        # expecting that they have better networking facilities.
        # Note: background updates SHOULD NOT discriminate peers by their rev number,
        # otherwise it can cause troubles in delivering updates to older versions.
        peers = sorted(peers, key=lambda peer: peer.connection.handshake.get("rev", 0) < config.rev - 100)

        # Add more, non-connected peers if necessary
        if len(peers) < limit * 2 and len(self.peers) > len(peers):
            peers += self.getRecentPeers(limit * 2)
            peers = set(peers)

        return peers

    # Update content.json on peers
    @util.Noparallel()
    def publish(self, limit="default", inner_path="content.json", diffs={}, cb_progress=None):
        published = []  # Successfully published (Peer)
        publishers = []  # Publisher threads

        if limit == "default":
            limit = 5
        threads = limit

        peers = self.getPeersForForegroundPublishing(limit)

        self.log.info("Publishing %s to %s/%s peers (connected: %s) diffs: %s (%.2fk)..." % (
            inner_path,
            limit, len(self.peers), len(self.getConnectedPeers()),
            list(diffs.keys()), float(len(str(diffs))) / 1024
        ))

        if not peers:
            self.addBackgroundPublisher(published=published, limit=limit, inner_path=inner_path, diffs=diffs)
            return 0  # No peers found

        event_done = gevent.event.AsyncResult()
        for i in range(min(len(peers), limit, threads)):
            publisher = self.spawn(self.publisher, inner_path, peers, published, limit, diffs, event_done, cb_progress)
            publishers.append(publisher)

        event_done.get()  # Wait for done
        if len(published) < min(len(self.peers), limit):
            time.sleep(0.2)  # If less than we need sleep a bit
        if len(published) == 0:
            gevent.joinall(publishers)  # No successful publish, wait for all publisher

        # Publish to more peers in the background
        self.log.info(
            "Published %s to %s peers, publishing to more peers in the background" %
            (inner_path, len(published))
        )

        self.addBackgroundPublisher(published=published, limit=limit, inner_path=inner_path, diffs=diffs)

        # Send my hashfield to every connected peer if changed
        self.spawn(self.sendMyHashfield, 100)

        return len(published)

    # Copy this site
    @util.Noparallel()
    def clone(self, address, privatekey=None, address_index=None, root_inner_path="", overwrite=False):
        import shutil
        new_site = SiteManager.site_manager.need(address, all_file=False)
        default_dirs = []  # Dont copy these directories (has -default version)
        for dir_name in os.listdir(self.storage.directory):
            if "-default" in dir_name:
                default_dirs.append(dir_name.replace("-default", ""))

        self.log.debug("Cloning to %s, ignore dirs: %s, root: %s" % (address, default_dirs, root_inner_path))

        # Copy root content.json
        if not new_site.storage.isFile("content.json") and not overwrite:
            # New site: Content.json not exist yet, create a new one from source site
            if "size_limit" in self.settings:
                new_site.settings["size_limit"] = self.settings["size_limit"]

            # Use content.json-default is specified
            if self.storage.isFile(root_inner_path + "/content.json-default"):
                content_json = self.storage.loadJson(root_inner_path + "/content.json-default")
            else:
                content_json = self.storage.loadJson("content.json")

            if "domain" in content_json:
                del content_json["domain"]
            content_json["title"] = "my" + content_json["title"]
            content_json["cloned_from"] = self.address
            content_json["clone_root"] = root_inner_path
            content_json["files"] = {}
            if address_index:
                content_json["address_index"] = address_index  # Site owner's BIP32 index
            new_site.storage.writeJson("content.json", content_json)
            new_site.content_manager.loadContent(
                "content.json", add_bad_files=False, delete_removed_files=False, load_includes=False
            )

        # Copy files
        for content_inner_path, content in list(self.content_manager.contents.items()):
            file_relative_paths = list(content.get("files", {}).keys())

            # Sign content.json at the end to make sure every file is included
            file_relative_paths.sort()
            file_relative_paths.sort(key=lambda key: key.replace("-default", "").endswith("content.json"))

            for file_relative_path in file_relative_paths:
                file_inner_path = helper.getDirname(content_inner_path) + file_relative_path  # Relative to content.json
                file_inner_path = file_inner_path.strip("/")  # Strip leading /
                if not file_inner_path.startswith(root_inner_path):
                    self.log.debug("[SKIP] %s (not in clone root)" % file_inner_path)
                    continue
                if file_inner_path.split("/")[0] in default_dirs:  # Dont copy directories that has -default postfixed alternative
                    self.log.debug("[SKIP] %s (has default alternative)" % file_inner_path)
                    continue
                file_path = self.storage.getPath(file_inner_path)

                # Copy the file normally to keep the -default postfixed dir and file to allow cloning later
                if root_inner_path:
                    file_inner_path_dest = re.sub("^%s/" % re.escape(root_inner_path), "", file_inner_path)
                    file_path_dest = new_site.storage.getPath(file_inner_path_dest)
                else:
                    file_inner_path_dest = file_inner_path
                    file_path_dest = new_site.storage.getPath(file_inner_path)

                self.log.debug("[COPY] %s to %s..." % (file_inner_path, file_path_dest))
                dest_dir = os.path.dirname(file_path_dest)
                if not os.path.isdir(dest_dir):
                    os.makedirs(dest_dir)
                if file_inner_path_dest.replace("-default", "") == "content.json":  # Don't copy root content.json-default
                    continue

                shutil.copy(file_path, file_path_dest)

                # If -default in path, create a -default less copy of the file
                if "-default" in file_inner_path_dest:
                    file_path_dest = new_site.storage.getPath(file_inner_path_dest.replace("-default", ""))
                    if new_site.storage.isFile(file_inner_path_dest.replace("-default", "")) and not overwrite:
                        # Don't overwrite site files with default ones
                        self.log.debug("[SKIP] Default file: %s (already exist)" % file_inner_path)
                        continue
                    self.log.debug("[COPY] Default file: %s to %s..." % (file_inner_path, file_path_dest))
                    dest_dir = os.path.dirname(file_path_dest)
                    if not os.path.isdir(dest_dir):
                        os.makedirs(dest_dir)
                    shutil.copy(file_path, file_path_dest)
                    # Sign if content json
                    if file_path_dest.endswith("/content.json"):
                        new_site.storage.onUpdated(file_inner_path_dest.replace("-default", ""))
                        new_site.content_manager.loadContent(
                            file_inner_path_dest.replace("-default", ""), add_bad_files=False,
                            delete_removed_files=False, load_includes=False
                        )
                        if privatekey:
                            new_site.content_manager.sign(file_inner_path_dest.replace("-default", ""), privatekey, remove_missing_optional=True)
                            new_site.content_manager.loadContent(
                                file_inner_path_dest, add_bad_files=False, delete_removed_files=False, load_includes=False
                            )

        if privatekey:
            new_site.content_manager.sign("content.json", privatekey, remove_missing_optional=True)
            new_site.content_manager.loadContent(
                "content.json", add_bad_files=False, delete_removed_files=False, load_includes=False
            )

        # Rebuild DB
        if new_site.storage.isFile("dbschema.json"):
            new_site.storage.closeDb()
            try:
                new_site.storage.rebuildDb()
            except Exception as err:
                self.log.error(err)

        return new_site

    @util.Pooled(100)
    def pooledNeedFile(self, *args, **kwargs):
        return self.needFile(*args, **kwargs)

    def isFileDownloadAllowed(self, inner_path, file_info):
        # Verify space for all site
        if self.settings["size"] > self.getSizeLimit() * 1024 * 1024:
            return False
        # Verify space for file
        if file_info.get("size", 0) > config.file_size_limit * 1024 * 1024:
            self.log.debug(
                "File size %s too large: %sMB > %sMB, skipping..." %
                (inner_path, file_info.get("size", 0) / 1024 / 1024, config.file_size_limit)
            )
            return False
        else:
            return True

    def needFileInfo(self, inner_path):
        file_info = self.content_manager.getFileInfo(inner_path)
        if not file_info:
            # No info for file, download all content.json first
            self.log.debug("No info for %s, waiting for all content.json" % inner_path)
            success = self.downloadContent("content.json", download_files=False)
            if not success:
                return False
            file_info = self.content_manager.getFileInfo(inner_path)
        return file_info

    # Check and download if file not exist
    def needFile(self, inner_path, update=False, blocking=True, peer=None, priority=0):
        if self.worker_manager.tasks.findTask(inner_path):
            task = self.worker_manager.addTask(inner_path, peer, priority=priority)
            if blocking:
                return task["evt"].get()
            else:
                return task["evt"]
        elif self.storage.isFile(inner_path) and not update:  # File exist, no need to do anything
            return True
        elif not self.isServing():  # Site not serving
            return False
        else:  # Wait until file downloaded
            if not self.content_manager.contents.get("content.json"):  # No content.json, download it first!
                self.log.debug("Need content.json first (inner_path: %s, priority: %s)" % (inner_path, priority))
                if priority > 0:
                    self.spawn(self.announce)
                if inner_path != "content.json":  # Prevent double download
                    task = self.worker_manager.addTask("content.json", peer)
                    task["evt"].get()
                    self.content_manager.loadContent()
                    if not self.content_manager.contents.get("content.json"):
                        return False  # Content.json download failed

            file_info = None
            if not inner_path.endswith("content.json"):
                file_info = self.needFileInfo(inner_path)
                if not file_info:
                    return False
                if "cert_signers" in file_info and not file_info["content_inner_path"] in self.content_manager.contents:
                    self.log.debug("Missing content.json for requested user file: %s" % inner_path)
                    if self.bad_files.get(file_info["content_inner_path"], 0) > 5:
                        self.log.debug("File %s not reachable: retry %s" % (
                            inner_path, self.bad_files.get(file_info["content_inner_path"], 0)
                        ))
                        return False
                    self.downloadContent(file_info["content_inner_path"])

                if not self.isFileDownloadAllowed(inner_path, file_info):
                    self.log.debug("%s: Download not allowed" % inner_path)
                    return False

            self.bad_files[inner_path] = self.bad_files.get(inner_path, 1)  # Mark as bad file

            task = self.worker_manager.addTask(inner_path, peer, priority=priority, file_info=file_info)
            if blocking:
                return task["evt"].get()
            else:
                return task["evt"]

    # Add or update a peer to site
    # return_peer: Always return the peer even if it was already present
    def addPeer(self, ip, port, return_peer=False, connection=None, source="other"):
        if not ip or ip == "0.0.0.0":
            return False

        key = "%s:%s" % (ip, port)
        peer = self.peers.get(key)
        if peer:  # Already has this ip
            peer.found(source)
            if return_peer:  # Always return peer
                return peer
            else:
                return False
        else:  # New peer
            if (ip, port) in self.peer_blacklist:
                return False  # Ignore blacklist (eg. myself)
            peer = Peer(ip, port, self)
            self.peers[key] = peer
            peer.found(source)

            self.peer_connector.processReqs()
            self.peer_connector.addPeer(peer)

            return peer

    # Called from peer.remove to erase links to peer
    def deregisterPeer(self, peer):
        self.peers.pop(peer.key, None)
        try:
            self.peers_recent.remove(peer)
        except:
            pass
        self.peer_connector.deregisterPeer(peer)

    def announce(self, *args, **kwargs):
        if self.isServing():
            self.announcer.announce(*args, **kwargs)

    def getActivityRating(self, force_safe=False):
        age = time.time() - self.settings.get("modified", 0)

        if age < 60 * 60:
            rating = 1.0
        elif age < 60 * 60 * 5:
            rating = 0.8
        elif age < 60 * 60 * 24:
            rating = 0.6
        elif age < 60 * 60 * 24 * 3:
            rating = 0.4
        elif age < 60 * 60 * 24 * 7:
            rating = 0.2
        else:
            rating = 0.0

        force_safe = force_safe or config.expose_no_ownership

        if (not force_safe) and self.settings["own"]:
            rating = min(rating, 0.6)

        if self.content_updated is False: # Last check modification failed
            rating += 0.1
        elif self.bad_files:
            rating += 0.1

        if rating > 1.0:
            rating = 1.0

        return rating

    def getAnnounceRating(self):
        # rare          frequent
        # announces    announces
        # 0 ------------------- 1
        # activity ------------->    -- active site   ==> frequent announces
        # <---------------- peers    -- many peers    ==> rare announces
        # trackers ------------->    -- many trackers ==> frequent announces to iterate over more trackers

        activity_rating = self.getActivityRating(force_safe=True)

        peer_count = len(self.peers)
        peer_rating = 1.0 - min(peer_count, 50) / 50.0

        tracker_count = self.announcer.getSupportedTrackerCount()
        tracker_count = max(tracker_count, 1)
        tracker_rating = 1.0 - (1.0 / tracker_count)

        v = [activity_rating, peer_rating, tracker_rating]
        return sum(v) / float(len(v))

    def getPreferableConnectablePeerCount(self):
        if not self.isServing():
            return 0

        count = lerp(
            config.site_connectable_peer_count_min,
            config.site_connectable_peer_count_max,
            self.getActivityRating(force_safe=True))
        return count

    # The engine tries to maintain the number of active connections:
    # >= getPreferableActiveConnectionCount()
    # and
    # <= getActiveConnectionCountLimit()

    def getPreferableActiveConnectionCount(self):
        if not self.isServing():
            return 0

        age = time.time() - self.settings.get("modified", 0)
        count = int(10 * self.getActivityRating(force_safe=True))

        if len(self.peers) < 50:
            count = max(count, 5)

        count = min(count, config.connected_limit)

        return count

    def getActiveConnectionCountLimit(self):
        count_above_preferable = 2
        limit = self.getPreferableActiveConnectionCount() + count_above_preferable
        limit = min(limit, config.connected_limit)
        return limit

    ############################################################################

    # Returns the maximum value of current reqs for connections
    def waitingForConnections(self):
        self.peer_connector.processReqs()
        return self.peer_connector.need_nr_connected_peers

    def needConnections(self, num=None, update_site_on_reconnect=False):
        if not self.connection_server.allowsCreatingConnections():
            return

        if num is None:
            num = self.getPreferableActiveConnectionCount()
            num = min(len(self.peers), num)

        req = self.peer_connector.newReq(0, num)
        return req

    # Wait for peers to be discovered and/or connected according to reqs
    # and send updates to the UI
    def waitForPeers(self, reqs, update_websocket=True):
        if not reqs:
            return 0
        i = 0
        nr_connected_peers = -1
        while self.isServing():
            ready_reqs = list(filter(lambda req: req.ready(), reqs))
            if len(ready_reqs) == len(reqs):
                if nr_connected_peers < 0:
                    nr_connected_peers = ready_reqs[0].nr_connected_peers
                break
            waiting_reqs = list(filter(lambda req: not req.ready(), reqs))
            if not waiting_reqs:
                break
            waiting_req = waiting_reqs[0]
            #self.log.debug("waiting_req: %s %s %s", waiting_req.need_nr_connected_peers, waiting_req.nr_connected_peers, waiting_req.expiration_interval)
            waiting_req.waitHeartbeat(timeout=1.0)
            if i > 0 and nr_connected_peers != waiting_req.nr_connected_peers:
                nr_connected_peers = waiting_req.nr_connected_peers
                if update_websocket:
                    self.updateWebsocket(connecting_to_peers=nr_connected_peers)
            i += 1
        if update_websocket:
            self.updateWebsocket(connected_to_peers=max(nr_connected_peers, 0))
            if i > 1:
                # If we waited some time, pause now for displaying connected_to_peers message in the UI.
                # This sleep is solely needed for site status updates on ZeroHello to be more cool-looking.
                gevent.sleep(1)
        return nr_connected_peers

    ############################################################################

    # Return: Peers verified to be connectable recently, or if not enough, other peers as well
    def getConnectablePeers(self, need_num=5, ignore=[], allow_private=True):
        peers = list(self.peers.values())
        random.shuffle(peers)
        connectable_peers = []
        reachable_peers = []
        for peer in peers:
            if peer.key in ignore:
                continue
            if not allow_private and helper.isPrivateIp(peer.ip):
                continue
            if peer.isConnectable():
                connectable_peers.append(peer)
            elif peer.isReachable():
                reachable_peers.append(peer)
            if len(connectable_peers) >= need_num:
                break  # Found requested number of peers

        if len(connectable_peers) < need_num:  # Return not that good peers
            connectable_peers += reachable_peers[0:need_num - len(connectable_peers)]

        return connectable_peers

    # Return: Recently found peers
    def getReachablePeers(self):
        return [peer for peer in self.peers.values() if peer.isReachable()]

    # Return: Recently found peers, sorted by reputation.
    # If there not enough recently found peers, adds other known peers with highest reputation
    def getRecentPeers(self, need_num):
        need_num = int(need_num)
        found = set(self.peers_recent)
        self.log.debug(
            "Recent peers %s of %s (need: %s)" %
            (len(found), len(self.peers), need_num)
        )

        if len(found) < need_num and len(found) < len(self.peers):
            # Add random peers
            peers = self.getReachablePeers()
            peers = sorted(
                list(peers),
                key=lambda peer: peer.reputation,
                reverse=True
            )
            while len(found) < need_num and len(peers) > 0:
                found.add(peers.pop())

        return sorted(
            list(found),
            key=lambda peer: peer.reputation,
            reverse=True
        )[0:need_num]

        return found[0:need_num]

    # Returns the list of connected peers
    # By default the result may contain peers chosen optimistically:
    #  If the connection is being established and 20 seconds have not yet passed
    #  since the connection start time, those peers are included in the result.
    # Set only_fully_connected=True for restricting only by fully connected peers.
    def getConnectedPeers(self, only_fully_connected=False):
        back = []
        if not self.connection_server:
            return []

        tor_manager = self.connection_server.tor_manager
        for connection in self.connection_server.connections:
            if len(back) >= len(self.peers): # short cut for breaking early; no peers to check left
                break

            if not connection.connected and time.time() - connection.start_time > 20:  # Still not connected after 20s
                continue
            if not connection.connected and only_fully_connected: # Only fully connected peers
                continue

            peer = self.peers.get("%s:%s" % (connection.ip, connection.port))
            if peer:
                if connection.ip.endswith(".onion") and connection.target_onion and tor_manager.start_onions:
                    # Check if the connection is made with the onion address created for the site
                    valid_target_onions = (tor_manager.getOnion(self.address), tor_manager.getOnion("global"))
                    if connection.target_onion not in valid_target_onions:
                        continue
                if not peer.connection:
                    peer.connect(connection)
                back.append(peer)
        return back

    def removeDeadPeers(self):
        peers = list(self.peers.values())
        if len(peers) <= 20:
            return

        removed = 0
        if len(peers) > 10000:
            ttl = 60 * 2
        elif len(peers) > 1000:
            ttl = 60 * 60 * 1
        elif len(peers) > 100:
            ttl = 60 * 60 * 4
        else:
            ttl = 60 * 60 * 8

        for peer in peers:
            if peer.isConnected() or peer.isProtected():
                continue
            if peer.isTtlExpired(ttl):
                peer.remove("TTL expired")
                removed += 1
            if removed > len(peers) * 0.1:  # Don't remove too much at once
                break

        if removed:
            self.log.debug("Cleanup peers result: Removed %s, left: %s" % (removed, len(self.peers)))

    # Cleanup probably dead peers and close connection if too much
    def cleanupPeers(self):
        self.removeDeadPeers()

        limit = max(self.getActiveConnectionCountLimit(), self.waitingForConnections())
        connected_peers = self.getConnectedPeers(only_fully_connected=True)
        need_to_close = len(connected_peers) - limit

        if need_to_close > 0:
            closed = 0
            for peer in sorted(connected_peers, key=lambda peer: min(peer.connection.sites, 5)):
                if not peer.isConnected():
                    continue
                if peer.isProtected():
                    continue
                if peer.connection.sites > 5:
                    break
                peer.disconnect("Cleanup peers")
                closed += 1
                if closed >= need_to_close:
                    break

            self.log.debug("Connected: %s, Need to close: %s, Closed: %s" % (
                len(connected_peers), need_to_close, closed))

    def lookForConnectablePeers(self):
        num_tries = 2
        need_connectable_peers = self.getPreferableConnectablePeerCount()

        connectable_peers = 0
        reachable_peers = []

        for peer in list(self.peers.values()):
            if peer.isConnected() or peer.isConnectable():
                connectable_peers += 1
            elif peer.isReachable():
                reachable_peers.append(peer)
            if connectable_peers >= need_connectable_peers:
                return True

        random.shuffle(reachable_peers)

        for peer in reachable_peers:
            if peer.isConnected() or peer.isConnectable() or peer.removed:
                continue
            peer.ping()
            if peer.isConnected():
                peer.pex()
            num_tries -= 1
            if num_tries < 1:
                break

    @util.Noparallel(queue=True)
    def runPeriodicMaintenance(self, startup=False, force=False):
        if not self.isServing():
            return False

        self.log.debug("runPeriodicMaintenance: startup=%s, force=%s" % (startup, force))

        result = False

        for handler in self.periodic_maintenance_handlers:
            result = result | bool(handler.run(startup=startup, force=force))

        return result

    def periodicMaintenanceHandler_general(self, startup=False, force=False):
        if not self.isServing():
            return False

        if not self.peers:
            return False

        self.log.debug("periodicMaintenanceHandler_general: startup=%s, force=%s" % (startup, force))

        #self.persistent_peer_req = self.needConnections(update_site_on_reconnect=True)
        #self.persistent_peer_req.result_connected.wait(timeout=2.0)

        #self.announcer.announcePex()

        self.processBackgroundPublishers()

        self.update()

        return True

    def periodicMaintenanceHandler_peer_check(self, startup=False, force=False):
        if not self.isServing():
            return False

        if not self.peers:
            return False

        self.log.debug("periodicMaintenanceHandler_peer_check: startup=%s, force=%s" % (startup, force))

        if not startup:
            self.cleanupPeers()

        self.lookForConnectablePeers()

        return True

    def periodicMaintenanceHandler_announce(self, startup=False, force=False):
        if not self.isServing():
            return False

        self.log.debug("periodicMaintenanceHandler_announce: startup=%s, force=%s" % (startup, force))

        if startup and len(self.peers) < 10:
            self.announce(mode="startup")
        else:
            self.announce(mode="update", pex=False)

        return True

    # Send hashfield to peers
    def sendMyHashfield(self, limit=5):
        if not self.isServing():
            return False

        if not self.content_manager.hashfield:  # No optional files
            return False

        sent = 0
        connected_peers = self.getConnectedPeers(only_fully_connected=True)
        for peer in connected_peers:
            if peer.sendMyHashfield():
                sent += 1
                if sent >= limit:
                    break
        if sent:
            my_hashfield_changed = self.content_manager.hashfield.time_changed
            self.log.debug("Sent my hashfield (chaged %.3fs ago) to %s peers" % (time.time() - my_hashfield_changed, sent))
        return sent

    # Update hashfield
    def updateHashfield(self, limit=5):
        if not self.isServing():
            return False

        # Return if no optional files
        if not self.content_manager.hashfield and not self.content_manager.has_optional_files:
            return False

        s = time.time()
        queried = 0
        connected_peers = self.getConnectedPeers(only_fully_connected=True)
        for peer in connected_peers:
            if peer.time_hashfield:
                continue
            if peer.updateHashfield():
                queried += 1
            if queried >= limit:
                break
        if queried:
            self.log.debug("Queried hashfield from %s peers in %.3fs" % (queried, time.time() - s))
        return queried

    # Returns if the optional file is need to be downloaded or not
    def isDownloadable(self, inner_path):
        return self.settings.get("autodownloadoptional")

    def delete(self):
        self.log.info("Deleting site...")
        s = time.time()
        self.settings["serving"] = False
        self.settings["deleting"] = True
        self.saveSettings()
        num_greenlets = self.greenlet_manager.stopGreenlets("Site %s deleted" % self.address)
        self.worker_manager.running = False
        num_workers = self.worker_manager.stopWorkers()
        SiteManager.site_manager.delete(self.address)
        self.content_manager.contents.db.deleteSite(self)
        self.updateWebsocket(deleted=True)
        self.storage.deleteFiles()
        self.log.info(
            "Deleted site in %.3fs (greenlets: %s, workers: %s)" %
            (time.time() - s, num_greenlets, num_workers)
        )

    # - Events -

    # Add event listeners
    def addEventListeners(self):
        self.onFileStart = util.Event() # If WorkerManager added new task
        self.onFileDone = util.Event()  # If WorkerManager successfully downloaded a file
        self.onFileFail = util.Event()  # If WorkerManager failed to download a file
        self.onComplete = util.Event()  # All files finished

        self.onFileStart.append(lambda inner_path: self.fileStarted())  # No parameters to make Noparallel batching working
        self.onFileDone.append(lambda inner_path: self.fileDone(inner_path))
        self.onFileFail.append(lambda inner_path: self.fileFailed(inner_path))

    # Send site status update to websocket clients
    def updateWebsocket(self, **kwargs):
        if kwargs:
            param = {"event": list(kwargs.items())[0]}
        else:
            param = None
        for ws in self.websockets:
            ws.event("siteChanged", self, param)
        time.sleep(0.001)

    def messageWebsocket(self, message, type="info", progress=None):
        for ws in self.websockets:
            if progress is None:
                ws.cmd("notification", [type, message])
            else:
                ws.cmd("progress", [type, message, progress])

    # File download started
    @util.Noparallel(blocking=False)
    def fileStarted(self):
        time.sleep(0.001)  # Wait for other files adds
        self.updateWebsocket(file_started=True)

    # File downloaded successfully
    def fileDone(self, inner_path):
        # File downloaded, remove it from bad files
        if inner_path in self.bad_files:
            if config.verbose:
                self.log.debug("Bad file solved: %s" % inner_path)
            del(self.bad_files[inner_path])

        # Update content.json last downlad time
        if inner_path == "content.json":
            if not self.settings.get("downloaded"):
                self.settings["downloaded"] = int(time.time())
            self.content_updated = time.time()

        self.updateWebsocket(file_done=inner_path)

    # File download failed
    def fileFailed(self, inner_path):
        if inner_path == "content.json":
            self.content_updated = False
            self.log.debug("Can't update content.json")
        if inner_path in self.bad_files and self.connection_server.has_internet:
            self.bad_files[inner_path] = self.bad_files.get(inner_path, 0) + 1

        self.updateWebsocket(file_failed=inner_path)

        if self.bad_files.get(inner_path, 0) > 30:
            self.fileForgot(inner_path)

    def fileForgot(self, inner_path):
        self.log.debug("Giving up on %s" % inner_path)
        del self.bad_files[inner_path]  # Give up after 30 tries

import os
import json
import logging
import hashlib
import re
import time
import random
import sys
import struct
import socket
import urllib
import urllib2

import gevent
import gevent.pool

import util
from lib import bencode
from lib.subtl.subtl import UdpTrackerClient
from Config import config
from Peer import Peer
from Worker import WorkerManager
from Debug import Debug
from Content import ContentManager
from SiteStorage import SiteStorage
from Crypt import CryptHash
from util import helper
from util import Diff
from Plugin import PluginManager
import SiteManager


@PluginManager.acceptPlugins
class Site(object):

    def __init__(self, address, allow_create=True, settings=None):
        self.address = re.sub("[^A-Za-z0-9]", "", address)  # Make sure its correct address
        self.address_short = "%s..%s" % (self.address[:6], self.address[-4:])  # Short address for logging
        self.log = logging.getLogger("Site:%s" % self.address_short)
        self.addEventListeners()

        self.content = None  # Load content.json
        self.peers = {}  # Key: ip:port, Value: Peer.Peer
        self.peer_blacklist = SiteManager.peer_blacklist  # Ignore this peers (eg. myself)
        self.time_announce = 0  # Last announce time to tracker
        self.last_tracker_id = random.randint(0, 10)  # Last announced tracker id
        self.worker_manager = WorkerManager(self)  # Handle site download from other peers
        self.bad_files = {}  # SHA check failed files, need to redownload {"inner.content": 1} (key: file, value: failed accept)
        self.content_updated = None  # Content.js update time
        self.notifications = []  # Pending notifications displayed once on page load [error|ok|info, message, timeout]
        self.page_requested = False  # Page viewed in browser
        self.websockets = []  # Active site websocket connections

        self.connection_server = None
        self.storage = SiteStorage(self, allow_create=allow_create)  # Save and load site files
        self.loadSettings(settings)  # Load settings from sites.json
        self.content_manager = ContentManager(self)
        self.content_manager.loadContents()  # Load content.json files
        if "main" in sys.modules and "file_server" in dir(sys.modules["main"]):  # Use global file server by default if possible
            self.connection_server = sys.modules["main"].file_server
        else:
            self.connection_server = None
        if not self.settings.get("auth_key"):  # To auth user in site (Obsolete, will be removed)
            self.settings["auth_key"] = CryptHash.random()
            self.log.debug("New auth key: %s" % self.settings["auth_key"])

        if not self.settings.get("wrapper_key"):  # To auth websocket permissions
            self.settings["wrapper_key"] = CryptHash.random()
            self.log.debug("New wrapper key: %s" % self.settings["wrapper_key"])

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
            if "cache" not in settings:
                settings["cache"] = {}
            if "size_files_optional" not in settings:
                settings["size_optional"] = 0
            if "optional_downloaded" not in settings:
                settings["optional_downloaded"] = 0
            self.bad_files = settings["cache"].get("bad_files", {})
            settings["cache"]["bad_files"] = {}
            # Reset tries
            for inner_path in self.bad_files:
                self.bad_files[inner_path] = 1
        else:
            self.settings = {"own": False, "serving": True, "permissions": [], "added": int(time.time()), "optional_downloaded": 0, "size_optional": 0}  # Default

        # Add admin permissions to homepage
        if self.address == config.homepage and "ADMIN" not in self.settings["permissions"]:
            self.settings["permissions"].append("ADMIN")

        return

    # Save site settings to data/sites.json
    def saveSettings(self):
        if not SiteManager.site_manager.sites:
            SiteManager.site_manager.sites = {}
        if not SiteManager.site_manager.sites.get(self.address):
            SiteManager.site_manager.sites[self.address] = self
            SiteManager.site_manager.load(False)
        SiteManager.site_manager.save()

    # Max site size in MB
    def getSizeLimit(self):
        return self.settings.get("size_limit", int(config.size_limit))

    # Next size limit based on current size
    def getNextSizeLimit(self):
        size_limits = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000]
        size = self.settings.get("size", 0)
        for size_limit in size_limits:
            if size * 1.2 < size_limit * 1024 * 1024:
                return size_limit
        return 999999

    # Download all file from content.json
    def downloadContent(self, inner_path, download_files=True, peer=None, check_modifications=False, diffs={}):
        s = time.time()
        if config.verbose:
            self.log.debug("Downloading %s..." % inner_path)

        found = self.needFile(inner_path, update=self.bad_files.get(inner_path))
        content_inner_dir = helper.getDirname(inner_path)
        if not found:
            self.log.debug("Download %s failed, check_modifications: %s" % (inner_path, check_modifications))
            if check_modifications:  # Download failed, but check modifications if its succed later
                self.onFileDone.once(lambda file_name: self.checkModifications(0), "check_modifications")
            return False  # Could not download content.json

        if config.verbose:
            self.log.debug("Got %s" % inner_path)
        changed, deleted = self.content_manager.loadContent(inner_path, load_includes=False)

        if inner_path == "content.json":
            self.saveSettings()

        if peer:  # Update last received update from peer to prevent re-sending the same update to it
            peer.last_content_json_update = self.content_manager.contents[inner_path]["modified"]

        # Start download files
        file_threads = []
        if download_files:
            for file_relative_path in self.content_manager.contents[inner_path].get("files", {}).keys():
                file_inner_path = content_inner_dir + file_relative_path

                # Try to diff first
                diff_success = False
                diff_actions = diffs.get(file_relative_path)
                if diff_actions and self.bad_files.get(file_inner_path):
                    try:
                        new_file = Diff.patch(self.storage.open(file_inner_path, "rb"), diff_actions)
                        new_file.seek(0)
                        diff_success = self.content_manager.verifyFile(file_inner_path, new_file)
                        if diff_success:
                            self.log.debug("Patched successfully: %s" % file_inner_path)
                            new_file.seek(0)
                            self.storage.write(file_inner_path, new_file)
                            self.onFileDone(file_inner_path)
                    except Exception, err:
                        self.log.debug("Failed to patch %s: %s" % (file_inner_path, err))
                        diff_success = False

                if not diff_success:
                    # Start download and dont wait for finish, return the event
                    res = self.needFile(file_inner_path, blocking=False, update=self.bad_files.get(file_inner_path), peer=peer)
                    if res is not True and res is not False:  # Need downloading and file is allowed
                        file_threads.append(res)  # Append evt

            # Optionals files
            if inner_path == "content.json":
                gevent.spawn(self.updateHashfield)

            for file_relative_path in self.content_manager.contents[inner_path].get("files_optional", {}).keys():
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
        for file_relative_path in self.content_manager.contents[inner_path].get("includes", {}).keys():
            file_inner_path = content_inner_dir + file_relative_path
            include_thread = gevent.spawn(self.downloadContent, file_inner_path, download_files=download_files, peer=peer)
            include_threads.append(include_thread)

        if config.verbose:
            self.log.debug("%s: Downloading %s includes..." % (inner_path, len(include_threads)))
        gevent.joinall(include_threads)
        if config.verbose:
            self.log.debug("%s: Includes download ended" % inner_path)

        if check_modifications:  # Check if every file is up-to-date
            self.checkModifications(0)

        if config.verbose:
            self.log.debug("%s: Downloading %s files, changed: %s..." % (inner_path, len(file_threads), len(changed)))
        gevent.joinall(file_threads)
        if config.verbose:
            self.log.debug("%s: DownloadContent ended in %.3fs" % (inner_path, time.time() - s))

        if not self.worker_manager.tasks:
            self.onComplete()  # No more task trigger site complete

        return True

    # Return bad files with less than 3 retry
    def getReachableBadFiles(self):
        if not self.bad_files:
            return False
        return [bad_file for bad_file, retry in self.bad_files.iteritems() if retry < 3]

    # Retry download bad files
    def retryBadFiles(self, force=False):
        self.log.debug("Retry %s bad files" % len(self.bad_files))
        content_inner_paths = []
        file_inner_paths = []
        for bad_file, tries in self.bad_files.items():
            if force or random.randint(0, min(40, tries)) < 4:  # Larger number tries = less likely to check every 15min
                if bad_file.endswith("content.json"):
                    content_inner_paths.append(bad_file)
                else:
                    file_inner_paths.append(bad_file)

        if content_inner_paths:
            self.pooledDownloadContent(content_inner_paths, only_if_bad=True)

        if file_inner_paths:
            self.pooledDownloadFile(file_inner_paths, only_if_bad=True)

    # Download all files of the site
    @util.Noparallel(blocking=False)
    def download(self, check_size=False, blind_includes=False):
        self.log.debug(
            "Start downloading, bad_files: %s, check_size: %s, blind_includes: %s" %
            (self.bad_files, check_size, blind_includes)
        )
        gevent.spawn(self.announce)
        if check_size:  # Check the size first
            valid = self.downloadContent("content.json", download_files=False)  # Just download content.json files
            if not valid:
                return False  # Cant download content.jsons or size is not fits

        # Download everything
        valid = self.downloadContent("content.json", check_modifications=blind_includes)

        self.onComplete.once(lambda: self.retryBadFiles(force=True))

        return valid

    def pooledDownloadContent(self, inner_paths, pool_size=100, only_if_bad=False):
        self.log.debug("New downloadContent pool: len: %s" % len(inner_paths))
        self.worker_manager.started_task_num += len(inner_paths)
        pool = gevent.pool.Pool(pool_size)
        for inner_path in inner_paths:
            if not only_if_bad or inner_path in self.bad_files:
                pool.spawn(self.downloadContent, inner_path)
            self.worker_manager.started_task_num -= 1
        self.log.debug("Ended downloadContent pool len: %s" % len(inner_paths))

    def pooledDownloadFile(self, inner_paths, pool_size=100, only_if_bad=False):
        self.log.debug("New downloadFile pool: len: %s" % len(inner_paths))
        self.worker_manager.started_task_num += len(inner_paths)
        pool = gevent.pool.Pool(pool_size)
        for inner_path in inner_paths:
            if not only_if_bad or inner_path in self.bad_files:
                pool.spawn(self.needFile, inner_path, update=True)
            self.worker_manager.started_task_num -= 1
        self.log.debug("Ended downloadFile pool len: %s" % len(inner_paths))

    # Update worker, try to find client that supports listModifications command
    def updater(self, peers_try, queried, since):
        while 1:
            if not peers_try or len(queried) >= 3:  # Stop after 3 successful query
                break
            peer = peers_try.pop(0)
            if config.verbose:
                self.log.debug("Try to get updates from: %s Left: %s" % (peer, peers_try))

            res = None
            with gevent.Timeout(20, exception=False):
                res = peer.listModified(since)

            if not res or "modified_files" not in res:
                continue  # Failed query

            queried.append(peer)
            modified_contents = []
            my_modified = self.content_manager.listModified(since)
            for inner_path, modified in res["modified_files"].iteritems():  # Check if the peer has newer files than we
                newer = int(modified) > my_modified.get(inner_path, 0)
                if newer and inner_path not in self.bad_files and not self.content_manager.isArchived(inner_path, modified):
                    # We dont have this file or we have older
                    modified_contents.append(inner_path)
                    self.bad_files[inner_path] = self.bad_files.get(inner_path, 0) + 1
            if modified_contents:
                self.log.debug("%s new modified file from %s" % (len(modified_contents), peer))
                modified_contents.sort(key=lambda inner_path: 0 - res["modified_files"][inner_path])  # Download newest first
                gevent.spawn(self.pooledDownloadContent, modified_contents)

    # Check modified content.json files from peers and add modified files to bad_files
    # Return: Successfully queried peers [Peer, Peer...]
    def checkModifications(self, since=None):
        s = time.time()
        peers_try = []  # Try these peers
        queried = []  # Successfully queried from these peers
        limit = 5

        # Wait for peers
        if not self.peers:
            self.announce()
            for wait in range(10):
                time.sleep(5 + wait)
                self.log.debug("Waiting for peers...")
                if self.peers:
                    break

        peers_try = self.getConnectedPeers()
        peers_connected_num = len(peers_try)
        if peers_connected_num < limit * 2:  # Add more, non-connected peers if necessary
            peers_try += self.getRecentPeers(limit * 5)

        if since is None:  # No since defined, download from last modification time-1day
            since = self.settings.get("modified", 60 * 60 * 24) - 60 * 60 * 24
        self.log.debug("Try to get listModifications from peers: %s, connected: %s, since: %s" % (peers_try, peers_connected_num, since))

        updaters = []
        for i in range(3):
            updaters.append(gevent.spawn(self.updater, peers_try, queried, since))

        gevent.joinall(updaters, timeout=10)  # Wait 10 sec to workers done query modifications

        if not queried:  # Start another 3 thread if first 3 is stuck
            peers_try[0:0] = [peer for peer in self.getConnectedPeers() if peer.connection.connected]  # Add really connected peers
            for _ in range(10):
                gevent.joinall(updaters, timeout=10)  # Wait another 10 sec if none of updaters finished
                if queried:
                    break

        self.log.debug("Queried listModifications from: %s in %.3fs" % (queried, time.time() - s))
        time.sleep(0.1)
        return queried

    # Update content.json from peers and download changed files
    # Return: None
    @util.Noparallel()
    def update(self, announce=False, check_files=False, since=None):
        self.content_manager.loadContent("content.json", load_includes=False)  # Reload content.json
        self.content_updated = None  # Reset content updated time
        self.updateWebsocket(updating=True)

        # Remove files that no longer in content.json
        for bad_file in self.bad_files.keys():
            if bad_file.endswith("content.json"):
                continue

            file_info = self.content_manager.getFileInfo(bad_file)
            if file_info is False or not file_info.get("size"):
                del self.bad_files[bad_file]
                self.log.debug("No info for file: %s, removing from bad_files" % bad_file)

        if announce:
            self.announce()

        # Full update, we can reset bad files
        if check_files and since == 0:
            self.bad_files = {}

        queried = self.checkModifications(since)

        if check_files:
            self.storage.updateBadFiles(quick_check=True)  # Quick check and mark bad files based on file size

        changed, deleted = self.content_manager.loadContent("content.json", load_includes=False)

        if self.bad_files:
            self.log.debug("Bad files: %s" % self.bad_files)
            gevent.spawn(self.retryBadFiles, force=True)

        if len(queried) == 0:
            # Failed to query modifications
            self.content_updated = False
            self.bad_files["content.json"] = 1

        self.updateWebsocket(updated=True)

    # Update site by redownload all content.json
    def redownloadContents(self):
        # Download all content.json again
        content_threads = []
        for inner_path in self.content_manager.contents.keys():
            content_threads.append(self.needFile(inner_path, update=True, blocking=False))

        self.log.debug("Waiting %s content.json to finish..." % len(content_threads))
        gevent.joinall(content_threads)

    # Publish worker
    def publisher(self, inner_path, peers, published, limit, diffs={}, event_done=None, cb_progress=None):
        file_size = self.storage.getSize(inner_path)
        content_json_modified = self.content_manager.contents[inner_path]["modified"]
        body = self.storage.read(inner_path)

        # Find out my ip and port
        tor_manager = self.connection_server.tor_manager
        if tor_manager and tor_manager.enabled and tor_manager.start_onions:
            my_ip = tor_manager.getOnion(self.address)
            if my_ip:
                my_ip += ".onion"
            my_port = config.fileserver_port
        else:
            my_ip = config.ip_external
            if self.connection_server.port_opened:
                my_port = config.fileserver_port
            else:
                my_port = 0

        while 1:
            if not peers or len(published) >= limit:
                if event_done:
                    event_done.set(True)
                break  # All peers done, or published engouht
            peer = peers.pop(0)
            if peer in peers:  # Remove duplicate
                peers.remove(peer)
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

            for retry in range(2):
                try:
                    with gevent.Timeout(timeout, False):
                        result = peer.request("update", {
                            "site": self.address,
                            "inner_path": inner_path,
                            "body": body,
                            "diffs": diffs,
                            "peer": (my_ip, my_port)
                        })
                    if result:
                        break
                except Exception, err:
                    self.log.error("Publish error: %s" % Debug.formatException(err))
                    result = {"exception": Debug.formatException(err)}

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

    # Update content.json on peers
    @util.Noparallel()
    def publish(self, limit="default", inner_path="content.json", diffs={}, cb_progress=None):
        published = []  # Successfully published (Peer)
        publishers = []  # Publisher threads

        if not self.peers:
            self.announce()

        if limit == "default":
            limit = 3
        threads = limit

        peers = self.getConnectedPeers()
        num_connected_peers = len(peers)

        random.shuffle(peers)
        peers = sorted(peers, key=lambda peer: peer.connection.handshake.get("rev", 0) < config.rev - 100)  # Prefer newer clients

        if len(peers) < limit * 2:  # Add more, non-connected peers if necessary
            peers += self.getRecentPeers(limit * 2)

        self.log.info("Publishing %s to %s/%s peers (connected: %s) diffs: %s (%.2fk)..." % (
            inner_path, limit, len(self.peers), num_connected_peers, diffs.keys(), float(len(str(diffs))) / 1024
        ))

        if not peers:
            return 0  # No peers found

        event_done = gevent.event.AsyncResult()
        for i in range(min(len(peers), limit, threads)):
            publisher = gevent.spawn(self.publisher, inner_path, peers, published, limit, diffs, event_done, cb_progress)
            publishers.append(publisher)

        event_done.get()  # Wait for done
        if len(published) < min(len(self.peers), limit):
            time.sleep(0.2)  # If less than we need sleep a bit
        if len(published) == 0:
            gevent.joinall(publishers)  # No successful publish, wait for all publisher

        # Publish more peers in the backgroup
        self.log.info(
            "Successfuly %s published to %s peers, publishing to %s more peers in the background" %
            (inner_path, len(published), limit)
        )

        for thread in range(2):
            gevent.spawn(self.publisher, inner_path, peers, published, limit=limit * 2, diffs=diffs)

        # Send my hashfield to every connected peer if changed
        gevent.spawn(self.sendMyHashfield, 100)

        return len(published)

    # Copy this site
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
            # Content.json not exist yet, create a new one from source site
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
        for content_inner_path, content in self.content_manager.contents.items():
            for file_relative_path in sorted(content["files"].keys()):
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
                if file_inner_path_dest == "content.json-default":  # Don't copy root content.json-default
                    continue

                shutil.copy(file_path, file_path_dest)

                # If -default in path, create a -default less copy of the file
                if "-default" in file_inner_path:
                    file_path_dest = new_site.storage.getPath(file_inner_path.replace("-default", ""))
                    if new_site.storage.isFile(file_inner_path.replace("-default", "")) and not overwrite:
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
                        new_site.storage.onUpdated(file_inner_path.replace("-default", ""))
                        new_site.content_manager.loadContent(
                            file_inner_path.replace("-default", ""), add_bad_files=False,
                            delete_removed_files=False, load_includes=False
                        )
                        if privatekey:
                            new_site.content_manager.sign(file_inner_path.replace("-default", ""), privatekey)
                            new_site.content_manager.loadContent(
                                file_inner_path, add_bad_files=False, delete_removed_files=False, load_includes=False
                            )

        if privatekey:
            new_site.content_manager.sign("content.json", privatekey)
            new_site.content_manager.loadContent(
                "content.json", add_bad_files=False, delete_removed_files=False, load_includes=False
            )

        # Rebuild DB
        if new_site.storage.isFile("dbschema.json"):
            new_site.storage.closeDb()
            new_site.storage.rebuildDb()

        return new_site

    @util.Pooled(100)
    def pooledNeedFile(self, *args, **kwargs):
        return self.needFile(*args, **kwargs)

    # Check and download if file not exist
    def needFile(self, inner_path, update=False, blocking=True, peer=None, priority=0):
        if self.storage.isFile(inner_path) and not update:  # File exist, no need to do anything
            return True
        elif self.settings["serving"] is False:  # Site not serving
            return False
        else:  # Wait until file downloaded
            self.bad_files[inner_path] = self.bad_files.get(inner_path, 0) + 1  # Mark as bad file
            if not self.content_manager.contents.get("content.json"):  # No content.json, download it first!
                self.log.debug("Need content.json first")
                gevent.spawn(self.announce)
                if inner_path != "content.json":  # Prevent double download
                    task = self.worker_manager.addTask("content.json", peer)
                    task.get()
                    self.content_manager.loadContent()
                    if not self.content_manager.contents.get("content.json"):
                        return False  # Content.json download failed

            if not inner_path.endswith("content.json"):
                file_info = self.content_manager.getFileInfo(inner_path)
                if not file_info:
                    # No info for file, download all content.json first
                    self.log.debug("No info for %s, waiting for all content.json" % inner_path)
                    success = self.downloadContent("content.json", download_files=False)
                    if not success:
                        return False
                    file_info = self.content_manager.getFileInfo(inner_path)
                    if not file_info:
                        return False  # Still no info for file
                if "cert_signers" in file_info and not file_info["content_inner_path"] in self.content_manager.contents:
                    self.log.debug("Missing content.json for requested user file: %s" % inner_path)
                    if self.bad_files.get(file_info["content_inner_path"], 0) > 5:
                        self.log.debug("File %s not reachable: retry %s" % (
                            inner_path, self.bad_files.get(file_info["content_inner_path"], 0)
                        ))
                        return False
                    self.downloadContent(file_info["content_inner_path"])

            task = self.worker_manager.addTask(inner_path, peer, priority=priority)
            if blocking:
                return task.get()
            else:
                return task

    # Add or update a peer to site
    # return_peer: Always return the peer even if it was already present
    def addPeer(self, ip, port, return_peer=False, connection=None):
        if not ip:
            return False
        key = "%s:%s" % (ip, port)
        if key in self.peers:  # Already has this ip
            self.peers[key].found()
            if return_peer:  # Always return peer
                return self.peers[key]
            else:
                return False
        else:  # New peer
            if (ip, port) in self.peer_blacklist:
                return False  # Ignore blacklist (eg. myself)
            peer = Peer(ip, port, self)
            self.peers[key] = peer
            return peer

    # Gather peer from connected peers
    @util.Noparallel(blocking=False)
    def announcePex(self, query_num=2, need_num=5):
        peers = [peer for peer in self.peers.values() if peer.connection and peer.connection.connected]  # Connected peers
        if len(peers) == 0:  # Small number of connected peers for this site, connect to any
            self.log.debug("Small number of peers detected...query all of peers using pex")
            peers = self.peers.values()
            need_num = 10

        random.shuffle(peers)
        done = 0
        added = 0
        for peer in peers:
            res = peer.pex(need_num=need_num)
            if type(res) == int:  # We have result
                done += 1
                added += res
                if res:
                    self.worker_manager.onPeers()
                    self.updateWebsocket(peers_added=res)
            if done == query_num:
                break
        self.log.debug("Queried pex from %s peers got %s new peers." % (done, added))

    # Gather peers from tracker
    # Return: Complete time or False on error
    def announceTracker(self, tracker_protocol, tracker_address, fileserver_port=0, add_types=[], my_peer_id="", mode="start"):
        s = time.time()
        if "ip4" not in add_types:
            fileserver_port = 0

        if tracker_protocol == "udp":  # Udp tracker
            if config.disable_udp:
                return False  # No udp supported
            ip, port = tracker_address.split(":")
            tracker = UdpTrackerClient(ip, int(port))
            tracker.peer_port = fileserver_port
            try:
                tracker.connect()
                tracker.poll_once()
                tracker.announce(info_hash=hashlib.sha1(self.address).hexdigest(), num_want=50)
                back = tracker.poll_once()
                peers = back["response"]["peers"]
            except Exception, err:
                return False

        elif tracker_protocol == "http":  # Http tracker
            params = {
                'info_hash': hashlib.sha1(self.address).digest(),
                'peer_id': my_peer_id, 'port': fileserver_port,
                'uploaded': 0, 'downloaded': 0, 'left': 0, 'compact': 1, 'numwant': 30,
                'event': 'started'
            }
            req = None
            try:
                url = "http://" + tracker_address + "?" + urllib.urlencode(params)
                # Load url
                with gevent.Timeout(30, False):  # Make sure of timeout
                    req = urllib2.urlopen(url, timeout=25)
                    response = req.read()
                    req.fp._sock.recv = None  # Hacky avoidance of memory leak for older python versions
                    req.close()
                    req = None
                if not response:
                    self.log.debug("Http tracker %s response error" % url)
                    return False
                # Decode peers
                peer_data = bencode.decode(response)["peers"]
                response = None
                peer_count = len(peer_data) / 6
                peers = []
                for peer_offset in xrange(peer_count):
                    off = 6 * peer_offset
                    peer = peer_data[off:off + 6]
                    addr, port = struct.unpack('!LH', peer)
                    peers.append({"addr": socket.inet_ntoa(struct.pack('!L', addr)), "port": port})
            except Exception, err:
                self.log.debug("Http tracker %s error: %s" % (url, err))
                if req:
                    req.close()
                    req = None
                return False
        else:
            peers = []

        # Adding peers
        added = 0
        for peer in peers:
            if not peer["port"]:
                continue  # Dont add peers with port 0
            if self.addPeer(peer["addr"], peer["port"]):
                added += 1
        if added:
            self.worker_manager.onPeers()
            self.updateWebsocket(peers_added=added)
            self.log.debug("Found %s peers, new: %s, total: %s" % (len(peers), added, len(self.peers)))
        return time.time() - s

    # Add myself and get other peers from tracker
    def announce(self, force=False, mode="start", pex=True):
        if time.time() < self.time_announce + 30 and not force:
            return  # No reannouncing within 30 secs
        self.time_announce = time.time()

        trackers = config.trackers
        # Filter trackers based on supported networks
        if config.disable_udp:
            trackers = [tracker for tracker in trackers if not tracker.startswith("udp://")]
        if self.connection_server and self.connection_server.tor_manager and not self.connection_server.tor_manager.enabled:
            trackers = [tracker for tracker in trackers if ".onion" not in tracker]

        if trackers and (mode == "update" or mode == "more"):  # Only announce on one tracker, increment the queried tracker id
            self.last_tracker_id += 1
            self.last_tracker_id = self.last_tracker_id % len(trackers)
            trackers = [trackers[self.last_tracker_id]]  # We only going to use this one

        errors = []
        slow = []
        add_types = []
        if self.connection_server:
            my_peer_id = self.connection_server.peer_id

            # Type of addresses they can reach me
            if self.connection_server.port_opened:
                add_types.append("ip4")
            if self.connection_server.tor_manager and self.connection_server.tor_manager.start_onions:
                add_types.append("onion")
        else:
            my_peer_id = ""

        s = time.time()
        announced = 0
        threads = []
        fileserver_port = config.fileserver_port

        for tracker in trackers:  # Start announce threads
            tracker_protocol, tracker_address = tracker.split("://")
            thread = gevent.spawn(
                self.announceTracker, tracker_protocol, tracker_address, fileserver_port, add_types, my_peer_id, mode
            )
            threads.append(thread)
            thread.tracker_address = tracker_address
            thread.tracker_protocol = tracker_protocol

        gevent.joinall(threads, timeout=10)  # Wait for announce finish

        for thread in threads:
            if thread.value:
                if thread.value > 1:
                    slow.append("%.2fs %s://%s" % (thread.value, thread.tracker_protocol, thread.tracker_address))
                announced += 1
            else:
                if thread.ready():
                    errors.append("%s://%s" % (thread.tracker_protocol, thread.tracker_address))
                else:  # Still running
                    slow.append("10s+ %s://%s" % (thread.tracker_protocol, thread.tracker_address))

        # Save peers num
        self.settings["peers"] = len(self.peers)

        if len(errors) < len(threads):  # Less errors than total tracker nums
            self.log.debug(
                "Announced types %s in mode %s to %s trackers in %.3fs, errors: %s, slow: %s" %
                (add_types, mode, announced, time.time() - s, errors, slow)
            )
        else:
            if mode != "update":
                self.log.error("Announce to %s trackers in %.3fs, failed" % (announced, time.time() - s))

        if pex:
            if not [peer for peer in self.peers.values() if peer.connection and peer.connection.connected]:
                # If no connected peer yet then wait for connections
                gevent.spawn_later(3, self.announcePex, need_num=10)  # Spawn 3 secs later
            else:  # Else announce immediately
                if mode == "more":  # Need more peers
                    self.announcePex(need_num=10)
                else:
                    self.announcePex()

    # Keep connections to get the updates
    def needConnections(self, num=4, check_site_on_reconnect=False):
        need = min(len(self.peers), num, config.connected_limit)  # Need 5 peer, but max total peers

        connected = len(self.getConnectedPeers())

        connected_before = connected

        self.log.debug("Need connections: %s, Current: %s, Total: %s" % (need, connected, len(self.peers)))

        if connected < need:  # Need more than we have
            for peer in self.peers.values():
                if not peer.connection or not peer.connection.connected:  # No peer connection or disconnected
                    peer.pex()  # Initiate peer exchange
                    if peer.connection and peer.connection.connected:
                        connected += 1  # Successfully connected
                if connected >= need:
                    break

        if check_site_on_reconnect and connected_before == 0 and connected > 0 and self.connection_server.has_internet:
            self.log.debug("Connected before: %s, after: %s. We need to check the site." % (connected_before, connected))
            gevent.spawn(self.update, check_files=False)

        return connected

    # Return: Probably peers verified to be connectable recently
    def getConnectablePeers(self, need_num=5, ignore=[]):
        peers = self.peers.values()
        found = []
        for peer in peers:
            if peer.key.endswith(":0"):
                continue  # Not connectable
            if not peer.connection:
                continue  # No connection
            if peer.key in ignore:
                continue  # The requester has this peer
            if time.time() - peer.connection.last_recv_time > 60 * 60 * 2:  # Last message more than 2 hours ago
                peer.connection = None  # Cleanup: Dead connection
                continue
            found.append(peer)
            if len(found) >= need_num:
                break  # Found requested number of peers

        if need_num > 5 and need_num < 100 and len(found) < need_num:  # Return not that good peers
            found = [peer for peer in peers if not peer.key.endswith(":0") and peer.key not in ignore][0:need_num - len(found)]

        return found

    # Return: Recently found peers
    def getRecentPeers(self, need_num):
        found = sorted(self.peers.values()[0:need_num*50], key=lambda peer: peer.time_found + peer.reputation * 60, reverse=True)[0:need_num*2]
        random.shuffle(found)
        return found[0:need_num]

    def getConnectedPeers(self):
        back = []
        for connection in self.connection_server.connections:
            if not connection.connected and time.time() - connection.start_time > 20:  # Still not connected after 20s
                continue
            peer = self.peers.get("%s:%s" % (connection.ip, connection.port))
            if peer:
                if not peer.connection:
                    peer.connect(connection)
                back.append(peer)
        return back

    # Cleanup probably dead peers and close connection if too much
    def cleanupPeers(self):
        peers = self.peers.values()
        if len(peers) > 20:
            # Cleanup old peers
            removed = 0
            if len(peers) > 1000:
                ttl = 60 * 60 * 1
            else:
                ttl = 60 * 60 * 4

            for peer in peers:
                if peer.connection and peer.connection.connected:
                    continue
                if peer.connection and not peer.connection.connected:
                    peer.connection = None  # Dead connection
                if time.time() - peer.time_found > ttl:  # Not found on tracker or via pex in last 4 hour
                    peer.remove("Time found expired")
                    removed += 1
                if removed > len(peers) * 0.1:  # Don't remove too much at once
                    break

            if removed:
                self.log.debug("Cleanup peers result: Removed %s, left: %s" % (removed, len(self.peers)))

        # Close peers over the limit
        closed = 0
        connected_peers = [peer for peer in self.getConnectedPeers() if peer.connection.connected]  # Only fully connected peers
        need_to_close = len(connected_peers) - config.connected_limit

        if closed < need_to_close:
            for peer in sorted(connected_peers, key=lambda peer: peer.connection.sites):  # Try to keep connections with more sites
                if not peer.connection:
                    continue
                if peer.connection.sites > 5:
                    break
                peer.connection.close("Cleanup peers")
                peer.connection = None
                closed += 1
                if closed >= need_to_close:
                    break

        if need_to_close > 0:
            self.log.debug("Connected: %s, Need to close: %s, Closed: %s" % (len(connected_peers), need_to_close, closed))

    # Send hashfield to peers
    def sendMyHashfield(self, limit=5):
        if not self.content_manager.hashfield:  # No optional files
            return False

        sent = 0
        connected_peers = self.getConnectedPeers()
        for peer in connected_peers:
            if peer.sendMyHashfield():
                sent += 1
                if sent >= limit:
                    break
        if sent:
            self.log.debug("Sent my hashfield to %s peers" % sent)
        return sent

    # Update hashfield
    def updateHashfield(self, limit=5):
        # Return if no optional files
        if not self.content_manager.hashfield and not self.content_manager.contents.get("content.json", {}).get("files_optional"):
            return False

        queried = 0
        connected_peers = self.getConnectedPeers()
        for peer in connected_peers:
            if peer.time_hashfield:
                continue
            if peer.updateHashfield():
                queried += 1
            if queried >= limit:
                break
        if queried:
            self.log.debug("Queried hashfield from %s peers" % queried)
        return queried

    # Returns if the optional file is need to be downloaded or not
    def isDownloadable(self, inner_path):
        return self.settings.get("autodownloadoptional")

    def delete(self):
        self.settings["serving"] = False
        self.saveSettings()
        self.worker_manager.running = False
        self.worker_manager.stopWorkers()
        self.storage.deleteFiles()
        self.updateWebsocket()
        self.content_manager.contents.db.deleteSite(self)
        SiteManager.site_manager.delete(self.address)

    # - Events -

    # Add event listeners
    def addEventListeners(self):
        self.onFileStart = util.Event()  # If WorkerManager added new task
        self.onFileDone = util.Event()  # If WorkerManager successfully downloaded a file
        self.onFileFail = util.Event()  # If WorkerManager failed to download a file
        self.onComplete = util.Event()  # All file finished

        self.onFileStart.append(lambda inner_path: self.fileStarted())  # No parameters to make Noparallel batching working
        self.onFileDone.append(lambda inner_path: self.fileDone(inner_path))
        self.onFileFail.append(lambda inner_path: self.fileFailed(inner_path))

    # Send site status update to websocket clients
    def updateWebsocket(self, **kwargs):
        if kwargs:
            param = {"event": kwargs.items()[0]}
        else:
            param = None
        for ws in self.websockets:
            ws.event("siteChanged", self, param)

    # File download started
    @util.Noparallel(blocking=False)
    def fileStarted(self):
        time.sleep(0.001)  # Wait for other files adds
        self.updateWebsocket(file_started=True)

    # File downloaded successful
    def fileDone(self, inner_path):
        # File downloaded, remove it from bad files
        if inner_path in self.bad_files:
            if config.verbose:
                self.log.debug("Bad file solved: %s" % inner_path)
            del(self.bad_files[inner_path])

        # Update content.json last downlad time
        if inner_path == "content.json":
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
            self.log.debug("Giving up on %s" % inner_path)
            del self.bad_files[inner_path]  # Give up after 30 tries

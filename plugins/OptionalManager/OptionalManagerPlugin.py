import time
import re
import collections

import gevent

from util import helper
from Plugin import PluginManager
from . import ContentDbPlugin


# We can only import plugin host clases after the plugins are loaded
@PluginManager.afterLoad
def importPluginnedClasses():
    global config
    from Config import config


def processAccessLog():
    if access_log:
        content_db = ContentDbPlugin.content_db
        now = int(time.time())
        num = 0
        for site_id in access_log:
            content_db.execute(
                "UPDATE file_optional SET time_accessed = %s WHERE ?" % now,
                {"site_id": site_id, "inner_path": list(access_log[site_id].keys())}
            )
            num += len(access_log[site_id])
        access_log.clear()


def processRequestLog():
    if request_log:
        content_db = ContentDbPlugin.content_db
        cur = content_db.getCursor()
        num = 0
        for site_id in request_log:
            for inner_path, uploaded in request_log[site_id].items():
                content_db.execute(
                    "UPDATE file_optional SET uploaded = uploaded + %s WHERE ?" % uploaded,
                    {"site_id": site_id, "inner_path": inner_path}
                )
                num += 1
        request_log.clear()


if "access_log" not in locals().keys():  # To keep between module reloads
    access_log = collections.defaultdict(dict)  # {site_id: {inner_path1: 1, inner_path2: 1...}}
    request_log = collections.defaultdict(lambda: collections.defaultdict(int))  # {site_id: {inner_path1: 1, inner_path2: 1...}}
    helper.timer(61, processAccessLog)
    helper.timer(60, processRequestLog)


@PluginManager.registerTo("ContentManager")
class ContentManagerPlugin(object):
    def __init__(self, *args, **kwargs):
        self.cache_is_pinned = {}
        super(ContentManagerPlugin, self).__init__(*args, **kwargs)

    def optionalDownloaded(self, inner_path, hash_id, size=None, own=False):
        if "|" in inner_path:  # Big file piece
            file_inner_path, file_range = inner_path.split("|")
        else:
            file_inner_path = inner_path

        self.contents.db.executeDelayed(
            "UPDATE file_optional SET time_downloaded = :now, is_downloaded = 1, peer = peer + 1 WHERE site_id = :site_id AND inner_path = :inner_path AND is_downloaded = 0",
            {"now": int(time.time()), "site_id": self.contents.db.site_ids[self.site.address], "inner_path": file_inner_path}
        )

        return super(ContentManagerPlugin, self).optionalDownloaded(inner_path, hash_id, size, own)

    def optionalRemoved(self, inner_path, hash_id, size=None):
        self.contents.db.execute(
            "UPDATE file_optional SET is_downloaded = 0, is_pinned = 0, peer = peer - 1 WHERE site_id = :site_id AND inner_path = :inner_path AND is_downloaded = 1",
            {"site_id": self.contents.db.site_ids[self.site.address], "inner_path": inner_path}
        )

        if self.contents.db.cur.cursor.rowcount > 0:
            back = super(ContentManagerPlugin, self).optionalRemoved(inner_path, hash_id, size)
            # Re-add to hashfield if we have other file with the same hash_id
            if self.isDownloaded(hash_id=hash_id, force_check_db=True):
                self.hashfield.appendHashId(hash_id)
        else:
            back = False
        self.cache_is_pinned = {}
        return back

    def optionalRenamed(self, inner_path_old, inner_path_new):
        back = super(ContentManagerPlugin, self).optionalRenamed(inner_path_old, inner_path_new)
        self.cache_is_pinned = {}
        self.contents.db.execute(
            "UPDATE file_optional SET inner_path = :inner_path_new WHERE site_id = :site_id AND inner_path = :inner_path_old",
            {"site_id": self.contents.db.site_ids[self.site.address], "inner_path_old": inner_path_old, "inner_path_new": inner_path_new}
        )
        return back

    def isDownloaded(self, inner_path=None, hash_id=None, force_check_db=False):
        if hash_id and not force_check_db and hash_id not in self.hashfield:
            return False

        if inner_path:
            res = self.contents.db.execute(
                "SELECT is_downloaded FROM file_optional WHERE site_id = :site_id AND inner_path = :inner_path LIMIT 1",
                {"site_id": self.contents.db.site_ids[self.site.address], "inner_path": inner_path}
            )
        else:
            res = self.contents.db.execute(
                "SELECT is_downloaded FROM file_optional WHERE site_id = :site_id AND hash_id = :hash_id AND is_downloaded = 1 LIMIT 1",
                {"site_id": self.contents.db.site_ids[self.site.address], "hash_id": hash_id}
            )
        row = res.fetchone()
        if row and row["is_downloaded"]:
            return True
        else:
            return False

    def isPinned(self, inner_path):
        if inner_path in self.cache_is_pinned:
            self.site.log.debug("Cached is pinned: %s" % inner_path)
            return self.cache_is_pinned[inner_path]

        res = self.contents.db.execute(
            "SELECT is_pinned FROM file_optional WHERE site_id = :site_id AND inner_path = :inner_path LIMIT 1",
            {"site_id": self.contents.db.site_ids[self.site.address], "inner_path": inner_path}
        )
        row = res.fetchone()

        if row and row[0]:
            is_pinned = True
        else:
            is_pinned = False

        self.cache_is_pinned[inner_path] = is_pinned
        self.site.log.debug("Cache set is pinned: %s %s" % (inner_path, is_pinned))

        return is_pinned

    def setPin(self, inner_path, is_pinned):
        content_db = self.contents.db
        site_id = content_db.site_ids[self.site.address]
        content_db.execute("UPDATE file_optional SET is_pinned = %d WHERE ?" % is_pinned, {"site_id": site_id, "inner_path": inner_path})
        self.cache_is_pinned = {}

    def optionalDelete(self, inner_path):
        if self.isPinned(inner_path):
            self.site.log.debug("Skip deleting pinned optional file: %s" % inner_path)
            return False
        else:
            return super(ContentManagerPlugin, self).optionalDelete(inner_path)


@PluginManager.registerTo("WorkerManager")
class WorkerManagerPlugin(object):
    def doneTask(self, task):
        super(WorkerManagerPlugin, self).doneTask(task)

        if task["optional_hash_id"] and not self.tasks:  # Execute delayed queries immedietly after tasks finished
            ContentDbPlugin.content_db.processDelayed()


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def parsePath(self, path):
        global access_log
        path_parts = super(UiRequestPlugin, self).parsePath(path)
        if path_parts:
            site_id = ContentDbPlugin.content_db.site_ids.get(path_parts["request_address"])
            if site_id:
                if ContentDbPlugin.content_db.isOptionalFile(site_id, path_parts["inner_path"]):
                    access_log[site_id][path_parts["inner_path"]] = 1
        return path_parts


@PluginManager.registerTo("FileRequest")
class FileRequestPlugin(object):
    def actionGetFile(self, params):
        stats = super(FileRequestPlugin, self).actionGetFile(params)
        self.recordFileRequest(params["site"], params["inner_path"], stats)
        return stats

    def actionStreamFile(self, params):
        stats = super(FileRequestPlugin, self).actionStreamFile(params)
        self.recordFileRequest(params["site"], params["inner_path"], stats)
        return stats

    def recordFileRequest(self, site_address, inner_path, stats):
        if not stats:
            # Only track the last request of files
            return False
        site_id = ContentDbPlugin.content_db.site_ids[site_address]
        if site_id and ContentDbPlugin.content_db.isOptionalFile(site_id, inner_path):
            request_log[site_id][inner_path] += stats["bytes_sent"]


@PluginManager.registerTo("Site")
class SitePlugin(object):
    def isDownloadable(self, inner_path):
        is_downloadable = super(SitePlugin, self).isDownloadable(inner_path)
        if is_downloadable:
            return is_downloadable

        for path in self.settings.get("optional_help", {}).keys():
            if inner_path.startswith(path):
                return True

        return False

    def fileForgot(self, inner_path):
        if "|" in inner_path and self.content_manager.isPinned(re.sub(r"\|.*", "", inner_path)):
            self.log.debug("File %s is pinned, no fileForgot" % inner_path)
            return False
        else:
            return super(SitePlugin, self).fileForgot(inner_path)

    def fileDone(self, inner_path):
        if "|" in inner_path and self.bad_files.get(inner_path, 0) > 5:  # Idle optional file done
            inner_path_file = re.sub(r"\|.*", "", inner_path)
            num_changed = 0
            for key, val in self.bad_files.items():
                if key.startswith(inner_path_file) and val > 1:
                    self.bad_files[key] = 1
                    num_changed += 1
            self.log.debug("Idle optional file piece done, changed retry number of %s pieces." % num_changed)
            if num_changed:
                gevent.spawn(self.retryBadFiles)

        return super(SitePlugin, self).fileDone(inner_path)


@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("OptionalManager plugin")
        group.add_argument('--optional_limit', help='Limit total size of optional files', default="10%", metavar="GB or free space %")
        group.add_argument('--optional_limit_exclude_minsize', help='Exclude files larger than this limit from optional size limit calculation', default=20, metavar="MB", type=int)

        return super(ConfigPlugin, self).createArguments()

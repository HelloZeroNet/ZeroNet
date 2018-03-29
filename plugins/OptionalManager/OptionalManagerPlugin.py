import time
import collections

from util import helper
from Plugin import PluginManager
import ContentDbPlugin


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
                {"site_id": site_id, "inner_path": access_log[site_id].keys()}
            )
            num += len(access_log[site_id])
        access_log.clear()


def processRequestLog():
    if request_log:
        content_db = ContentDbPlugin.content_db
        cur = content_db.getCursor()
        num = 0
        cur.execute("BEGIN")
        for site_id in request_log:
            for inner_path, uploaded in request_log[site_id].iteritems():
                content_db.execute(
                    "UPDATE file_optional SET uploaded = uploaded + %s WHERE ?" % uploaded,
                    {"site_id": site_id, "inner_path": inner_path}
                )
                num += 1
        cur.execute("END")
        request_log.clear()


if "access_log" not in locals().keys():  # To keep between module reloads
    access_log = collections.defaultdict(dict)  # {site_id: {inner_path1: 1, inner_path2: 1...}}
    request_log = collections.defaultdict(lambda: collections.defaultdict(int))  # {site_id: {inner_path1: 1, inner_path2: 1...}}
    helper.timer(61, processAccessLog)
    helper.timer(60, processRequestLog)


@PluginManager.registerTo("ContentManager")
class ContentManagerPlugin(object):
    def optionalDownloaded(self, inner_path, hash_id, size=None, own=False):
        is_pinned = 0
        if "|" in inner_path:  # Big file piece
            file_inner_path, file_range = inner_path.split("|")
            # Auto-pin bigfiles
            if size and config.pin_bigfile and size > 1024 * 1024 * config.pin_bigfile:
                is_pinned = 1
        else:
            file_inner_path = inner_path

        self.contents.db.executeDelayed(
            "UPDATE file_optional SET time_downloaded = :now, is_downloaded = 1, peer = peer + 1, is_pinned = :is_pinned WHERE site_id = :site_id AND inner_path = :inner_path AND is_downloaded = 0",
            {"now": int(time.time()), "site_id": self.contents.db.site_ids[self.site.address], "inner_path": file_inner_path, "is_pinned": is_pinned}
        )

        return super(ContentManagerPlugin, self).optionalDownloaded(inner_path, hash_id, size, own)

    def optionalRemoved(self, inner_path, hash_id, size=None):
        self.contents.db.execute(
            "UPDATE file_optional SET is_downloaded = 0, peer = peer - 1 WHERE site_id = :site_id AND inner_path = :inner_path AND is_downloaded = 1",
            {"site_id": self.contents.db.site_ids[self.site.address], "inner_path": inner_path}
        )

        print "Removed hash_id: %s" % hash_id, self.contents.db.cur.cursor.rowcount
        if self.contents.db.cur.cursor.rowcount > 0:
            back = super(ContentManagerPlugin, self).optionalRemoved(inner_path, hash_id, size)
            # Re-add to hashfield if we have other file with the same hash_id
            if self.isDownloaded(hash_id=hash_id, force_check_db=True):
                self.hashfield.appendHashId(hash_id)

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
        if row and row[0]:
            return True
        else:
            return False


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

        for path in self.settings.get("optional_help", {}).iterkeys():
            if inner_path.startswith(path):
                return True

        return False


@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("OptionalManager plugin")
        group.add_argument('--optional_limit', help='Limit total size of optional files', default="10%", metavar="GB or free space %")
        group.add_argument('--pin_bigfile', help='Automatically pin files larger than this limit', default=20, metavar="MB", type=int)

        return super(ConfigPlugin, self).createArguments()

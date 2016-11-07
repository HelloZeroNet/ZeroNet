import time
import collections

from util import helper
from Plugin import PluginManager
import ContentDbPlugin


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


@PluginManager.registerTo("WorkerManager")
class WorkerManagerPlugin(object):
    def doneTask(self, task):
        if task["optional_hash_id"]:
            content_db = self.site.content_manager.contents.db
            content_db.executeDelayed(
                "UPDATE file_optional SET time_downloaded = :now, is_downloaded = 1, peer = peer + 1 WHERE site_id = :site_id AND inner_path = :inner_path",
                {"now": int(time.time()), "site_id": content_db.site_ids[self.site.address], "inner_path": task["inner_path"]}
            )

        super(WorkerManagerPlugin, self).doneTask(task)

        if task["optional_hash_id"] and not self.tasks:
            content_db.processDelayed()


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

        return super(ConfigPlugin, self).createArguments()

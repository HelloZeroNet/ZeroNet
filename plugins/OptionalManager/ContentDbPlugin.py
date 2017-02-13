import time
import collections
import itertools
import re

import gevent

from util import helper
from Plugin import PluginManager
from Config import config

if "content_db" not in locals().keys():  # To keep between module reloads
    content_db = None


@PluginManager.registerTo("ContentDb")
class ContentDbPlugin(object):
    def __init__(self, *args, **kwargs):
        global content_db
        content_db = self
        self.filled = {}  # Site addresses that already filled from content.json
        self.need_filling = False  # file_optional table just created, fill data from content.json files
        self.time_peer_numbers_updated = 0
        self.my_optional_files = {}  # Last 50 site_address/inner_path called by fileWrite (auto-pinning these files)
        self.optional_files = collections.defaultdict(dict)
        self.optional_files_loading = False
        helper.timer(60 * 5, self.checkOptionalLimit)
        super(ContentDbPlugin, self).__init__(*args, **kwargs)

    def getSchema(self):
        schema = super(ContentDbPlugin, self).getSchema()

        # Need file_optional table
        schema["tables"]["file_optional"] = {
            "cols": [
                ["file_id", "INTEGER PRIMARY KEY UNIQUE NOT NULL"],
                ["site_id", "INTEGER REFERENCES site (site_id) ON DELETE CASCADE"],
                ["inner_path", "TEXT"],
                ["hash_id", "INTEGER"],
                ["size", "INTEGER"],
                ["peer", "INTEGER DEFAULT 0"],
                ["uploaded", "INTEGER DEFAULT 0"],
                ["is_downloaded", "INTEGER DEFAULT 0"],
                ["is_pinned", "INTEGER DEFAULT 0"],
                ["time_added", "INTEGER DEFAULT 0"],
                ["time_downloaded", "INTEGER DEFAULT 0"],
                ["time_accessed", "INTEGER DEFAULT 0"]
            ],
            "indexes": [
                "CREATE UNIQUE INDEX file_optional_key ON file_optional (site_id, inner_path)",
                "CREATE INDEX is_downloaded ON file_optional (is_downloaded)"
            ],
            "schema_changed": 11
        }

        return schema

    def initSite(self, site):
        super(ContentDbPlugin, self).initSite(site)
        if self.need_filling:
            self.fillTableFileOptional(site)
        if not self.optional_files_loading:
            gevent.spawn_later(1, self.loadFilesOptional)
            self.optional_files_loading = True

    def checkTables(self):
        changed_tables = super(ContentDbPlugin, self).checkTables()
        if "file_optional" in changed_tables:
            self.need_filling = True
        return changed_tables

    # Load optional files ending
    def loadFilesOptional(self):
        s = time.time()
        num = 0
        total = 0
        total_downloaded = 0
        res = content_db.execute("SELECT site_id, inner_path, size, is_downloaded FROM file_optional")
        site_sizes = collections.defaultdict(lambda: collections.defaultdict(int))
        for row in res:
            self.optional_files[row["site_id"]][row["inner_path"][-8:]] = 1
            num += 1

            # Update site size stats
            site_sizes[row["site_id"]]["size_optional"] += row["size"]
            if row["is_downloaded"]:
                site_sizes[row["site_id"]]["optional_downloaded"] += row["size"]

        # Site site size stats to sites.json settings
        site_ids_reverse = {val: key for key, val in self.site_ids.iteritems()}
        for site_id, stats in site_sizes.iteritems():
            site_address = site_ids_reverse.get(site_id)
            if not site_address:
                self.log.error("Not found site_id: %s" % site_id)
                continue
            site = self.sites[site_address]
            site.settings["size_optional"] = stats["size_optional"]
            site.settings["optional_downloaded"] = stats["optional_downloaded"]
            total += stats["size_optional"]
            total_downloaded += stats["optional_downloaded"]

        self.log.debug(
            "Loaded %s optional files: %.2fMB, downloaded: %.2fMB in %.3fs" %
            (num, float(total) / 1024 / 1024, float(total_downloaded) / 1024 / 1024, time.time() - s)
        )

        if self.need_filling and self.getOptionalLimitBytes() >= 0 and self.getOptionalLimitBytes() < total_downloaded:
            limit_bytes = self.getOptionalLimitBytes()
            limit_new = round((float(total_downloaded) / 1024 / 1024 / 1024) * 1.1, 2)  # Current limit + 10%
            self.log.debug(
                "First startup after update and limit is smaller than downloaded files size (%.2fGB), increasing it from %.2fGB to %.2fGB" %
                (float(total_downloaded) / 1024 / 1024 / 1024, float(limit_bytes) / 1024 / 1024 / 1024, limit_new)
            )
            config.saveValue("optional_limit", limit_new)
            config.optional_limit = str(limit_new)

    # Predicts if the file is optional
    def isOptionalFile(self, site_id, inner_path):
        return self.optional_files[site_id].get(inner_path[-8:])

    # Fill file_optional table with optional files found in sites
    def fillTableFileOptional(self, site):
        s = time.time()
        site_id = self.site_ids.get(site.address)
        if not site_id:
            return False
        cur = self.getCursor()
        cur.execute("BEGIN")
        res = cur.execute("SELECT * FROM content WHERE size_files_optional > 0 AND site_id = %s" % site_id)
        num = 0
        for row in res.fetchall():
            content = site.content_manager.contents[row["inner_path"]]
            try:
                num += self.setContentFilesOptional(site, row["inner_path"], content, cur=cur)
            except Exception, err:
                self.log.error("Error loading %s into file_optional: %s" % (row["inner_path"], err))
        cur.execute("COMMIT")
        cur.close()

        # Set my files to pinned
        from User import UserManager
        user = UserManager.user_manager.get()
        if not user:
            user = UserManager.user_manager.create()
        auth_address = user.getAuthAddress(site.address)
        self.execute(
            "UPDATE file_optional SET is_pinned = 1 WHERE site_id = :site_id AND inner_path LIKE :inner_path",
            {"site_id": site_id, "inner_path": "%%/%s/%%" % auth_address}
        )

        self.log.debug(
            "Filled file_optional table for %s in %.3fs (loaded: %s, is_pinned: %s)" %
            (site.address, time.time() - s, num, self.cur.cursor.rowcount)
        )
        self.filled[site.address] = True

    def setContentFilesOptional(self, site, content_inner_path, content, cur=None):
        if not cur:
            cur = self
            try:
                cur.execute("BEGIN")
            except Exception, err:
                self.log.warning("Transaction begin error %s %s: %s" % (site, content_inner_path, Debug.formatException(err)))

        num = 0
        site_id = self.site_ids[site.address]
        content_inner_dir = helper.getDirname(content_inner_path)
        for relative_inner_path, file in content.get("files_optional", {}).iteritems():
            file_inner_path = content_inner_dir + relative_inner_path
            hash_id = int(file["sha512"][0:4], 16)
            if hash_id in site.content_manager.hashfield:
                is_downloaded = 1
            else:
                is_downloaded = 0
            if site.address + "/" + file_inner_path in self.my_optional_files:
                is_pinned = 1
            else:
                is_pinned = 0
            cur.insertOrUpdate("file_optional", {
                "hash_id": hash_id,
                "size": int(file["size"]),
                "is_pinned": is_pinned
            }, {
                "site_id": site_id,
                "inner_path": file_inner_path
            }, oninsert={
                "time_added": int(time.time()),
                "time_downloaded": int(time.time()) if is_downloaded else 0,
                "is_downloaded": is_downloaded,
                "peer": is_downloaded
            })
            self.optional_files[site_id][file_inner_path[-8:]] = 1
            num += 1

        if cur == self:
            try:
                cur.execute("END")
            except Exception, err:
                self.log.warning("Transaction end error %s %s: %s" % (site, content_inner_path, Debug.formatException(err)))
        return num

    def setContent(self, site, inner_path, content, size=0):
        super(ContentDbPlugin, self).setContent(site, inner_path, content, size=size)
        old_content = site.content_manager.contents.get(inner_path, {})
        if (not self.need_filling or self.filled.get(site.address)) and "files_optional" in content or "files_optional" in old_content:
            self.setContentFilesOptional(site, inner_path, content)
            # Check deleted files
            if old_content:
                old_files = old_content.get("files_optional", {}).keys()
                new_files = content.get("files_optional", {}).keys()
                content_inner_dir = helper.getDirname(inner_path)
                deleted = [content_inner_dir + key for key in old_files if key not in new_files]
                if deleted:
                    site_id = self.site_ids[site.address]
                    self.execute("DELETE FROM file_optional WHERE ?", {"site_id": site_id, "inner_path": deleted})

    def deleteContent(self, site, inner_path):
        content = site.content_manager.contents.get(inner_path)
        if content and "files_optional" in content:
            site_id = self.site_ids[site.address]
            content_inner_dir = helper.getDirname(inner_path)
            optional_inner_paths = [
                content_inner_dir + relative_inner_path
                for relative_inner_path in content.get("files_optional", {}).keys()
            ]
            self.execute("DELETE FROM file_optional WHERE ?", {"site_id": site_id, "inner_path": optional_inner_paths})
        super(ContentDbPlugin, self).deleteContent(site, inner_path)

    def updatePeerNumbers(self):
        s = time.time()
        num_file = 0
        num_updated = 0
        num_site = 0
        for site in self.sites.values():
            if not site.content_manager.has_optional_files:
                continue
            has_updated_hashfield = next((
                peer
                for peer in site.peers.itervalues()
                if peer.has_hashfield and peer.hashfield.time_changed > self.time_peer_numbers_updated
            ), None)

            if not has_updated_hashfield and site.content_manager.hashfield.time_changed < self.time_peer_numbers_updated:
                continue

            hashfield_peers = itertools.chain.from_iterable(
                peer.hashfield.storage
                for peer in site.peers.itervalues()
                if peer.has_hashfield
            )
            peer_nums = collections.Counter(
                itertools.chain(
                    hashfield_peers,
                    site.content_manager.hashfield
                )
            )

            site_id = self.site_ids[site.address]
            if not site_id:
                continue

            res = self.execute("SELECT file_id, hash_id, peer FROM file_optional WHERE ?", {"site_id": site_id})
            updates = {}
            for row in res:
                peer_num = peer_nums.get(row["hash_id"], 0)
                if peer_num != row["peer"]:
                    updates[row["file_id"]] = peer_num

            self.execute("BEGIN")
            for file_id, peer_num in updates.iteritems():
                self.execute("UPDATE file_optional SET peer = ? WHERE file_id = ?", (peer_num, file_id))
            self.execute("END")

            num_updated += len(updates)
            num_file += len(peer_nums)
            num_site += 1

        self.time_peer_numbers_updated = time.time()
        self.log.debug("%s/%s peer number for %s site updated in %.3fs" % (num_updated, num_file, num_site, time.time() - s))

    def queryDeletableFiles(self):
        # First return the files with atleast 10 seeder and not accessed in last weed
        query = """
            SELECT * FROM file_optional
            WHERE peer > 10 AND is_downloaded = 1 AND is_pinned = 0
            ORDER BY time_accessed < %s DESC, uploaded / size
        """ % int(time.time() - 60 * 60 * 7)
        limit_start = 0
        while 1:
            num = 0
            res = self.execute("%s LIMIT %s, 50" % (query, limit_start))
            for row in res:
                yield row
                num += 1
            if num < 50:
                break
            limit_start += 50

        self.log.debug("queryDeletableFiles returning less-seeded files")

        # Then return files less seeder but still not accessed in last week
        query = """
            SELECT * FROM file_optional
            WHERE is_downloaded = 1 AND peer <= 10 AND is_pinned = 0
            ORDER BY peer DESC, time_accessed < %s DESC, uploaded / size
        """ % int(time.time() - 60 * 60 * 7)
        limit_start = 0
        while 1:
            num = 0
            res = self.execute("%s LIMIT %s, 50" % (query, limit_start))
            for row in res:
                yield row
                num += 1
            if num < 50:
                break
            limit_start += 50

        self.log.debug("queryDeletableFiles returning everyting")

        # At the end return all files
        query = """
            SELECT * FROM file_optional
            WHERE is_downloaded = 1 AND peer <= 10 AND is_pinned = 0
            ORDER BY peer DESC, time_accessed, uploaded / size
        """
        limit_start = 0
        while 1:
            num = 0
            res = self.execute("%s LIMIT %s, 50" % (query, limit_start))
            for row in res:
                yield row
                num += 1
            if num < 50:
                break
            limit_start += 50

    def getOptionalLimitBytes(self):
        if config.optional_limit.endswith("%"):
            limit_percent = float(re.sub("[^0-9.]", "", config.optional_limit))
            limit_bytes = helper.getFreeSpace() * (limit_percent / 100)
        else:
            limit_bytes = float(re.sub("[^0-9.]", "", config.optional_limit)) * 1024 * 1024 * 1024
        return limit_bytes

    def getOptionalNeedDelete(self, size):
        if config.optional_limit.endswith("%"):
            limit_percent = float(re.sub("[^0-9.]", "", config.optional_limit))
            need_delete = size - ((helper.getFreeSpace() + size) * (limit_percent / 100))
        else:
            need_delete = size - self.getOptionalLimitBytes()
        return need_delete

    def checkOptionalLimit(self, limit=None):
        if not limit:
            limit = self.getOptionalLimitBytes()

        if limit < 0:
            self.log.debug("Invalid limit for optional files: %s" % limit)
            return False

        size = self.execute("SELECT SUM(size) FROM file_optional WHERE is_downloaded = 1 AND is_pinned = 0").fetchone()[0]
        if not size:
            size = 0

        need_delete = self.getOptionalNeedDelete(size)

        self.log.debug(
            "Optional size: %.1fMB/%.1fMB, Need delete: %.1fMB" %
            (float(size) / 1024 / 1024, float(limit) / 1024 / 1024, float(need_delete) / 1024 / 1024)
        )
        if need_delete <= 0:
            return False

        self.updatePeerNumbers()

        site_ids_reverse = {val: key for key, val in self.site_ids.iteritems()}
        deleted_file_ids = []
        for row in self.queryDeletableFiles():
            site_address = site_ids_reverse.get(row["site_id"])
            site = self.sites.get(site_address)
            if not site:
                self.log.error("No site found for id: %s" % row["site_id"])
                continue
            site.log.debug("Deleting %s %.3f MB left" % (row["inner_path"], float(need_delete) / 1024 / 1024))
            deleted_file_ids.append(row["file_id"])
            try:
                site.content_manager.optionalRemove(row["inner_path"], row["hash_id"], row["size"])
                site.storage.delete(row["inner_path"])
                need_delete -= row["size"]
            except Exception, err:
                site.log.error("Error deleting %s: %s" % (row["inner_path"], err))

            if need_delete <= 0:
                break

        cur = self.getCursor()
        cur.execute("BEGIN")
        for file_id in deleted_file_ids:
            cur.execute("UPDATE file_optional SET is_downloaded = 0, is_pinned = 0, peer = peer - 1 WHERE ?", {"file_id": file_id})
        cur.execute("COMMIT")
        cur.close()

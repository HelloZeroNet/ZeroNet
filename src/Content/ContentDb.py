import time

from Db import Db
from Config import config
from Plugin import PluginManager


@PluginManager.acceptPlugins
class ContentDb(Db):
    def __init__(self, path):
        self.version = 4
        super(ContentDb, self).__init__({"db_name": "ContentDb"}, path)
        self.foreign_keys = True
        self.checkTables()
        self.site_ids = {}

    def checkTables(self):
        s = time.time()
        version = int(self.execute("PRAGMA user_version").fetchone()[0])
        self.log.debug("Db version: %s, needed: %s" % (version, self.version))
        if version < self.version:
            self.createTables()
        else:
            self.execute("VACUUM")
        self.log.debug("Check tables in %.3fs" % (time.time() - s))

    def createTables(self):
        # Delete all tables
        self.execute("PRAGMA writable_schema = 1")
        self.execute("DELETE FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')")
        self.execute("PRAGMA writable_schema = 0")
        self.execute("VACUUM")
        self.execute("PRAGMA INTEGRITY_CHECK")
        # Create new tables
        self.execute("""
            CREATE TABLE site (
                site_id        INTEGER  PRIMARY KEY ASC AUTOINCREMENT NOT NULL UNIQUE,
                address        TEXT NOT NULL
            );
        """)
        self.execute("CREATE UNIQUE INDEX site_address ON site (address);")

        self.execute("""
            CREATE TABLE content (
                content_id		    INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                site_id             INTEGER REFERENCES site (site_id) ON DELETE CASCADE,
                inner_path          TEXT,
                size                INTEGER,
                size_files          INTEGER,
                size_files_optional INTEGER,
                modified            INTEGER
            );
        """)
        self.execute("CREATE UNIQUE INDEX content_key ON content (site_id, inner_path);")
        self.execute("CREATE INDEX content_modified ON content (site_id, modified);")

        self.execute("PRAGMA user_version = %s" % self.version)

    def needSite(self, site_address):
        if site_address not in self.site_ids:
            self.execute("INSERT OR IGNORE INTO site ?", {"address": site_address})
            for row in self.execute("SELECT * FROM site"):
                self.site_ids[row["address"]] = row["site_id"]
        return self.site_ids[site_address]

    def deleteSite(self, site_address):
        site_id = self.site_ids[site_address]
        self.execute("DELETE FROM site WHERE site_id = :site_id", {"site_id": site_id})
        del self.site_ids[site_address]

    def setContent(self, site_address, inner_path, content, size=0):
        self.execute("INSERT OR REPLACE INTO content ?", {
            "site_id": self.site_ids[site_address],
            "inner_path": inner_path,
            "size": size,
            "size_files": sum([val["size"] for key, val in content.get("files", {}).iteritems()]),
            "size_files_optional": sum([val["size"] for key, val in content.get("files_optional", {}).iteritems()]),
            "modified": int(content["modified"])
        })

    def deleteContent(self, site_address, inner_path):
        self.execute("DELETE FROM content WHERE ?", {"site_id": self.site_ids[site_address], "inner_path": inner_path})

    def loadDbDict(self, site_address):
        res = self.execute(
            "SELECT GROUP_CONCAT(inner_path, '|') AS inner_paths FROM content WHERE ?",
            {"site_id": self.site_ids[site_address]}
        )
        row = res.fetchone()
        if row and row["inner_paths"]:
            inner_paths = row["inner_paths"].split("|")
            return dict.fromkeys(inner_paths, False)
        else:
            return {}

    def getTotalSize(self, site_address, ignore=None):
        params = {"site_id": self.site_ids[site_address]}
        if ignore:
            params["not__inner_path"] = ignore
        res = self.execute("SELECT SUM(size) + SUM(size_files) AS size FROM content WHERE ?", params)
        return res.fetchone()["size"]

    def getOptionalSize(self, site_address):
        res = self.execute(
            "SELECT SUM(size_files_optional) AS size FROM content WHERE ?",
            {"site_id": self.site_ids[site_address]}
        )
        return res.fetchone()["size"]

    def listModified(self, site_address, since):
        res = self.execute(
            "SELECT inner_path, modified FROM content WHERE site_id = :site_id AND modified > :since",
            {"site_id": self.site_ids[site_address], "since": since}
        )
        return {row["inner_path"]: row["modified"] for row in res}

content_dbs = {}


def getContentDb(path=None):
    if not path:
        path = "%s/content.db" % config.data_dir
    if path not in content_dbs:
        content_dbs[path] = ContentDb(path)
    return content_dbs[path]

getContentDb()  # Pre-connect to default one

import time
import os

from Db import Db
from Config import config
from Plugin import PluginManager
from Debug import Debug


@PluginManager.acceptPlugins
class ContentDb(Db):
    def __init__(self, path):
        Db.__init__(self, {"db_name": "ContentDb", "tables": {}}, path)
        self.foreign_keys = True
        try:
            self.schema = self.getSchema()
            self.checkTables()
        except Exception, err:
            self.log.error("Error loading content.db: %s, rebuilding..." % Debug.formatException(err))
            self.close()
            os.unlink(path)  # Remove and try again
            self.schema = self.getSchema()
            self.checkTables()
        self.site_ids = {}
        self.sites = {}

    def getSchema(self):
        schema = {}
        schema["db_name"] = "ContentDb"
        schema["version"] = 3
        schema["tables"] = {}

        if not self.getTableVersion("site"):
            self.log.debug("Migrating from table version-less content.db")
            version = int(self.execute("PRAGMA user_version").fetchone()[0])
            if version > 0:
                self.checkTables()
                self.execute("INSERT INTO keyvalue ?", {"json_id": 0, "key": "table.site.version", "value": 1})
                self.execute("INSERT INTO keyvalue ?", {"json_id": 0, "key": "table.content.version", "value": 1})

        schema["tables"]["site"] = {
            "cols": [
                ["site_id", "INTEGER  PRIMARY KEY ASC NOT NULL UNIQUE"],
                ["address", "TEXT NOT NULL"]
            ],
            "indexes": [
                "CREATE UNIQUE INDEX site_address ON site (address)"
            ],
            "schema_changed": 1
        }

        schema["tables"]["content"] = {
            "cols": [
                ["content_id", "INTEGER PRIMARY KEY UNIQUE NOT NULL"],
                ["site_id", "INTEGER REFERENCES site (site_id) ON DELETE CASCADE"],
                ["inner_path", "TEXT"],
                ["size", "INTEGER"],
                ["size_files", "INTEGER"],
                ["size_files_optional", "INTEGER"],
                ["modified", "INTEGER"]
            ],
            "indexes": [
                "CREATE UNIQUE INDEX content_key ON content (site_id, inner_path)",
                "CREATE INDEX content_modified ON content (site_id, modified)"
            ],
            "schema_changed": 1
        }

        return schema

    def initSite(self, site):
        self.sites[site.address] = site

    def needSite(self, site):
        if site.address not in self.site_ids:
            self.execute("INSERT OR IGNORE INTO site ?", {"address": site.address})
            self.site_ids = {}
            for row in self.execute("SELECT * FROM site"):
                self.site_ids[row["address"]] = row["site_id"]
        return self.site_ids[site.address]

    def deleteSite(self, site):
        site_id = self.site_ids.get(site.address, 0)
        if site_id:
            self.execute("DELETE FROM site WHERE site_id = :site_id", {"site_id": site_id})
            del self.site_ids[site.address]
            del self.sites[site.address]

    def setContent(self, site, inner_path, content, size=0):
        self.insertOrUpdate("content", {
            "size": size,
            "size_files": sum([val["size"] for key, val in content.get("files", {}).iteritems()]),
            "size_files_optional": sum([val["size"] for key, val in content.get("files_optional", {}).iteritems()]),
            "modified": int(content["modified"])
        }, {
            "site_id": self.site_ids.get(site.address, 0),
            "inner_path": inner_path
        })

    def deleteContent(self, site, inner_path):
        self.execute("DELETE FROM content WHERE ?", {"site_id": self.site_ids.get(site.address, 0), "inner_path": inner_path})

    def loadDbDict(self, site):
        res = self.execute(
            "SELECT GROUP_CONCAT(inner_path, '|') AS inner_paths FROM content WHERE ?",
            {"site_id": self.site_ids.get(site.address, 0)}
        )
        row = res.fetchone()
        if row and row["inner_paths"]:
            inner_paths = row["inner_paths"].split("|")
            return dict.fromkeys(inner_paths, False)
        else:
            return {}

    def getTotalSize(self, site, ignore=None):
        params = {"site_id": self.site_ids.get(site.address, 0)}
        if ignore:
            params["not__inner_path"] = ignore
        res = self.execute("SELECT SUM(size) + SUM(size_files) AS size FROM content WHERE ?", params)
        return res.fetchone()["size"]

    def getOptionalSize(self, site):
        res = self.execute(
            "SELECT SUM(size_files_optional) AS size FROM content WHERE ?",
            {"site_id": self.site_ids.get(site.address, 0)}
        )
        return res.fetchone()["size"]

    def listModified(self, site, since):
        res = self.execute(
            "SELECT inner_path, modified FROM content WHERE site_id = :site_id AND modified > :since",
            {"site_id": self.site_ids.get(site.address, 0), "since": since}
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

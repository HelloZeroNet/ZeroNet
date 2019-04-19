from Config import config
from Db.Db import Db
import time


class ChartDb(Db):
    def __init__(self):
        self.version = 2
        super(ChartDb, self).__init__(self.getSchema(), "%s/chart.db" % config.data_dir)
        self.foreign_keys = True
        self.checkTables()
        self.sites = self.loadSites()
        self.types = self.loadTypes()

    def getSchema(self):
        schema = {}
        schema["db_name"] = "Chart"
        schema["tables"] = {}
        schema["tables"]["data"] = {
            "cols": [
                ["data_id", "INTEGER PRIMARY KEY ASC AUTOINCREMENT NOT NULL UNIQUE"],
                ["type_id", "INTEGER NOT NULL"],
                ["site_id", "INTEGER"],
                ["value", "INTEGER"],
                ["date_added", "DATETIME DEFAULT (CURRENT_TIMESTAMP)"]
            ],
            "indexes": [
                "CREATE INDEX site_id ON data (site_id)",
                "CREATE INDEX date_added ON data (date_added)"
            ],
            "schema_changed": 2
        }
        schema["tables"]["type"] = {
            "cols": [
                ["type_id", "INTEGER PRIMARY KEY NOT NULL UNIQUE"],
                ["name", "TEXT"]
            ],
            "schema_changed": 1
        }
        schema["tables"]["site"] = {
            "cols": [
                ["site_id", "INTEGER PRIMARY KEY NOT NULL UNIQUE"],
                ["address", "TEXT"]
            ],
            "schema_changed": 1
        }
        return schema

    def getTypeId(self, name):
        if name not in self.types:
            self.execute("INSERT INTO type ?", {"name": name})
            self.types[name] = self.cur.cursor.lastrowid

        return self.types[name]

    def getSiteId(self, address):
        if address not in self.sites:
            self.execute("INSERT INTO site ?", {"address": address})
            self.sites[address] = self.cur.cursor.lastrowid

        return self.sites[address]

    def loadSites(self):
        sites = {}
        for row in self.execute("SELECT * FROM site"):
            sites[row["address"]] = row["site_id"]
        return sites

    def loadTypes(self):
        types = {}
        for row in self.execute("SELECT * FROM type"):
            types[row["name"]] = row["type_id"]
        return types

    def deleteSite(self, address):
        if address in self.sites:
            site_id = self.sites[address]
            del self.sites[address]
            self.execute("DELETE FROM site WHERE ?", {"site_id": site_id})
            self.execute("DELETE FROM data WHERE ?", {"site_id": site_id})

    def archive(self):
        week_back = 1
        while 1:
            s = time.time()
            date_added_from = time.time() - 60 * 60 * 24 * 7 * (week_back + 1)
            date_added_to = date_added_from + 60 * 60 * 24 * 7
            res = self.execute("""
                SELECT
                 MAX(date_added) AS date_added,
                 SUM(value) AS value,
                 GROUP_CONCAT(data_id) AS data_ids,
                 type_id,
                 site_id,
                 COUNT(*) AS num
                FROM data
                WHERE
                 site_id IS NULL AND
                 date_added > :date_added_from AND
                 date_added < :date_added_to
                GROUP BY strftime('%Y-%m-%d %H', date_added, 'unixepoch', 'localtime'), type_id
            """, {"date_added_from": date_added_from, "date_added_to": date_added_to})

            num_archived = 0
            cur = self.getCursor()
            for row in res:
                if row["num"] == 1:
                    continue
                cur.execute("INSERT INTO data ?", {
                    "type_id": row["type_id"],
                    "site_id": row["site_id"],
                    "value": row["value"],
                    "date_added": row["date_added"]
                })
                cur.execute("DELETE FROM data WHERE data_id IN (%s)" % row["data_ids"])
                num_archived += row["num"]
            self.log.debug("Archived %s data from %s weeks ago in %.3fs" % (num_archived, week_back, time.time() - s))
            week_back += 1
            time.sleep(0.1)
            if num_archived == 0:
                break
        # Only keep 6 month of global stats
        self.execute(
            "DELETE FROM data WHERE site_id IS NULL AND date_added < :date_added_limit",
            {"date_added_limit": time.time() - 60 * 60 * 24 * 30 * 6 }
        )
        # Only keep 1 month of site stats
        self.execute(
            "DELETE FROM data WHERE site_id IS NOT NULL AND date_added < :date_added_limit",
            {"date_added_limit": time.time() - 60 * 60 * 24 * 30 }
        )
        if week_back > 1:
            self.execute("VACUUM")

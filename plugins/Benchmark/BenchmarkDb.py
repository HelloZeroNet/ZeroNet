import os
import json
import contextlib
import time

from Plugin import PluginManager
from Config import config


@PluginManager.registerTo("Actions")
class ActionsPlugin:
    def getBenchmarkTests(self, online=False):
        tests = super().getBenchmarkTests(online)
        tests.extend([
            {"func": self.testDbConnect, "num": 10, "time_standard": 0.27},
            {"func": self.testDbInsert, "num": 10, "time_standard": 0.91},
            {"func": self.testDbInsertMultiuser, "num": 1, "time_standard": 0.57},
            {"func": self.testDbQueryIndexed, "num": 1000, "time_standard": 0.84},
            {"func": self.testDbQueryNotIndexed, "num": 1000, "time_standard": 1.30}
        ])
        return tests


    @contextlib.contextmanager
    def getTestDb(self):
        from Db import Db
        path = "%s/benchmark.db" % config.data_dir
        if os.path.isfile(path):
            os.unlink(path)
        schema = {
            "db_name": "TestDb",
            "db_file": path,
            "maps": {
                ".*": {
                    "to_table": {
                        "test": "test"
                    }
                }
            },
            "tables": {
                "test": {
                    "cols": [
                        ["test_id", "INTEGER"],
                        ["title", "TEXT"],
                        ["json_id", "INTEGER REFERENCES json (json_id)"]
                    ],
                    "indexes": ["CREATE UNIQUE INDEX test_key ON test(test_id, json_id)"],
                    "schema_changed": 1426195822
                }
            }
        }

        db = Db.Db(schema, path)

        yield db

        db.close()
        if os.path.isfile(path):
            os.unlink(path)

    def testDbConnect(self, num_run=1):
        import sqlite3
        for i in range(num_run):
            with self.getTestDb() as db:
                db.checkTables()
            yield "."
        yield "(SQLite version: %s, API: %s)" % (sqlite3.sqlite_version, sqlite3.version)

    def testDbInsert(self, num_run=1):
        yield "x 1000 lines "
        for u in range(num_run):
            with self.getTestDb() as db:
                db.checkTables()
                data = {"test": []}
                for i in range(1000):  # 1000 line of data
                    data["test"].append({"test_id": i, "title": "Testdata for %s message %s" % (u, i)})
                json.dump(data, open("%s/test_%s.json" % (config.data_dir, u), "w"))
                db.updateJson("%s/test_%s.json" % (config.data_dir, u))
                os.unlink("%s/test_%s.json" % (config.data_dir, u))
                assert db.execute("SELECT COUNT(*) FROM test").fetchone()[0] == 1000
            yield "."

    def fillTestDb(self, db):
        db.checkTables()
        cur = db.getCursor()
        cur.logging = False
        for u in range(100, 200):  # 100 user
            data = {"test": []}
            for i in range(100):  # 1000 line of data
                data["test"].append({"test_id": i, "title": "Testdata for %s message %s" % (u, i)})
            json.dump(data, open("%s/test_%s.json" % (config.data_dir, u), "w"))
            db.updateJson("%s/test_%s.json" % (config.data_dir, u), cur=cur)
            os.unlink("%s/test_%s.json" % (config.data_dir, u))
            if u % 10 == 0:
                yield "."

    def testDbInsertMultiuser(self, num_run=1):
        yield "x 100 users x 100 lines "
        for u in range(num_run):
            with self.getTestDb() as db:
                for progress in self.fillTestDb(db):
                    yield progress
                num_rows = db.execute("SELECT COUNT(*) FROM test").fetchone()[0]
                assert num_rows == 10000, "%s != 10000" % num_rows

    def testDbQueryIndexed(self, num_run=1):
        s = time.time()
        with self.getTestDb() as db:
            for progress in self.fillTestDb(db):
                pass
            yield " (Db warmup done in %.3fs) " % (time.time() - s)
            found_total = 0
            for i in range(num_run):  # 1000x by test_id
                found = 0
                res = db.execute("SELECT * FROM test WHERE test_id = %s" % (i % 100))
                for row in res:
                    found_total += 1
                    found += 1
                del(res)
                yield "."
                assert found == 100, "%s != 100 (i: %s)" % (found, i)
            yield "Found: %s" % found_total

    def testDbQueryNotIndexed(self, num_run=1):
        s = time.time()
        with self.getTestDb() as db:
            for progress in self.fillTestDb(db):
                pass
            yield " (Db warmup done in %.3fs) " % (time.time() - s)
            found_total = 0
            for i in range(num_run):  # 1000x by test_id
                found = 0
                res = db.execute("SELECT * FROM test WHERE json_id = %s" % i)
                for row in res:
                    found_total += 1
                    found += 1
                yield "."
                del(res)
                if i == 0 or i > 100:
                    assert found == 0, "%s != 0 (i: %s)" % (found, i)
                else:
                    assert found == 100, "%s != 100 (i: %s)" % (found, i)
            yield "Found: %s" % found_total

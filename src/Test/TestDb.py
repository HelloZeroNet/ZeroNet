import os

from Config import config
from Db import Db


class TestDb:
    def testCheckTables(self):
        db_path = "%s/zeronet.db" % config.data_dir
        schema = {
            "db_name": "TestDb",
            "db_file": "%s/zeronet.db" % config.data_dir,
            "map": {
                "data.json": {
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
                    ],
                    "indexes": ["CREATE UNIQUE INDEX test_id ON test(test_id)"],
                    "schema_changed": 1426195822
                }
            }
        }

        if os.path.isfile(db_path):
            os.unlink(db_path)
        db = Db(schema, db_path)
        db.checkTables()
        db.close()

        # Verify tables
        assert os.path.isfile(db_path)
        db = Db(schema, db_path)

        tables = [row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "keyvalue" in tables  # To store simple key -> value
        assert "json" in tables  # Json file path registry
        assert "test" in tables  # The table defined in dbschema.json

        # Verify test table
        cols = [col["name"] for col in db.execute("PRAGMA table_info(test)")]
        assert "test_id" in cols
        assert "title" in cols

        # Add new table
        assert "newtest" not in tables
        db.schema["tables"]["newtest"] = {
            "cols": [
                ["newtest_id", "INTEGER"],
                ["newtitle", "TEXT"],
            ],
            "indexes": ["CREATE UNIQUE INDEX newtest_id ON newtest(newtest_id)"],
            "schema_changed": 1426195822
        }
        db.checkTables()
        tables = [row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert "test" in tables
        assert "newtest" in tables

        db.close()

        # Cleanup
        os.unlink(db_path)

    def testQueries(self):
        db_path = "%s/zeronet.db" % config.data_dir
        schema = {
            "db_name": "TestDb",
            "db_file": "%s/zeronet.db" % config.data_dir,
            "map": {
                "data.json": {
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
                    ],
                    "indexes": ["CREATE UNIQUE INDEX test_id ON test(test_id)"],
                    "schema_changed": 1426195822
                }
            }
        }

        if os.path.isfile(db_path):
            os.unlink(db_path)
        db = Db(schema, db_path)
        db.checkTables()

        # Test insert
        for i in range(100):
            db.execute("INSERT INTO test ?", {"test_id": i, "title": "Test #%s" % i})

        assert db.execute("SELECT COUNT(*) AS num FROM test").fetchone()["num"] == 100

        # Test single select
        assert db.execute("SELECT COUNT(*) AS num FROM test WHERE ?", {"test_id": 1}).fetchone()["num"] == 1

        # Test multiple select
        assert db.execute("SELECT COUNT(*) AS num FROM test WHERE ?", {"test_id": [1,2,3]}).fetchone()["num"] == 3
        assert db.execute("SELECT COUNT(*) AS num FROM test WHERE ?", {"test_id": [1,2,3], "title": "Test #2"}).fetchone()["num"] == 1
        assert db.execute("SELECT COUNT(*) AS num FROM test WHERE ?", {"test_id": [1,2,3], "title": ["Test #2", "Test #3", "Test #4"]}).fetchone()["num"] == 2

        # Test named parameter escaping
        assert db.execute("SELECT COUNT(*) AS num FROM test WHERE test_id = :test_id AND title LIKE :titlelike", {"test_id": 1, "titlelike": "Test%"}).fetchone()["num"] == 1

        db.close()

        # Cleanup
        os.unlink(db_path)

import io


class TestDb:
    def testCheckTables(self, db):
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

    def testQueries(self, db):
        # Test insert
        for i in range(100):
            db.execute("INSERT INTO test ?", {"test_id": i, "title": "Test #%s" % i})

        assert db.execute("SELECT COUNT(*) AS num FROM test").fetchone()["num"] == 100

        # Test single select
        assert db.execute("SELECT COUNT(*) AS num FROM test WHERE ?", {"test_id": 1}).fetchone()["num"] == 1

        # Test multiple select
        assert db.execute("SELECT COUNT(*) AS num FROM test WHERE ?", {"test_id": [1, 2, 3]}).fetchone()["num"] == 3
        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE ?",
            {"test_id": [1, 2, 3], "title": "Test #2"}
        ).fetchone()["num"] == 1
        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE ?",
            {"test_id": [1, 2, 3], "title": ["Test #2", "Test #3", "Test #4"]}
        ).fetchone()["num"] == 2

        # Test multiple select using named params
        assert db.execute("SELECT COUNT(*) AS num FROM test WHERE test_id IN :test_id", {"test_id": [1, 2, 3]}).fetchone()["num"] == 3
        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE test_id IN :test_id AND title = :title",
            {"test_id": [1, 2, 3], "title": "Test #2"}
        ).fetchone()["num"] == 1
        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE test_id IN :test_id AND title IN :title",
            {"test_id": [1, 2, 3], "title": ["Test #2", "Test #3", "Test #4"]}
        ).fetchone()["num"] == 2

        # Large ammount of IN values
        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE ?",
            {"not__test_id": list(range(2, 3000))}
        ).fetchone()["num"] == 2
        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE ?",
            {"test_id": list(range(50, 3000))}
        ).fetchone()["num"] == 50

        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE ?",
            {"not__title": ["Test #%s" % i for i in range(50, 3000)]}
        ).fetchone()["num"] == 50

        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE ?",
            {"title__like": "%20%"}
        ).fetchone()["num"] == 1

        # Test named parameter escaping
        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE test_id = :test_id AND title LIKE :titlelike",
            {"test_id": 1, "titlelike": "Test%"}
        ).fetchone()["num"] == 1

    def testEscaping(self, db):
        # Test insert
        for i in range(100):
            db.execute("INSERT INTO test ?", {"test_id": i, "title": "Test '\" #%s" % i})

        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE ?",
            {"title": "Test '\" #1"}
        ).fetchone()["num"] == 1

        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE ?",
            {"title": ["Test '\" #%s" % i for i in range(0, 50)]}
        ).fetchone()["num"] == 50

        assert db.execute(
            "SELECT COUNT(*) AS num FROM test WHERE ?",
            {"not__title": ["Test '\" #%s" % i for i in range(50, 3000)]}
        ).fetchone()["num"] == 50


    def testUpdateJson(self, db):
        f = io.BytesIO()
        f.write("""
            {
                "test": [
                    {"test_id": 1, "title": "Test 1 title", "extra col": "Ignore it"}
                ]
            }
        """.encode())
        f.seek(0)
        assert db.updateJson(db.db_dir + "data.json", f) is True
        assert db.execute("SELECT COUNT(*) AS num FROM test_importfilter").fetchone()["num"] == 1
        assert db.execute("SELECT COUNT(*) AS num FROM test").fetchone()["num"] == 1

    def testUnsafePattern(self, db):
        db.schema["maps"] = {"[A-Za-z.]*": db.schema["maps"]["data.json"]}  # Only repetition of . supported
        f = io.StringIO()
        f.write("""
            {
                "test": [
                    {"test_id": 1, "title": "Test 1 title", "extra col": "Ignore it"}
                ]
            }
        """)
        f.seek(0)
        assert db.updateJson(db.db_dir + "data.json", f) is False
        assert db.execute("SELECT COUNT(*) AS num FROM test_importfilter").fetchone()["num"] == 0
        assert db.execute("SELECT COUNT(*) AS num FROM test").fetchone()["num"] == 0

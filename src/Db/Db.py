import sqlite3
import json
import time
import logging
import re
import os
import gevent

from DbCursor import DbCursor
from Config import config

opened_dbs = []


# Close idle databases to save some memory
def dbCleanup():
    while 1:
        time.sleep(60 * 5)
        for db in opened_dbs[:]:
            idle = time.time() - db.last_query_time
            if idle > 60 * 5:
                db.close()

gevent.spawn(dbCleanup)


class Db(object):

    def __init__(self, schema, db_path):
        self.db_path = db_path
        self.db_dir = os.path.dirname(db_path) + "/"
        self.schema = schema
        self.schema["version"] = self.schema.get("version", 1)
        self.conn = None
        self.cur = None
        self.log = logging.getLogger("Db:%s" % schema["db_name"])
        self.table_names = None
        self.collect_stats = False
        self.foreign_keys = False
        self.query_stats = {}
        self.db_keyvalues = {}
        self.delayed_queue = []
        self.delayed_queue_thread = None
        self.last_query_time = time.time()

    def __repr__(self):
        return "<Db:%s>" % self.db_path

    def connect(self):
        if self not in opened_dbs:
            opened_dbs.append(self)
        s = time.time()
        if not os.path.isdir(self.db_dir):  # Directory not exist yet
            os.makedirs(self.db_dir)
            self.log.debug("Created Db path: %s" % self.db_dir)
        if not os.path.isfile(self.db_path):
            self.log.debug("Db file not exist yet: %s" % self.db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.isolation_level = None
        self.cur = self.getCursor()
        if config.db_mode == "security":
            self.cur.execute("PRAGMA journal_mode = WAL")
            self.cur.execute("PRAGMA synchronous = NORMAL")
        else:
            self.cur.execute("PRAGMA journal_mode = MEMORY")
            self.cur.execute("PRAGMA synchronous = OFF")
        if self.foreign_keys:
            self.execute("PRAGMA foreign_keys = ON")
        self.log.debug(
            "Connected to %s in %.3fs (opened: %s, sqlite version: %s)..." %
            (self.db_path, time.time() - s, len(opened_dbs), sqlite3.version)
        )

    # Execute query using dbcursor
    def execute(self, query, params=None):
        self.last_query_time = time.time()
        if not self.conn:
            self.connect()
        return self.cur.execute(query, params)

    def insertOrUpdate(self, *args, **kwargs):
        self.last_query_time = time.time()
        if not self.conn:
            self.connect()
        return self.cur.insertOrUpdate(*args, **kwargs)

    def executeDelayed(self, *args, **kwargs):
        if not self.delayed_queue_thread:
            self.delayed_queue_thread = gevent.spawn_later(10, self.processDelayed)
        self.delayed_queue.append(("execute", (args, kwargs)))

    def insertOrUpdateDelayed(self, *args, **kwargs):
        if not self.delayed_queue:
            gevent.spawn_later(1, self.processDelayed)
        self.delayed_queue.append(("insertOrUpdate", (args, kwargs)))

    def processDelayed(self):
        if not self.delayed_queue:
            self.log.debug("processDelayed aborted")
            return
        self.last_query_time = time.time()
        if not self.conn:
            self.connect()

        s = time.time()
        cur = self.getCursor()
        cur.execute("BEGIN")
        for command, params in self.delayed_queue:
            if command == "insertOrUpdate":
                cur.insertOrUpdate(*params[0], **params[1])
            else:
                cur.execute(*params[0], **params[1])

        cur.execute("END")
        if len(self.delayed_queue) > 10:
            self.log.debug("Processed %s delayed queue in %.3fs" % (len(self.delayed_queue), time.time() - s))
        self.delayed_queue = []
        self.delayed_queue_thread = None

    def close(self):
        s = time.time()
        if self.delayed_queue:
            self.processDelayed()
        if self in opened_dbs:
            opened_dbs.remove(self)
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        self.conn = None
        self.cur = None
        self.log.debug("%s closed in %.3fs, opened: %s" % (self.db_path, time.time() - s, len(opened_dbs)))

    # Gets a cursor object to database
    # Return: Cursor class
    def getCursor(self):
        if not self.conn:
            self.connect()
        return DbCursor(self.conn, self)

    # Get the table version
    # Return: Table version or None if not exist
    def getTableVersion(self, table_name):
        if not self.db_keyvalues:  # Get db keyvalues
            try:
                res = self.execute("SELECT * FROM keyvalue WHERE json_id=0")  # json_id = 0 is internal keyvalues
            except sqlite3.OperationalError, err:  # Table not exist
                self.log.debug("Query error: %s" % err)
                return False

            for row in res:
                self.db_keyvalues[row["key"]] = row["value"]

        return self.db_keyvalues.get("table.%s.version" % table_name, 0)

    # Check Db tables
    # Return: <list> Changed table names
    def checkTables(self):
        s = time.time()
        changed_tables = []
        cur = self.getCursor()

        cur.execute("BEGIN")

        # Check internal tables
        # Check keyvalue table
        changed = cur.needTable("keyvalue", [
            ["keyvalue_id", "INTEGER PRIMARY KEY AUTOINCREMENT"],
            ["key", "TEXT"],
            ["value", "INTEGER"],
            ["json_id", "INTEGER"],
        ], [
            "CREATE UNIQUE INDEX key_id ON keyvalue(json_id, key)"
        ], version=self.schema["version"])
        if changed:
            changed_tables.append("keyvalue")

        # Check json table
        if self.schema["version"] == 1:
            changed = cur.needTable("json", [
                ["json_id", "INTEGER PRIMARY KEY AUTOINCREMENT"],
                ["path", "VARCHAR(255)"]
            ], [
                "CREATE UNIQUE INDEX path ON json(path)"
            ], version=self.schema["version"])
        elif self.schema["version"] == 2:
            changed = cur.needTable("json", [
                ["json_id", "INTEGER PRIMARY KEY AUTOINCREMENT"],
                ["directory", "VARCHAR(255)"],
                ["file_name", "VARCHAR(255)"]
            ], [
                "CREATE UNIQUE INDEX path ON json(directory, file_name)"
            ], version=self.schema["version"])
        elif self.schema["version"] == 3:
            changed = cur.needTable("json", [
                ["json_id", "INTEGER PRIMARY KEY AUTOINCREMENT"],
                ["site", "VARCHAR(255)"],
                ["directory", "VARCHAR(255)"],
                ["file_name", "VARCHAR(255)"]
            ], [
                "CREATE UNIQUE INDEX path ON json(directory, site, file_name)"
            ], version=self.schema["version"])
        if changed:
            changed_tables.append("json")

        # Check schema tables
        for table_name, table_settings in self.schema["tables"].items():
            changed = cur.needTable(
                table_name, table_settings["cols"],
                table_settings["indexes"], version=table_settings["schema_changed"]
            )
            if changed:
                changed_tables.append(table_name)

        cur.execute("COMMIT")
        self.log.debug("Db check done in %.3fs, changed tables: %s" % (time.time() - s, changed_tables))
        if changed_tables:
            self.db_keyvalues = {}  # Refresh table version cache

        return changed_tables

    # Update json file to db
    # Return: True if matched
    def updateJson(self, file_path, file=None, cur=None):
        if not file_path.startswith(self.db_dir):
            return False  # Not from the db dir: Skipping
        relative_path = re.sub("^%s" % self.db_dir, "", file_path)  # File path realative to db file
        # Check if filename matches any of mappings in schema
        matched_maps = []
        for match, map_settings in self.schema["maps"].items():
            if re.match(match, relative_path):
                matched_maps.append(map_settings)

        # No match found for the file
        if not matched_maps:
            return False

        # Load the json file
        try:
            if file is None:  # Open file is not file object passed
                file = open(file_path)

            if file is False:  # File deleted
                data = {}
            else:
                data = json.load(file)
        except Exception, err:
            self.log.debug("Json file %s load error: %s" % (file_path, err))
            data = {}

        # No cursor specificed
        if not cur:
            cur = self.getCursor()
            cur.execute("BEGIN")
            cur.logging = False
            commit_after_done = True
        else:
            commit_after_done = False

        # Row for current json file if required
        if not data or filter(lambda dbmap: "to_keyvalue" in dbmap or "to_table" in dbmap, matched_maps):
            json_row = cur.getJsonRow(relative_path)

        # Check matched mappings in schema
        for dbmap in matched_maps:
            # Insert non-relational key values
            if dbmap.get("to_keyvalue"):
                # Get current values
                res = cur.execute("SELECT * FROM keyvalue WHERE json_id = ?", (json_row["json_id"],))
                current_keyvalue = {}
                current_keyvalue_id = {}
                for row in res:
                    current_keyvalue[row["key"]] = row["value"]
                    current_keyvalue_id[row["key"]] = row["keyvalue_id"]

                for key in dbmap["to_keyvalue"]:
                    if key not in current_keyvalue:  # Keyvalue not exist yet in the db
                        cur.execute(
                            "INSERT INTO keyvalue ?",
                            {"key": key, "value": data.get(key), "json_id": json_row["json_id"]}
                        )
                    elif data.get(key) != current_keyvalue[key]:  # Keyvalue different value
                        cur.execute(
                            "UPDATE keyvalue SET value = ? WHERE keyvalue_id = ?",
                            (data.get(key), current_keyvalue_id[key])
                        )

            # Insert data to json table for easier joins
            if dbmap.get("to_json_table"):
                directory, file_name = re.match("^(.*?)/*([^/]*)$", relative_path).groups()
                data_json_row = dict(cur.getJsonRow(directory + "/" + dbmap.get("file_name", file_name)))
                changed = False
                for key in dbmap["to_json_table"]:
                    if data.get(key) != data_json_row.get(key):
                        changed = True
                if changed:
                    # Add the custom col values
                    data_json_row.update({key: val for key, val in data.iteritems() if key in dbmap["to_json_table"]})
                    cur.execute("INSERT OR REPLACE INTO json ?", data_json_row)

            # Insert data to tables
            for table_settings in dbmap.get("to_table", []):
                if isinstance(table_settings, dict):  # Custom settings
                    table_name = table_settings["table"]  # Table name to insert datas
                    node = table_settings.get("node", table_name)  # Node keyname in data json file
                    key_col = table_settings.get("key_col")  # Map dict key as this col
                    val_col = table_settings.get("val_col")  # Map dict value as this col
                    import_cols = table_settings.get("import_cols")
                    replaces = table_settings.get("replaces")
                else:  # Simple settings
                    table_name = table_settings
                    node = table_settings
                    key_col = None
                    val_col = None
                    import_cols = None
                    replaces = None

                # Fill import cols from table cols
                if not import_cols:
                    import_cols = set(map(lambda item: item[0], self.schema["tables"][table_name]["cols"]))

                cur.execute("DELETE FROM %s WHERE json_id = ?" % table_name, (json_row["json_id"],))

                if node not in data:
                    continue

                if key_col:  # Map as dict
                    for key, val in data[node].iteritems():
                        if val_col:  # Single value
                            cur.execute(
                                "INSERT OR REPLACE INTO %s ?" % table_name,
                                {key_col: key, val_col: val, "json_id": json_row["json_id"]}
                            )
                        else:  # Multi value
                            if isinstance(val, dict):  # Single row
                                row = val
                                if import_cols:
                                    row = {key: row[key] for key in row if key in import_cols}  # Filter row by import_cols
                                row[key_col] = key
                                # Replace in value if necessary
                                if replaces:
                                    for replace_key, replace in replaces.iteritems():
                                        if replace_key in row:
                                            for replace_from, replace_to in replace.iteritems():
                                                row[replace_key] = row[replace_key].replace(replace_from, replace_to)

                                row["json_id"] = json_row["json_id"]
                                cur.execute("INSERT OR REPLACE INTO %s ?" % table_name, row)
                            else:  # Multi row
                                for row in val:
                                    row[key_col] = key
                                    row["json_id"] = json_row["json_id"]
                                    cur.execute("INSERT OR REPLACE INTO %s ?" % table_name, row)
                else:  # Map as list
                    for row in data[node]:
                        row["json_id"] = json_row["json_id"]
                        if import_cols:
                            row = {key: row[key] for key in row if key in import_cols}  # Filter row by import_cols
                        cur.execute("INSERT OR REPLACE INTO %s ?" % table_name, row)

        # Cleanup json row
        if not data:
            self.log.debug("Cleanup json row for %s" % file_path)
            cur.execute("DELETE FROM json WHERE json_id = %s" % json_row["json_id"])

        if commit_after_done:
            cur.execute("COMMIT")
        return True


if __name__ == "__main__":
    s = time.time()
    console_log = logging.StreamHandler()
    logging.getLogger('').setLevel(logging.DEBUG)
    logging.getLogger('').addHandler(console_log)
    console_log.setLevel(logging.DEBUG)
    dbjson = Db(json.load(open("zerotalk.schema.json")), "data/users/zerotalk.db")
    dbjson.collect_stats = True
    dbjson.checkTables()
    cur = dbjson.getCursor()
    cur.execute("BEGIN")
    cur.logging = False
    dbjson.updateJson("data/users/content.json", cur=cur)
    for user_dir in os.listdir("data/users"):
        if os.path.isdir("data/users/%s" % user_dir):
            dbjson.updateJson("data/users/%s/data.json" % user_dir, cur=cur)
            # print ".",
    cur.logging = True
    cur.execute("COMMIT")
    print "Done in %.3fs" % (time.time() - s)
    for query, stats in sorted(dbjson.query_stats.items()):
        print "-", query, stats

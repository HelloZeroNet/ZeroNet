import time
import re
import gevent
from util import helper


# Special sqlite cursor


class DbCursor:

    def __init__(self, conn, db):
        self.conn = conn
        self.db = db
        self.cursor = conn.cursor()
        self.logging = False

    def quoteValue(self, value):
        if type(value) is int:
            return str(value)
        else:
            return "'%s'" % value.replace("'", "''")

    def parseQuery(self, query, params):
        query_type = query.split(" ", 1)[0].upper()
        if isinstance(params, dict) and "?" in query:  # Make easier select and insert by allowing dict params
            if query_type in ("SELECT", "DELETE", "UPDATE"):
                # Convert param dict to SELECT * FROM table WHERE key = ? AND key2 = ? format
                query_wheres = []
                values = []
                for key, value in params.items():
                    if type(value) is list:
                        if key.startswith("not__"):
                            field = key.replace("not__", "")
                            operator = "NOT IN"
                        else:
                            field = key
                            operator = "IN"
                        if len(value) > 100:
                            # Embed values in query to avoid "too many SQL variables" error
                            query_values = ",".join(map(helper.sqlquote, value))
                        else:
                            query_values = ",".join(["?"] * len(value))
                            values += value
                        query_wheres.append(
                            "%s %s (%s)" %
                            (field, operator, query_values)
                        )
                    else:
                        if key.startswith("not__"):
                            query_wheres.append(key.replace("not__", "") + " != ?")
                        elif key.endswith("__like"):
                            query_wheres.append(key.replace("__like", "") + " LIKE ?")
                        elif key.endswith(">"):
                            query_wheres.append(key.replace(">", "") + " > ?")
                        elif key.endswith("<"):
                            query_wheres.append(key.replace("<", "") + " < ?")
                        else:
                            query_wheres.append(key + " = ?")
                        values.append(value)
                wheres = " AND ".join(query_wheres)
                if wheres == "":
                    wheres = "1"
                query = re.sub("(.*)[?]", "\\1 %s" % wheres, query)  # Replace the last ?
                params = values
            else:
                # Convert param dict to INSERT INTO table (key, key2) VALUES (?, ?) format
                keys = ", ".join(params.keys())
                values = ", ".join(['?' for key in params.keys()])
                keysvalues = "(%s) VALUES (%s)" % (keys, values)
                query = re.sub("(.*)[?]", "\\1%s" % keysvalues, query)  # Replace the last ?
                params = tuple(params.values())
        elif isinstance(params, dict) and ":" in query:
            new_params = dict()
            values = []
            for key, value in params.items():
                if type(value) is list:
                    for idx, val in enumerate(value):
                        new_params[key + "__" + str(idx)] = val

                    new_names = [":" + key + "__" + str(idx) for idx in range(len(value))]
                    query = re.sub(r":" + re.escape(key) + r"([)\s]|$)", "(%s)%s" % (", ".join(new_names), r"\1"), query)
                else:
                    new_params[key] = value

            params = new_params
        return query, params

    def execute(self, query, params=None):
        if query.upper().strip("; ") == "VACUUM":
            self.db.commit("vacuum called")
        query = query.strip()
        while self.db.progress_sleeping:
            time.sleep(0.1)

        self.db.last_query_time = time.time()

        query, params = self.parseQuery(query, params)

        s = time.time()

        if params:  # Query has parameters
            res = self.cursor.execute(query, params)
            if self.logging:
                self.db.log.debug(query + " " + str(params) + " (Done in %.4f)" % (time.time() - s))
        else:
            res = self.cursor.execute(query)
            if self.logging:
                self.db.log.debug(query + " (Done in %.4f)" % (time.time() - s))

        # Log query stats
        if self.db.collect_stats:
            if query not in self.db.query_stats:
                self.db.query_stats[query] = {"call": 0, "time": 0.0}
            self.db.query_stats[query]["call"] += 1
            self.db.query_stats[query]["time"] += time.time() - s

        if not self.db.need_commit:
            query_type = query.split(" ", 1)[0].upper()
            if query_type in ["UPDATE", "DELETE", "INSERT", "CREATE"]:
                self.db.need_commit = True

        return res

    # Creates on updates a database row without incrementing the rowid
    def insertOrUpdate(self, table, query_sets, query_wheres, oninsert={}):
        sql_sets = ["%s = :%s" % (key, key) for key in query_sets.keys()]
        sql_wheres = ["%s = :%s" % (key, key) for key in query_wheres.keys()]

        params = query_sets
        params.update(query_wheres)
        self.execute(
            "UPDATE %s SET %s WHERE %s" % (table, ", ".join(sql_sets), " AND ".join(sql_wheres)),
            params
        )
        if self.cursor.rowcount == 0:
            params.update(oninsert)  # Add insert-only fields
            self.execute("INSERT INTO %s ?" % table, params)

    # Create new table
    # Return: True on success
    def createTable(self, table, cols):
        # TODO: Check current structure
        self.execute("DROP TABLE IF EXISTS %s" % table)
        col_definitions = []
        for col_name, col_type in cols:
            col_definitions.append("%s %s" % (col_name, col_type))

        self.execute("CREATE TABLE %s (%s)" % (table, ",".join(col_definitions)))
        return True

    # Create indexes on table
    # Return: True on success
    def createIndexes(self, table, indexes):
        for index in indexes:
            if not index.strip().upper().startswith("CREATE"):
                self.db.log.error("Index command should start with CREATE: %s" % index)
                continue
            self.execute(index)

    # Create table if not exist
    # Return: True if updated
    def needTable(self, table, cols, indexes=None, version=1):
        current_version = self.db.getTableVersion(table)
        if int(current_version) < int(version):  # Table need update or not extis
            self.db.log.info("Table %s outdated...version: %s need: %s, rebuilding..." % (table, current_version, version))
            self.createTable(table, cols)
            if indexes:
                self.createIndexes(table, indexes)
            self.execute(
                "INSERT OR REPLACE INTO keyvalue ?",
                {"json_id": 0, "key": "table.%s.version" % table, "value": version}
            )
            return True
        else:  # Not changed
            return False

    # Get or create a row for json file
    # Return: The database row
    def getJsonRow(self, file_path):
        directory, file_name = re.match("^(.*?)/*([^/]*)$", file_path).groups()
        if self.db.schema["version"] == 1:
            # One path field
            res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"path": file_path})
            row = res.fetchone()
            if not row:  # No row yet, create it
                self.execute("INSERT INTO json ?", {"path": file_path})
                res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"path": file_path})
                row = res.fetchone()
        elif self.db.schema["version"] == 2:
            # Separate directory, file_name (easier join)
            res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"directory": directory, "file_name": file_name})
            row = res.fetchone()
            if not row:  # No row yet, create it
                self.execute("INSERT INTO json ?", {"directory": directory, "file_name": file_name})
                res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"directory": directory, "file_name": file_name})
                row = res.fetchone()
        elif self.db.schema["version"] == 3:
            # Separate site, directory, file_name (for merger sites)
            site_address, directory = re.match("^([^/]*)/(.*)$", directory).groups()
            res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"site": site_address, "directory": directory, "file_name": file_name})
            row = res.fetchone()
            if not row:  # No row yet, create it
                self.execute("INSERT INTO json ?", {"site": site_address, "directory": directory, "file_name": file_name})
                res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"site": site_address, "directory": directory, "file_name": file_name})
                row = res.fetchone()
        else:
            raise Exception("Dbschema version %s not supported" % self.db.schema.get("version"))
        return row

    def close(self):
        self.cursor.close()

import time, re

# Special sqlite cursor
class DbCursor: 
	def __init__(self, conn, db):
		self.conn = conn
		self.db = db
		self.cursor = conn.cursor()
		self.logging = True


	def execute(self, query, params=None):
		if isinstance(params, dict): # Make easier select and insert by allowing dict params
			if query.startswith("SELECT") or query.startswith("DELETE"): # Convert param dict to SELECT * FROM table WHERE key = ?, key2 = ? format
				wheres = "AND ".join([key+" = ?" for key in params])
				query = query.replace("?", wheres)
				params = params.values()
			else: # Convert param dict to INSERT INTO table (key, key2) VALUES (?, ?) format
				keys = ", ".join(params.keys())
				values = ", ".join(['?' for key in params.keys()])
				query = query.replace("?", "(%s) VALUES (%s)" % (keys, values))
				params = tuple(params.values())

		s = time.time()
		# if query == "COMMIT": self.logging = True # Turn logging back on transaction commit

		if params: # Query has parameters
			res = self.cursor.execute(query, params)
			if self.logging: 
				self.db.log.debug((query.replace("?", "%s") % params)+" (Done in %.4f)" % (time.time()-s))
		else:
			res = self.cursor.execute(query)
			if self.logging: self.db.log.debug(query+" (Done in %.4f)" % (time.time()-s))

		# Log query stats
		if self.db.collect_stats: 
			if query not in self.db.query_stats:
				self.db.query_stats[query] = {"call": 0, "time": 0.0}
			self.db.query_stats[query]["call"] += 1
			self.db.query_stats[query]["time"] += time.time()-s
		
		# if query == "BEGIN": self.logging = False # Turn logging off on transaction commit
		return res


	# Create new table
	# Return: True on success
	def createTable(self, table, cols):
		# TODO: Check current structure
		"""table_changed = False
		res = c.execute("PRAGMA table_info(%s)" % table)
		if res:
			for row in res:
				print row["name"], row["type"], cols[row["name"]]
				print row
		else:
			table_changed = True

		if table_changed: # Table structure changed, drop and create again"""
		self.execute("DROP TABLE IF EXISTS %s" % table)
		col_definitions = []
		for col_name, col_type in cols:
			col_definitions.append("%s %s" % (col_name, col_type))

		self.execute("CREATE TABLE %s (%s)" % (table, ",".join(col_definitions)))
		return True



	# Create indexes on table
	# Return: True on success
	def createIndexes(self, table, indexes):
		# indexes.append("CREATE INDEX %s_id ON %s(%s_id)" % (table, table, table)) # Primary key index
		for index in indexes:
			self.execute(index)


	# Create table if not exits
	# Return: True if updated
	def needTable(self, table, cols, indexes=None, version=1):
		current_version = self.db.getTableVersion(table)
		if int(current_version) < int(version): # Table need update or not extis
			self.db.log.info("Table %s outdated...version: %s need: %s, rebuilding..." % (table, current_version, version))
			self.createTable(table, cols)
			if indexes: self.createIndexes(table, indexes)
			self.execute("INSERT OR REPLACE INTO keyvalue ?", 
				{"json_id": 0, "key": "table.%s.version" % table, "value": version}
			)
			return True
		else: # Not changed
			return False


	# Get or create a row for json file
	# Return: The database row
	def getJsonRow(self, file_path):
		directory, file_name = re.match("^(.*?)/*([^/]*)$", file_path).groups()
		if self.db.schema["version"] == 1:
			res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"path": file_path})
			row = res.fetchone()
			if not row: # No row yet, create it
				self.execute("INSERT INTO json ?", {"path": file_path})
				res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"path": file_path})
				row = res.fetchone()
		else:
			res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"directory": directory, "file_name": file_name})
			row = res.fetchone()
			if not row: # No row yet, create it
				self.execute("INSERT INTO json ?", {"directory": directory, "file_name": file_name})
				res = self.execute("SELECT * FROM json WHERE ? LIMIT 1", {"directory": directory, "file_name": file_name})
				row = res.fetchone()
		return row

	def close(self):
		self.cursor.close()

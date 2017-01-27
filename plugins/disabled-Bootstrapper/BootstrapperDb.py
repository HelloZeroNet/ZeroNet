import time
import re

import gevent

from Config import config
from Db import Db
from util import helper


class BootstrapperDb(Db):
    def __init__(self):
        self.version = 6
        self.hash_ids = {}  # hash -> id cache
        super(BootstrapperDb, self).__init__({"db_name": "Bootstrapper"}, "%s/bootstrapper.db" % config.data_dir)
        self.foreign_keys = True
        self.checkTables()
        self.updateHashCache()
        gevent.spawn(self.cleanup)

    def cleanup(self):
        while 1:
            self.execute("DELETE FROM peer WHERE date_announced < DATETIME('now', '-40 minute')")
            time.sleep(4*60)

    def updateHashCache(self):
        res = self.execute("SELECT * FROM hash")
        self.hash_ids = {str(row["hash"]): row["hash_id"] for row in res}
        self.log.debug("Loaded %s hash_ids" % len(self.hash_ids))

    def checkTables(self):
        version = int(self.execute("PRAGMA user_version").fetchone()[0])
        self.log.debug("Db version: %s, needed: %s" % (version, self.version))
        if version < self.version:
            self.createTables()
        else:
            self.execute("VACUUM")

    def createTables(self):
        # Delete all tables
        self.execute("PRAGMA writable_schema = 1")
        self.execute("DELETE FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')")
        self.execute("PRAGMA writable_schema = 0")
        self.execute("VACUUM")
        self.execute("PRAGMA INTEGRITY_CHECK")
        # Create new tables
        self.execute("""
            CREATE TABLE peer (
                peer_id        INTEGER  PRIMARY KEY ASC AUTOINCREMENT NOT NULL UNIQUE,
                port           INTEGER NOT NULL,
                ip4            TEXT,
                onion          TEXT,
                date_added     DATETIME DEFAULT (CURRENT_TIMESTAMP),
                date_announced DATETIME DEFAULT (CURRENT_TIMESTAMP)
            );
        """)

        self.execute("""
            CREATE TABLE peer_to_hash (
                peer_to_hash_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                peer_id         INTEGER REFERENCES peer (peer_id) ON DELETE CASCADE,
                hash_id         INTEGER REFERENCES hash (hash_id)
            );
        """)
        self.execute("CREATE INDEX peer_id ON peer_to_hash (peer_id);")
        self.execute("CREATE INDEX hash_id ON peer_to_hash (hash_id);")

        self.execute("""
            CREATE TABLE hash (
                hash_id    INTEGER  PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                hash       BLOB     UNIQUE NOT NULL,
                date_added DATETIME DEFAULT (CURRENT_TIMESTAMP)
            );
        """)
        self.execute("PRAGMA user_version = %s" % self.version)

    def getHashId(self, hash):
        if hash not in self.hash_ids:
            self.log.debug("New hash: %s" % repr(hash))
            self.execute("INSERT OR IGNORE INTO hash ?", {"hash": buffer(hash)})
            self.hash_ids[hash] = self.cur.cursor.lastrowid
        return self.hash_ids[hash]

    def peerAnnounce(self, ip4=None, onion=None, port=None, hashes=[], onion_signed=False, delete_missing_hashes=False):
        hashes_ids_announced = []
        for hash in hashes:
            hashes_ids_announced.append(self.getHashId(hash))

        if not ip4 and not onion:
            return 0

        # Check user
        if onion:
            res = self.execute("SELECT * FROM peer WHERE ? LIMIT 1", {"onion": onion})
        else:
            res = self.execute("SELECT * FROM peer WHERE ? LIMIT 1", {"ip4": ip4, "port": port})

        user_row = res.fetchone()
        if user_row:
            peer_id = user_row["peer_id"]
            self.execute("UPDATE peer SET date_announced = DATETIME('now') WHERE ?", {"peer_id": peer_id})
        else:
            self.log.debug("New peer: %s %s signed: %s" % (ip4, onion, onion_signed))
            if onion and not onion_signed:
                return len(hashes)
            self.execute("INSERT INTO peer ?", {"ip4": ip4, "onion": onion, "port": port})
            peer_id = self.cur.cursor.lastrowid

        # Check user's hashes
        res = self.execute("SELECT * FROM peer_to_hash WHERE ?", {"peer_id": peer_id})
        hash_ids_db = [row["hash_id"] for row in res]
        if hash_ids_db != hashes_ids_announced:
            hash_ids_added = set(hashes_ids_announced) - set(hash_ids_db)
            hash_ids_removed = set(hash_ids_db) - set(hashes_ids_announced)
            if not onion or onion_signed:
                for hash_id in hash_ids_added:
                    self.execute("INSERT INTO peer_to_hash ?", {"peer_id": peer_id, "hash_id": hash_id})
                if hash_ids_removed and delete_missing_hashes:
                    self.execute("DELETE FROM peer_to_hash WHERE ?", {"peer_id": peer_id, "hash_id": list(hash_ids_removed)})

            return len(hash_ids_added) + len(hash_ids_removed)
        else:
            return 0

    def peerList(self, hash, ip4=None, onions=[], port=None, limit=30, need_types=["ip4", "onion"]):
        hash_peers = {"ip4": [], "onion": []}
        if limit == 0:
            return hash_peers
        hashid = self.getHashId(hash)

        where = "hash_id = :hashid"
        if onions:
            onions_escaped = ["'%s'" % re.sub("[^a-z0-9,]", "", onion) for onion in onions if type(onion) is str]
            where += " AND (onion NOT IN (%s) OR onion IS NULL)" % ",".join(onions_escaped)
        elif ip4:
            where += " AND (NOT (ip4 = :ip4 AND port = :port) OR ip4 IS NULL)"

        query = """
            SELECT ip4, port, onion
            FROM peer_to_hash
            LEFT JOIN peer USING (peer_id)
            WHERE %s
            ORDER BY date_announced DESC
            LIMIT :limit
        """ % where
        res = self.execute(query, {"hashid": hashid, "ip4": ip4, "onions": onions, "port": port, "limit": limit})

        for row in res:
            if row["ip4"] and "ip4" in need_types:
                hash_peers["ip4"].append(
                    helper.packAddress(row["ip4"], row["port"])
                )
            if row["onion"] and "onion" in need_types:
                hash_peers["onion"].append(
                    helper.packOnionAddress(row["onion"], row["port"])
                )

        return hash_peers

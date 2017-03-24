import time
import sqlite3
import random
import atexit

import gevent
from Plugin import PluginManager


@PluginManager.registerTo("ContentDb")
class ContentDbPlugin(object):
    def __init__(self, *args, **kwargs):
        atexit.register(self.saveAllPeers)
        super(ContentDbPlugin, self).__init__(*args, **kwargs)

    def getSchema(self):
        schema = super(ContentDbPlugin, self).getSchema()

        schema["tables"]["peer"] = {
            "cols": [
                ["site_id", "INTEGER REFERENCES site (site_id) ON DELETE CASCADE"],
                ["address", "TEXT NOT NULL"],
                ["port", "INTEGER NOT NULL"],
                ["hashfield", "BLOB"],
                ["time_added", "INTEGER NOT NULL"]
            ],
            "indexes": [
                "CREATE UNIQUE INDEX peer_key ON peer (site_id, address, port)"
            ],
            "schema_changed": 1
        }

        return schema

    def loadPeers(self, site):
        s = time.time()
        site_id = self.site_ids.get(site.address)
        res = self.execute("SELECT * FROM peer WHERE site_id = :site_id", {"site_id": site_id})
        num = 0
        num_hashfield = 0
        for row in res:
            peer = site.addPeer(row["address"], row["port"])
            if not peer:  # Already exist
                continue
            if row["hashfield"]:
                peer.hashfield.replaceFromString(row["hashfield"])
                num_hashfield += 1
            peer.time_added = row["time_added"]
            peer.reputation = int((time.time() - peer.time_added) / (60 * 60 * 24))  # Older peers has more reputation
            num += 1
        site.log.debug("%s peers (%s with hashfield) loaded in %.3fs" % (num, num_hashfield, time.time() - s))

    def iteratePeers(self, site):
        site_id = self.site_ids.get(site.address)
        for key, peer in site.peers.iteritems():
            address, port = key.split(":")
            if peer.has_hashfield:
                hashfield = sqlite3.Binary(peer.hashfield.tostring())
            else:
                hashfield = ""
            yield (site_id, address, port, hashfield, int(peer.time_added))

    def savePeers(self, site, spawn=False):
        if spawn:
            # Save peers every hour (+random some secs to not update very site at same time)
            gevent.spawn_later(60 * 60 + random.randint(0, 60), self.savePeers, site, spawn=True)
        if not site.peers:
            site.log.debug("Peers not saved: No peers found")
            return
        s = time.time()
        site_id = self.site_ids.get(site.address)
        cur = self.getCursor()
        cur.execute("BEGIN")
        self.execute("DELETE FROM peer WHERE site_id = :site_id", {"site_id": site_id})
        self.cur.cursor.executemany(
            "INSERT INTO peer (site_id, address, port, hashfield, time_added) VALUES (?, ?, ?, ?, ?)",
            self.iteratePeers(site)
        )
        cur.execute("END")
        site.log.debug("Peers saved in %.3fs" % (time.time() - s))

    def initSite(self, site):
        super(ContentDbPlugin, self).initSite(site)
        gevent.spawn_later(0.5, self.loadPeers, site)
        gevent.spawn_later(60*60, self.savePeers, site, spawn=True)

    def saveAllPeers(self):
        for site in self.sites.values():
            try:
                self.savePeers(site)
            except Exception, err:
                site.log.error("Save peer error: %s" % err)

import time
import itertools

import gevent

from Config import config
from util import helper
from Plugin import PluginManager
from .ChartDb import ChartDb
from .ChartCollector import ChartCollector

if "db" not in locals().keys():  # Share on reloads
    db = ChartDb()
    gevent.spawn_later(10 * 60, db.archive)
    helper.timer(60 * 60 * 6, db.archive)
    collector = ChartCollector(db)

@PluginManager.registerTo("SiteManager")
class SiteManagerPlugin(object):
    def load(self, *args, **kwargs):
        back = super(SiteManagerPlugin, self).load(*args, **kwargs)
        collector.setInitialLastValues(self.sites.values())
        return back

    def delete(self, address, *args, **kwargs):
        db.deleteSite(address)
        return super(SiteManagerPlugin, self).delete(address, *args, **kwargs)

@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def actionChartDbQuery(self, to, query, params=None):
        if not "ADMIN" in self.permissions:
            return {"error": "No permission"}

        if config.debug or config.verbose:
            s = time.time()
        rows = []
        try:
            if not query.strip().upper().startswith("SELECT"):
                raise Exception("Only SELECT query supported")
            res = db.execute(query, params)
        except Exception as err:  # Response the error to client
            self.log.error("ChartDbQuery error: %s" % err)
            return {"error": str(err)}
        # Convert result to dict
        for row in res:
            rows.append(dict(row))
        if config.verbose and time.time() - s > 0.1:  # Log slow query
            self.log.debug("Slow query: %s (%.3fs)" % (query, time.time() - s))
        return rows

    def actionChartGetPeerLocations(self, to):
        if not "ADMIN" in self.permissions:
            return {"error": "No permission"}

        peers = {}
        for site in self.server.sites.values():
            peers.update(site.peers)
        peer_locations = self.getPeerLocations(peers)
        return peer_locations

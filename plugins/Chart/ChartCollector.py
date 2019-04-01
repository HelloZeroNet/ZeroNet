import time
import sys
import collections
import itertools
import logging

import gevent
from util import helper
from Config import config


class ChartCollector(object):
    def __init__(self, db):
        self.db = db
        if config.action == "main":
            gevent.spawn_later(60 * 3, self.collector)
        self.log = logging.getLogger("ChartCollector")
        self.last_values = collections.defaultdict(dict)

    def setInitialLastValues(self, sites):
        # Recover last value of site bytes/sent
        for site in sites:
            self.last_values["site:" + site.address]["site_bytes_recv"] = site.settings.get("bytes_recv", 0)
            self.last_values["site:" + site.address]["site_bytes_sent"] = site.settings.get("bytes_sent", 0)

    def getCollectors(self):
        collectors = {}
        import main
        file_server = main.file_server
        sites = file_server.sites
        if not sites:
            return collectors
        content_db = list(sites.values())[0].content_manager.contents.db

        # Connection stats
        collectors["connection"] = lambda: len(file_server.connections)
        collectors["connection_in"] = (
            lambda: len([1 for connection in file_server.connections if connection.type == "in"])
        )
        collectors["connection_onion"] = (
            lambda: len([1 for connection in file_server.connections if connection.ip.endswith(".onion")])
        )
        collectors["connection_ping_avg"] = (
            lambda: round(1000 * helper.avg(
                [connection.last_ping_delay for connection in file_server.connections if connection.last_ping_delay]
            ))
        )
        collectors["connection_ping_min"] = (
            lambda: round(1000 * min(
                [connection.last_ping_delay for connection in file_server.connections if connection.last_ping_delay]
            ))
        )
        collectors["connection_rev_avg"] = (
            lambda: helper.avg(
                [connection.handshake["rev"] for connection in file_server.connections if connection.handshake]
            )
        )

        # Request stats
        collectors["file_bytes_recv|change"] = lambda: file_server.bytes_recv
        collectors["file_bytes_sent|change"] = lambda: file_server.bytes_sent
        collectors["request_num_recv|change"] = lambda: file_server.num_recv
        collectors["request_num_sent|change"] = lambda: file_server.num_sent

        # Limit
        collectors["optional_limit"] = lambda: content_db.getOptionalLimitBytes()
        collectors["optional_used"] = lambda: content_db.getOptionalUsedBytes()
        collectors["optional_downloaded"] = lambda: sum([site.settings.get("optional_downloaded", 0) for site in sites.values()])

        # Peers
        collectors["peer"] = lambda peers: len(peers)
        collectors["peer_onion"] = lambda peers: len([True for peer in peers if ".onion" in peer])

        # Size
        collectors["size"] = lambda: sum([site.settings.get("size", 0) for site in sites.values()])
        collectors["size_optional"] = lambda: sum([site.settings.get("size_optional", 0) for site in sites.values()])
        collectors["content"] = lambda: sum([len(site.content_manager.contents) for site in sites.values()])

        return collectors

    def getSiteCollectors(self):
        site_collectors = {}

        # Size
        site_collectors["site_size"] = lambda site: site.settings.get("size", 0)
        site_collectors["site_size_optional"] = lambda site: site.settings.get("size_optional", 0)
        site_collectors["site_optional_downloaded"] = lambda site: site.settings.get("optional_downloaded", 0)
        site_collectors["site_content"] = lambda site: len(site.content_manager.contents)

        # Data transfer
        site_collectors["site_bytes_recv|change"] = lambda site: site.settings.get("bytes_recv", 0)
        site_collectors["site_bytes_sent|change"] = lambda site: site.settings.get("bytes_sent", 0)

        # Peers
        site_collectors["site_peer"] = lambda site: len(site.peers)
        site_collectors["site_peer_onion"] = lambda site: len(
            [True for peer in site.peers.values() if peer.ip.endswith(".onion")]
        )
        site_collectors["site_peer_connected"] = lambda site: len([True for peer in site.peers.values() if peer.connection])

        return site_collectors

    def getUniquePeers(self):
        import main
        sites = main.file_server.sites
        return set(itertools.chain.from_iterable(
            [site.peers.keys() for site in sites.values()]
        ))

    def collectDatas(self, collectors, last_values, site=None):
        if site is None:
            peers = self.getUniquePeers()
        datas = {}
        for key, collector in collectors.items():
            try:
                if site:
                    value = collector(site)
                elif key.startswith("peer"):
                    value = collector(peers)
                else:
                    value = collector()
            except Exception as err:
                self.log.info("Collector %s error: %s" % (key, err))
                value = None

            if "|change" in key:  # Store changes relative to last value
                key = key.replace("|change", "")
                last_value = last_values.get(key, 0)
                last_values[key] = value
                value = value - last_value

            if value is None:
                datas[key] = None
            else:
                datas[key] = round(value, 3)
        return datas

    def collectGlobal(self, collectors, last_values):
        now = int(time.time())
        s = time.time()
        datas = self.collectDatas(collectors, last_values["global"])
        values = []
        for key, value in datas.items():
            values.append((self.db.getTypeId(key), value, now))
        self.log.debug("Global collectors done in %.3fs" % (time.time() - s))

        s = time.time()
        cur = self.db.getCursor()
        cur.cursor.executemany("INSERT INTO data (type_id, value, date_added) VALUES (?, ?, ?)", values)
        cur.close()
        self.log.debug("Global collectors inserted in %.3fs" % (time.time() - s))

    def collectSites(self, sites, collectors, last_values):
        now = int(time.time())
        s = time.time()
        values = []
        for address, site in sites.items():
            site_datas = self.collectDatas(collectors, last_values["site:%s" % address], site)
            for key, value in site_datas.items():
                values.append((self.db.getTypeId(key), self.db.getSiteId(address), value, now))
            time.sleep(0.001)
        self.log.debug("Site collections done in %.3fs" % (time.time() - s))

        s = time.time()
        cur = self.db.getCursor()
        cur.cursor.executemany("INSERT INTO data (type_id, site_id, value, date_added) VALUES (?, ?, ?, ?)", values)
        cur.close()
        self.log.debug("Site collectors inserted in %.3fs" % (time.time() - s))

    def collector(self):
        collectors = self.getCollectors()
        site_collectors = self.getSiteCollectors()
        import main
        sites = main.file_server.sites
        i = 0
        while 1:
            self.collectGlobal(collectors, self.last_values)
            if i % 12 == 0:  # Only collect sites data every hour
                self.collectSites(sites, site_collectors, self.last_values)
            time.sleep(60 * 5)
            i += 1

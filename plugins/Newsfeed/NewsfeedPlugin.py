import time
import re

from Plugin import PluginManager
from Db import DbQuery
from Debug import Debug


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def formatSiteInfo(self, site, create_user=True):
        site_info = super(UiWebsocketPlugin, self).formatSiteInfo(site, create_user=True)
        feed_following = self.user.sites[site.address].get("follow", None)
        if feed_following == None:
            site_info["feed_follow_num"] = None
        else:
            site_info["feed_follow_num"] = len(feed_following)
        return site_info

    def actionFeedFollow(self, to, feeds):
        self.user.setFeedFollow(self.site.address, feeds)
        self.user.save()
        self.response(to, "ok")

    def actionFeedListFollow(self, to):
        feeds = self.user.sites[self.site.address].get("follow", {})
        self.response(to, feeds)

    def actionFeedQuery(self, to, limit=10, day_limit=3):
        if "ADMIN" not in self.site.settings["permissions"]:
            return self.response(to, "FeedQuery not allowed")

        from Site import SiteManager
        rows = []
        stats = []

        total_s = time.time()
        num_sites = 0

        for address, site_data in self.user.sites.iteritems():
            feeds = site_data.get("follow")
            if not feeds:
                continue
            if type(feeds) is not dict:
                self.log.debug("Invalid feed for site %s" % address)
                continue
            num_sites += 1
            for name, query_set in feeds.iteritems():
                site = SiteManager.site_manager.get(address)
                if not site or not site.storage.has_db:
                    continue

                s = time.time()
                try:
                    query_raw, params = query_set
                    query_parts = re.split(r"UNION(?:\s+ALL|)", query_raw)
                    for i, query_part in enumerate(query_parts):
                        db_query = DbQuery(query_part)
                        if day_limit:
                            where = " WHERE %s > strftime('%%s', 'now', '-%s day')" % (db_query.fields.get("date_added", "date_added"), day_limit)
                            if "WHERE" in query_part:
                                query_part = re.sub("WHERE (.*?)(?=$| GROUP BY)", where+" AND (\\1)", query_part)
                            else:
                                query_part += where
                        query_parts[i] = query_part
                    query = " UNION ".join(query_parts)

                    if ":params" in query:
                        query = query.replace(":params", ",".join(["?"] * len(params)))
                        res = site.storage.query(query + " ORDER BY date_added DESC LIMIT %s" % limit, params * query_raw.count(":params"))
                    else:
                        res = site.storage.query(query + " ORDER BY date_added DESC LIMIT %s" % limit)

                except Exception as err:  # Log error
                    self.log.error("%s feed query %s error: %s" % (address, name, Debug.formatException(err)))
                    stats.append({"site": site.address, "feed_name": name, "error": str(err), "query": query})
                    continue

                for row in res:
                    row = dict(row)
                    if row["date_added"] > 1000000000000:  # Formatted as millseconds
                        row["date_added"] = row["date_added"] / 1000
                    if "date_added" not in row or row["date_added"] > time.time() + 120:
                        self.log.debug("Newsfeed from the future from from site %s" % address)
                        continue  # Feed item is in the future, skip it
                    row["site"] = address
                    row["feed_name"] = name
                    rows.append(row)
                stats.append({"site": site.address, "feed_name": name, "taken": round(time.time() - s, 3)})
                time.sleep(0.0001)
        return self.response(to, {"rows": rows, "stats": stats, "num": len(rows), "sites": num_sites, "taken": round(time.time() - total_s, 3)})

    def parseSearch(self, search):
        parts = re.split("(site|type):", search)
        if len(parts) > 1:  # Found filter
            search_text = parts[0]
            parts = [part.strip() for part in parts]
            filters = dict(zip(parts[1::2], parts[2::2]))
        else:
            search_text = search
            filters = {}
        return [search_text, filters]

    def actionFeedSearch(self, to, search):
        if "ADMIN" not in self.site.settings["permissions"]:
            return self.response(to, "FeedSearch not allowed")

        from Site import SiteManager
        rows = []
        stats = []
        num_sites = 0
        total_s = time.time()

        search_text, filters = self.parseSearch(search)

        for address, site in SiteManager.site_manager.list().iteritems():
            if not site.storage.has_db:
                continue

            if "site" in filters:
                if filters["site"].lower() not in [site.address, site.content_manager.contents["content.json"].get("title").lower()]:
                    continue

            if site.storage.db:  # Database loaded
                feeds = site.storage.db.schema.get("feeds")
            else:
                try:
                    feeds = site.storage.loadJson("dbschema.json").get("feeds")
                except:
                    continue

            if not feeds:
                continue

            num_sites += 1

            for name, query in feeds.iteritems():
                s = time.time()
                try:
                    db_query = DbQuery(query)

                    params = []
                    # Filters
                    if search_text:
                        db_query.wheres.append("(%s LIKE ? OR %s LIKE ?)" % (db_query.fields["body"], db_query.fields["title"]))
                        search_like = "%" + search_text.replace(" ", "%") + "%"
                        params.append(search_like)
                        params.append(search_like)
                    if filters.get("type") and filters["type"] not in query:
                        continue

                    # Order
                    db_query.parts["ORDER BY"] = "date_added DESC"
                    db_query.parts["LIMIT"] = "30"

                    res = site.storage.query(str(db_query), params)
                except Exception, err:
                    self.log.error("%s feed query %s error: %s" % (address, name, Debug.formatException(err)))
                    stats.append({"site": site.address, "feed_name": name, "error": str(err), "query": query})
                    continue
                for row in res:
                    row = dict(row)
                    if row["date_added"] > time.time() + 120:
                        continue  # Feed item is in the future, skip it
                    row["site"] = address
                    row["feed_name"] = name
                    rows.append(row)
                stats.append({"site": site.address, "feed_name": name, "taken": round(time.time() - s, 3)})
        return self.response(to, {"rows": rows, "num": len(rows), "sites": num_sites, "taken": round(time.time() - total_s, 3), "stats": stats})


@PluginManager.registerTo("User")
class UserPlugin(object):
    # Set queries that user follows
    def setFeedFollow(self, address, feeds):
        site_data = self.getSiteData(address)
        site_data["follow"] = feeds
        self.save()
        return site_data

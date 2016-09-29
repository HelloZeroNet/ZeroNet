import time
import re

from Plugin import PluginManager
from Db import DbQuery


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def actionFeedFollow(self, to, feeds):
        self.user.setFeedFollow(self.site.address, feeds)
        self.user.save()
        self.response(to, "ok")

    def actionFeedListFollow(self, to):
        feeds = self.user.sites[self.site.address].get("follow", {})
        self.response(to, feeds)

    def actionFeedQuery(self, to):
        if "ADMIN" not in self.site.settings["permissions"]:
            return self.response(to, "FeedQuery not allowed")

        from Site import SiteManager
        rows = []
        for address, site_data in self.user.sites.iteritems():
            feeds = site_data.get("follow")
            if not feeds:
                continue
            for name, query_set in feeds.iteritems():
                site = SiteManager.site_manager.get(address)
                try:
                    query, params = query_set
                    query_parts = query.split("UNION")
                    for i, query_part in enumerate(query_parts):
                        db_query = DbQuery(query_part)
                        where = " WHERE %s > strftime('%%s', 'now', '-3 day')" % db_query.fields.get("date_added", "date_added")
                        if "WHERE" in query_part:
                            query_part = re.sub("WHERE (.*?)(?=$| GROUP BY)", where+" AND (\\1)", query_part)
                        else:
                            query_part += where
                        query_parts[i] = query_part
                    query = " UNION ".join(query_parts)

                    if ":params" in query:
                        query = query.replace(":params", ",".join(["?"] * len(params)))
                        res = site.storage.query(query + " ORDER BY date_added DESC LIMIT 10", params)
                    else:
                        res = site.storage.query(query + " ORDER BY date_added DESC LIMIT 10")
                except Exception, err:  # Log error
                    self.log.error("%s feed query %s error: %s" % (address, name, err))
                    continue
                for row in res:
                    row = dict(row)
                    if "date_added" not in row or row["date_added"] > time.time() + 120:
                        continue  # Feed item is in the future, skip it
                    row["site"] = address
                    row["feed_name"] = name
                    rows.append(row)
        return self.response(to, rows)

    def actionFeedSearch(self, to, search):
        if "ADMIN" not in self.site.settings["permissions"]:
            return self.response(to, "FeedSearch not allowed")

        from Site import SiteManager
        rows = []
        num_sites = 0
        s = time.time()
        for address, site in SiteManager.site_manager.list().iteritems():
            if not site.storage.has_db:
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
                try:
                    db_query = DbQuery(query)
                    db_query.wheres.append("%s LIKE ? OR %s LIKE ?" % (db_query.fields["body"], db_query.fields["title"]))
                    db_query.parts["ORDER BY"] = "date_added DESC"
                    db_query.parts["LIMIT"] = "30"

                    search_like = "%" + search.replace(" ", "%") + "%"
                    res = site.storage.query(str(db_query), [search_like, search_like])
                except Exception, err:
                    self.log.error("%s feed query %s error: %s" % (address, name, err))
                    continue
                for row in res:
                    row = dict(row)
                    if row["date_added"] > time.time() + 120:
                        continue  # Feed item is in the future, skip it
                    row["site"] = address
                    row["feed_name"] = name
                    rows.append(row)
        return self.response(to, {"rows": rows, "num": len(rows), "sites": num_sites, "taken": time.time() - s})


@PluginManager.registerTo("User")
class UserPlugin(object):
    # Set queries that user follows
    def setFeedFollow(self, address, feeds):
        site_data = self.getSiteData(address)
        site_data["follow"] = feeds
        self.save()
        return site_data

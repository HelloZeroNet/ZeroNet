import re
import time
import cgi

import gevent

from Plugin import PluginManager
from Config import config
from util import helper
from Translate import Translate

if "_" not in locals():
    _ = Translate("plugins/OptionalManager/languages/")

@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def __init__(self, *args, **kwargs):
        self.time_peer_numbers_updated = 0
        super(UiWebsocketPlugin, self).__init__(*args, **kwargs)

    def actionSiteSign(self, to, privatekey=None, inner_path="content.json", *args, **kwargs):
        # Add file to content.db and set it as pinned
        content_db = self.site.content_manager.contents.db
        content_inner_dir = helper.getDirname(inner_path)
        content_db.my_optional_files[self.site.address + "/" + content_inner_dir] = time.time()
        if len(content_db.my_optional_files) > 50:  # Keep only last 50
            oldest_key = min(
                content_db.my_optional_files.iterkeys(),
                key=(lambda key: content_db.my_optional_files[key])
            )
            del content_db.my_optional_files[oldest_key]

        return super(UiWebsocketPlugin, self).actionSiteSign(to, privatekey, inner_path, *args, **kwargs)

    def updatePeerNumbers(self):
        content_db = self.site.content_manager.contents.db
        content_db.updatePeerNumbers()
        self.site.updateWebsocket(peernumber_updated=True)

    def addBigfileInfo(self, row):
        content_db = self.site.content_manager.contents.db
        site = content_db.sites[row["address"]]
        if not site.settings.get("has_bigfile"):
            return False

        file_info = site.content_manager.getFileInfo(row["inner_path"])
        if not file_info.get("piece_size"):
            return False

        sha512 = file_info["sha512"]
        if sha512 in site.storage.piecefields:
            piecefield = site.storage.piecefields[sha512].tostring()
        else:
            piecefield = None

        if piecefield:
            row["pieces"] = len(piecefield)
            row["pieces_downloaded"] = piecefield.count("1")
            row["downloaded_percent"] = 100 * row["pieces_downloaded"] / row["pieces"]
            row["bytes_downloaded"] = row["pieces_downloaded"] * file_info["piece_size"]
            row["is_downloading"] = bool(next((task for task in site.worker_manager.tasks if task["inner_path"].startswith(row["inner_path"])), False))

        # Add leech / seed stats
        row["peer_seed"] = 0
        row["peer_leech"] = 0
        for peer in site.peers.itervalues():
            if not peer.time_piecefields_updated or sha512 not in peer.piecefields:
                continue
            peer_piecefield = peer.piecefields[sha512].tostring()
            if not peer_piecefield:
                continue
            if peer_piecefield == "1" * len(peer_piecefield):
                row["peer_seed"] += 1
            else:
                row["peer_leech"] += 1

        # Add myself
        if piecefield:
            if row["pieces_downloaded"] == row["pieces"]:
                row["peer_seed"] += 1
            else:
                row["peer_leech"] += 1

        return True

    # Optional file functions

    def actionOptionalFileList(self, to, address=None, orderby="time_downloaded DESC", limit=10, filter="downloaded"):
        if not address:
            address = self.site.address

        # Update peer numbers if necessary
        content_db = self.site.content_manager.contents.db
        if time.time() - content_db.time_peer_numbers_updated > 60 * 1 and time.time() - self.time_peer_numbers_updated > 60 * 5:
            # Start in new thread to avoid blocking
            self.time_peer_numbers_updated = time.time()
            gevent.spawn(self.updatePeerNumbers)

        if address == "all" and "ADMIN" not in self.permissions:
            return self.response(to, {"error": "Forbidden"})

        if not self.hasSitePermission(address):
            return self.response(to, {"error": "Forbidden"})

        if not all([re.match("^[a-z_*/+-]+( DESC| ASC|)$", part.strip()) for part in orderby.split(",")]):
            return self.response(to, "Invalid order_by")

        if type(limit) != int:
            return self.response(to, "Invalid limit")

        back = []
        content_db = self.site.content_manager.contents.db

        wheres = {}
        if "bigfile" in filter:
            wheres["size >"] = 1024 * 1024 * 10
        if "downloaded" in filter:
            wheres["is_downloaded"] = 1

        if address == "all":
            join = "LEFT JOIN site USING (site_id)"
        else:
            wheres["site_id"] = content_db.site_ids[address]
            join = ""

        query = "SELECT * FROM file_optional %s WHERE ? ORDER BY %s LIMIT %s" % (join, orderby, limit)

        for row in content_db.execute(query, wheres):
            row = dict(row)
            if address != "all":
                row["address"] = address

            if row["size"] > 1024 * 1024:
                has_info = self.addBigfileInfo(row)
            else:
                has_info = False

            if not has_info:
                if row["is_downloaded"]:
                    row["bytes_downloaded"] = row["size"]
                    row["downloaded_percent"] = 100
                else:
                    row["bytes_downloaded"] = 0
                    row["downloaded_percent"] = 0

            back.append(row)
        self.response(to, back)

    def actionOptionalFileInfo(self, to, inner_path):
        content_db = self.site.content_manager.contents.db
        site_id = content_db.site_ids[self.site.address]

        # Update peer numbers if necessary
        if time.time() - content_db.time_peer_numbers_updated > 60 * 1 and time.time() - self.time_peer_numbers_updated > 60 * 5:
            # Start in new thread to avoid blocking
            self.time_peer_numbers_updated = time.time()
            gevent.spawn(self.updatePeerNumbers)

        query = "SELECT * FROM file_optional WHERE site_id = :site_id AND inner_path = :inner_path LIMIT 1"
        res = content_db.execute(query, {"site_id": site_id, "inner_path": inner_path})
        row = next(res, None)
        if row:
            row = dict(row)
            if row["size"] > 1024 * 1024:
                row["address"] = self.site.address
                self.addBigfileInfo(row)
            self.response(to, row)
        else:
            self.response(to, None)

    def setPin(self, inner_path, is_pinned, address=None):
        if not address:
            address = self.site.address

        if not self.hasSitePermission(address):
            return {"error": "Forbidden"}

        site = self.server.sites[address]

        content_db = site.content_manager.contents.db
        site_id = content_db.site_ids[site.address]
        content_db.execute("UPDATE file_optional SET is_pinned = %s WHERE ?" % is_pinned, {"site_id": site_id, "inner_path": inner_path})

        return "ok"

    def actionOptionalFilePin(self, to, inner_path, address=None):
        back = self.setPin(inner_path, 1, address)
        if back == "ok":
            self.cmd("notification", ["done", _["Pinned %s files"] % len(inner_path) if type(inner_path) is list else 1, 5000])
        self.response(to, back)

    def actionOptionalFileUnpin(self, to, inner_path, address=None):
        back = self.setPin(inner_path, 0, address)
        if back == "ok":
            self.cmd("notification", ["done", _["Removed pin from %s files"] % len(inner_path) if type(inner_path) is list else 1, 5000])
        self.response(to, back)

    def actionOptionalFileDelete(self, to, inner_path, address=None):
        if not address:
            address = self.site.address

        if not self.hasSitePermission(address):
            return self.response(to, {"error": "Forbidden"})

        site = self.server.sites[address]

        content_db = site.content_manager.contents.db
        site_id = content_db.site_ids[site.address]

        res = content_db.execute("SELECT * FROM file_optional WHERE ? LIMIT 1", {"site_id": site_id, "inner_path": inner_path, "is_downloaded": 1})
        row = next(res, None)

        if not row:
            return self.response(to, {"error": "Not found in content.db"})

        removed = site.content_manager.optionalRemove(inner_path, row["hash_id"], row["size"])
        # if not removed:
        #    return self.response(to, {"error": "Not found in hash_id: %s" % row["hash_id"]})

        content_db.execute("UPDATE file_optional SET is_downloaded = 0, is_pinned = 0, peer = peer - 1 WHERE ?", {"site_id": site_id, "inner_path": inner_path})

        try:
            site.storage.delete(inner_path)
        except Exception as err:
            return self.response(to, {"error": "File delete error: %s" % err})
        site.updateWebsocket(file_delete=inner_path)

        self.response(to, "ok")


    # Limit functions

    def actionOptionalLimitStats(self, to):
        if "ADMIN" not in self.site.settings["permissions"]:
            return self.response(to, "Forbidden")

        back = {}
        back["limit"] = config.optional_limit
        back["used"] = self.site.content_manager.contents.db.execute(
            "SELECT SUM(size) FROM file_optional WHERE is_downloaded = 1 AND is_pinned = 0"
        ).fetchone()[0]
        back["free"] = helper.getFreeSpace()

        self.response(to, back)

    def actionOptionalLimitSet(self, to, limit):
        if "ADMIN" not in self.site.settings["permissions"]:
            return self.response(to, {"error": "Forbidden"})
        config.optional_limit = re.sub("\.0+$", "", limit)  # Remove unnecessary digits from end
        config.saveValue("optional_limit", limit)
        self.response(to, "ok")

    # Distribute help functions

    def actionOptionalHelpList(self, to, address=None):
        if not address:
            address = self.site.address

        if not self.hasSitePermission(address):
            return self.response(to, {"error": "Forbidden"})

        site = self.server.sites[address]

        self.response(to, site.settings.get("optional_help", {}))

    def actionOptionalHelp(self, to, directory, title, address=None):
        if not address:
            address = self.site.address

        if not self.hasSitePermission(address):
            return self.response(to, {"error": "Forbidden"})

        site = self.server.sites[address]
        content_db = site.content_manager.contents.db
        site_id = content_db.site_ids[address]

        if "optional_help" not in site.settings:
            site.settings["optional_help"] = {}

        stats = content_db.execute(
            "SELECT COUNT(*) AS num, SUM(size) AS size FROM file_optional WHERE site_id = :site_id AND inner_path LIKE :inner_path",
            {"site_id": site_id, "inner_path": directory + "%"}
        ).fetchone()
        stats = dict(stats)

        if not stats["size"]:
            stats["size"] = 0
        if not stats["num"]:
            stats["num"] = 0

        self.cmd("notification", [
            "done",
            _["You started to help distribute <b>%s</b>.<br><small>Directory: %s</small>"] %
            (cgi.escape(title), cgi.escape(directory)),
            10000
        ])

        site.settings["optional_help"][directory] = title

        self.response(to, dict(stats))

    def actionOptionalHelpRemove(self, to, directory, address=None):
        if not address:
            address = self.site.address

        if not self.hasSitePermission(address):
            return self.response(to, {"error": "Forbidden"})

        site = self.server.sites[address]

        try:
            del site.settings["optional_help"][directory]
            self.response(to, "ok")
        except Exception:
            self.response(to, {"error": "Not found"})

    def cbOptionalHelpAll(self, to, site, value):
        site.settings["autodownloadoptional"] = value
        self.response(to, value)

    def actionOptionalHelpAll(self, to, value, address=None):
        if not address:
            address = self.site.address

        if not self.hasSitePermission(address):
            return self.response(to, {"error": "Forbidden"})

        site = self.server.sites[address]

        if value:
            if "ADMIN" in self.site.settings["permissions"]:
                self.cbOptionalHelpAll(to, site, True)
            else:
                site_title = site.content_manager.contents["content.json"].get("title", address)
                self.cmd(
                    "confirm",
                    [
                        _["Help distribute all new optional files on site <b>%s</b>"] % cgi.escape(site_title),
                        _["Yes, I want to help!"]
                    ],
                    lambda (res): self.cbOptionalHelpAll(to, site, True)
                )
        else:
            site.settings["autodownloadoptional"] = False
            self.response(to, False)

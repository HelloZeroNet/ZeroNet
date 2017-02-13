import time
import json
import os
import re

from Plugin import PluginManager
from Translate import Translate
from Config import config
from util import helper


if os.path.isfile("%s/mutes.json" % config.data_dir):
    try:
        mutes = json.load(open("%s/mutes.json" % config.data_dir))["mutes"]
    except Exception, err:
        mutes = {}
else:
    open("%s/mutes.json" % config.data_dir, "w").write('{"mutes": {}}')
    mutes = {}

if "_" not in locals():
    _ = Translate("plugins/Mute/languages/")


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    # Search and remove or readd files of an user
    def changeDb(self, auth_address, action):
        self.log.debug("Mute action %s on user %s" % (action, auth_address))
        res = self.site.content_manager.contents.db.execute(
            "SELECT * FROM content LEFT JOIN site USING (site_id) WHERE inner_path LIKE :inner_path",
            {"inner_path": "%%/%s/%%" % auth_address}
        )
        for row in res:
            site = self.server.sites.get(row["address"])
            if not site:
                continue
            dir_inner_path = helper.getDirname(row["inner_path"])
            for file_name in site.storage.list(dir_inner_path):
                if action == "remove":
                    site.storage.onUpdated(dir_inner_path + file_name, False)
                else:
                    site.storage.onUpdated(dir_inner_path + file_name)
                site.onFileDone(dir_inner_path + file_name)

    def cbMuteAdd(self, to, auth_address, cert_user_id, reason):
        mutes[auth_address] = {"cert_user_id": cert_user_id, "reason": reason, "source": self.site.address, "date_added": time.time()}
        self.saveMutes()
        self.changeDb(auth_address, "remove")
        self.response(to, "ok")

    def actionMuteAdd(self, to, auth_address, cert_user_id, reason):
        if "ADMIN" in self.getPermissions(to):
            self.cbMuteAdd(to, auth_address, cert_user_id, reason)
        else:
            self.cmd(
                "confirm",
                [_["Hide all content from <b>%s</b>?"] % cert_user_id, _["Mute"]],
                lambda (res): self.cbMuteAdd(to, auth_address, cert_user_id, reason)
            )

    def cbMuteRemove(self, to, auth_address):
        del mutes[auth_address]
        self.saveMutes()
        self.changeDb(auth_address, "load")
        self.response(to, "ok")

    def actionMuteRemove(self, to, auth_address):
        if "ADMIN" in self.getPermissions(to):
            self.cbMuteRemove(to, auth_address)
        else:
            self.cmd(
                "confirm",
                [_["Unmute <b>%s</b>?"] % mutes[auth_address]["cert_user_id"], _["Unmute"]],
                lambda (res): self.cbMuteRemove(to, auth_address)
            )

    def actionMuteList(self, to):
        if "ADMIN" in self.getPermissions(to):
            self.response(to, mutes)
        else:
            return self.response(to, {"error": "Only ADMIN sites can list mutes"})

    def saveMutes(self):
        helper.atomicWrite("%s/mutes.json" % config.data_dir, json.dumps({"mutes": mutes}, indent=2, sort_keys=True))


@PluginManager.registerTo("SiteStorage")
class SiteStoragePlugin(object):
    def updateDbFile(self, inner_path, file=None, cur=None):
        if file is not False:  # File deletion always allowed
            # Find for bitcoin addresses in file path
            matches = re.findall("/(1[A-Za-z0-9]{26,35})/", inner_path)
            # Check if any of the adresses are in the mute list
            for auth_address in matches:
                if auth_address in mutes:
                    self.log.debug("Mute match: %s, ignoring %s" % (auth_address, inner_path))
                    return False

        return super(SiteStoragePlugin, self).updateDbFile(inner_path, file=file, cur=cur)

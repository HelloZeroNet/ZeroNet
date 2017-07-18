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
        data = json.load(open("%s/mutes.json" % config.data_dir))
        mutes = data.get("mutes", {})
        site_blacklist = data.get("site_blacklist", {})
    except Exception as err:
        mutes = {}
        site_blacklist = {}
else:
    open("%s/mutes.json" % config.data_dir, "w").write('{"mutes": {}, "site_blacklist": {}}')
    mutes = {}
    site_blacklist = {}

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
            for file_name in site.storage.walk(dir_inner_path):
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

    # Blacklist
    def actionBlacklistAdd(self, to, site_address, reason=None):
        if "ADMIN" not in self.getPermissions(to):
            return self.response(to, {"error": "Forbidden, only admin sites can add to blacklist"})
        site_blacklist[site_address] = {"date_added": time.time(), "reason": reason}
        self.saveMutes()
        self.response(to, "ok")

    def actionBlacklistRemove(self, to, site_address):
        if "ADMIN" not in self.getPermissions(to):
            return self.response(to, {"error": "Forbidden, only admin sites can remove from blacklist"})
        del site_blacklist[site_address]
        self.saveMutes()
        self.response(to, "ok")

    def actionBlacklistList(self, to):
        if "ADMIN" in self.getPermissions(to):
            self.response(to, site_blacklist)
        else:
            return self.response(to, {"error": "Only ADMIN sites can list blacklists"})

    # Write mutes and blacklist to json file
    def saveMutes(self):
        helper.atomicWrite("%s/mutes.json" % config.data_dir, json.dumps({"mutes": mutes, "site_blacklist": site_blacklist}, indent=2, sort_keys=True))


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


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def actionWrapper(self, path, extra_headers=None):
        match = re.match("/(?P<address>[A-Za-z0-9\._-]+)(?P<inner_path>/.*|$)", path)
        if not match:
            return False
        address = match.group("address")

        if self.server.site_manager.get(address):  # Site already exists
            return super(UiRequestPlugin, self).actionWrapper(path, extra_headers)

        if self.server.site_manager.isDomain(address):
            address = self.server.site_manager.resolveDomain(address)

        if address in site_blacklist:
            site = self.server.site_manager.get(config.homepage)
            if not extra_headers:
                extra_headers = []
            self.sendHeader(extra_headers=extra_headers[:])
            return iter([super(UiRequestPlugin, self).renderWrapper(
                site, path, "uimedia/plugins/mute/blacklisted.html?address=" + address,
                "Blacklisted site", extra_headers, show_loadingscreen=False
            )])
        else:
            return super(UiRequestPlugin, self).actionWrapper(path, extra_headers)

    def actionUiMedia(self, path, *args, **kwargs):
        if path.startswith("/uimedia/plugins/mute/"):
            file_path = path.replace("/uimedia/plugins/mute/", "plugins/Mute/media/")
            return self.actionFile(file_path)
        else:
            return super(UiRequestPlugin, self).actionUiMedia(path)

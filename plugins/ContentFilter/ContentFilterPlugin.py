import time
import re
import html
import hashlib

from Plugin import PluginManager
from Translate import Translate
from Config import config

from .ContentFilterStorage import ContentFilterStorage


if "_" not in locals():
    _ = Translate("plugins/ContentFilter/languages/")


@PluginManager.registerTo("SiteManager")
class SiteManagerPlugin(object):
    def load(self, *args, **kwargs):
        global filter_storage
        super(SiteManagerPlugin, self).load(*args, **kwargs)
        filter_storage = ContentFilterStorage(site_manager=self)


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    # Mute
    def cbMuteAdd(self, to, auth_address, cert_user_id, reason):
        filter_storage.file_content["mutes"][auth_address] = {
            "cert_user_id": cert_user_id, "reason": reason, "source": self.site.address, "date_added": time.time()
        }
        filter_storage.save()
        filter_storage.changeDbs(auth_address, "remove")
        self.response(to, "ok")

    def actionMuteAdd(self, to, auth_address, cert_user_id, reason):
        if "ADMIN" in self.getPermissions(to):
            self.cbMuteAdd(to, auth_address, cert_user_id, reason)
        else:
            self.cmd(
                "confirm",
                [_["Hide all content from <b>%s</b>?"] % html.escape(cert_user_id), _["Mute"]],
                lambda res: self.cbMuteAdd(to, auth_address, cert_user_id, reason)
            )

    def cbMuteRemove(self, to, auth_address):
        del filter_storage.file_content["mutes"][auth_address]
        filter_storage.save()
        filter_storage.changeDbs(auth_address, "load")
        self.response(to, "ok")

    def actionMuteRemove(self, to, auth_address):
        if "ADMIN" in self.getPermissions(to):
            self.cbMuteRemove(to, auth_address)
        else:
            self.cmd(
                "confirm",
                [_["Unmute <b>%s</b>?"] % html.escape(filter_storage.file_content["mutes"][auth_address]["cert_user_id"]), _["Unmute"]],
                lambda res: self.cbMuteRemove(to, auth_address)
            )

    def actionMuteList(self, to):
        if "ADMIN" in self.getPermissions(to):
            self.response(to, filter_storage.file_content["mutes"])
        else:
            return self.response(to, {"error": "Forbidden: Only ADMIN sites can list mutes"})

    # Siteblock
    def actionSiteblockAdd(self, to, site_address, reason=None):
        if "ADMIN" not in self.getPermissions(to):
            return self.response(to, {"error": "Forbidden: Only ADMIN sites can add to blocklist"})
        filter_storage.file_content["siteblocks"][site_address] = {"date_added": time.time(), "reason": reason}
        filter_storage.save()
        self.response(to, "ok")

    def actionSiteblockRemove(self, to, site_address):
        if "ADMIN" not in self.getPermissions(to):
            return self.response(to, {"error": "Forbidden: Only ADMIN sites can remove from blocklist"})
        del filter_storage.file_content["siteblocks"][site_address]
        filter_storage.save()
        self.response(to, "ok")

    def actionSiteblockList(self, to):
        if "ADMIN" in self.getPermissions(to):
            self.response(to, filter_storage.file_content["siteblocks"])
        else:
            return self.response(to, {"error": "Forbidden: Only ADMIN sites can list blocklists"})

    # Include
    def actionFilterIncludeAdd(self, to, inner_path, description=None, address=None):
        if address:
            if "ADMIN" not in self.getPermissions(to):
                return self.response(to, {"error": "Forbidden: Only ADMIN sites can manage different site include"})
            site = self.server.sites[address]
        else:
            address = self.site.address
            site = self.site

        if "ADMIN" in self.getPermissions(to):
            self.cbFilterIncludeAdd(to, True, address, inner_path, description)
        else:
            content = site.storage.loadJson(inner_path)
            title = _["New shared global content filter: <b>%s</b> (%s sites, %s users)"] % (
                html.escape(inner_path), len(content.get("siteblocks", {})), len(content.get("mutes", {}))
            )

            self.cmd(
                "confirm",
                [title, "Add"],
                lambda res: self.cbFilterIncludeAdd(to, res, address, inner_path, description)
            )

    def cbFilterIncludeAdd(self, to, res, address, inner_path, description):
        if not res:
            self.response(to, res)
            return False

        filter_storage.includeAdd(address, inner_path, description)
        self.response(to, "ok")

    def actionFilterIncludeRemove(self, to, inner_path, address=None):
        if address:
            if "ADMIN" not in self.getPermissions(to):
                return self.response(to, {"error": "Forbidden: Only ADMIN sites can manage different site include"})
        else:
            address = self.site.address

        key = "%s/%s" % (address, inner_path)
        if key not in filter_storage.file_content["includes"]:
            self.response(to, {"error": "Include not found"})
        filter_storage.includeRemove(address, inner_path)
        self.response(to, "ok")

    def actionFilterIncludeList(self, to, all_sites=False, filters=False):
        if all_sites and "ADMIN" not in self.getPermissions(to):
            return self.response(to, {"error": "Forbidden: Only ADMIN sites can list all sites includes"})

        back = []
        includes = filter_storage.file_content.get("includes", {}).values()
        for include in includes:
            if not all_sites and include["address"] != self.site.address:
                continue
            if filters:
                include = dict(include)  # Don't modify original file_content
                include_site = filter_storage.site_manager.get(include["address"])
                if not include_site:
                    continue
                content = include_site.storage.loadJson(include["inner_path"])
                include["mutes"] = content.get("mutes", {})
                include["siteblocks"] = content.get("siteblocks", {})
            back.append(include)
        self.response(to, back)


@PluginManager.registerTo("SiteStorage")
class SiteStoragePlugin(object):
    def updateDbFile(self, inner_path, file=None, cur=None):
        if file is not False:  # File deletion always allowed
            # Find for bitcoin addresses in file path
            matches = re.findall("/(1[A-Za-z0-9]{26,35})/", inner_path)
            # Check if any of the adresses are in the mute list
            for auth_address in matches:
                if filter_storage.isMuted(auth_address):
                    self.log.debug("Mute match: %s, ignoring %s" % (auth_address, inner_path))
                    return False

        return super(SiteStoragePlugin, self).updateDbFile(inner_path, file=file, cur=cur)

    def onUpdated(self, inner_path, file=None):
        file_path = "%s/%s" % (self.site.address, inner_path)
        if file_path in filter_storage.file_content["includes"]:
            self.log.debug("Filter file updated: %s" % inner_path)
            filter_storage.includeUpdateAll()
        return super(SiteStoragePlugin, self).onUpdated(inner_path, file=file)


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

        if address:
            address_sha256 = "0x" + hashlib.sha256(address.encode("utf8")).hexdigest()
        else:
            address_sha256 = None

        if filter_storage.isSiteblocked(address) or filter_storage.isSiteblocked(address_sha256):
            site = self.server.site_manager.get(config.homepage)
            if not extra_headers:
                extra_headers = {}

            script_nonce = self.getScriptNonce()

            self.sendHeader(extra_headers=extra_headers, script_nonce=script_nonce)
            return iter([super(UiRequestPlugin, self).renderWrapper(
                site, path, "uimedia/plugins/contentfilter/blocklisted.html?address=" + address,
                "Blacklisted site", extra_headers, show_loadingscreen=False, script_nonce=script_nonce
            )])
        else:
            return super(UiRequestPlugin, self).actionWrapper(path, extra_headers)

    def actionUiMedia(self, path, *args, **kwargs):
        if path.startswith("/uimedia/plugins/contentfilter/"):
            file_path = path.replace("/uimedia/plugins/contentfilter/", "plugins/ContentFilter/media/")
            return self.actionFile(file_path)
        else:
            return super(UiRequestPlugin, self).actionUiMedia(path)

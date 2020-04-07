import re
import time
import copy
import os

from Plugin import PluginManager
from Translate import Translate
from util import RateLimit
from util import helper
from util.Flag import flag
from Debug import Debug
try:
    import OptionalManager.UiWebsocketPlugin  # To make optioanlFileInfo merger sites compatible
except Exception:
    pass

if "merger_db" not in locals().keys():  # To keep merger_sites between module reloads
    merger_db = {}  # Sites that allowed to list other sites {address: [type1, type2...]}
    merged_db = {}  # Sites that allowed to be merged to other sites {address: type, ...}
    merged_to_merger = {}  # {address: [site1, site2, ...]} cache
    site_manager = None  # Site manager for merger sites


plugin_dir = os.path.dirname(__file__)

if "_" not in locals():
    _ = Translate(plugin_dir + "/languages/")


# Check if the site has permission to this merger site
def checkMergerPath(address, inner_path):
    merged_match = re.match("^merged-(.*?)/([A-Za-z0-9]{26,35})/", inner_path)
    if merged_match:
        merger_type = merged_match.group(1)
        # Check if merged site is allowed to include other sites
        if merger_type in merger_db.get(address, []):
            # Check if included site allows to include
            merged_address = merged_match.group(2)
            if merged_db.get(merged_address) == merger_type:
                inner_path = re.sub("^merged-(.*?)/([A-Za-z0-9]{26,35})/", "", inner_path)
                return merged_address, inner_path
            else:
                raise Exception(
                    "Merger site (%s) does not have permission for merged site: %s (%s)" %
                    (merger_type, merged_address, merged_db.get(merged_address))
                )
        else:
            raise Exception("No merger (%s) permission to load: <br>%s (%s not in %s)" % (
                address, inner_path, merger_type, merger_db.get(address, []))
            )
    else:
        raise Exception("Invalid merger path: %s" % inner_path)


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    # Download new site
    def actionMergerSiteAdd(self, to, addresses):
        if type(addresses) != list:
            # Single site add
            addresses = [addresses]
        # Check if the site has merger permission
        merger_types = merger_db.get(self.site.address)
        if not merger_types:
            return self.response(to, {"error": "Not a merger site"})

        if RateLimit.isAllowed(self.site.address + "-MergerSiteAdd", 10) and len(addresses) == 1:
            # Without confirmation if only one site address and not called in last 10 sec
            self.cbMergerSiteAdd(to, addresses)
        else:
            self.cmd(
                "confirm",
                [_["Add <b>%s</b> new site?"] % len(addresses), "Add"],
                lambda res: self.cbMergerSiteAdd(to, addresses)
            )
        self.response(to, "ok")

    # Callback of adding new site confirmation
    def cbMergerSiteAdd(self, to, addresses):
        added = 0
        for address in addresses:
            try:
                site_manager.need(address)
                added += 1
            except Exception as err:
                self.cmd("notification", ["error", _["Adding <b>%s</b> failed: %s"] % (address, err)])
        if added:
            self.cmd("notification", ["done", _["Added <b>%s</b> new site"] % added, 5000])
        RateLimit.called(self.site.address + "-MergerSiteAdd")
        site_manager.updateMergerSites()

    # Delete a merged site
    @flag.no_multiuser
    def actionMergerSiteDelete(self, to, address):
        site = self.server.sites.get(address)
        if not site:
            return self.response(to, {"error": "No site found: %s" % address})

        merger_types = merger_db.get(self.site.address)
        if not merger_types:
            return self.response(to, {"error": "Not a merger site"})
        if merged_db.get(address) not in merger_types:
            return self.response(to, {"error": "Merged type (%s) not in %s" % (merged_db.get(address), merger_types)})

        self.cmd("notification", ["done", _["Site deleted: <b>%s</b>"] % address, 5000])
        self.response(to, "ok")

    # Lists merged sites
    def actionMergerSiteList(self, to, query_site_info=False):
        merger_types = merger_db.get(self.site.address)
        ret = {}
        if not merger_types:
            return self.response(to, {"error": "Not a merger site"})
        for address, merged_type in merged_db.items():
            if merged_type not in merger_types:
                continue  # Site not for us
            if query_site_info:
                site = self.server.sites.get(address)
                ret[address] = self.formatSiteInfo(site, create_user=False)
            else:
                ret[address] = merged_type
        self.response(to, ret)

    def hasSitePermission(self, address, *args, **kwargs):
        if super(UiWebsocketPlugin, self).hasSitePermission(address, *args, **kwargs):
            return True
        else:
            if self.site.address in [merger_site.address for merger_site in merged_to_merger.get(address, [])]:
                return True
            else:
                return False

    # Add support merger sites for file commands
    def mergerFuncWrapper(self, func_name, to, inner_path, *args, **kwargs):
        if inner_path.startswith("merged-"):
            merged_address, merged_inner_path = checkMergerPath(self.site.address, inner_path)

            # Set the same cert for merged site
            merger_cert = self.user.getSiteData(self.site.address).get("cert")
            if merger_cert and self.user.getSiteData(merged_address).get("cert") != merger_cert:
                self.user.setCert(merged_address, merger_cert)

            req_self = copy.copy(self)
            req_self.site = self.server.sites.get(merged_address)  # Change the site to the merged one

            func = getattr(super(UiWebsocketPlugin, req_self), func_name)
            return func(to, merged_inner_path, *args, **kwargs)
        else:
            func = getattr(super(UiWebsocketPlugin, self), func_name)
            return func(to, inner_path, *args, **kwargs)

    def actionFileList(self, to, inner_path, *args, **kwargs):
        return self.mergerFuncWrapper("actionFileList", to, inner_path, *args, **kwargs)

    def actionDirList(self, to, inner_path, *args, **kwargs):
        return self.mergerFuncWrapper("actionDirList", to, inner_path, *args, **kwargs)

    def actionFileGet(self, to, inner_path, *args, **kwargs):
        return self.mergerFuncWrapper("actionFileGet", to, inner_path, *args, **kwargs)

    def actionFileWrite(self, to, inner_path, *args, **kwargs):
        return self.mergerFuncWrapper("actionFileWrite", to, inner_path, *args, **kwargs)

    def actionFileDelete(self, to, inner_path, *args, **kwargs):
        return self.mergerFuncWrapper("actionFileDelete", to, inner_path, *args, **kwargs)

    def actionFileRules(self, to, inner_path, *args, **kwargs):
        return self.mergerFuncWrapper("actionFileRules", to, inner_path, *args, **kwargs)

    def actionFileNeed(self, to, inner_path, *args, **kwargs):
        return self.mergerFuncWrapper("actionFileNeed", to, inner_path, *args, **kwargs)

    def actionOptionalFileInfo(self, to, inner_path, *args, **kwargs):
        return self.mergerFuncWrapper("actionOptionalFileInfo", to, inner_path, *args, **kwargs)

    def actionOptionalFileDelete(self, to, inner_path, *args, **kwargs):
        return self.mergerFuncWrapper("actionOptionalFileDelete", to, inner_path, *args, **kwargs)

    def actionBigfileUploadInit(self, to, inner_path, *args, **kwargs):
        back = self.mergerFuncWrapper("actionBigfileUploadInit", to, inner_path, *args, **kwargs)
        if inner_path.startswith("merged-"):
            merged_address, merged_inner_path = checkMergerPath(self.site.address, inner_path)
            back["inner_path"] = "merged-%s/%s/%s" % (merged_db[merged_address], merged_address, back["inner_path"])
        return back

    # Add support merger sites for file commands with privatekey parameter
    def mergerFuncWrapperWithPrivatekey(self, func_name, to, privatekey, inner_path, *args, **kwargs):
        func = getattr(super(UiWebsocketPlugin, self), func_name)
        if inner_path.startswith("merged-"):
            merged_address, merged_inner_path = checkMergerPath(self.site.address, inner_path)
            merged_site = self.server.sites.get(merged_address)

            # Set the same cert for merged site
            merger_cert = self.user.getSiteData(self.site.address).get("cert")
            if merger_cert:
                self.user.setCert(merged_address, merger_cert)

            site_before = self.site  # Save to be able to change it back after we ran the command
            self.site = merged_site  # Change the site to the merged one
            try:
                back = func(to, privatekey, merged_inner_path, *args, **kwargs)
            finally:
                self.site = site_before  # Change back to original site
            return back
        else:
            return func(to, privatekey, inner_path, *args, **kwargs)

    def actionSiteSign(self, to, privatekey=None, inner_path="content.json", *args, **kwargs):
        return self.mergerFuncWrapperWithPrivatekey("actionSiteSign", to, privatekey, inner_path, *args, **kwargs)

    def actionSitePublish(self, to, privatekey=None, inner_path="content.json", *args, **kwargs):
        return self.mergerFuncWrapperWithPrivatekey("actionSitePublish", to, privatekey, inner_path, *args, **kwargs)

    def actionPermissionAdd(self, to, permission):
        super(UiWebsocketPlugin, self).actionPermissionAdd(to, permission)
        if permission.startswith("Merger"):
            self.site.storage.rebuildDb()

    def actionPermissionDetails(self, to, permission):
        if not permission.startswith("Merger"):
            return super(UiWebsocketPlugin, self).actionPermissionDetails(to, permission)

        merger_type = permission.replace("Merger:", "")
        if not re.match("^[A-Za-z0-9-]+$", merger_type):
            raise Exception("Invalid merger_type: %s" % merger_type)
        merged_sites = []
        for address, merged_type in merged_db.items():
            if merged_type != merger_type:
                continue
            site = self.server.sites.get(address)
            try:
                merged_sites.append(site.content_manager.contents.get("content.json").get("title", address))
            except Exception:
                merged_sites.append(address)

        details = _["Read and write permissions to sites with merged type of <b>%s</b> "] % merger_type
        details += _["(%s sites)"] % len(merged_sites)
        details += "<div style='white-space: normal; max-width: 400px'>%s</div>" % ", ".join(merged_sites)
        self.response(to, details)


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    # Allow to load merged site files using /merged-ZeroMe/address/file.jpg
    def parsePath(self, path):
        path_parts = super(UiRequestPlugin, self).parsePath(path)
        if "merged-" not in path:  # Optimization
            return path_parts
        path_parts["address"], path_parts["inner_path"] = checkMergerPath(path_parts["address"], path_parts["inner_path"])
        return path_parts


@PluginManager.registerTo("SiteStorage")
class SiteStoragePlugin(object):
    # Also rebuild from merged sites
    def getDbFiles(self):
        merger_types = merger_db.get(self.site.address)

        # First return the site's own db files
        for item in super(SiteStoragePlugin, self).getDbFiles():
            yield item

        # Not a merger site, that's all
        if not merger_types:
            return

        merged_sites = [
            site_manager.sites[address]
            for address, merged_type in merged_db.items()
            if merged_type in merger_types
        ]
        found = 0
        for merged_site in merged_sites:
            self.log.debug("Loading merged site: %s" % merged_site)
            merged_type = merged_db[merged_site.address]
            for content_inner_path, content in merged_site.content_manager.contents.items():
                # content.json file itself
                if merged_site.storage.isFile(content_inner_path):  # Missing content.json file
                    merged_inner_path = "merged-%s/%s/%s" % (merged_type, merged_site.address, content_inner_path)
                    yield merged_inner_path, merged_site.storage.getPath(content_inner_path)
                else:
                    merged_site.log.error("[MISSING] %s" % content_inner_path)
                # Data files in content.json
                content_inner_path_dir = helper.getDirname(content_inner_path)  # Content.json dir relative to site
                for file_relative_path in list(content.get("files", {}).keys()) + list(content.get("files_optional", {}).keys()):
                    if not file_relative_path.endswith(".json"):
                        continue  # We only interesed in json files
                    file_inner_path = content_inner_path_dir + file_relative_path  # File Relative to site dir
                    file_inner_path = file_inner_path.strip("/")  # Strip leading /
                    if merged_site.storage.isFile(file_inner_path):
                        merged_inner_path = "merged-%s/%s/%s" % (merged_type, merged_site.address, file_inner_path)
                        yield merged_inner_path, merged_site.storage.getPath(file_inner_path)
                    else:
                        merged_site.log.error("[MISSING] %s" % file_inner_path)
                    found += 1
                    if found % 100 == 0:
                        time.sleep(0.001)  # Context switch to avoid UI block

    # Also notice merger sites on a merged site file change
    def onUpdated(self, inner_path, file=None):
        super(SiteStoragePlugin, self).onUpdated(inner_path, file)

        merged_type = merged_db.get(self.site.address)

        for merger_site in merged_to_merger.get(self.site.address, []):
            if merger_site.address == self.site.address:  # Avoid infinite loop
                continue
            virtual_path = "merged-%s/%s/%s" % (merged_type, self.site.address, inner_path)
            if inner_path.endswith(".json"):
                if file is not None:
                    merger_site.storage.onUpdated(virtual_path, file=file)
                else:
                    merger_site.storage.onUpdated(virtual_path, file=self.open(inner_path))
            else:
                merger_site.storage.onUpdated(virtual_path)


@PluginManager.registerTo("Site")
class SitePlugin(object):
    def fileDone(self, inner_path):
        super(SitePlugin, self).fileDone(inner_path)

        for merger_site in merged_to_merger.get(self.address, []):
            if merger_site.address == self.address:
                continue
            for ws in merger_site.websockets:
                ws.event("siteChanged", self, {"event": ["file_done", inner_path]})

    def fileFailed(self, inner_path):
        super(SitePlugin, self).fileFailed(inner_path)

        for merger_site in merged_to_merger.get(self.address, []):
            if merger_site.address == self.address:
                continue
            for ws in merger_site.websockets:
                ws.event("siteChanged", self, {"event": ["file_failed", inner_path]})


@PluginManager.registerTo("SiteManager")
class SiteManagerPlugin(object):
    # Update merger site for site types
    def updateMergerSites(self):
        global merger_db, merged_db, merged_to_merger, site_manager
        s = time.time()
        merger_db_new = {}
        merged_db_new = {}
        merged_to_merger_new = {}
        site_manager = self
        if not self.sites:
            return
        for site in self.sites.values():
            # Update merged sites
            try:
                merged_type = site.content_manager.contents.get("content.json", {}).get("merged_type")
            except Exception as err:
                self.log.error("Error loading site %s: %s" % (site.address, Debug.formatException(err)))
                continue
            if merged_type:
                merged_db_new[site.address] = merged_type

            # Update merger sites
            for permission in site.settings["permissions"]:
                if not permission.startswith("Merger:"):
                    continue
                if merged_type:
                    self.log.error(
                        "Removing permission %s from %s: Merger and merged at the same time." %
                        (permission, site.address)
                    )
                    site.settings["permissions"].remove(permission)
                    continue
                merger_type = permission.replace("Merger:", "")
                if site.address not in merger_db_new:
                    merger_db_new[site.address] = []
                merger_db_new[site.address].append(merger_type)
                site_manager.sites[site.address] = site

            # Update merged to merger
            if merged_type:
                for merger_site in self.sites.values():
                    if "Merger:" + merged_type in merger_site.settings["permissions"]:
                        if site.address not in merged_to_merger_new:
                            merged_to_merger_new[site.address] = []
                        merged_to_merger_new[site.address].append(merger_site)

        # Update globals
        merger_db = merger_db_new
        merged_db = merged_db_new
        merged_to_merger = merged_to_merger_new

        self.log.debug("Updated merger sites in %.3fs" % (time.time() - s))

    def load(self, *args, **kwags):
        super(SiteManagerPlugin, self).load(*args, **kwags)
        self.updateMergerSites()

    def saveDelayed(self, *args, **kwags):
        super(SiteManagerPlugin, self).saveDelayed(*args, **kwags)
        self.updateMergerSites()

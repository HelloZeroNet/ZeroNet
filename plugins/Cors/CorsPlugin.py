import re
import html
import copy
import os
import gevent

from Plugin import PluginManager
from Translate import Translate


plugin_dir = os.path.dirname(__file__)

if "_" not in locals():
    _ = Translate(plugin_dir + "/languages/")


def getCorsPath(site, inner_path):
    match = re.match("^cors-([A-Za-z0-9]{26,35})/(.*)", inner_path)
    if not match:
        raise Exception("Invalid cors path: %s" % inner_path)
    cors_address = match.group(1)
    cors_inner_path = match.group(2)

    if not "Cors:%s" % cors_address in site.settings["permissions"]:
        raise Exception("This site has no permission to access site %s" % cors_address)

    return cors_address, cors_inner_path


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def hasSitePermission(self, address, cmd=None):
        if super(UiWebsocketPlugin, self).hasSitePermission(address, cmd=cmd):
            return True

        allowed_commands = [
            "fileGet", "fileList", "dirList", "fileRules", "optionalFileInfo",
            "fileQuery", "dbQuery", "userGetSettings", "siteInfo"
        ]
        if not "Cors:%s" % address in self.site.settings["permissions"] or cmd not in allowed_commands:
            return False
        else:
            return True

    # Add cors support for file commands
    def corsFuncWrapper(self, func_name, to, inner_path, *args, **kwargs):
        if inner_path.startswith("cors-"):
            cors_address, cors_inner_path = getCorsPath(self.site, inner_path)

            req_self = copy.copy(self)
            req_self.site = self.server.sites.get(cors_address)  # Change the site to the merged one
            if not req_self.site:
                return {"error": "No site found"}

            func = getattr(super(UiWebsocketPlugin, req_self), func_name)
            back = func(to, cors_inner_path, *args, **kwargs)
            return back
        else:
            func = getattr(super(UiWebsocketPlugin, self), func_name)
            return func(to, inner_path, *args, **kwargs)

    def actionFileGet(self, to, inner_path, *args, **kwargs):
        return self.corsFuncWrapper("actionFileGet", to, inner_path, *args, **kwargs)

    def actionFileList(self, to, inner_path, *args, **kwargs):
        return self.corsFuncWrapper("actionFileList", to, inner_path, *args, **kwargs)

    def actionDirList(self, to, inner_path, *args, **kwargs):
        return self.corsFuncWrapper("actionDirList", to, inner_path, *args, **kwargs)

    def actionFileRules(self, to, inner_path, *args, **kwargs):
        return self.corsFuncWrapper("actionFileRules", to, inner_path, *args, **kwargs)

    def actionOptionalFileInfo(self, to, inner_path, *args, **kwargs):
        return self.corsFuncWrapper("actionOptionalFileInfo", to, inner_path, *args, **kwargs)

    def actionCorsPermission(self, to, address):
        if isinstance(address, list):
            addresses = address
        else:
            addresses = [address]

        button_title = _["Grant"]
        site_names = []
        site_addresses = []
        for address in addresses:
            site = self.server.sites.get(address)
            if site:
                site_name = site.content_manager.contents.get("content.json", {}).get("title", address)
            else:
                site_name = address
                # If at least one site is not downloaded yet, show "Grant & Add" instead
                button_title = _["Grant & Add"]

            if not (site and "Cors:" + address in self.permissions):
                # No site or no permission
                site_names.append(site_name)
                site_addresses.append(address)

        if len(site_names) == 0:
            return "ignored"

        self.cmd(
            "confirm",
            [_["This site requests <b>read</b> permission to: <b>%s</b>"] % ", ".join(map(html.escape, site_names)), button_title],
            lambda res: self.cbCorsPermission(to, site_addresses)
        )

    def cbCorsPermission(self, to, addresses):
        # Add permissions
        for address in addresses:
            permission = "Cors:" + address
            if permission not in self.site.settings["permissions"]:
                self.site.settings["permissions"].append(permission)

        self.site.saveSettings()
        self.site.updateWebsocket(permission_added=permission)

        self.response(to, "ok")

        for address in addresses:
            site = self.server.sites.get(address)
            if not site:
                gevent.spawn(self.server.site_manager.need, address)


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    # Allow to load cross origin files using /cors-address/file.jpg
    def parsePath(self, path):
        path_parts = super(UiRequestPlugin, self).parsePath(path)
        if "cors-" not in path:  # Optimization
            return path_parts
        site = self.server.sites[path_parts["address"]]
        try:
            path_parts["address"], path_parts["inner_path"] = getCorsPath(site, path_parts["inner_path"])
        except Exception:
            return None
        return path_parts

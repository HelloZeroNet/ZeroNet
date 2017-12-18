import re
import cgi
import copy

from Plugin import PluginManager
from Translate import Translate
from util import helper
from Debug import Debug
if "_" not in locals():
    _ = Translate("plugins/Cors/languages/")

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

    def actionFileRules(self, to, inner_path, *args, **kwargs):
        return self.corsFuncWrapper("actionFileRules", to, inner_path, *args, **kwargs)

    def actionOptionalFileInfo(self, to, inner_path, *args, **kwargs):
        return self.corsFuncWrapper("actionOptionalFileInfo", to, inner_path, *args, **kwargs)

    def actionCorsPermission(self, to, address):
        site = self.server.sites.get(address)
        if site:
            site_name = site.content_manager.contents.get("content.json", {}).get("title")
            button_title = _["Grant"]
        else:
            site_name = address
            button_title = _["Grant & Add"]

        if site and "Cors:"+address in self.permissions:
            return "ignored"

        self.cmd(
            "confirm",
            [_["This site requests <b>read</b> permission to: <b>%s</b>"] % cgi.escape(site_name), button_title],
            lambda (res): self.cbCorsPermission(to, address)
        )

    def cbCorsPermission(self, to, address):
        self.actionPermissionAdd(to, "Cors:"+address)
        site = self.server.sites.get(address)
        if not site:
            self.server.site_manager.need(address)

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
        except:
            return None
        return path_parts

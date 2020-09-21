import io
import os
import re
import urllib

from Plugin import PluginManager
from Config import config
from Translate import Translate

plugin_dir = os.path.dirname(__file__)

if "_" not in locals():
    _ = Translate(plugin_dir + "/languages/")


@PluginManager.registerTo("UiRequest")
class UiFileManagerPlugin(object):
    def actionWrapper(self, path, extra_headers=None):
        match = re.match("/list/(.*?)(/.*|)$", path)
        if not match:
            return super().actionWrapper(path, extra_headers)

        if not extra_headers:
            extra_headers = {}

        request_address, inner_path = match.groups()

        script_nonce = self.getScriptNonce()

        self.sendHeader(extra_headers=extra_headers, script_nonce=script_nonce)

        site = self.server.site_manager.need(request_address)

        if not site:
            return super().actionWrapper(path, extra_headers)

        request_params = urllib.parse.urlencode(
            {"address": site.address, "site": request_address, "inner_path": inner_path.strip("/")}
        )

        is_content_loaded = "content.json" in site.content_manager.contents

        return iter([super().renderWrapper(
            site, path, "uimedia/plugins/uifilemanager/list.html?%s" % request_params,
            "List", extra_headers, show_loadingscreen=not is_content_loaded, script_nonce=script_nonce
        )])

    def actionUiMedia(self, path, *args, **kwargs):
        if path.startswith("/uimedia/plugins/uifilemanager/"):
            file_path = path.replace("/uimedia/plugins/uifilemanager/", plugin_dir + "/media/")
            if config.debug and (file_path.endswith("all.js") or file_path.endswith("all.css")):
                # If debugging merge *.css to all.css and *.js to all.js
                from Debug import DebugMedia
                DebugMedia.merge(file_path)

            if file_path.endswith("js"):
                data = _.translateData(open(file_path).read(), mode="js").encode("utf8")
            elif file_path.endswith("html"):
                if self.get.get("address"):
                    site = self.server.site_manager.need(self.get.get("address"))
                    if "content.json" not in site.content_manager.contents:
                        site.needFile("content.json")
                data = _.translateData(open(file_path).read(), mode="html").encode("utf8")
            else:
                data = open(file_path, "rb").read()

            return self.actionFile(file_path, file_obj=io.BytesIO(data), file_size=len(data))
        else:
            return super().actionUiMedia(path)

    def error404(self, path=""):
        if not path.endswith("index.html") and not path.endswith("/"):
            return super().error404(path)

        path_parts = self.parsePath(path)
        site = self.server.site_manager.get(path_parts["request_address"])

        if not site or not site.content_manager.contents.get("content.json"):
            return super().error404(path)

        self.sendHeader(200)
        path_redirect = "/list" + re.sub("^/media/", "/", path)
        self.log.debug("Index.html not found: %s, redirecting to: %s" % (path, path_redirect))
        return self.formatRedirect(path_redirect)

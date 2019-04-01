import os
import io
import re
import Resources

from Plugin import PluginManager
from Config import config
from Translate import Translate

from . import media

MEDIA_URL = "uimedia/plugins/uiconfig"

if "_" not in locals():
    from . import languages
    _ = Translate(languages)


@PluginManager.afterLoad
def importPluginnedClasses():
    from Ui import UiWebsocket
    UiWebsocket.admin_commands.add("configList")

@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):

    def actionWrapper(self, path, extra_headers=None):
        if path.strip("/") != "Config":
            return super(UiRequestPlugin, self).actionWrapper(path, extra_headers)

        if not extra_headers:
            extra_headers = {}

        script_nonce = self.getScriptNonce()

        self.sendHeader(extra_headers=extra_headers, script_nonce=script_nonce)
        site = self.server.site_manager.get(config.homepage)
        return iter([super(UiRequestPlugin, self).renderWrapper(
            site, path, MEDIA_URL + "/config.html",
            "Config", extra_headers, show_loadingscreen=False, script_nonce=script_nonce
        )])

    def actionUiMedia(self, path, *args, **kwargs):
        try:
            res_pkg, res_file = self.resourceFromURL(path, media, MEDIA_URL)

            # If debugging merge *.css to all.css and *.js to all.js
            # Input files are read from the file system, not as resources
            if config.debug and res_file.startswith("all."):
                from Debug import DebugMedia
                DebugMedia.merge(os.path.join(*(res_pkg.split('.') + [res_file])))

            match = re.match(".*(?P<ext>js|html)$", res_file)
            if match:
                file_type = match.group('ext')
                in_data = Resources.read_text(res_pkg, res_file)
                data = _.translateData(in_data, mode=file_type).encode("utf8")
            else:
                data = Resources.read_binary(res_pkg, res_file)

            with Resources.path(res_pkg, res_file) as file_path:
                return self.actionFile(file_path, file_obj=io.BytesIO(data), file_size=len(data))
        except self.ResourceException:
            return super(UiRequestPlugin, self).actionUiMedia(path)


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def actionConfigList(self, to):
        back = {}
        config_values = vars(config.arguments)
        config_values.update(config.pending_changes)
        for key, val in config_values.items():
            if key not in config.keys_api_change_allowed:
                continue
            is_pending = key in config.pending_changes
            if val is None and is_pending:
                val = config.parser.get_default(key)
            back[key] = {
                "value": val,
                "default": config.parser.get_default(key),
                "pending": is_pending
            }
        return back

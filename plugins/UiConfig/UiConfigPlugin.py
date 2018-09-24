from Plugin import PluginManager
from Config import config
from Translate import Translate
from cStringIO import StringIO


if "_" not in locals():
    _ = Translate("plugins/UiConfig/languages/")


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
        self.sendHeader(extra_headers=extra_headers)
        site = self.server.site_manager.get(config.homepage)
        return iter([super(UiRequestPlugin, self).renderWrapper(
            site, path, "uimedia/plugins/uiconfig/config.html",
            "Config", extra_headers, show_loadingscreen=False
        )])

    def actionUiMedia(self, path, *args, **kwargs):
        if path.startswith("/uimedia/plugins/uiconfig/"):
            file_path = path.replace("/uimedia/plugins/uiconfig/", "plugins/UiConfig/media/")
            if config.debug and (file_path.endswith("all.js") or file_path.endswith("all.css")):
                # If debugging merge *.css to all.css and *.js to all.js
                from Debug import DebugMedia
                DebugMedia.merge(file_path)

            if file_path.endswith("js"):
                data = _.translateData(open(file_path).read(), mode="js")
            elif file_path.endswith("html"):
                data = _.translateData(open(file_path).read(), mode="html")
            else:
                data = open(file_path).read()

            return self.actionFile(file_path, file_obj=StringIO(data), file_size=len(data))
        else:
            return super(UiRequestPlugin, self).actionUiMedia(path)


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def actionConfigList(self, to):
        back = {}
        config_values = vars(config.arguments)
        config_values.update(config.pending_changes)
        for key, val in config_values.iteritems():
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

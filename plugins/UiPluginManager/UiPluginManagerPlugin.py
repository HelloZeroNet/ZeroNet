import io
import os
import json
import shutil
import time

from Plugin import PluginManager
from Config import config
from Debug import Debug
from Translate import Translate
from util.Flag import flag


plugin_dir = os.path.dirname(__file__)

if "_" not in locals():
    _ = Translate(plugin_dir + "/languages/")


# Convert non-str,int,float values to str in a dict
def restrictDictValues(input_dict):
    allowed_types = (int, str, float)
    return {
        key: val if type(val) in allowed_types else str(val)
        for key, val in input_dict.items()
    }


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def actionWrapper(self, path, extra_headers=None):
        if path.strip("/") != "Plugins":
            return super(UiRequestPlugin, self).actionWrapper(path, extra_headers)

        if not extra_headers:
            extra_headers = {}

        script_nonce = self.getScriptNonce()

        self.sendHeader(extra_headers=extra_headers, script_nonce=script_nonce)
        site = self.server.site_manager.get(config.homepage)
        return iter([super(UiRequestPlugin, self).renderWrapper(
            site, path, "uimedia/plugins/plugin_manager/plugin_manager.html",
            "Plugin Manager", extra_headers, show_loadingscreen=False, script_nonce=script_nonce
        )])

    def actionUiMedia(self, path, *args, **kwargs):
        if path.startswith("/uimedia/plugins/plugin_manager/"):
            file_path = path.replace("/uimedia/plugins/plugin_manager/", plugin_dir + "/media/")
            if config.debug and (file_path.endswith("all.js") or file_path.endswith("all.css")):
                # If debugging merge *.css to all.css and *.js to all.js
                from Debug import DebugMedia
                DebugMedia.merge(file_path)

            if file_path.endswith("js"):
                data = _.translateData(open(file_path).read(), mode="js").encode("utf8")
            elif file_path.endswith("html"):
                data = _.translateData(open(file_path).read(), mode="html").encode("utf8")
            else:
                data = open(file_path, "rb").read()

            return self.actionFile(file_path, file_obj=io.BytesIO(data), file_size=len(data))
        else:
            return super(UiRequestPlugin, self).actionUiMedia(path)


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    @flag.admin
    def actionPluginList(self, to):
        plugins = []
        for plugin in PluginManager.plugin_manager.listPlugins(list_disabled=True):
            plugin_info_path = plugin["dir_path"] + "/plugin_info.json"
            plugin_info = {}
            if os.path.isfile(plugin_info_path):
                try:
                    plugin_info = json.load(open(plugin_info_path))
                except Exception as err:
                    self.log.error(
                        "Error loading plugin info for %s: %s" %
                        (plugin["name"], Debug.formatException(err))
                    )
            if plugin_info:
                plugin_info = restrictDictValues(plugin_info)  # For security reasons don't allow complex values
                plugin["info"] = plugin_info

            if plugin["source"] != "builtin":
                plugin_site = self.server.sites.get(plugin["source"])
                if plugin_site:
                    try:
                        plugin_site_info = plugin_site.storage.loadJson(plugin["inner_path"] + "/plugin_info.json")
                        plugin_site_info = restrictDictValues(plugin_site_info)
                        plugin["site_info"] = plugin_site_info
                        plugin["site_title"] = plugin_site.content_manager.contents["content.json"].get("title")
                        plugin_key = "%s/%s" % (plugin["source"], plugin["inner_path"])
                        plugin["updated"] = plugin_key in PluginManager.plugin_manager.plugins_updated
                    except Exception:
                        pass

            plugins.append(plugin)

        return {"plugins": plugins}

    @flag.admin
    @flag.no_multiuser
    def actionPluginConfigSet(self, to, source, inner_path, key, value):
        plugin_manager = PluginManager.plugin_manager
        plugins = plugin_manager.listPlugins(list_disabled=True)
        plugin = None
        for item in plugins:
            if item["source"] == source and item["inner_path"] in (inner_path, "disabled-" + inner_path):
                plugin = item
                break

        if not plugin:
            return {"error": "Plugin not found"}

        config_source = plugin_manager.config.setdefault(source, {})
        config_plugin = config_source.setdefault(inner_path, {})

        if key in config_plugin and value is None:
            del config_plugin[key]
        else:
            config_plugin[key] = value

        plugin_manager.saveConfig()

        return "ok"

    def pluginAction(self, action, address, inner_path):
        site = self.server.sites.get(address)
        plugin_manager = PluginManager.plugin_manager

        # Install/update path should exists
        if action in ("add", "update", "add_request"):
            if not site:
                raise Exception("Site not found")

            if not site.storage.isDir(inner_path):
                raise Exception("Directory not found on the site")

            try:
                plugin_info = site.storage.loadJson(inner_path + "/plugin_info.json")
                plugin_data = (plugin_info["rev"], plugin_info["description"], plugin_info["name"])
            except Exception as err:
                raise Exception("Invalid plugin_info.json: %s" % Debug.formatExceptionMessage(err))

            source_path = site.storage.getPath(inner_path)

        target_path = plugin_manager.path_installed_plugins + "/" + address + "/" + inner_path
        plugin_config = plugin_manager.config.setdefault(site.address, {}).setdefault(inner_path, {})

        # Make sure plugin (not)installed
        if action in ("add", "add_request") and os.path.isdir(target_path):
            raise Exception("Plugin already installed")

        if action in ("update", "remove") and not os.path.isdir(target_path):
            raise Exception("Plugin not installed")

        # Do actions
        if action == "add":
            shutil.copytree(source_path, target_path)

            plugin_config["date_added"] = int(time.time())
            plugin_config["rev"] = plugin_info["rev"]
            plugin_config["enabled"] = True

        if action == "update":
            shutil.rmtree(target_path)

            shutil.copytree(source_path, target_path)

            plugin_config["rev"] = plugin_info["rev"]
            plugin_config["date_updated"] = time.time()

        if action == "remove":
            del plugin_manager.config[address][inner_path]
            shutil.rmtree(target_path)

    def doPluginAdd(self, to, inner_path, res):
        if not res:
            return None

        self.pluginAction("add", self.site.address, inner_path)
        PluginManager.plugin_manager.saveConfig()

        self.cmd(
            "confirm",
            ["Plugin installed!<br>You have to restart the client to load the plugin", "Restart"],
            lambda res: self.actionServerShutdown(to, restart=True)
        )

        self.response(to, "ok")

    @flag.no_multiuser
    def actionPluginAddRequest(self, to, inner_path):
        self.pluginAction("add_request", self.site.address, inner_path)
        plugin_info = self.site.storage.loadJson(inner_path + "/plugin_info.json")
        warning = "<b>Warning!<br/>Plugins has the same permissions as the ZeroNet client.<br/>"
        warning += "Do not install it if you don't trust the developer.</b>"

        self.cmd(
            "confirm",
            ["Install new plugin: %s?<br>%s" % (plugin_info["name"], warning), "Trust & Install"],
            lambda res: self.doPluginAdd(to, inner_path, res)
        )

    @flag.admin
    @flag.no_multiuser
    def actionPluginRemove(self, to, address, inner_path):
        self.pluginAction("remove", address, inner_path)
        PluginManager.plugin_manager.saveConfig()
        return "ok"

    @flag.admin
    @flag.no_multiuser
    def actionPluginUpdate(self, to, address, inner_path):
        self.pluginAction("update", address, inner_path)
        PluginManager.plugin_manager.saveConfig()
        PluginManager.plugin_manager.plugins_updated["%s/%s" % (address, inner_path)] = True
        return "ok"

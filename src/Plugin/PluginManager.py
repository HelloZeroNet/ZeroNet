import logging
import os
import sys

from Debug import Debug
from Config import config


class PluginManager:

    def __init__(self):
        self.log = logging.getLogger("PluginManager")
        self.plugin_path = "plugins"  # Plugin directory
        self.plugins = {}  # Registered plugins (key: class name, value: list of plugins for class)
        self.plugin_names = []  # Loaded plugin names

        sys.path.append(self.plugin_path)

        if config.debug:  # Auto reload Plugins on file change
            from Debug import DebugReloader
            DebugReloader(self.reloadPlugins)

    # -- Load / Unload --

    # Load all plugin
    def loadPlugins(self):
        for dir_name in os.listdir(self.plugin_path):
            dir_path = os.path.join(self.plugin_path, dir_name)
            if dir_name.startswith("disabled"):
                continue  # Dont load if disabled
            if not os.path.isdir(dir_path):
                continue  # Dont load if not dir
            if dir_name.startswith("Debug") and not config.debug:
                continue  # Only load in debug mode if module name starts with Debug
            self.log.debug("Loading plugin: %s" % dir_name)
            try:
                __import__(dir_name)
            except Exception, err:
                self.log.error("Plugin %s load error: %s" % (dir_name, Debug.formatException(err)))
            if dir_name not in self.plugin_names:
                self.plugin_names.append(dir_name)

    # Reload all plugins
    def reloadPlugins(self):
        self.plugins = {}  # Reset registered plugins
        for module_name, module in sys.modules.items():
            if module and "__file__" in dir(module) and self.plugin_path in module.__file__:  # Module file within plugin_path
                if "allow_reload" not in dir(module) or module.allow_reload:  # Check if reload disabled
                    try:
                        reload(module)
                    except Exception, err:
                        self.log.error("Plugin %s reload error: %s" % (module_name, Debug.formatException(err)))

        self.loadPlugins()  # Load new plugins


plugin_manager = PluginManager()  # Singletone

# -- Decorators --

# Accept plugin to class decorator


def acceptPlugins(base_class):
    class_name = base_class.__name__
    if class_name in plugin_manager.plugins:  # Has plugins
        classes = plugin_manager.plugins[class_name][:]  # Copy the current plugins
        classes.reverse()
        classes.append(base_class)  # Add the class itself to end of inherience line
        plugined_class = type(class_name, tuple(classes), dict())  # Create the plugined class
        plugin_manager.log.debug("New class accepts plugins: %s (Loaded plugins: %s)" % (class_name, classes))
    else:  # No plugins just use the original
        plugined_class = base_class
    return plugined_class


# Register plugin to class name decorator
def registerTo(class_name):
    plugin_manager.log.debug("New plugin registered to: %s" % class_name)
    if class_name not in plugin_manager.plugins:
        plugin_manager.plugins[class_name] = []

    def classDecorator(self):
        plugin_manager.plugins[class_name].append(self)
        return self
    return classDecorator


# - Example usage -

if __name__ == "__main__":
    @registerTo("Request")
    class RequestPlugin(object):

        def actionMainPage(self, path):
            return "Hello MainPage!"

    @acceptPlugins
    class Request(object):

        def route(self, path):
            func = getattr(self, "action" + path, None)
            if func:
                return func(path)
            else:
                return "Can't route to", path

    print Request().route("MainPage")

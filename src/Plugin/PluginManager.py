import logging
import os
import sys
import shutil
import time
from collections import defaultdict

from Debug import Debug
from Config import config

import plugins

import importlib


class PluginManager:
    def __init__(self):
        self.log = logging.getLogger("PluginManager")
        self.plugin_path = os.path.abspath(os.path.dirname(plugins.__file__))
        self.plugins = defaultdict(list)  # Registered plugins (key: class name, value: list of plugins for class)
        self.subclass_order = {}  # Record the load order of the plugins, to keep it after reload
        self.pluggable = {}
        self.plugin_names = []  # Loaded plugin names
        self.after_load = []  # Execute functions after loaded plugins
        self.reloading = False

        sys.path.append(os.path.join(os.getcwd(), self.plugin_path))
        self.migratePlugins()

        if config.debug:  # Auto reload Plugins on file change
            from Debug import DebugReloader
            DebugReloader.watcher.addCallback(self.reloadPlugins)

    def migratePlugins(self):
        for dir_name in os.listdir(self.plugin_path):
            if dir_name == "Mute":
                self.log.info("Deleting deprecated/renamed plugin: %s" % dir_name)
                shutil.rmtree("%s/%s" % (self.plugin_path, dir_name))

    # -- Load / Unload --

    # Load all plugin
    def loadPlugins(self):
        all_loaded = True
        s = time.time()
        for dir_name in sorted(os.listdir(self.plugin_path)):
            dir_path = os.path.join(self.plugin_path, dir_name)
            if dir_name == "__pycache__":
                continue  # skip
            if dir_name.startswith("disabled"):
                continue  # Dont load if disabled
            if not os.path.isdir(dir_path):
                continue  # Dont load if not dir
            if dir_name.startswith("Debug") and not config.debug:
                continue  # Only load in debug mode if module name starts with Debug
            self.log.debug("Loading plugin: %s" % dir_name)
            try:
                __import__(dir_name)
            except Exception as err:
                self.log.error("Plugin %s load error: %s" % (dir_name, Debug.formatException(err)))
                all_loaded = False
            if dir_name not in self.plugin_names:
                self.plugin_names.append(dir_name)

        self.log.debug("Plugins loaded in %.3fs" % (time.time() - s))
        for func in self.after_load:
            func()
        return all_loaded

    # Reload all plugins
    def reloadPlugins(self):
        self.reloading = True
        self.after_load = []
        self.plugins_before = self.plugins
        self.plugins = defaultdict(list)  # Reset registered plugins
        for module_name, module in list(sys.modules.items()):
            if module and getattr(module, "__file__", None) and self.plugin_path in module.__file__:  # Module file in plugin_path
                if "allow_reload" in dir(module) and not module.allow_reload:  # Reload disabled
                    # Re-add non-reloadable plugins
                    for class_name, classes in self.plugins_before.items():
                        for c in classes:
                            if c.__module__ != module.__name__:
                                continue
                            self.plugins[class_name].append(c)
                else:
                    try:
                        importlib.reload(module)
                    except Exception as err:
                        self.log.error("Plugin %s reload error: %s" % (module_name, Debug.formatException(err)))

        self.loadPlugins()  # Load new plugins

        # Change current classes in memory
        import gc
        patched = {}
        for class_name, classes in self.plugins.items():
            classes = classes[:]  # Copy the current plugins
            classes.reverse()
            base_class = self.pluggable[class_name]  # Original class
            classes.append(base_class)  # Add the class itself to end of inherience line
            plugined_class = type(class_name, tuple(classes), dict())  # Create the plugined class
            for obj in gc.get_objects():
                if type(obj).__name__ == class_name:
                    obj.__class__ = plugined_class
                    patched[class_name] = patched.get(class_name, 0) + 1
        self.log.debug("Patched objects: %s" % patched)

        # Change classes in modules
        patched = {}
        for class_name, classes in self.plugins.items():
            for module_name, module in list(sys.modules.items()):
                if class_name in dir(module):
                    if "__class__" not in dir(getattr(module, class_name)):  # Not a class
                        continue
                    base_class = self.pluggable[class_name]
                    classes = self.plugins[class_name][:]
                    classes.reverse()
                    classes.append(base_class)
                    plugined_class = type(class_name, tuple(classes), dict())
                    setattr(module, class_name, plugined_class)
                    patched[class_name] = patched.get(class_name, 0) + 1

        self.log.debug("Patched modules: %s" % patched)
        self.reloading = False


plugin_manager = PluginManager()  # Singletone

# -- Decorators --

# Accept plugin to class decorator


def acceptPlugins(base_class):
    class_name = base_class.__name__
    plugin_manager.pluggable[class_name] = base_class
    if class_name in plugin_manager.plugins:  # Has plugins
        classes = plugin_manager.plugins[class_name][:]  # Copy the current plugins

        # Restore the subclass order after reload
        if class_name in plugin_manager.subclass_order:
            classes = sorted(
                classes,
                key=lambda key:
                    plugin_manager.subclass_order[class_name].index(str(key))
                    if str(key) in plugin_manager.subclass_order[class_name]
                    else 9999
            )
        plugin_manager.subclass_order[class_name] = list(map(str, classes))

        classes.reverse()
        classes.append(base_class)  # Add the class itself to end of inherience line
        plugined_class = type(class_name, tuple(classes), dict())  # Create the plugined class
        plugin_manager.log.debug("New class accepts plugins: %s (Loaded plugins: %s)" % (class_name, classes))
    else:  # No plugins just use the original
        plugined_class = base_class
    return plugined_class


# Register plugin to class name decorator
def registerTo(class_name):
    if config.debug and not plugin_manager.reloading:
        import gc
        for obj in gc.get_objects():
            if type(obj).__name__ == class_name:
                raise Exception("Class %s instances already present in memory" % class_name)
                break

    plugin_manager.log.debug("New plugin registered to: %s" % class_name)
    if class_name not in plugin_manager.plugins:
        plugin_manager.plugins[class_name] = []

    def classDecorator(self):
        plugin_manager.plugins[class_name].append(self)
        return self
    return classDecorator


def afterLoad(func):
    plugin_manager.after_load.append(func)
    return func


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

    print(Request().route("MainPage"))

import logging
import time
import threading

from Config import config

if config.debug:  # Only load pyfilesytem if using debug mode
    try:
        import fs.watch
        import fs.osfs
        pyfilesystem = fs.osfs.OSFS("src")
        pyfilesystem_plugins = fs.osfs.OSFS("plugins")
        logging.debug("Pyfilesystem detected, source code autoreload enabled")
    except Exception, err:
        pyfilesystem = False
else:
    pyfilesystem = False


class DebugReloader:

    def __init__(self, callback, directory="/"):
        self.last_chaged = 0
        if pyfilesystem:
            self.directory = directory
            self.callback = callback
            if config.action == "main":
                logging.debug("Adding autoreload: %s, cb: %s" % (directory, callback))
                thread = threading.Thread(target=self.addWatcher)
                thread.daemon = True
                thread.start()

    def addWatcher(self, recursive=True):
        try:
            time.sleep(1)  # Wait for .pyc compiles
            watch_events = [fs.watch.CREATED, fs.watch.MODIFIED]
            pyfilesystem.add_watcher(self.changed, path=self.directory, events=watch_events, recursive=recursive)
            pyfilesystem_plugins.add_watcher(self.changed, path=self.directory, events=watch_events, recursive=recursive)
        except Exception, err:
            print "File system watcher failed: %s (on linux pyinotify not gevent compatible yet :( )" % err

    def changed(self, evt):
        if (
            not evt.path or "%s/" % config.data_dir in evt.path or
            (not evt.path.endswith("py") and not evt.path.endswith("json")) or
            "Test" in evt.path or
            time.time() - self.last_chaged < 5.0
        ):
            return False  # Ignore *.pyc changes and no reload within 1 sec
        self.last_chaged = time.time()
        logging.debug("File changed: %s, cb: %s reloading source code" % (evt.path, self.callback))
        time.sleep(0.1)  # Wait for lock release
        self.callback()

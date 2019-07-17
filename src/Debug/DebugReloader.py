import logging
import time
import os

from Config import config

if config.debug and config.action == "main":
    try:
        import watchdog
        import watchdog.observers
        import watchdog.events
        logging.debug("Watchdog fs listener detected, source code autoreload enabled")
        enabled = True
    except Exception as err:
        logging.debug("Watchdog fs listener could not be loaded: %s" % err)
        enabled = False
else:
    enabled = False


class DebugReloader:
    def __init__(self, paths=["src", "plugins"]):
        self.log = logging.getLogger("DebugReloader")
        self.last_chaged = 0
        self.callbacks = []
        if enabled:
            self.observer = watchdog.observers.Observer()
            event_handler = watchdog.events.FileSystemEventHandler()
            event_handler.on_modified = event_handler.on_deleted = self.onChanged
            event_handler.on_created = event_handler.on_moved = self.onChanged
            for path in paths:
                self.log.debug("Adding autoreload: %s" % path)
                self.observer.schedule(event_handler, path, recursive=True)
            self.observer.start()

    def addCallback(self, f):
        self.callbacks.append(f)

    def onChanged(self, evt):
        path = evt.src_path
        ext = path.rsplit(".", 1)[-1]
        if ext not in ["py", "json"] or "Test" in path or time.time() - self.last_chaged < 1.0:
            return False
        self.last_chaged = time.time()
        time_modified = os.path.getmtime(path)
        self.log.debug("File changed: %s reloading source code (modified %.3fs ago)" % (evt, time.time() - time_modified))
        if time.time() - time_modified > 5:  # Probably it's just an attribute change, ignore it
            return False

        time.sleep(0.1)  # Wait for lock release
        for callback in self.callbacks:
            try:
                callback()
            except Exception as err:
                self.log.exception(err)

    def stop(self):
        if enabled:
            self.observer.stop()
            self.log.debug("Stopped autoreload observer")

watcher = DebugReloader()

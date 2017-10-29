import time

import gevent

from Debug import Debug
from Config import config


class Worker(object):

    def __init__(self, manager, peer):
        self.manager = manager
        self.peer = peer
        self.task = None
        self.key = None
        self.running = False
        self.thread = None

    def __str__(self):
        return "Worker %s %s" % (self.manager.site.address_short, self.key)

    def __repr__(self):
        return "<%s>" % self.__str__()

    # Downloader thread
    def downloader(self):
        self.peer.hash_failed = 0  # Reset hash error counter
        while self.running:
            # Try to pickup free file download task
            task = self.manager.getTask(self.peer)
            if not task:  # No more task
                time.sleep(0.1)  # Wait a bit for new tasks
                task = self.manager.getTask(self.peer)
                if not task:  # Still no task, stop it
                    self.manager.log.debug("%s: No task found, stopping" % self.key)
                    break
            if not task["time_started"]:
                task["time_started"] = time.time()  # Task started now

            if task["workers_num"] > 0:  # Wait a bit if someone already working on it
                if config.verbose:
                    self.manager.log.debug("%s: Someone already working on %s (pri: %s), sleeping 1 sec..." % (self.key, task["inner_path"], task["priority"]))
                for sleep_i in range(1,10):
                    time.sleep(0.1)
                    if task["done"] or task["workers_num"] == 0:
                        if config.verbose:
                            self.manager.log.debug("%s: %s, picked task free after %ss sleep. (done: %s)" % (self.key, task["inner_path"], 0.1 * sleep_i, task["done"]))
                        break

            if task["done"]:
                continue

            self.task = task
            site = task["site"]
            task["workers_num"] += 1
            try:
                buff = self.peer.getFile(site.address, task["inner_path"], task["size"])
            except Exception, err:
                self.manager.log.debug("%s: getFile error: %s" % (self.key, err))
                buff = None
            if self.running is False:  # Worker no longer needed or got killed
                self.manager.log.debug("%s: No longer needed, returning: %s" % (self.key, task["inner_path"]))
                break
            if task["done"] is True:  # Task done, try to find new one
                continue
            if buff:  # Download ok
                try:
                    correct = site.content_manager.verifyFile(task["inner_path"], buff)
                except Exception, err:
                    correct = False
            else:  # Download error
                err = "Download failed"
                correct = False
            if correct is True or correct is None:  # Verify ok or same file
                self.manager.log.debug("%s: Verify correct: %s" % (self.key, task["inner_path"]))
                if correct is True and task["done"] is False:  # Save if changed and task not done yet
                    buff.seek(0)
                    site.storage.write(task["inner_path"], buff)
                if task["done"] is False:
                    self.manager.doneTask(task)
                task["workers_num"] -= 1
            else:  # Verify failed
                task["workers_num"] -= 1
                self.manager.log.debug(
                    "%s: Verify failed: %s, error: %s, failed peers: %s, workers: %s" %
                    (self.key, task["inner_path"], err, len(task["failed"]), task["workers_num"])
                )
                task["failed"].append(self.peer)
                self.peer.hash_failed += 1
                if self.peer.hash_failed >= max(len(self.manager.tasks), 3) or self.peer.connection_error > 10:
                    # Broken peer: More fails than tasks number but atleast 3
                    break
                time.sleep(1)
        self.peer.onWorkerDone()
        self.running = False
        self.manager.removeWorker(self)

    # Start the worker
    def start(self):
        self.running = True
        self.thread = gevent.spawn(self.downloader)

    # Skip current task
    def skip(self):
        self.manager.log.debug("%s: Force skipping" % self.key)
        if self.thread:
            self.thread.kill(exception=Debug.Notify("Worker stopped"))
        self.start()

    # Force stop the worker
    def stop(self):
        self.manager.log.debug("%s: Force stopping" % self.key)
        self.running = False
        if self.thread:
            self.thread.kill(exception=Debug.Notify("Worker stopped"))
        del self.thread
        self.manager.removeWorker(self)

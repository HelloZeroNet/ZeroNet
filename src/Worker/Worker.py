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
        self.num_downloaded = 0
        self.num_failed = 0

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
                    stats = "downloaded files: %s, failed: %s" % (self.num_downloaded, self.num_failed)
                    self.manager.log.debug("%s: No task found, stopping (%s)" % (self.key, stats))
                    break
            if not task["time_started"]:
                task["time_started"] = time.time()  # Task started now

            if task["workers_num"] > 0:  # Wait a bit if someone already working on it
                if task["peers"]:  # It's an update
                    timeout = 3
                else:
                    timeout = 1

                if task["size"] > 100 * 1024 * 1024:
                    timeout = timeout * 2

                if config.verbose:
                    self.manager.log.debug("%s: Someone already working on %s (pri: %s), sleeping %s sec..." % (
                        self.key, task["inner_path"], task["priority"], timeout
                    ))

                for sleep_i in range(1, timeout * 10):
                    time.sleep(0.1)
                    if task["done"] or task["workers_num"] == 0:
                        if config.verbose:
                            self.manager.log.debug("%s: %s, picked task free after %ss sleep. (done: %s)" % (
                                self.key, task["inner_path"], 0.1 * sleep_i, task["done"]
                            ))
                        break

                    if sleep_i % 10 == 0:
                        workers = self.manager.findWorkers(task)
                        if not workers or not workers[0].peer.connection:
                            break
                        worker_idle = time.time() - workers[0].peer.connection.last_recv_time
                        if worker_idle > 1:
                            if config.verbose:
                                self.manager.log.debug("%s: %s, worker %s seems idle, picked up task after %ss sleep. (done: %s)" % (
                                    self.key, task["inner_path"], workers[0].key, 0.1 * sleep_i, task["done"]
                                ))
                            break

            if task["done"]:
                continue

            self.task = task
            site = task["site"]
            task["workers_num"] += 1
            error_message = "Unknown error"
            try:
                buff = self.peer.getFile(site.address, task["inner_path"], task["size"])
            except Exception as err:
                self.manager.log.debug("%s: getFile error: %s" % (self.key, err))
                error_message = str(err)
                buff = None
            if self.running is False:  # Worker no longer needed or got killed
                self.manager.log.debug("%s: No longer needed, returning: %s" % (self.key, task["inner_path"]))
                break
            if task["done"] is True:  # Task done, try to find new one
                continue
            if buff:  # Download ok
                try:
                    correct = site.content_manager.verifyFile(task["inner_path"], buff)
                except Exception as err:
                    error_message = str(err)
                    correct = False
            else:  # Download error
                error_message = "Download failed"
                correct = False
            if correct is True or correct is None:  # Verify ok or same file
                if self.manager.started_task_num < 50 or config.verbose:
                    self.manager.log.debug("%s: Verify correct: %s" % (self.key, task["inner_path"]))
                write_error = None
                if correct is True and task["done"] is False:  # Save if changed and task not done yet
                    buff.seek(0)
                    try:
                        site.storage.write(task["inner_path"], buff)
                        write_error = False
                    except Exception as err:
                        self.manager.log.error("%s: Error writing: %s (%s)" % (self.key, task["inner_path"], err))
                        write_error = err
                if task["done"] is False:
                    if write_error:
                        self.manager.failTask(task)
                        self.num_failed += 1
                    else:
                        self.manager.doneTask(task)
                        self.num_downloaded += 1
                task["workers_num"] -= 1
            else:  # Verify failed
                self.num_failed += 1
                task["workers_num"] -= 1
                if self.manager.started_task_num < 50 or config.verbose:
                    self.manager.log.debug(
                        "%s: Verify failed: %s, error: %s, failed peers: %s, workers: %s" %
                        (self.key, task["inner_path"], error_message, len(task["failed"]), task["workers_num"])
                    )
                task["failed"].append(self.peer)
                self.peer.hash_failed += 1
                if self.peer.hash_failed >= max(len(self.manager.tasks), 3) or self.peer.connection_error > 10:
                    # Broken peer: More fails than tasks number but atleast 3
                    break
                if task["inner_path"] not in site.bad_files:
                    # Don't need this file anymore
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

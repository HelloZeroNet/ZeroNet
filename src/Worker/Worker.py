import time

import gevent
import gevent.lock

from Debug import Debug
from Config import config
from Content.ContentManager import VerifyError


class WorkerDownloadError(Exception):
    pass


class WorkerIOError(Exception):
    pass


class WorkerStop(Exception):
    pass


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

    def waitForTask(self, task, timeout):  # Wait for other workers to finish the task
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
        return True

    def pickTask(self):  # Find and select a new task for the worker
        task = self.manager.getTask(self.peer)
        if not task:  # No more task
            time.sleep(0.1)  # Wait a bit for new tasks
            task = self.manager.getTask(self.peer)
            if not task:  # Still no task, stop it
                stats = "downloaded files: %s, failed: %s" % (self.num_downloaded, self.num_failed)
                self.manager.log.debug("%s: No task found, stopping (%s)" % (self.key, stats))
                return False

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

            self.waitForTask(task, timeout)
        return task

    def downloadTask(self, task):
        try:
            buff = self.peer.getFile(task["site"].address, task["inner_path"], task["size"])
        except Exception as err:
            self.manager.log.debug("%s: getFile error: %s" % (self.key, err))
            raise WorkerDownloadError(str(err))

        if not buff:
            raise WorkerDownloadError("No response")

        return buff

    def getTaskLock(self, task):
        if task["lock"] is None:
            task["lock"] = gevent.lock.Semaphore()
        return task["lock"]

    def writeTask(self, task, buff):
        buff.seek(0)
        try:
            task["site"].storage.write(task["inner_path"], buff)
        except Exception as err:
            if type(err) == Debug.Notify:
                self.manager.log.debug("%s: Write aborted: %s (%s: %s)" % (self.key, task["inner_path"], type(err), err))
            else:
                self.manager.log.error("%s: Error writing: %s (%s: %s)" % (self.key, task["inner_path"], type(err), err))
            raise WorkerIOError(str(err))

    def onTaskVerifyFail(self, task, error_message):
        self.num_failed += 1
        if self.manager.started_task_num < 50 or config.verbose:
            self.manager.log.debug(
                "%s: Verify failed: %s, error: %s, failed peers: %s, workers: %s" %
                (self.key, task["inner_path"], error_message, len(task["failed"]), task["workers_num"])
            )
        task["failed"].append(self.peer)
        self.peer.hash_failed += 1
        if self.peer.hash_failed >= max(len(self.manager.tasks), 3) or self.peer.connection_error > 10:
            # Broken peer: More fails than tasks number but atleast 3
            raise WorkerStop(
                "Too many errors (hash failed: %s, connection error: %s)" %
                (self.peer.hash_failed, self.peer.connection_error)
            )

    def handleTask(self, task):
        download_err = write_err = False

        write_lock = None
        try:
            buff = self.downloadTask(task)

            if task["done"] is True:  # Task done, try to find new one
                return None

            if self.running is False:  # Worker no longer needed or got killed
                self.manager.log.debug("%s: No longer needed, returning: %s" % (self.key, task["inner_path"]))
                raise WorkerStop("Running got disabled")

            write_lock = self.getTaskLock(task)
            write_lock.acquire()
            if task["site"].content_manager.verifyFile(task["inner_path"], buff) is None:
                is_same = True
            else:
                is_same = False
            is_valid = True
        except (WorkerDownloadError, VerifyError) as err:
            download_err = err
            is_valid = False
            is_same = False

        if is_valid and not is_same:
            if self.manager.started_task_num < 50 or task["priority"] > 10 or config.verbose:
                self.manager.log.debug("%s: Verify correct: %s" % (self.key, task["inner_path"]))
            try:
                self.writeTask(task, buff)
            except WorkerIOError as err:
                write_err = err

        if not task["done"]:
            if write_err:
                self.manager.failTask(task, reason="Write error")
                self.num_failed += 1
                self.manager.log.error("%s: Error writing %s: %s" % (self.key, task["inner_path"], write_err))
            elif is_valid:
                self.manager.doneTask(task)
                self.num_downloaded += 1

        if write_lock is not None and write_lock.locked():
            write_lock.release()

        if not is_valid:
            self.onTaskVerifyFail(task, download_err)
            time.sleep(1)
            return False

        return True

    def downloader(self):
        self.peer.hash_failed = 0  # Reset hash error counter
        while self.running:
            # Try to pickup free file download task
            task = self.pickTask()

            if not task:
                break

            if task["done"]:
                continue

            self.task = task

            self.manager.addTaskWorker(task, self)

            try:
                success = self.handleTask(task)
            except WorkerStop as err:
                self.manager.log.debug("%s: Worker stopped: %s" % (self.key, err))
                self.manager.removeTaskWorker(task, self)
                break

            self.manager.removeTaskWorker(task, self)

        self.peer.onWorkerDone()
        self.running = False
        self.manager.removeWorker(self)

    # Start the worker
    def start(self):
        self.running = True
        self.thread = gevent.spawn(self.downloader)

    # Skip current task
    def skip(self, reason="Unknown"):
        self.manager.log.debug("%s: Force skipping (reason: %s)" % (self.key, reason))
        if self.thread:
            self.thread.kill(exception=Debug.Notify("Worker skipping (reason: %s)" % reason))
        self.start()

    # Force stop the worker
    def stop(self, reason="Unknown"):
        self.manager.log.debug("%s: Force stopping (reason: %s)" % (self.key, reason))
        self.running = False
        if self.thread:
            self.thread.kill(exception=Debug.Notify("Worker stopped (reason: %s)" % reason))
        del self.thread
        self.manager.removeWorker(self)

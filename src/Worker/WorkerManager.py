import time
import logging
import random
import collections

import gevent

from Worker import Worker
from Config import config
from util import helper
from Plugin import PluginManager
import util


@PluginManager.acceptPlugins
class WorkerManager(object):

    def __init__(self, site):
        self.site = site
        self.workers = {}  # Key: ip:port, Value: Worker.Worker
        self.tasks = []
        # {"evt": evt, "workers_num": 0, "site": self.site, "inner_path": inner_path, "done": False, "optional_hash_id": None,
        # "time_started": None, "time_added": time.time(), "peers": peers, "priority": 0, "failed": peer_ids}
        self.started_task_num = 0  # Last added task num
        self.asked_peers = []
        self.running = True
        self.time_task_added = 0
        self.log = logging.getLogger("WorkerManager:%s" % self.site.address_short)
        self.process_taskchecker = gevent.spawn(self.checkTasks)

    def __str__(self):
        return "WorkerManager %s" % self.site.address_short

    def __repr__(self):
        return "<%s>" % self.__str__()

    # Check expired tasks
    def checkTasks(self):
        while self.running:
            tasks = task = worker = workers = None  # Cleanup local variables
            time.sleep(15)  # Check every 15 sec

            # Clean up workers
            for worker in self.workers.values():
                if worker.task and worker.task["done"]:
                    worker.skip()  # Stop workers with task done

            if not self.tasks:
                continue

            tasks = self.tasks[:]  # Copy it so removing elements wont cause any problem
            for task in tasks:
                size_extra_time = task["size"] / (1024 * 100)  # 1 second for every 100k
                if task["time_started"] and time.time() >= task["time_started"] + 60 + size_extra_time:
                    self.log.debug("Timeout, Skipping: %s" % task)  # Task taking too long time, skip it
                    # Skip to next file workers
                    workers = self.findWorkers(task)
                    if workers:
                        for worker in workers:
                            worker.skip()
                    else:
                        self.failTask(task)
                elif time.time() >= task["time_added"] + 60 + size_extra_time and not self.workers:  # No workers left
                    self.log.debug("Timeout, Cleanup task: %s" % task)
                    # Remove task
                    self.failTask(task)

                elif (task["time_started"] and time.time() >= task["time_started"] + 15) or not self.workers:
                    # Find more workers: Task started more than 15 sec ago or no workers
                    workers = self.findWorkers(task)
                    self.log.debug(
                        "Slow task: %s 15+%ss, (workers: %s, optional_hash_id: %s, peers: %s, failed: %s, asked: %s)" %
                        (
                            task["inner_path"], size_extra_time, len(workers), task["optional_hash_id"],
                            len(task["peers"] or []), len(task["failed"]), len(self.asked_peers)
                        )
                    )
                    task["site"].announce(mode="more")  # Find more peers
                    if task["optional_hash_id"]:
                        if not task["time_started"]:
                            ask_limit = 20
                        elif task["priority"] > 0:
                            ask_limit = max(10, time.time() - task["time_started"])
                        else:
                            ask_limit = max(10, (time.time() - task["time_started"]) / 2)
                        if len(self.asked_peers) < ask_limit and len(task["peers"] or []) <= len(task["failed"]) * 2:
                            # Re-search for high priority
                            self.startFindOptional(find_more=True)
                    else:
                        if task["peers"]:  # Release the peer lock
                            self.log.debug("Task peer lock release: %s" % task["inner_path"])
                            task["peers"] = []
                            self.startWorkers()
                    break  # One reannounce per loop

        self.log.debug("checkTasks stopped running")

    # Returns the next free or less worked task
    def getTask(self, peer):
        # Sort tasks by priority and worker numbers
        self.tasks.sort(key=lambda task: task["priority"] - task["workers_num"] * 5, reverse=True)

        for task in self.tasks:  # Find a task
            if task["peers"] and peer not in task["peers"]:
                continue  # This peer not allowed to pick this task
            if peer in task["failed"]:
                continue  # Peer already tried to solve this, but failed
            if task["optional_hash_id"] and task["peers"] is None:
                continue  # No peers found yet for the optional task
            return task

    def removeGoodFileTasks(self):
        for task in self.tasks[:]:
            if task["inner_path"] not in self.site.bad_files:
                self.log.debug("No longer in bad_files, marking as good: %s" % task["inner_path"])
                task["done"] = True
                task["evt"].set(True)
                self.tasks.remove(task)
        if not self.tasks:
            self.started_task_num = 0
        self.site.updateWebsocket()

    # New peers added to site
    def onPeers(self):
        self.startWorkers()

    def getMaxWorkers(self):
        if len(self.tasks) > 100:
            return config.workers * 3
        else:
            return config.workers

    # Add new worker
    def addWorker(self, peer):
        key = peer.key
        if key not in self.workers and len(self.workers) < self.getMaxWorkers():
            # We dont have worker for that peer and workers num less than max
            worker = Worker(self, peer)
            self.workers[key] = worker
            worker.key = key
            worker.start()
            return worker
        else:  # We have woker for this peer or its over the limit
            return False

    # Start workers to process tasks
    def startWorkers(self, peers=None):
        if not self.tasks:
            return False  # No task for workers
        self.log.debug("Starting workers, tasks: %s, peers: %s, workers: %s" % (len(self.tasks), len(peers or []), len(self.workers)))
        if len(self.workers) >= self.getMaxWorkers() and not peers:
            return False  # Workers number already maxed and no starting peers defined
        if not peers:
            peers = self.site.getConnectedPeers()
            if len(peers) < self.getMaxWorkers():
                peers += self.site.peers.values()[0:self.getMaxWorkers()]
        if type(peers) is set:
            peers = list(peers)

        random.shuffle(peers)
        for peer in peers:  # One worker for every peer
            if peers and peer not in peers:
                continue  # If peers defined and peer not valid
            worker = self.addWorker(peer)
            if worker:
                self.log.debug("Added worker: %s, workers: %s/%s" % (peer.key, len(self.workers), self.getMaxWorkers()))

    # Find peers for optional hash in local hash tables and add to task peers
    def findOptionalTasks(self, optional_tasks, reset_task=False):
        found = collections.defaultdict(list)  # { found_hash: [peer1, peer2...], ...}

        for peer in self.site.peers.values():
            if not peer.has_hashfield:
                continue

            hashfield_set = set(peer.hashfield)  # Finding in set is much faster
            for task in optional_tasks:
                optional_hash_id = task["optional_hash_id"]
                if optional_hash_id in hashfield_set:
                    if reset_task and len(task["failed"]) > 0:
                        task["failed"] = []
                    if peer in task["failed"]:
                        continue
                    found[optional_hash_id].append(peer)
                    if task["peers"] and peer not in task["peers"]:
                        task["peers"].append(peer)
                    else:
                        task["peers"] = [peer]

        return found

    # Find peers for optional hash ids in local hash tables
    def findOptionalHashIds(self, optional_hash_ids, limit=0):
        found = collections.defaultdict(list)  # { found_hash_id: [peer1, peer2...], ...}

        for peer in self.site.peers.values():
            if not peer.has_hashfield:
                continue

            hashfield_set = set(peer.hashfield)  # Finding in set is much faster
            for optional_hash_id in optional_hash_ids:
                if optional_hash_id in hashfield_set:
                    found[optional_hash_id].append(peer)
                    if limit and len(found[optional_hash_id]) >= limit:
                        optional_hash_ids.remove(optional_hash_id)

        return found

    # Add peers to tasks from found result
    def addOptionalPeers(self, found_ips):
        found = collections.defaultdict(list)
        for hash_id, peer_ips in found_ips.iteritems():
            task = [task for task in self.tasks if task["optional_hash_id"] == hash_id]
            if task:  # Found task, lets take the first
                task = task[0]
            else:
                continue
            for peer_ip in peer_ips:
                peer = self.site.addPeer(peer_ip[0], peer_ip[1], return_peer=True)
                if not peer:
                    continue
                if task["peers"] is None:
                    task["peers"] = []
                if peer not in task["peers"]:
                    task["peers"].append(peer)
                    found[hash_id].append(peer)
                if peer.hashfield.appendHashId(hash_id):  # Peer has this file
                    peer.time_hashfield = None  # Peer hashfield probably outdated

        return found

    # Start find peers for optional files
    @util.Noparallel(blocking=False, ignore_args=True)
    def startFindOptional(self, reset_task=False, find_more=False, high_priority=False):
        # Wait for more file requests
        if len(self.tasks) < 20 or high_priority:
            time.sleep(0.01)
        if len(self.tasks) > 90:
            time.sleep(5)
        else:
            time.sleep(0.5)

        optional_tasks = [task for task in self.tasks if task["optional_hash_id"]]
        if not optional_tasks:
            return False
        optional_hash_ids = set([task["optional_hash_id"] for task in optional_tasks])
        time_tasks = self.time_task_added

        self.log.debug(
            "Finding peers for optional files: %s (reset_task: %s, find_more: %s)" %
            (optional_hash_ids, reset_task, find_more)
        )
        found = self.findOptionalTasks(optional_tasks, reset_task=reset_task)

        if found:
            found_peers = set([peer for peers in found.values() for peer in peers])
            self.startWorkers(found_peers)

        if len(found) < len(optional_hash_ids) or find_more or (high_priority and any(len(peers) < 10 for peers in found.itervalues())):
            self.log.debug("No local result for optional files: %s" % (optional_hash_ids - set(found)))

            # Query hashfield from connected peers
            threads = []
            peers = self.site.getConnectedPeers()
            if not peers:
                peers = self.site.getConnectablePeers()
            for peer in peers:
                if not peer.time_hashfield:
                    threads.append(gevent.spawn(peer.updateHashfield))
            gevent.joinall(threads, timeout=5)

            if time_tasks != self.time_task_added:  # New task added since start
                optional_tasks = [task for task in self.tasks if task["optional_hash_id"]]
                optional_hash_ids = set([task["optional_hash_id"] for task in optional_tasks])

            found = self.findOptionalTasks(optional_tasks)
            self.log.debug("Found optional files after query hashtable connected peers: %s/%s" % (
                len(found), len(optional_hash_ids)
            ))

            if found:
                found_peers = set([peer for hash_id_peers in found.values() for peer in hash_id_peers])
                self.startWorkers(found_peers)

        if len(found) < len(optional_hash_ids) or find_more:
            self.log.debug("No connected hashtable result for optional files: %s" % (optional_hash_ids - set(found)))

            # Try to query connected peers
            threads = []
            peers = [peer for peer in self.site.getConnectedPeers() if peer not in self.asked_peers]
            if not peers:
                peers = self.site.getConnectablePeers()

            for peer in peers:
                threads.append(gevent.spawn(peer.findHashIds, list(optional_hash_ids)))
                self.asked_peers.append(peer)

            for i in range(5):
                time.sleep(1)
                thread_values = [thread.value for thread in threads if thread.value]
                if not thread_values:
                    continue

                found_ips = helper.mergeDicts(thread_values)
                found = self.addOptionalPeers(found_ips)
                self.log.debug("Found optional files after findhash connected peers: %s/%s (asked: %s)" % (
                    len(found), len(optional_hash_ids), len(threads)
                ))

                if found:
                    found_peers = set([peer for hash_id_peers in found.values() for peer in hash_id_peers])
                    self.startWorkers(found_peers)

                if len(thread_values) == len(threads):
                    # Got result from all started thread
                    break

        if len(found) < len(optional_hash_ids):
            self.log.debug("No findHash result, try random peers: %s" % (optional_hash_ids - set(found)))
            # Try to query random peers

            if time_tasks != self.time_task_added:  # New task added since start
                optional_tasks = [task for task in self.tasks if task["optional_hash_id"]]
                optional_hash_ids = set([task["optional_hash_id"] for task in optional_tasks])

            threads = []
            peers = self.site.getConnectablePeers(ignore=self.asked_peers)

            for peer in peers:
                threads.append(gevent.spawn(peer.findHashIds, list(optional_hash_ids)))
                self.asked_peers.append(peer)

            gevent.joinall(threads, timeout=15)

            found_ips = helper.mergeDicts([thread.value for thread in threads if thread.value])
            found = self.addOptionalPeers(found_ips)
            self.log.debug("Found optional files after findhash random peers: %s/%s" % (len(found), len(optional_hash_ids)))

            if found:
                found_peers = set([peer for hash_id_peers in found.values() for peer in hash_id_peers])
                self.startWorkers(found_peers)

        if len(found) < len(optional_hash_ids):
            self.log.debug("No findhash result for optional files: %s" % (optional_hash_ids - set(found)))

    # Stop all worker
    def stopWorkers(self):
        for worker in self.workers.values():
            worker.stop()
        tasks = self.tasks[:]  # Copy
        for task in tasks:  # Mark all current task as failed
            self.failTask(task)

    # Find workers by task
    def findWorkers(self, task):
        workers = []
        for worker in self.workers.values():
            if worker.task == task:
                workers.append(worker)
        return workers

    # Ends and remove a worker
    def removeWorker(self, worker):
        worker.running = False
        if worker.key in self.workers:
            del(self.workers[worker.key])
            self.log.debug("Removed worker, workers: %s/%s" % (len(self.workers), self.getMaxWorkers()))
        if len(self.workers) <= self.getMaxWorkers() / 3 and len(self.asked_peers) < 10:
            important_task = (task for task in self.tasks if task["priority"] > 0)
            if next(important_task, None) or len(self.asked_peers) == 0:
                self.startFindOptional(find_more=True)
            else:
                self.startFindOptional()


    # Tasks sorted by this
    def getPriorityBoost(self, inner_path):
        if inner_path == "content.json":
            return 9999  # Content.json always priority
        if inner_path == "index.html":
            return 9998  # index.html also important
        if "-default" in inner_path:
            return -4  # Default files are cloning not important
        elif inner_path.endswith(".css"):
            return 5  # boost css files priority
        elif inner_path.endswith(".js"):
            return 4  # boost js files priority
        elif inner_path.endswith("dbschema.json"):
            return 3  # boost database specification
        elif inner_path.endswith("content.json"):
            return 1  # boost included content.json files priority a bit
        elif inner_path.endswith(".json"):
            return 2  # boost data json files priority more
        return 0

    # Create new task and return asyncresult
    def addTask(self, inner_path, peer=None, priority=0):
        self.site.onFileStart(inner_path)  # First task, trigger site download started
        task = self.findTask(inner_path)
        if task:  # Already has task for that file
            if peer and task["peers"]:  # This peer also has new version, add it to task possible peers
                task["peers"].append(peer)
                self.log.debug("Added peer %s to %s" % (peer.key, task["inner_path"]))
                self.startWorkers([peer])
            elif peer and peer in task["failed"]:
                task["failed"].remove(peer)  # New update arrived, remove the peer from failed peers
                self.log.debug("Removed peer %s from failed %s" % (peer.key, task["inner_path"]))
                self.startWorkers([peer])

            if priority:
                task["priority"] += priority  # Boost on priority
            return task["evt"]
        else:  # No task for that file yet
            evt = gevent.event.AsyncResult()
            if peer:
                peers = [peer]  # Only download from this peer
            else:
                peers = None
            file_info = self.site.content_manager.getFileInfo(inner_path)
            if file_info and file_info["optional"]:
                optional_hash_id = helper.toHashId(file_info["sha512"])
            else:
                optional_hash_id = None
            if file_info:
                size = file_info.get("size", 0)
            else:
                size = 0
            priority += self.getPriorityBoost(inner_path)
            task = {
                "evt": evt, "workers_num": 0, "site": self.site, "inner_path": inner_path, "done": False,
                "optional_hash_id": optional_hash_id, "time_added": time.time(), "time_started": None,
                "time_action": None, "peers": peers, "priority": priority, "failed": [], "size": size
            }

            self.tasks.append(task)

            self.started_task_num += 1
            self.log.debug(
                "New task: %s, peer lock: %s, priority: %s, optional_hash_id: %s, tasks started: %s" %
                (task["inner_path"], peers, priority, optional_hash_id, self.started_task_num)
            )
            self.time_task_added = time.time()

            if optional_hash_id:
                if self.asked_peers:
                    del self.asked_peers[:]  # Reset asked peers
                self.startFindOptional(high_priority=priority > 0)

                if peers:
                    self.startWorkers(peers)

            else:
                self.startWorkers(peers)
            return evt

    # Find a task using inner_path
    def findTask(self, inner_path):
        for task in self.tasks:
            if task["inner_path"] == inner_path:
                return task
        return None  # Not found

    # Wait for other tasks
    def checkComplete(self):
        time.sleep(0.1)
        if not self.tasks:
            self.log.debug("Check compelte: No tasks")
            self.onComplete()

    def onComplete(self):
        self.started_task_num = 0
        del self.asked_peers[:]
        self.site.onComplete()  # No more task trigger site complete

    # Mark a task done
    def doneTask(self, task):
        task["done"] = True
        self.tasks.remove(task)  # Remove from queue
        if task["optional_hash_id"]:
            self.log.debug("Downloaded optional file, adding to hashfield: %s" % task["inner_path"])
            self.site.content_manager.optionalDownloaded(task["inner_path"], task["optional_hash_id"], task["size"])
        self.site.onFileDone(task["inner_path"])
        task["evt"].set(True)
        if not self.tasks:
            gevent.spawn(self.checkComplete)

    # Mark a task failed
    def failTask(self, task):
        if task in self.tasks:
            task["done"] = True
            self.tasks.remove(task)  # Remove from queue
            self.site.onFileFail(task["inner_path"])
            task["evt"].set(False)
            if not self.tasks:
                self.started_task_num = 0

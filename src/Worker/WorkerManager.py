import time
import logging
import collections

import gevent

from .Worker import Worker
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
            announced = False
            time.sleep(15)  # Check every 15 sec

            # Clean up workers
            for worker in list(self.workers.values()):
                if worker.task and worker.task["done"]:
                    worker.skip()  # Stop workers with task done

            if not self.tasks:
                continue

            tasks = self.tasks[:]  # Copy it so removing elements wont cause any problem
            num_tasks_started = len([task for task in tasks if task["time_started"]])

            self.log.debug(
                "Tasks: %s, started: %s, bad files: %s, total started: %s" %
                (len(tasks), num_tasks_started, len(self.site.bad_files), self.started_task_num)
            )

            for task in tasks:
                if task["time_started"] and time.time() >= task["time_started"] + 60:
                    self.log.debug("Timeout, Skipping: %s" % task)  # Task taking too long time, skip it
                    # Skip to next file workers
                    workers = self.findWorkers(task)
                    if workers:
                        for worker in workers:
                            worker.skip()
                    else:
                        self.failTask(task)

                elif time.time() >= task["time_added"] + 60 and not self.workers:  # No workers left
                    self.log.debug("Timeout, Cleanup task: %s" % task)
                    # Remove task
                    self.failTask(task)

                elif (task["time_started"] and time.time() >= task["time_started"] + 15) or not self.workers:
                    # Find more workers: Task started more than 15 sec ago or no workers
                    workers = self.findWorkers(task)
                    self.log.debug(
                        "Slow task: %s, (workers: %s, optional_hash_id: %s, peers: %s, failed: %s, asked: %s)" %
                        (
                            task["inner_path"], len(workers), task["optional_hash_id"],
                            len(task["peers"] or []), len(task["failed"]), len(self.asked_peers)
                        )
                    )
                    if not announced:
                        task["site"].announce(mode="more")  # Find more peers
                        announced = True
                    if task["optional_hash_id"]:
                        if self.workers:
                            if not task["time_started"]:
                                ask_limit = 20
                            else:
                                ask_limit = max(10, time.time() - task["time_started"])
                            if len(self.asked_peers) < ask_limit and len(task["peers"] or []) <= len(task["failed"]) * 2:
                                # Re-search for high priority
                                self.startFindOptional(find_more=True)
                        if task["peers"]:
                            peers_try = [peer for peer in task["peers"] if peer not in task["failed"] and peer not in workers]
                            if peers_try:
                                self.startWorkers(peers_try, force_num=5, reason="Task checker (optional, has peers)")
                            else:
                                self.startFindOptional(find_more=True)
                        else:
                            self.startFindOptional(find_more=True)
                    else:
                        if task["peers"]:  # Release the peer lock
                            self.log.debug("Task peer lock release: %s" % task["inner_path"])
                            task["peers"] = []
                        self.startWorkers(reason="Task checker")

            if len(self.tasks) > len(self.workers) * 2 and len(self.workers) < self.getMaxWorkers():
                self.startWorkers(reason="Task checker (need more workers)")

        self.log.debug("checkTasks stopped running")

    # Returns the next free or less worked task
    def getTask(self, peer):
        # Sort tasks by priority and worker numbers
        self.tasks.sort(key=lambda task: task["priority"] - task["workers_num"] * 10, reverse=True)

        for task in self.tasks:  # Find a task
            if task["peers"] and peer not in task["peers"]:
                continue  # This peer not allowed to pick this task
            if peer in task["failed"]:
                continue  # Peer already tried to solve this, but failed
            if task["optional_hash_id"] and task["peers"] is None:
                continue  # No peers found yet for the optional task
            return task

    def removeSolvedFileTasks(self, mark_as_good=True):
        for task in self.tasks[:]:
            if task["inner_path"] not in self.site.bad_files:
                self.log.debug("No longer in bad_files, marking as %s: %s" % (mark_as_good, task["inner_path"]))
                task["done"] = True
                task["evt"].set(mark_as_good)
                self.tasks.remove(task)
        if not self.tasks:
            self.started_task_num = 0
        self.site.updateWebsocket()

    # New peers added to site
    def onPeers(self):
        self.startWorkers(reason="More peers found")

    def getMaxWorkers(self):
        if len(self.tasks) > 50:
            return config.workers * 3
        else:
            return config.workers

    # Add new worker
    def addWorker(self, peer, multiplexing=False, force=False):
        key = peer.key
        if len(self.workers) > self.getMaxWorkers() and not force:
            return False
        if multiplexing:  # Add even if we already have worker for this peer
            key = "%s/%s" % (key, len(self.workers))
        if key not in self.workers:
            # We dont have worker for that peer and workers num less than max
            task = self.getTask(peer)
            if task:
                worker = Worker(self, peer)
                self.workers[key] = worker
                worker.key = key
                worker.start()
                return worker
            else:
                return False
        else:  # We have worker for this peer or its over the limit
            return False

    def taskAddPeer(self, task, peer):
        if task["peers"] is None:
            task["peers"] = []
        if peer in task["failed"]:
            return False

        if peer not in task["peers"]:
            task["peers"].append(peer)
        return True

    # Start workers to process tasks
    def startWorkers(self, peers=None, force_num=0, reason="Unknown"):
        if not self.tasks:
            return False  # No task for workers
        max_workers = min(self.getMaxWorkers(), len(self.site.peers))
        if len(self.workers) >= max_workers and not peers:
            return False  # Workers number already maxed and no starting peers defined
        self.log.debug(
            "Starting workers (%s), tasks: %s, peers: %s, workers: %s" %
            (reason, len(self.tasks), len(peers or []), len(self.workers))
        )
        if not peers:
            peers = self.site.getConnectedPeers()
            if len(peers) < max_workers:
                peers += self.site.getRecentPeers(max_workers * 2)
        if type(peers) is set:
            peers = list(peers)


        # Sort by ping
        peers.sort(key=lambda peer: peer.connection.last_ping_delay if peer.connection and peer.connection.last_ping_delay and len(peer.connection.waiting_requests) == 0 and peer.connection.connected else 9999)

        for peer in peers:  # One worker for every peer
            if peers and peer not in peers:
                continue  # If peers defined and peer not valid

            if force_num:
                worker = self.addWorker(peer, force=True)
                force_num -= 1
            else:
                worker = self.addWorker(peer)

            if worker:
                self.log.debug("Added worker: %s, workers: %s/%s" % (peer.key, len(self.workers), max_workers))

    # Find peers for optional hash in local hash tables and add to task peers
    def findOptionalTasks(self, optional_tasks, reset_task=False):
        found = collections.defaultdict(list)  # { found_hash: [peer1, peer2...], ...}

        for peer in list(self.site.peers.values()):
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
                    if self.taskAddPeer(task, peer):
                        found[optional_hash_id].append(peer)

        return found

    # Find peers for optional hash ids in local hash tables
    def findOptionalHashIds(self, optional_hash_ids, limit=0):
        found = collections.defaultdict(list)  # { found_hash_id: [peer1, peer2...], ...}

        for peer in list(self.site.peers.values()):
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
        for hash_id, peer_ips in found_ips.items():
            task = [task for task in self.tasks if task["optional_hash_id"] == hash_id]
            if task:  # Found task, lets take the first
                task = task[0]
            else:
                continue
            for peer_ip in peer_ips:
                peer = self.site.addPeer(peer_ip[0], peer_ip[1], return_peer=True, source="optional")
                if not peer:
                    continue
                if self.taskAddPeer(task, peer):
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
        elif len(self.tasks) > 90:
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
            found_peers = set([peer for peers in list(found.values()) for peer in peers])
            self.startWorkers(found_peers, force_num=3, reason="Optional found in local peers")

        if len(found) < len(optional_hash_ids) or find_more or (high_priority and any(len(peers) < 10 for peers in found.values())):
            self.log.debug("No local result for optional files: %s" % (optional_hash_ids - set(found)))

            # Query hashfield from connected peers
            threads = []
            peers = self.site.getConnectedPeers()
            if not peers:
                peers = self.site.getConnectablePeers()
            for peer in peers:
                threads.append(gevent.spawn(peer.updateHashfield, force=find_more))
            gevent.joinall(threads, timeout=5)

            if time_tasks != self.time_task_added:  # New task added since start
                optional_tasks = [task for task in self.tasks if task["optional_hash_id"]]
                optional_hash_ids = set([task["optional_hash_id"] for task in optional_tasks])

            found = self.findOptionalTasks(optional_tasks)
            self.log.debug("Found optional files after query hashtable connected peers: %s/%s" % (
                len(found), len(optional_hash_ids)
            ))

            if found:
                found_peers = set([peer for hash_id_peers in list(found.values()) for peer in hash_id_peers])
                self.startWorkers(found_peers, force_num=3, reason="Optional found in connected peers")

        if len(found) < len(optional_hash_ids) or find_more:
            self.log.debug(
                "No connected hashtable result for optional files: %s (asked: %s)" %
                (optional_hash_ids - set(found), len(self.asked_peers))
            )
            if not self.tasks:
                self.log.debug("No tasks, stopping finding optional peers")
                return

            # Try to query connected peers
            threads = []
            peers = [peer for peer in self.site.getConnectedPeers() if peer.key not in self.asked_peers][0:10]
            if not peers:
                peers = self.site.getConnectablePeers(ignore=self.asked_peers)

            for peer in peers:
                threads.append(gevent.spawn(peer.findHashIds, list(optional_hash_ids)))
                self.asked_peers.append(peer.key)

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
                    found_peers = set([peer for hash_id_peers in list(found.values()) for peer in hash_id_peers])
                    self.startWorkers(found_peers, force_num=3, reason="Optional found by findhash connected peers")

                if len(thread_values) == len(threads):
                    # Got result from all started thread
                    break

        if len(found) < len(optional_hash_ids):
            self.log.debug(
                "No findHash result, try random peers: %s (asked: %s)" %
                (optional_hash_ids - set(found), len(self.asked_peers))
            )
            # Try to query random peers

            if time_tasks != self.time_task_added:  # New task added since start
                optional_tasks = [task for task in self.tasks if task["optional_hash_id"]]
                optional_hash_ids = set([task["optional_hash_id"] for task in optional_tasks])

            threads = []
            peers = self.site.getConnectablePeers(ignore=self.asked_peers)

            for peer in peers:
                threads.append(gevent.spawn(peer.findHashIds, list(optional_hash_ids)))
                self.asked_peers.append(peer.key)

            gevent.joinall(threads, timeout=15)

            found_ips = helper.mergeDicts([thread.value for thread in threads if thread.value])
            found = self.addOptionalPeers(found_ips)
            self.log.debug("Found optional files after findhash random peers: %s/%s" % (len(found), len(optional_hash_ids)))

            if found:
                found_peers = set([peer for hash_id_peers in list(found.values()) for peer in hash_id_peers])
                self.startWorkers(found_peers, force_num=3, reason="Option found using findhash random peers")

        if len(found) < len(optional_hash_ids):
            self.log.debug("No findhash result for optional files: %s" % (optional_hash_ids - set(found)))

        if time_tasks != self.time_task_added:  # New task added since start
            self.log.debug("New task since start, restarting...")
            gevent.spawn_later(0.1, self.startFindOptional)
        else:
            self.log.debug("startFindOptional ended")

    # Stop all worker
    def stopWorkers(self):
        for worker in list(self.workers.values()):
            worker.stop()
        tasks = self.tasks[:]  # Copy
        for task in tasks:  # Mark all current task as failed
            self.failTask(task)

    # Find workers by task
    def findWorkers(self, task):
        workers = []
        for worker in list(self.workers.values()):
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
            optional_task = next((task for task in self.tasks if task["optional_hash_id"]), None)
            if optional_task:
                if len(self.workers) == 0:
                    self.startFindOptional(find_more=True)
                else:
                    self.startFindOptional()
            elif self.tasks and not self.workers and worker.task:
                self.log.debug("Starting new workers... (tasks: %s)" % len(self.tasks))
                self.startWorkers(reason="Removed worker")

    # Tasks sorted by this
    def getPriorityBoost(self, inner_path):
        if inner_path == "content.json":
            return 9999  # Content.json always priority
        if inner_path == "index.html":
            return 9998  # index.html also important
        if "-default" in inner_path:
            return -4  # Default files are cloning not important
        elif inner_path.endswith("all.css"):
            return 14  # boost css files priority
        elif inner_path.endswith("all.js"):
            return 13  # boost js files priority
        elif inner_path.endswith("dbschema.json"):
            return 12  # boost database specification
        elif inner_path.endswith("content.json"):
            return 1  # boost included content.json files priority a bit
        elif inner_path.endswith(".json"):
            if len(inner_path) < 50:  # Boost non-user json files
                return 11
            else:
                return 2
        return 0

    # Create new task and return asyncresult
    def addTask(self, inner_path, peer=None, priority=0, file_info=None):
        self.site.onFileStart(inner_path)  # First task, trigger site download started
        task = self.findTask(inner_path)
        if task:  # Already has task for that file
            task["priority"] = max(priority, task["priority"])
            if peer and task["peers"]:  # This peer also has new version, add it to task possible peers
                task["peers"].append(peer)
                self.log.debug("Added peer %s to %s" % (peer.key, task["inner_path"]))
                self.startWorkers([peer], reason="Added new task (update received by peer)")
            elif peer and peer in task["failed"]:
                task["failed"].remove(peer)  # New update arrived, remove the peer from failed peers
                self.log.debug("Removed peer %s from failed %s" % (peer.key, task["inner_path"]))
                self.startWorkers([peer], reason="Added new task (peer failed before)")
            return task
        else:  # No task for that file yet
            evt = gevent.event.AsyncResult()
            if peer:
                peers = [peer]  # Only download from this peer
            else:
                peers = None
            if not file_info:
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

            if self.started_task_num == 0:  # Boost priority for first requested file
                priority += 1

            task = {
                "evt": evt, "workers_num": 0, "site": self.site, "inner_path": inner_path, "done": False,
                "optional_hash_id": optional_hash_id, "time_added": time.time(), "time_started": None,
                "time_action": None, "peers": peers, "priority": priority, "failed": [], "size": size
            }

            self.tasks.append(task)

            self.started_task_num += 1
            if config.verbose:
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
                    self.startWorkers(peers, reason="Added new optional task")

            else:
                self.startWorkers(peers, reason="Added new task")
            return task

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
            self.log.debug("Check complete: No tasks")
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
            self.log.debug(
                "Downloaded optional file in %.3fs, adding to hashfield: %s" %
                (time.time() - task["time_started"], task["inner_path"])
            )
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

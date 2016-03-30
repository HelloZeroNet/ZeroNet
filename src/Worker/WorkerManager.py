import time
import logging
import random
import collections

import gevent

from Worker import Worker
from util import helper
import util


class WorkerManager:

    def __init__(self, site):
        self.site = site
        self.workers = {}  # Key: ip:port, Value: Worker.Worker
        self.tasks = []
        # {"evt": evt, "workers_num": 0, "site": self.site, "inner_path": inner_path, "done": False, "optional_hash_id": None,
        # "time_started": None, "time_added": time.time(), "peers": peers, "priority": 0, "failed": peer_ids}
        self.started_task_num = 0  # Last added task num
        self.running = True
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
                if task["time_started"] and time.time() >= task["time_started"] + 60 + size_extra_time:  # Task taking too long time, skip it
                    self.log.debug("Timeout, Skipping: %s" % task)
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
                        "Task taking more than 15+%s secs, workers: %s find more peers: %s" %
                        (size_extra_time, len(workers), task["inner_path"])
                    )
                    task["site"].announce(mode="more")  # Find more peers
                    if task["optional_hash_id"]:
                        self.startFindOptional(find_more=True)
                    else:
                        if task["peers"]:  # Release the peer lock
                            self.log.debug("Task peer lock release: %s" % task["inner_path"])
                            task["peers"] = []
                            self.startWorkers()
                    break  # One reannounce per loop

        self.log.debug("checkTasks stopped running")

    # Tasks sorted by this
    def taskSorter(self, task):
        inner_path = task["inner_path"]
        if inner_path == "content.json":
            return 9999  # Content.json always priority
        if inner_path == "index.html":
            return 9998  # index.html also important
        priority = task["priority"]
        if "-default" in inner_path:
            priority -= 4  # Default files are cloning not important
        elif inner_path.endswith(".css"):
            priority += 5  # boost css files priority
        elif inner_path.endswith(".js"):
            priority += 4  # boost js files priority
        elif inner_path.endswith("dbschema.json"):
            priority += 3  # boost database specification
        elif inner_path.endswith("content.json"):
            priority += 1  # boost included content.json files priority a bit
        elif inner_path.endswith(".json"):
            priority += 2  # boost data json files priority more
        return priority - task["workers_num"] * 5  # Prefer more priority and less workers

    # Returns the next free or less worked task
    def getTask(self, peer):
        self.tasks.sort(key=self.taskSorter, reverse=True)  # Sort tasks by priority and worker numbers
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
        if len(self.tasks) < 30:
            return 10
        else:
            return 20

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
        if len(self.workers) >= self.getMaxWorkers() and not peers:
            return False  # Workers number already maxed and no starting peers defined
        if not peers:
            peers = self.site.peers.values()  # No peers defined, use any from site
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
            if not peer.hashfield:
                continue

            for task in optional_tasks:
                optional_hash_id = task["optional_hash_id"]
                if optional_hash_id in peer.hashfield:
                    found[optional_hash_id].append(peer)
                    if task["peers"] and peer not in task["peers"]:
                        task["peers"].append(peer)
                    else:
                        task["peers"] = [peer]
                    if reset_task and len(task["failed"]) > 0:
                        task["failed"] = []

        return found

    # Find peers for optional hash ids in local hash tables
    def findOptionalHashIds(self, optional_hash_ids):
        found = collections.defaultdict(list)  # { found_hash_id: [peer1, peer2...], ...}

        for peer in self.site.peers.values():
            if not peer.hashfield:
                continue
            for optional_hash_id in optional_hash_ids:
                if optional_hash_id in peer.hashfield:
                    found[optional_hash_id].append(peer)

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
                if peer.hashfield.appendHashId(hash_id):  # Peer has this file
                    peer.time_hashfield = None  # Peer hashfield probably outdated
                found[hash_id].append(peer)

        return found

    # Start find peers for optional files
    @util.Noparallel(blocking=False)
    def startFindOptional(self, reset_task=False, find_more=False):
        time.sleep(0.01)  # Wait for more file requests
        optional_tasks = [task for task in self.tasks if task["optional_hash_id"]]
        optional_hash_ids = set([task["optional_hash_id"] for task in optional_tasks])
        self.log.debug(
            "Finding peers for optional files: %s (reset_task: %s, find_more: %s)" %
            (optional_hash_ids, reset_task, find_more)
        )
        found = self.findOptionalTasks(optional_tasks, reset_task=reset_task)

        if found:
            found_peers = set([peer for peers in found.values() for peer in peers])
            self.startWorkers(found_peers)

        if len(found) < len(optional_hash_ids) or find_more:
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

            found = self.findOptionalTasks(optional_tasks)
            self.log.debug("Found optional files after query hashtable connected peers: %s/%s" % (len(found), len(optional_hash_ids)))

            if found:
                found_peers = set([peer for hash_id_peers in found.values() for peer in hash_id_peers])
                self.startWorkers(found_peers)

        if len(found) < len(optional_hash_ids) or find_more:
            self.log.debug("No connected hashtable result for optional files: %s" % (optional_hash_ids - set(found)))

            # Try to query connected peers
            threads = []
            peers = self.site.getConnectedPeers()
            if not peers:
                peers = self.site.getConnectablePeers()

            for peer in peers:
                threads.append(gevent.spawn(peer.findHashIds, list(optional_hash_ids)))

            gevent.joinall(threads, timeout=5)

            found_ips = helper.mergeDicts([thread.value for thread in threads if thread.value])
            found = self.addOptionalPeers(found_ips)
            self.log.debug("Found optional files after findhash connected peers: %s/%s" % (len(found), len(optional_hash_ids)))

            if found:
                found_peers = set([peer for hash_id_peers in found.values() for peer in hash_id_peers])
                self.startWorkers(found_peers)

        if len(found) < len(optional_hash_ids):
            self.log.debug("No findHash result, try random peers: %s" % (optional_hash_ids - set(found)))
            # Try to query random peers
            threads = []
            peers = self.site.getConnectablePeers()

            for peer in peers[0:5]:
                threads.append(gevent.spawn(peer.findHashIds, list(optional_hash_ids)))

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
            task = {
                "evt": evt, "workers_num": 0, "site": self.site, "inner_path": inner_path, "done": False, "optional_hash_id": optional_hash_id,
                "time_added": time.time(), "time_started": None, "time_action": None, "peers": peers, "priority": priority, "failed": [], "size": size
            }

            self.tasks.append(task)

            self.started_task_num += 1
            self.log.debug(
                "New task: %s, peer lock: %s, priority: %s, optional_hash_id: %s, tasks: %s" %
                (task["inner_path"], peers, priority, optional_hash_id, self.started_task_num)
            )

            if optional_hash_id:
                self.startFindOptional()
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

    # Mark a task failed
    def failTask(self, task):
        if task in self.tasks:
            task["done"] = True
            self.tasks.remove(task)  # Remove from queue
            self.site.onFileFail(task["inner_path"])
            task["evt"].set(False)
            if not self.tasks:
                self.started_task_num = 0

    # Wait for other tasks
    def checkComplete(self):
        time.sleep(0.1)
        if not self.tasks:
            self.log.debug("Check compelte: No tasks")
            self.started_task_num = 0
            self.site.onComplete()  # No more task trigger site complete

    # Mark a task done
    def doneTask(self, task):
        task["done"] = True
        self.tasks.remove(task)  # Remove from queue
        self.site.onFileDone(task["inner_path"])
        task["evt"].set(True)
        if not self.tasks:
            self.log.debug("No tasks")
            gevent.spawn(self.checkComplete)

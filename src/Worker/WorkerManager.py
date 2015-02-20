from Worker import Worker
import gevent, time, logging, random

MAX_WORKERS = 10

# Worker manager for site
class WorkerManager:
	def __init__(self, site):
		self.site = site
		self.workers = {} # Key: ip:port, Value: Worker.Worker
		self.tasks = [] # {"evt": evt, "workers_num": 0, "site": self.site, "inner_path": inner_path, "done": False, "time_started": None, "time_added": time.time(), "peers": peers, "priority": 0}
		self.running = True
		self.log = logging.getLogger("WorkerManager:%s" % self.site.address_short)
		self.process_taskchecker = gevent.spawn(self.checkTasks)


	# Check expired tasks
	def checkTasks(self):
		while self.running:
			time.sleep(15) # Check every 15 sec

			# Clean up workers
			if not self.tasks and self.workers: # No task but workers still running
				for worker in self.workers.values(): worker.stop()

			if not self.tasks: continue
			tasks = self.tasks[:] # Copy it so removing elements wont cause any problem
			for task in tasks:
				if (task["time_started"] and time.time() >= task["time_started"]+60) or (time.time() >= task["time_added"]+60 and not self.workers): # Task taking too long time, or no peer after 60sec kill it
					self.log.debug("Timeout, Cleaning up task: %s" % task)
					# Clean up workers
					workers = self.findWorkers(task)
					for worker in workers:
						worker.stop()
					# Remove task
					self.failTask(task)

				elif (task["time_started"] and time.time() >= task["time_started"]+15) or not self.workers: # Task started more than 15 sec ago or no workers
						self.log.debug("Task taking more than 15 secs, find more peers: %s" % task["inner_path"])
						task["site"].announce() # Find more peers
						if task["peers"]: # Release the peer olck
							self.log.debug("Task peer lock release: %s" % task["inner_path"])
							task["peers"] = []
							self.startWorkers()
						break # One reannounce per loop
		self.log.debug("checkTasks stopped running")




	# Tasks sorted by this
	def taskSorter(self, task):
		if task["inner_path"] == "content.json": return 9999 # Content.json always prority
		if task["inner_path"] == "index.html": return 9998 # index.html also important
		priority = task["priority"]
		if task["inner_path"].endswith(".js") or task["inner_path"].endswith(".css"): priority += 1 # download js and css files first
		return priority-task["workers_num"] # Prefer more priority and less workers


	# Returns the next free or less worked task
	def getTask(self, peer):
		self.tasks.sort(key=self.taskSorter, reverse=True) # Sort tasks by priority and worker numbers
		for task in self.tasks: # Find a task
			if task["peers"] and peer not in task["peers"]: continue # This peer not allowed to pick this task
			return task


	# New peers added to site
	def onPeers(self):
		self.startWorkers()


	# Add new worker
	def addWorker(self, peer):
		key = peer.key
		if key not in self.workers and len(self.workers) < MAX_WORKERS: # We dont have worker for that peer and workers num less than max
			worker = Worker(self, peer)
			self.workers[key] = worker
			worker.key = key
			worker.start()
			return worker
		else: # We have woker for this peer or its over the limit
			return False


	# Start workers to process tasks
	def startWorkers(self, peers=None):
		if len(self.workers) >= MAX_WORKERS and not peers: return False # Workers number already maxed
		if not self.tasks: return False # No task for workers
		peers = self.site.peers.values()
		random.shuffle(peers)
		for peer in peers: # One worker for every peer
			if peers and peer not in peers: continue # If peers definied and peer not valid 
			worker = self.addWorker(peer)
			if worker: self.log.debug("Added worker: %s, workers: %s/%s" % (peer.key, len(self.workers), MAX_WORKERS))


	# Stop all worker
	def stopWorkers(self):
		for worker in self.workers.values():
			worker.stop()
		tasks = self.tasks[:] # Copy
		for task in tasks: # Mark all current task as failed
			self.failTask(task)



	# Find workers by task
	def findWorkers(self, task):
		workers = []
		for worker in self.workers.values():
			if worker.task == task: workers.append(worker)
		return workers


	# Ends and remove a worker
	def removeWorker(self, worker):
		worker.running = False
		if worker.key in self.workers: 
			del(self.workers[worker.key])
			self.log.debug("Removed worker, workers: %s/%s" % (len(self.workers), MAX_WORKERS))


	# Create new task and return asyncresult
	def addTask(self, inner_path, peer=None, priority = 0):
		self.site.onFileStart(inner_path) # First task, trigger site download started
		task = self.findTask(inner_path)
		if task: # Already has task for that file
			if peer and task["peers"]: # This peer also has new version, add it to task possible peers
				task["peers"].append(peer)
				self.log.debug("Added peer %s to %s" % (peer.key, task["inner_path"]))
				self.startWorkers([peer])
			if priority: 
				task["priority"] += priority # Boost on priority
			return task["evt"]
		else: # No task for that file yet
			evt = gevent.event.AsyncResult()
			if peer:
				peers = [peer] # Only download from this peer
			else:
				peers = None
			task = {"evt": evt, "workers_num": 0, "site": self.site, "inner_path": inner_path, "done": False, "time_added": time.time(), "time_started": None, "peers": peers, "priority": priority}
			self.tasks.append(task)
			self.log.debug("New task: %s, peer lock: %s, priority: %s" % (task["inner_path"], peers, priority))
			self.startWorkers(peers)
			return evt


	# Find a task using inner_path
	def findTask(self, inner_path):
		for task in self.tasks:
			if task["inner_path"] == inner_path: 
				return task
		return None # Not found


	# Mark a task failed
	def failTask(self, task):
		task["done"] = True
		self.tasks.remove(task) # Remove from queue
		self.site.onFileFail(task["inner_path"])
		task["evt"].set(False)


	# Mark a task done
	def doneTask(self, task):
		task["done"] = True
		self.tasks.remove(task) # Remove from queue
		self.site.onFileDone(task["inner_path"])
		task["evt"].set(True)
		if not self.tasks: self.site.onComplete() # No more task trigger site compelte


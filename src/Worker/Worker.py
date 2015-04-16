import gevent, time, logging, shutil, os
from Peer import Peer
from Debug import Debug

class Worker:
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
		self.peer.hash_failed = 0 # Reset hash error counter
		while self.running:
			# Try to pickup free file download task
			task = self.manager.getTask(self.peer)
			if not task: # Die, no more task
				self.manager.log.debug("%s: No task found, stopping" % self.key)
				break
			if not task["time_started"]: task["time_started"] = time.time() # Task started now

			if task["workers_num"] > 0: # Wait a bit if someone already working on it
				self.manager.log.debug("%s: Someone already working on %s, sleeping 1 sec..." % (self.key, task["inner_path"]))
				time.sleep(1)
				self.manager.log.debug("%s: %s, task done after sleep: %s" % (self.key, task["inner_path"], task["done"]))

			if task["done"] == False:
				self.task = task
				site = task["site"]
				task["workers_num"] += 1
				buff = self.peer.getFile(site.address, task["inner_path"])
				if self.running == False: # Worker no longer needed or got killed
					self.manager.log.debug("%s: No longer needed, returning: %s" % (self.key, task["inner_path"]))
					break
				if buff: # Download ok
					correct = site.content_manager.verifyFile(task["inner_path"], buff)
				else: # Download error
					correct = False
				if correct == True or correct == None: # Hash ok or same file
					self.manager.log.debug("%s: Hash correct: %s" % (self.key, task["inner_path"]))
					if correct == True and task["done"] == False: # Save if changed and task not done yet
						buff.seek(0)
						file_path = site.storage.getPath(task["inner_path"])
						file_dir = os.path.dirname(file_path)
						if not os.path.isdir(file_dir): os.makedirs(file_dir) # Make directory for files
						site.storage.write(task["inner_path"], buff)
					if task["done"] == False: self.manager.doneTask(task)
					task["workers_num"] -= 1
					self.task = None
				else: # Hash failed
					self.manager.log.debug("%s: Hash failed: %s, failed peers: %s" % (self.key, task["inner_path"], len(task["failed"])))
					task["failed"].append(self.key)
					self.task = None
					self.peer.hash_failed += 1
					if self.peer.hash_failed >= 3: # Broken peer
						break
					task["workers_num"] -= 1
					time.sleep(1)
		self.peer.onWorkerDone()
		self.running = False
		self.manager.removeWorker(self)


	# Start the worker
	def start(self):
		self.running = True
		self.thread = gevent.spawn(self.downloader)


	# Force stop the worker
	def stop(self):
		self.manager.log.debug("%s: Force stopping, thread: %s" % (self.key, self.thread))
		self.running = False
		if self.thread:
			self.thread.kill(exception=Debug.Notify("Worker stopped"))
		del self.thread
		self.manager.removeWorker(self)

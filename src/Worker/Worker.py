import gevent, time, logging, shutil, os
from Peer import Peer

class Worker:
	def __init__(self, manager, peer):
		self.manager = manager
		self.peer = peer
		self.task = None
		self.key = None
		self.running = False
		self.thread = None


	# Downloader thread
	def downloader(self):
		while self.running:
			# Try to pickup free file download task
			task = self.manager.getTask(self.peer)
			if not task: # Die, no more task
				self.manager.log.debug("%s: No task found, stopping" % self.key)
				break

			if task["workers_num"] > 0: # Wait a bit if someone already working on it
				self.manager.log.debug("%s: Someone already working on %s, sleeping 1 sec..." % (self.key, task["inner_path"]))
				time.sleep(1)

			if task["done"] == False:
				self.task = task
				task["workers_num"] += 1
				buff = self.peer.getFile(task["site"].address, task["inner_path"])
				if buff: # Download ok
					correct = task["site"].verifyFile(task["inner_path"], buff)
				else: # Download error
					correct = False
				if correct == True or correct == None: # Hash ok or same file
					self.manager.log.debug("%s: Hash correct: %s" % (self.key, task["inner_path"]))
					if task["done"] == False: # Task not done yet
						buff.seek(0)
						file_path = task["site"].getPath(task["inner_path"])
						file_dir = os.path.dirname(file_path)
						if not os.path.isdir(file_dir): os.makedirs(file_dir) # Make directory for files
						file = open(file_path, "wb")
						shutil.copyfileobj(buff, file) # Write buff to disk
						file.close()
						task["workers_num"] -= 1
						self.manager.doneTask(task)
					self.task = None
				else: # Hash failed
					self.task = None
					self.peer.hash_failed += 1
					if self.peer.hash_failed > 5: # Broken peer
						break
					task["workers_num"] -= 1
					self.manager.log.error("%s: Hash failed: %s" % (self.key, task["inner_path"]))
					time.sleep(1)
		self.running = False
		self.peer.disconnect()
		self.manager.removeWorker(self)


	# Start the worker
	def start(self):
		self.running = True
		self.thread = gevent.spawn(self.downloader)

	def stop(self):
		self.running = False
		self.manager.removeWorker(self)

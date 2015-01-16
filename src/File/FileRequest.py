import os, msgpack, shutil
from Site import SiteManager
from cStringIO import StringIO

FILE_BUFF = 1024*512

# Request from me
class FileRequest:
	def __init__(self, server = None):
		if server:
			self.server = server
			self.log = server.log
		self.sites = SiteManager.list()


	def send(self, msg):
		if not isinstance(msg, dict): # If msg not a dict create a {"body": msg}
			msg = {"body": msg}
		self.server.socket.send(msgpack.packb(msg, use_bin_type=True))


	# Route file requests
	def route(self, cmd, params):
		if cmd == "getFile":
			self.actionGetFile(params)
		elif cmd == "update":
			self.actionUpdate(params)
		elif cmd == "ping":
			self.actionPing()
		else:
			self.actionUnknown(cmd, params)


	# Update a site file request
	def actionUpdate(self, params):
		site = self.sites.get(params["site"])
		if not site or not site.settings["serving"]: # Site unknown or not serving
			self.send({"error": "Unknown site"})
			return False
		if site.settings["own"]:
			self.log.debug("Someone trying to push a file to own site %s, reload local content.json first" % site.address)
			site.loadContent()
		buff = StringIO(params["body"])
		valid = site.verifyFile(params["inner_path"], buff)
		if valid == True: # Valid and changed
			self.log.debug("Update for %s looks valid, saving..." % params["inner_path"])
			buff.seek(0)
			file = open(site.getPath(params["inner_path"]), "wb")
			shutil.copyfileobj(buff, file) # Write buff to disk
			file.close()

			if params["inner_path"] == "content.json": # Download every changed file from peer
				changed = site.loadContent() # Get changed files
				peer = site.addPeer(*params["peer"], return_peer = True) # Add or get peer
				self.log.info("%s changed files: %s" % (site.address_short, changed))
				for inner_path in changed: # Updated files in content.json
					site.needFile(inner_path, peer=peer, update=True, blocking=False) # Download file from peer
				site.onComplete.once(lambda: site.publish()) # On complete publish to other peers

			self.send({"ok": "Thanks, file %s updated!" % params["inner_path"]})

		elif valid == None: # Not changed
			peer = site.addPeer(*params["peer"], return_peer = True) # Add or get peer
			self.log.debug("Same version, adding new peer for locked files: %s, tasks: %s" % (peer.key, len(site.worker_manager.tasks)) )
			for task in site.worker_manager.tasks: # New peer add to every ongoing task
				if task["peers"]: site.needFile(task["inner_path"], peer=peer, update=True, blocking=False) # Download file from this peer too if its peer locked

			self.send({"ok": "File not changed"})

		else: # Invalid sign or sha1 hash
			self.log.debug("Update for %s is invalid" % params["inner_path"])
			self.send({"error": "File invalid"})


	# Send file content request
	def actionGetFile(self, params):
		site = self.sites.get(params["site"])
		if not site or not site.settings["serving"]: # Site unknown or not serving
			self.send({"error": "Unknown site"})
			return False
		try:
			file = open(site.getPath(params["inner_path"]), "rb")
			file.seek(params["location"])
			back = {}
			back["body"] = file.read(FILE_BUFF)
			back["location"] = file.tell()
			back["size"] = os.fstat(file.fileno()).st_size
			self.send(back)
		except Exception, err:
			self.send({"error": "File read error: %s" % err})
			return False


	# Send a simple Pong! answer
	def actionPing(self):
		self.send("Pong!")


	# Unknown command
	def actionUnknown(self, cmd, params):
		self.send({"error": "Unknown command: %s" % cmd})

import os, json, logging, hashlib, re, time, string, random
from lib.subtl.subtl import UdpTrackerClient
import gevent
import util
from Config import config
from Peer import Peer
from Worker import WorkerManager
from Crypt import CryptHash
from Debug import Debug
from Content import ContentManager
import SiteManager

class Site:
	def __init__(self, address, allow_create=True):
		self.address = re.sub("[^A-Za-z0-9]", "", address) # Make sure its correct address
		self.address_short = "%s..%s" % (self.address[:6], self.address[-4:]) # Short address for logging
		self.directory = "data/%s" % self.address # Site data diretory
		self.log = logging.getLogger("Site:%s" % self.address_short)

		if not os.path.isdir(self.directory): 
			if allow_create:
				os.mkdir(self.directory) # Create directory if not found
			else:
				raise Exception("Directory not exists: %s" % self.directory)
		self.content = None # Load content.json
		self.peers = {} # Key: ip:port, Value: Peer.Peer
		self.peer_blacklist = SiteManager.peer_blacklist # Ignore this peers (eg. myself)
		self.last_announce = 0 # Last announce time to tracker
		self.worker_manager = WorkerManager(self) # Handle site download from other peers
		self.bad_files = {} # SHA512 check failed files, need to redownload
		self.content_updated = None # Content.js update time
		self.last_downloads = [] # Files downloaded in run of self.download()
		self.notifications = [] # Pending notifications displayed once on page load [error|ok|info, message, timeout]
		self.page_requested = False # Page viewed in browser

		self.content_manager = ContentManager(self) # Load contents
		self.loadSettings() # Load settings from sites.json

		if not self.settings.get("auth_key"): # To auth user in site (Obsolete, will be removed)
			self.settings["auth_key"] = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(24))
			self.log.debug("New auth key: %s" % self.settings["auth_key"])
			self.saveSettings()

		if not self.settings.get("wrapper_key"): # To auth websocket permissions
			self.settings["wrapper_key"] = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(12)) 
			self.log.debug("New wrapper key: %s" % self.settings["wrapper_key"])
			self.saveSettings()

		self.websockets = [] # Active site websocket connections

		# Add event listeners
		self.addEventListeners()


	# Load site settings from data/sites.json
	def loadSettings(self):
		sites_settings = json.load(open("data/sites.json"))
		if self.address in sites_settings:
			self.settings = sites_settings[self.address]
		else:
			if self.address == config.homepage: # Add admin permissions to homepage
				permissions = ["ADMIN"]
			else:
				permissions = []
			self.settings = { "own": False, "serving": True, "permissions": permissions } # Default
		return


	# Save site settings to data/sites.json
	def saveSettings(self):
		sites_settings = json.load(open("data/sites.json"))
		sites_settings[self.address] = self.settings
		open("data/sites.json", "w").write(json.dumps(sites_settings, indent=2, sort_keys=True))
		return


	# Sercurity check and return path of site's file
	def getPath(self, inner_path):
		inner_path = inner_path.replace("\\", "/") # Windows separator fix
		inner_path = re.sub("^%s/" % re.escape(self.directory), "", inner_path) # Remove site directory if begins with it
		file_path = self.directory+"/"+inner_path
		allowed_dir = os.path.abspath(self.directory) # Only files within this directory allowed
		if ".." in file_path or not os.path.dirname(os.path.abspath(file_path)).startswith(allowed_dir):
			raise Exception("File not allowed: %s" % file_path)
		return file_path


	# Download all file from content.json
	@util.Noparallel(blocking=True)
	def downloadContent(self, inner_path, download_files=True, peer=None):
		s = time.time()
		self.log.debug("Downloading %s..." % inner_path)
		self.last_downloads.append(inner_path)
		found = self.needFile(inner_path, update=self.bad_files.get(inner_path))
		content_inner_dir = self.content_manager.toDir(inner_path)
		if not found: return False # Could not download content.json

		self.log.debug("Got %s" % inner_path)
		changed = self.content_manager.loadContent(inner_path, load_includes=False)

		# Start download files
		evts = []
		if download_files:
			for file_relative_path in self.content_manager.contents[inner_path].get("files", {}).keys():
				file_inner_path = content_inner_dir+file_relative_path
				res = self.needFile(file_inner_path, blocking=False, update=self.bad_files.get(file_inner_path), peer=peer) # No waiting for finish, return the event
				if res != True: # Need downloading
					self.last_downloads.append(file_inner_path)
					evts.append(res) # Append evt

		# Wait for includes download
		for file_relative_path in self.content_manager.contents[inner_path].get("includes", {}).keys():
			file_inner_path = content_inner_dir+file_relative_path
			self.downloadContent(file_inner_path, download_files=download_files, peer=peer)

		self.log.debug("%s: Includes downloaded" % inner_path)
		self.log.debug("%s: Downloading %s files..." % (inner_path, len(evts)))
		gevent.joinall(evts)
		self.log.debug("%s: All file downloaded in %.2fs" % (inner_path, time.time()-s))

		return True


	# Download all files of the site
	@util.Noparallel(blocking=False)
	def download(self):
		self.log.debug("Start downloading...%s" % self.bad_files)
		self.announce()
		self.last_downloads = []
		found = self.downloadContent("content.json")

		return found


	# Update content.json from peers and download changed files
	@util.Noparallel()
	def update(self):
		self.content_manager.loadContent("content.json") # Reload content.json
		self.content_updated = None
		# Download all content.json again
		for inner_path in self.content_manager.contents.keys():
			self.needFile(inner_path, update=True)
		changed = self.content_manager.loadContent("content.json")
		if changed:
			for changed_file in changed:
				self.bad_files[changed_file] = True
		if not self.settings["own"]: self.checkFiles(quick_check=True) # Quick check files based on file size
		if self.bad_files:
			self.download()
		return changed


	def publisher(self, inner_path, peers, published, limit):
		timeout = 5+int(os.path.getsize(self.getPath(inner_path))/1024) # Timeout: 5sec + size in kb
		while 1:
			if not peers or len(published) >= limit: break # All peers done, or published engouht
			peer = peers.pop(0)
			result = {"exception": "Timeout"}
			try:
				with gevent.Timeout(timeout, False):
					result = peer.sendCmd("update", {
						"site": self.address, 
						"inner_path": inner_path, 
						"body": open(self.getPath(inner_path), "rb").read(),
						"peer": (config.ip_external, config.fileserver_port)
					})
			except Exception, err:
				result = {"exception": Debug.formatException(err)}

			if result and "ok" in result:
				published.append(peer)
				self.log.info("[OK] %s: %s" % (peer.key, result["ok"]))
			else:
				self.log.info("[ERROR] %s: %s" % (peer.key, result))
			




	# Update content.json on peers
	def publish(self, limit=3, inner_path="content.json"):
		self.log.info( "Publishing to %s/%s peers..." % (limit, len(self.peers)) )
		published = [] # Successfuly published (Peer)
		publishers = [] # Publisher threads
		peers = self.peers.values()
		for i in range(limit):
			publisher = gevent.spawn(self.publisher, inner_path, peers, published, limit)
			publishers.append(publisher)

		gevent.joinall(publishers) # Wait for all publishers

		self.log.info("Successfuly published to %s peers" % len(published))
		return len(published)


	# Check and download if file not exits
	def needFile(self, inner_path, update=False, blocking=True, peer=None, priority=0):
		if os.path.isfile(self.getPath(inner_path)) and not update: # File exits, no need to do anything
			return True
		elif self.settings["serving"] == False: # Site not serving
			return False
		else: # Wait until file downloaded
			if not self.content_manager.contents.get("content.json"): # No content.json, download it first!
				self.log.debug("Need content.json first")
				self.announce()
				if inner_path != "content.json": # Prevent double download
					task = self.worker_manager.addTask("content.json", peer)
					task.get()
					self.content_manager.loadContent()
					if not self.content_manager.contents.get("content.json"): return False # Content.json download failed

			if not inner_path.endswith("content.json") and not self.content_manager.getFileInfo(inner_path): # No info for file, download all content.json first
				self.log.debug("No info for %s, waiting for all content.json" % inner_path)
				success = self.downloadContent("content.json", download_files=False)
				if not success: return False

			task = self.worker_manager.addTask(inner_path, peer, priority=priority)
			if blocking:
				return task.get()
			else:
				return task


	# Add or update a peer to site
	def addPeer(self, ip, port, return_peer = False):
		if not ip: return False
		key = "%s:%s" % (ip, port)
		if key in self.peers: # Already has this ip
			self.peers[key].found()
			if return_peer: # Always return peer
				return self.peers[key]
			else:
				return False
		else: # New peer
			peer = Peer(ip, port, self)
			self.peers[key] = peer
			return peer


	# Add myself and get other peers from tracker
	def announce(self, force=False):
		if time.time() < self.last_announce+15 and not force: return # No reannouncing within 15 secs
		self.last_announce = time.time()
		errors = []

		for protocol, ip, port in SiteManager.TRACKERS:
			if protocol == "udp":
				# self.log.debug("Announcing to %s://%s:%s..." % (protocol, ip, port))
				tracker = UdpTrackerClient(ip, port)
				tracker.peer_port = config.fileserver_port
				try:
					tracker.connect()
					tracker.poll_once()
					tracker.announce(info_hash=hashlib.sha1(self.address).hexdigest(), num_want=50)
					back = tracker.poll_once()
					peers = back["response"]["peers"]
				except Exception, err:
					errors.append("%s://%s:%s" % (protocol, ip, port))
					continue
			
				added = 0
				for peer in peers:
					if (peer["addr"], peer["port"]) in self.peer_blacklist: # Ignore blacklist (eg. myself)
						continue
					if self.addPeer(peer["addr"], peer["port"]): added += 1
				if added:
					self.worker_manager.onPeers()
					self.updateWebsocket(peers_added=added)
					self.log.debug("Found %s peers, new: %s" % (len(peers), added))
			else:
				pass # TODO: http tracker support
		
		if len(errors) < len(SiteManager.TRACKERS): # Less errors than total tracker nums
			self.log.debug("Announced to %s trackers, errors: %s" % (len(SiteManager.TRACKERS), errors))
		else:
			self.log.error("Announced to %s trackers, failed" % len(SiteManager.TRACKERS))


	# Check and try to fix site files integrity
	def checkFiles(self, quick_check=True):
		self.log.debug("Checking files... Quick:%s" % quick_check)
		bad_files = self.verifyFiles(quick_check)
		if bad_files:
			for bad_file in bad_files:
				self.bad_files[bad_file] = True


	def deleteFiles(self):
		self.log.debug("Deleting files from content.json...")
		files = [] # Get filenames
		for content_inner_path, content in self.content_manager.contents.items():
			files.append(content_inner_path)
			for file_relative_path in content["files"].keys():
				file_inner_path = self.content_manager.toDir(content_inner_path)+file_relative_path # Relative to content.json
				files.append(file_inner_path)
				
		for inner_path in files:
			path = self.getPath(inner_path)
			if os.path.isfile(path): os.unlink(path)
		
		self.log.debug("Deleting empty dirs...")
		for root, dirs, files in os.walk(self.directory, topdown=False):
			for dir in dirs:
				path = os.path.join(root,dir)
				if os.path.isdir(path) and os.listdir(path) == []:
					os.removedirs(path)
					self.log.debug("Removing %s" % path)
		if os.path.isdir(self.directory) and os.listdir(self.directory) == []: os.removedirs(self.directory) # Remove sites directory if empty

		if os.path.isdir(self.directory):
			self.log.debug("Some unknown file remained in site data dir: %s..." % self.directory)
			return False # Some files not deleted
		else:
			self.log.debug("Site data directory deleted: %s..." % self.directory)
			return True # All clean
		


	# - Events -

	# Add event listeners
	def addEventListeners(self):
		self.onFileStart = util.Event() # If WorkerManager added new task
		self.onFileDone = util.Event() # If WorkerManager successfuly downloaded a file
		self.onFileFail = util.Event() # If WorkerManager failed to download a file
		self.onComplete = util.Event() # All file finished
		
		self.onFileStart.append(lambda inner_path: self.fileStarted()) # No parameters to make Noparallel batching working
		self.onFileDone.append(lambda inner_path: self.fileDone(inner_path))
		self.onFileFail.append(lambda inner_path: self.fileFailed(inner_path))


	# Send site status update to websocket clients
	def updateWebsocket(self, **kwargs):
		if kwargs:
			param = {"event": kwargs.items()[0]}
		else:
			param = None
		for ws in self.websockets:
			ws.event("siteChanged", self, param)


	# File download started
	@util.Noparallel(blocking=False)
	def fileStarted(self):
		time.sleep(0.001) # Wait for other files adds
		self.updateWebsocket(file_started=True)


	# File downloaded successful
	def fileDone(self, inner_path):
		# File downloaded, remove it from bad files
		if inner_path in self.bad_files:
			self.log.info("Bad file solved: %s" % inner_path)
			del(self.bad_files[inner_path])

		# Update content.json last downlad time
		if inner_path == "content.json":
			self.content_updated = time.time()

		self.updateWebsocket(file_done=inner_path)


	# File download failed
	def fileFailed(self, inner_path):
		if inner_path == "content.json":
			self.content_updated = False
			self.log.error("Can't update content.json")

		self.updateWebsocket(file_failed=inner_path)


	# Verify all files sha512sum using content.json
	def verifyFiles(self, quick_check=False): # Fast = using file size
		bad_files = []
		if not self.content_manager.contents.get("content.json"): # No content.json, download it first
			self.needFile("content.json", update=True) # Force update to fix corrupt file
			self.content_manager.loadContent() # Reload content.json
		for content_inner_path, content in self.content_manager.contents.items():
			for file_relative_path in content["files"].keys():
				file_inner_path = self.content_manager.toDir(content_inner_path)+file_relative_path # Relative to content.json
				file_inner_path = file_inner_path.strip("/") # Strip leading /
				file_path = self.getPath(file_inner_path)
				if not os.path.isfile(file_path):
					self.log.error("[MISSING] %s" % file_inner_path)
					bad_files.append(file_inner_path)
					continue

				if quick_check:
					ok = os.path.getsize(file_path) == content["files"][file_relative_path]["size"]
				else:
					ok = self.content_manager.verifyFile(file_inner_path, open(file_path, "rb"))

				if not ok:
					self.log.error("[ERROR] %s" % file_inner_path)
					bad_files.append(file_inner_path)
			self.log.debug("%s verified: %s files, quick_check: %s, bad files: %s" % (content_inner_path, len(content["files"]), quick_check, bad_files))

		return bad_files

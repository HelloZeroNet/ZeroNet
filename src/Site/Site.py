import os, json, logging, hashlib, re, time, string, random
from lib.subtl.subtl import UdpTrackerClient
import gevent
import util
from Config import config
from Peer import Peer
from Worker import WorkerManager
from Crypt import CryptHash
from Debug import Debug
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
		self.bad_files = {} # SHA1 check failed files, need to redownload
		self.content_updated = None # Content.js update time
		self.last_downloads = [] # Files downloaded in run of self.download()
		self.notifications = [] # Pending notifications displayed once on page load [error|ok|info, message, timeout]
		self.page_requested = False # Page viewed in browser

		self.loadContent(init=True) # Load content.json
		self.loadSettings() # Load settings from sites.json

		if not self.settings.get("auth_key"):
			self.settings["auth_key"] = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(12)) # To auth websocket
			self.log.debug("New auth key: %s" % self.settings["auth_key"])
			self.saveSettings()
		self.websockets = [] # Active site websocket connections

		# Add event listeners
		self.addEventListeners()


	# Load content.json to self.content
	def loadContent(self, init=False):
		old_content = self.content
		content_path = "%s/content.json" % self.directory
		if os.path.isfile(content_path): 
			try:
				new_content = json.load(open(content_path))
			except Exception, err:
				self.log.error("Content.json load error: %s" % Debug.formatException(err))
				return None
		else:
			return None # Content.json not exits

		try:
			changed = []
			for inner_path, details in new_content["files"].items():
				new_sha1 = details["sha1"]
				if old_content and old_content["files"].get(inner_path):
					old_sha1 = old_content["files"][inner_path]["sha1"]
				else:
					old_sha1 = None
				if old_sha1 != new_sha1: changed.append(inner_path)
			self.content = new_content
		except Exception, err:
			self.log.error("Content.json parse error: %s" % Debug.formatException(err))
			return None # Content.json parse error
		# Add to bad files
		if not init:
			for inner_path in changed:
				self.bad_files[inner_path] = True
		return changed


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
		open("data/sites.json", "w").write(json.dumps(sites_settings, indent=4, sort_keys=True))
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


	# Start downloading site
	@util.Noparallel(blocking=False)
	def download(self):
		self.log.debug("Start downloading...%s" % self.bad_files)
		self.announce()
		found = self.needFile("content.json", update=self.bad_files.get("content.json"))
		if not found: return False # Could not download content.json
		self.loadContent() # Load the content.json
		self.log.debug("Got content.json")
		evts = []
		self.last_downloads = ["content.json"] # Files downloaded in this run
		for inner_path in self.content["files"].keys():
			res = self.needFile(inner_path, blocking=False, update=self.bad_files.get(inner_path)) # No waiting for finish, return the event
			if res != True: # Need downloading
				self.last_downloads.append(inner_path)
				evts.append(res) # Append evt
		self.log.debug("Downloading %s files..." % len(evts))
		s = time.time()
		gevent.joinall(evts)
		self.log.debug("All file downloaded in %.2fs" % (time.time()-s))


	# Update content.json from peers and download changed files
	@util.Noparallel()
	def update(self):
		self.loadContent() # Reload content.json
		self.content_updated = None
		self.needFile("content.json", update=True)
		changed_files = self.loadContent()
		if changed_files:
			for changed_file in changed_files:
				self.bad_files[changed_file] = True
		self.checkFiles(quick_check=True) # Quick check files based on file size
		if self.bad_files:
			self.download()
		return changed_files



	# Update content.json on peers
	def publish(self, limit=3):
		self.log.info( "Publishing to %s/%s peers..." % (limit, len(self.peers)) )
		published = 0
		for key, peer in self.peers.items(): # Send update command to each peer
			result = {"exception": "Timeout"}
			try:
				with gevent.Timeout(1, False): # 1 sec timeout
					result = peer.sendCmd("update", {
						"site": self.address, 
						"inner_path": "content.json", 
						"body": open(self.getPath("content.json")).read(),
						"peer": (config.ip_external, config.fileserver_port)
					})
			except Exception, err:
				result = {"exception": Debug.formatException(err)}

			if result and "ok" in result:
				published += 1
				self.log.info("[OK] %s: %s" % (key, result["ok"]))
			else:
				self.log.info("[ERROR] %s: %s" % (key, result))
			
			if published >= limit: break
		self.log.info("Successfuly published to %s peers" % published)
		return published


	# Check and download if file not exits
	def needFile(self, inner_path, update=False, blocking=True, peer=None, priority=0):
		if os.path.isfile(self.getPath(inner_path)) and not update: # File exits, no need to do anything
			return True
		elif self.settings["serving"] == False: # Site not serving
			return False
		else: # Wait until file downloaded
			if not self.content: # No content.json, download it first!
				self.log.debug("Need content.json first")
				self.announce()
				if inner_path != "content.json": # Prevent double download
					task = self.worker_manager.addTask("content.json", peer)
					task.get()
					self.loadContent()
					if not self.content: return False

			task = self.worker_manager.addTask(inner_path, peer, priority=priority)
			if blocking:
				return task.get()
			else:
				return task


	# Add or update a peer to site
	def addPeer(self, ip, port, return_peer = False):
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

		for protocol, ip, port in SiteManager.TRACKERS:
			if protocol == "udp":
				self.log.debug("Announing to %s://%s:%s..." % (protocol, ip, port))
				tracker = UdpTrackerClient(ip, port)
				tracker.peer_port = config.fileserver_port
				try:
					tracker.connect()
					tracker.poll_once()
					tracker.announce(info_hash=hashlib.sha1(self.address).hexdigest(), num_want=50)
					back = tracker.poll_once()
					peers = back["response"]["peers"]
				except Exception, err:
					self.log.error("Tracker error: %s" % Debug.formatException(err))
					time.sleep(1)
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
				break # Successful announcing, break the list					
			else:
				pass # TODO: http tracker support


	# Check and try to fix site files integrity
	def checkFiles(self, quick_check=True):
		self.log.debug("Checking files... Quick:%s" % quick_check)
		bad_files = self.verifyFiles(quick_check)
		if bad_files:
			for bad_file in bad_files:
				self.bad_files[bad_file] = True


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


	# - Sign and verify -


	# Verify fileobj using sha1 in content.json
	def verifyFile(self, inner_path, file, force=False):
		if inner_path == "content.json": # Check using sign
			from Crypt import CryptBitcoin

			try:
				content = json.load(file)
				if self.content and not force:
					if self.content["modified"] == content["modified"]: # Ignore, have the same content.json
						return None
					elif self.content["modified"] > content["modified"]: # We have newer
						self.log.debug("We have newer content.json (Our: %s, Sent: %s)" % (self.content["modified"], content["modified"]))
						return False
				if content["modified"] > time.time()+60*60*24: # Content modified in the far future (allow 1 day window)
					self.log.error("Content.json modify is in the future!")
					return False
				# Check sign
				sign = content["sign"]
				del(content["sign"]) # The file signed without the sign
				sign_content = json.dumps(content, sort_keys=True) # Dump the json to string to remove whitepsace

				return CryptBitcoin.verify(sign_content, self.address, sign)
			except Exception, err:
				self.log.error("Verify sign error: %s" % Debug.formatException(err))
				return False

		else: # Check using sha1 hash
			if self.content and inner_path in self.content["files"]:
				return CryptHash.sha1sum(file) == self.content["files"][inner_path]["sha1"]
			else: # File not in content.json
				self.log.error("File not in content.json: %s" % inner_path)
				return False


	# Verify all files sha1sum using content.json
	def verifyFiles(self, quick_check=False): # Fast = using file size
		bad_files = []
		if not self.content: # No content.json, download it first
			self.needFile("content.json", update=True) # Force update to fix corrupt file
			self.loadContent() # Reload content.json
		for inner_path in self.content["files"].keys():
			file_path = self.getPath(inner_path)
			if not os.path.isfile(file_path):
				self.log.error("[MISSING] %s" % inner_path)
				bad_files.append(inner_path)
				continue

			if quick_check:
				ok = os.path.getsize(file_path) == self.content["files"][inner_path]["size"]
			else:
				ok = self.verifyFile(inner_path, open(file_path, "rb"))

			if ok:
				self.log.debug("[OK] %s" % inner_path)
			else:
				self.log.error("[ERROR] %s" % inner_path)
				bad_files.append(inner_path)

		return bad_files


	# Create and sign content.json using private key
	def signContent(self, privatekey=None):
		if not self.content: # New site
			self.log.info("Site not exits yet, loading default content.json values...")
			self.content = {"files": {}, "title": "%s - ZeroNet_" % self.address, "sign": "", "modified": 0.0, "description": "", "address": self.address, "ignore": "", "zeronet_version": config.version} # Default content.json

		self.log.info("Opening site data directory: %s..." % self.directory)

		hashed_files = {}

		for root, dirs, files in os.walk(self.directory):
			for file_name in files:
				file_path = self.getPath("%s/%s" % (root, file_name))
				
				if file_name == "content.json" or (self.content["ignore"] and re.match(self.content["ignore"], file_path.replace(self.directory+"/", "") )): # Dont add content.json and ignore regexp pattern definied in content.json
					self.log.info("- [SKIPPED] %s" % file_path)
				else:
					sha1sum = CryptHash.sha1sum(file_path) # Calculate sha sum of file
					inner_path = re.sub("^%s/" % re.escape(self.directory), "", file_path)
					self.log.info("- %s (SHA1: %s)" % (file_path, sha1sum))
					hashed_files[inner_path] = {"sha1": sha1sum, "size": os.path.getsize(file_path)}

		# Generate new content.json
		self.log.info("Adding timestamp and sha1sums to new content.json...")

		content = self.content.copy() # Create a copy of current content.json
		content["address"] = self.address # Add files sha1 hash
		content["files"] = hashed_files # Add files sha1 hash
		content["modified"] = time.time() # Add timestamp
		content["zeronet_version"] = config.version # Signer's zeronet version
		del(content["sign"]) # Delete old sign

		# Signing content
		from Crypt import CryptBitcoin

		self.log.info("Verifying private key...")
		privatekey_address = CryptBitcoin.privatekeyToAddress(privatekey)
		if self.address != privatekey_address:
			return self.log.error("Private key invalid! Site address: %s, Private key address: %s" % (self.address, privatekey_address))

		self.log.info("Signing modified content.json...")
		sign_content = json.dumps(content, sort_keys=True)
		self.log.debug("Content: %s" % sign_content)
		sign = CryptBitcoin.sign(sign_content, privatekey)
		content["sign"] = sign

		# Saving modified content.json
		self.log.info("Saving to %s/content.json..." % self.directory)
		open("%s/content.json" % self.directory, "w").write(json.dumps(content, indent=4, sort_keys=True))

		self.log.info("Site signed!")

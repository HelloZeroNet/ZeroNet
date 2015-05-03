import os, logging, urllib2, re, time
import gevent, msgpack
from Config import config
from FileRequest import FileRequest
from Site import SiteManager
from Debug import Debug
from Connection import ConnectionServer
from util import UpnpPunch


class FileServer(ConnectionServer):
	def __init__(self):
		ConnectionServer.__init__(self, config.fileserver_ip, config.fileserver_port, self.handleRequest)
		if config.ip_external: # Ip external definied in arguments
			self.port_opened = True
			SiteManager.peer_blacklist.append((config.ip_external, self.port)) # Add myself to peer blacklist
		else:
			self.port_opened = None # Is file server opened on router
		self.sites = SiteManager.site_manager.list()


	# Handle request to fileserver
	def handleRequest(self, connection, message):
		if "params" in message:
			self.log.debug("FileRequest: %s %s %s %s" % (str(connection), message["cmd"], message["params"].get("site"), message["params"].get("inner_path")))
		else:
			self.log.debug("FileRequest: %s %s" % (str(connection), req["cmd"]))
		req = FileRequest(self, connection)
		req.route(message["cmd"], message.get("req_id"), message.get("params"))


	# Reload the FileRequest class to prevent restarts in debug mode
	def reload(self):
		global FileRequest
		import imp
		FileRequest = imp.load_source("FileRequest", "src/File/FileRequest.py").FileRequest


	# Try to open the port using upnp
	def openport(self, port=None, check=True):
		if not port: port = self.port
		if self.port_opened: return True # Port already opened
		if check: # Check first if its already opened
			if self.testOpenport(port)["result"] == True:
				return True # Port already opened

		self.log.info("Trying to open port using UpnpPunch...")
		try:
			upnp_punch = UpnpPunch.open_port(self.port, 'ZeroNet')
			upnp_punch = True
		except Exception, err:
			self.log.error("UpnpPunch run error: %s" % Debug.formatException(err))
			upnp_punch = False

		if upnp_punch and self.testOpenport(port)["result"] == True:
			return True

		self.log.info("Upnp mapping failed :( Please forward port %s on your router to your ipaddress" % port)
		return False


	# Test if the port is open
	def testOpenport(self, port = None):
		time.sleep(1) # Wait for port open
		if not port: port = self.port
		self.log.info("Checking port %s using canyouseeme.org..." % port)
		try:
			data = urllib2.urlopen("http://www.canyouseeme.org/", "port=%s" % port, timeout=20.0).read()
			message = re.match('.*<p style="padding-left:15px">(.*?)</p>', data, re.DOTALL).group(1)
			message = re.sub("<.*?>", "", message.replace("<br>", " ").replace("&nbsp;", " ")) # Strip http tags
		except Exception, err:
			message = "Error: %s" % Debug.formatException(err)
		if "Error" in message:
			self.log.info("[BAD :(] Port closed: %s" % message)
			if port == self.port: 
				self.port_opened = False # Self port, update port_opened status
				match = re.match(".*?([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", message) # Try find my external ip in message
				if match: # Found my ip in message
					config.ip_external = match.group(1)
					SiteManager.peer_blacklist.append((config.ip_external, self.port)) # Add myself to peer blacklist
				else:
					config.ip_external = False
			return {"result": False, "message": message}
		else:
			self.log.info("[OK :)] Port open: %s" % message)
			if port == self.port: # Self port, update port_opened status
				self.port_opened = True
				match = re.match(".*?([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", message) # Try find my external ip in message
				if match: # Found my ip in message
					config.ip_external = match.group(1)
					SiteManager.peer_blacklist.append((config.ip_external, self.port)) # Add myself to peer blacklist
				else:
					config.ip_external = False
			return {"result": True, "message": message}


	# Set external ip without testing
	def setIpExternal(self, ip_external):
		logging.info("Setting external ip without testing: %s..." % ip_external)
		config.ip_external = ip_external
		self.port_opened = True


	# Check site file integrity
	def checkSite(self, site):
		if site.settings["serving"]:
			site.announce() # Announce site to tracker
			site.update() # Update site's content.json and download changed files
			if self.port_opened == False: # In passive mode keep 5 active peer connection to get the updates
				site.needConnections()


	# Check sites integrity
	def checkSites(self):
		if self.port_opened == None: # Test and open port if not tested yet
			self.openport()

		self.log.debug("Checking sites integrity..")
		for address, site in self.sites.items(): # Check sites integrity
			gevent.spawn(self.checkSite, site) # Check in new thread
			time.sleep(2) # Prevent too quick request
		site = None


	# Announce sites every 20 min
	def announceSites(self):
		import gc
		while 1:
			time.sleep(20*60) # Announce sites every 20 min
			for address, site in self.sites.items():
				if site.settings["serving"]:
					site.announce() # Announce site to tracker

					# Reset bad file retry counter
					for inner_path in site.bad_files: 
						site.bad_files[inner_path] = 0

					# Retry failed files
					if site.bad_files:
						site.retryBadFiles()
						
					# In passive mode keep 5 active peer connection to get the updates
					if self.port_opened == False:
						site.needConnections()

				time.sleep(2) # Prevent too quick request

			site = None
			gc.collect() # Implicit grabage collection


	# Detects if computer back from wakeup
	def wakeupWatcher(self):
		last_time = time.time()
		while 1:
			time.sleep(30)
			if time.time()-last_time > 60: # If taken more than 60 second then the computer was in sleep mode
				self.log.info("Wakeup detected: time wrap from %s to %s (%s sleep seconds), acting like startup..." % (last_time, time.time(), time.time()-last_time))
				self.port_opened = None # Check if we still has the open port on router
				self.checkSites()
			last_time = time.time()


	# Bind and start serving sites
	def start(self, check_sites = True):
		self.log = logging.getLogger("FileServer")

		if config.debug:
			# Auto reload FileRequest on change
			from Debug import DebugReloader
			DebugReloader(self.reload)

		if check_sites: # Open port, Update sites, Check files integrity
			gevent.spawn(self.checkSites)
		
		thread_announce_sites = gevent.spawn(self.announceSites)
		thread_wakeup_watcher = gevent.spawn(self.wakeupWatcher)

		ConnectionServer.start(self)

		# thread_wakeup_watcher.kill(exception=Debug.Notify("Stopping FileServer"))
		# thread_announce_sites.kill(exception=Debug.Notify("Stopping FileServer"))
		self.log.debug("Stopped.")

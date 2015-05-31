import os, sys
update_after_shutdown = False # If set True then update and restart zeronet after main loop ended

# Load config
from Config import config

# Create necessary files and dirs
if not os.path.isdir(config.log_dir): os.mkdir(config.log_dir)
if not os.path.isdir(config.data_dir): os.mkdir(config.data_dir)
if not os.path.isfile("%s/sites.json" % config.data_dir): open("%s/sites.json" % config.data_dir, "w").write("{}")
if not os.path.isfile("%s/users.json" % config.data_dir): open("%s/users.json" % config.data_dir, "w").write("{}")


# Setup logging
import logging
if config.action == "main":
	if os.path.isfile("%s/debug.log" % config.log_dir):  # Simple logrotate
		if os.path.isfile("%s/debug-last.log" % config.log_dir): os.unlink("%s/debug-last.log" % config.log_dir)
		os.rename("%s/debug.log" % config.log_dir, "%s/debug-last.log" % config.log_dir)
	logging.basicConfig(format='[%(asctime)s] %(levelname)-8s %(name)s %(message)s', level=logging.DEBUG, filename="%s/debug.log" % config.log_dir)
else:
	logging.basicConfig(level=logging.DEBUG, stream=open(os.devnull,"w")) # No file logging if action is not main

# Console logger
console_log = logging.StreamHandler()
if config.action == "main": # Add time if main action
	console_log.setFormatter(logging.Formatter('[%(asctime)s] %(name)s %(message)s', "%H:%M:%S"))
else:
	console_log.setFormatter(logging.Formatter('%(name)s %(message)s', "%H:%M:%S"))

logging.getLogger('').addHandler(console_log) # Add console logger
logging.getLogger('').name = "-" # Remove root prefix


# Debug dependent configuration
from Debug import DebugHook
if config.debug:
	console_log.setLevel(logging.DEBUG) # Display everything to console
else:
	console_log.setLevel(logging.INFO) # Display only important info to console

from gevent import monkey; monkey.patch_all(thread=False, ssl=False) # Make time, socket gevent compatible. Not thread: pyfilesystem and system tray icon not compatible, Not ssl: broken in 2.7.9
import gevent
import time

# Log current config
logging.debug("Config: %s" % config)


# Socks Proxy monkey patch
if config.proxy:
	from util import SocksProxy
	import urllib2
	logging.info("Patching sockets to socks proxy: %s" % config.proxy)
	config.fileserver_ip = '127.0.0.1' # Do not accept connections anywhere but localhost
	SocksProxy.monkeyPath(*config.proxy.split(":"))


# Load plugins
from Plugin import PluginManager
PluginManager.plugin_manager.loadPlugins()


# -- Actions --

@PluginManager.acceptPlugins
class Actions:
	# Default action: Start serving UiServer and FileServer
	def main(self):
		logging.info("Version: %s r%s, Python %s, Gevent: %s" % (config.version, config.rev, sys.version, gevent.__version__))
		global ui_server, file_server
		from File import FileServer
		from Ui import UiServer
		logging.info("Creating UiServer....")
		ui_server = UiServer()

		logging.info("Creating FileServer....")
		file_server = FileServer()

		logging.info("Starting servers....")
		gevent.joinall([gevent.spawn(ui_server.start), gevent.spawn(file_server.start)])


	# Site commands

	def siteCreate(self):
		logging.info("Generating new privatekey...")
		from Crypt import CryptBitcoin
		privatekey = CryptBitcoin.newPrivatekey()
		logging.info("----------------------------------------------------------------------")
		logging.info("Site private key: %s" % privatekey)
		logging.info("                  !!! ^ Save it now, required to modify the site ^ !!!")
		address = CryptBitcoin.privatekeyToAddress(privatekey)
		logging.info("Site address:     %s" % address)
		logging.info("----------------------------------------------------------------------")

		while True:
			if raw_input("? Have you secured your private key? (yes, no) > ").lower() == "yes": break
			else: logging.info("Please, secure it now, you going to need it to modify your site!")

		logging.info("Creating directory structure...")
		from Site import Site
		os.mkdir("%s/%s" % (config.data_dir, address))
		open("%s/%s/index.html" % (config.data_dir, address), "w").write("Hello %s!" % address)

		logging.info("Creating content.json...")
		site = Site(address)
		site.content_manager.sign(privatekey=privatekey)
		site.settings["own"] = True
		site.saveSettings()

		logging.info("Site created!")


	def siteSign(self, address, privatekey=None, inner_path="content.json", publish=False):
		from Site import Site
		logging.info("Signing site: %s..." % address)
		site = Site(address, allow_create = False)

		if not privatekey: # If no privatekey in args then ask it now
			import getpass
			privatekey = getpass.getpass("Private key (input hidden):")
		succ = site.content_manager.sign(inner_path=inner_path, privatekey=privatekey, update_changed_files=True)
		if succ and publish:
			self.sitePublish(address, inner_path=inner_path)


	def siteVerify(self, address):
		import time
		from Site import Site
		s = time.time()
		logging.info("Verifing site: %s..." % address)
		site = Site(address)
		bad_files = []

		for content_inner_path in site.content_manager.contents:
			logging.info("Verifing %s signature..." % content_inner_path)
			if site.content_manager.verifyFile(content_inner_path, site.storage.open(content_inner_path, "rb"), ignore_same=False) == True:
				logging.info("[OK] %s signed by address %s!" % (content_inner_path, address))
			else:
				logging.error("[ERROR] %s: invalid file!" % content_inner_path)
				bad_files += content_inner_path

		logging.info("Verifying site files...")
		bad_files += site.storage.verifyFiles()
		if not bad_files:
			logging.info("[OK] All file sha512sum matches! (%.3fs)" % (time.time()-s))
		else:
			logging.error("[ERROR] Error during verifying site files!")


	def dbRebuild(self, address):
		from Site import Site
		logging.info("Rebuilding site sql cache: %s..." % address)
		site = Site(address)
		s = time.time()
		site.storage.rebuildDb()
		logging.info("Done in %.3fs" % (time.time()-s))


	def dbQuery(self, address, query):
		from Site import Site
		import json
		site = Site(address)
		result = []
		for row in site.storage.query(query):
			result.append(dict(row))
		print json.dumps(result, indent=4)


	def siteAnnounce(self, address):
		from Site.Site import Site
		logging.info("Announcing site %s to tracker..." % address)
		site = Site(address)

		s = time.time()
		site.announce()
		print "Response time: %.3fs" % (time.time()-s)
		print site.peers


	def siteNeedFile(self, address, inner_path):
		from Site import Site
		site = Site(address)
		site.announce()
		print site.needFile(inner_path, update=True)


	def sitePublish(self, address, peer_ip=None, peer_port=15441, inner_path="content.json"):
		global file_server
		from Site import Site
		from File import FileServer # We need fileserver to handle incoming file requests

		logging.info("Creating FileServer....")
		file_server = FileServer()
		file_server_thread = gevent.spawn(file_server.start, check_sites=False) # Dont check every site integrity
		file_server.openport()
		site = file_server.sites[address]
		site.settings["serving"] = True # Serving the site even if its disabled
		if peer_ip: # Announce ip specificed
			site.addPeer(peer_ip, peer_port)
		else: # Just ask the tracker
			logging.info("Gathering peers from tracker")
			site.announce() # Gather peers
		published = site.publish(20, inner_path) # Push to 20 peers
		if published > 0:
			time.sleep(3)
			logging.info("Serving files (max 60s)...")
			gevent.joinall([file_server_thread], timeout=60)
			logging.info("Done.")
		else:
			logging.info("No peers found for this site, sitePublish command only works if you already have peers serving your site")
		


	# Crypto commands

	def cryptPrivatekeyToAddress(self, privatekey=None):
		from Crypt import CryptBitcoin
		if not privatekey: # If no privatekey in args then ask it now
			import getpass
			privatekey = getpass.getpass("Private key (input hidden):")

		print CryptBitcoin.privatekeyToAddress(privatekey)


	def cryptSign(self, message, privatekey):
		from Crypt import CryptBitcoin
		print CryptBitcoin.sign(message, privatekey)


	# Peer

	def peerPing(self, peer_ip, peer_port):
		logging.info("Opening a simple connection server")
		global file_server
		from Connection import ConnectionServer
		file_server = ConnectionServer("127.0.0.1", 1234)

		from Peer import Peer
		logging.info("Pinging 5 times peer: %s:%s..." % (peer_ip, int(peer_port)))
		peer = Peer(peer_ip, peer_port)
		for i in range(5):
			s = time.time()
			print peer.ping(),
			print "Response time: %.3fs" % (time.time()-s)
			time.sleep(1)


	def peerGetFile(self, peer_ip, peer_port, site, filename):
		logging.info("Opening a simple connection server")
		global file_server
		from Connection import ConnectionServer
		file_server = ConnectionServer()

		from Peer import Peer
		logging.info("Getting %s/%s from peer: %s:%s..." % (site, filename, peer_ip, peer_port))
		peer = Peer(peer_ip, peer_port)
		s = time.time()
		print peer.getFile(site, filename).read()
		print "Response time: %.3fs" % (time.time()-s)


	def peerCmd(self, peer_ip, peer_port, cmd, parameters):
		logging.info("Opening a simple connection server")
		global file_server
		from Connection import ConnectionServer
		file_server = ConnectionServer()
		from Peer import Peer
		peer = Peer(peer_ip, peer_port)

		import json
		if parameters:
			parameters = json.loads(parameters.replace("'", '"'))
		else:
			parameters = {}
		logging.info("Response: %s" % peer.request(cmd, parameters))



actions = Actions()
# Starts here when running zeronet.py
def start():
	# Call function
	func = getattr(actions, config.action, None)
	action_kwargs = config.getActionArguments()
	func(**action_kwargs)

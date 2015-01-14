import os, sys
sys.path.insert(0, os.path.dirname(__file__)) # Imports relative to main.py

# Create necessary files and dirs
if not os.path.isdir("log"): os.mkdir("log")
if not os.path.isdir("data"): os.mkdir("data")
if not os.path.isfile("data/sites.json"): open("data/sites.json", "w").write("{}")

# Load config
from Config import config

# Init logging
import logging
if config.action == "main":
	if os.path.isfile("log/debug.log"):  # Simple logrotate
		if os.path.isfile("log/debug-last.log"): os.unlink("log/debug-last.log")
		os.rename("log/debug.log", "log/debug-last.log")
	logging.basicConfig(format='[%(asctime)s] %(levelname)-8s %(name)s %(message)s', level=logging.DEBUG, filename="log/debug.log")
else:
	logging.basicConfig(level=logging.DEBUG, stream=open(os.devnull,"w")) # No file logging if action is not main

console_log = logging.StreamHandler()
console_log.setFormatter(logging.Formatter('%(name)s %(message)s', "%H:%M:%S"))
logging.getLogger('').addHandler(console_log) # Add console logger
logging.getLogger('').name = "-" # Remove root prefix

# Debug dependent configuration
if config.debug:
	console_log.setLevel(logging.DEBUG)
	from Debug import DebugHook
	from gevent import monkey; monkey.patch_all(thread=False) # thread=False because of pyfilesystem
else:
	console_log.setLevel(logging.INFO)
	from gevent import monkey; monkey.patch_all()

import gevent
import time


logging.debug("Starting... %s" % config)

# Starts here when running zeronet.py
def start():
	action_func = globals()[config.action] # Function reference
	action_kwargs = config.getActionArguments() # non-config arguments when calling zeronet.py

	action_func(**action_kwargs)


# Start serving UiServer and PeerServer
def main():
	from File import FileServer
	from Ui import UiServer
	logging.info("Creating UiServer....")
	ui_server = UiServer()

	logging.info("Creating FileServer....")
	file_server = FileServer()

	logging.info("Starting servers....")
	gevent.joinall([gevent.spawn(ui_server.start), gevent.spawn(file_server.start)])


# Site commands

def siteCreate():
	logging.info("Generating new privatekey...")
	from src.Crypt import CryptBitcoin
	privatekey = CryptBitcoin.newPrivatekey()
	logging.info("-----------------------------------------------------------")
	logging.info("Site private key: %s (save it, required to modify the site)" % privatekey)
	address = CryptBitcoin.privatekeyToAddress(privatekey)
	logging.info("Site address: %s" % address)
	logging.info("-----------------------------------------------------------")

	logging.info("Creating directory structure...")
	from Site import Site
	os.mkdir("data/%s" % address)
	open("data/%s/index.html" % address, "w").write("Hello %s!" % address)

	#start:dydx
	logging.info("Saving address and private ket to data/mysite.txt...")
	open("data/mysite.txt", "a+").write("address: %s, private key: %s" % (address, privatekey))
	#end:dydx

	logging.info("Creating content.json...")
	site = Site(address)
	site.signContent(privatekey)

	logging.info("Site created!")


def siteSign(address, privatekey=None):
	from Site import Site
	logging.info("Signing site: %s..." % address)
	site = Site(address, allow_create = False)

	if not privatekey: # If no privatekey in args then ask it now
		import getpass
		privatekey = getpass.getpass("Private key (input hidden):")
	site.signContent(privatekey)


def siteVerify(address):
	from Site import Site
	logging.info("Verifing site: %s..." % address)
	site = Site(address)

	logging.info("Verifing content.json signature...")
	if site.verifyFile("content.json", open(site.getPath("content.json"), "rb"), force=True) != False: # Force check the sign
		logging.info("[OK] content.json signed by address %s!" % address)
	else:
		logging.error("[ERROR] Content.json not signed by address %s!" % address)

	logging.info("Verifying site files...")
	bad_files = site.verifyFiles()
	if not bad_files:
		logging.info("[OK] All file sha1sum matches!")
	else:
		logging.error("[ERROR] Error during verifying site files!")


def siteAnnounce(address):
	from Site.Site import Site
	logging.info("Announcing site %s to tracker..." % address)
	site = Site(address)

	s = time.time()
	site.announce()
	print "Response time: %.3fs" % (time.time()-s)
	print site.peers


def siteNeedFile(address, inner_path):
	from Site import Site
	site = Site(address)
	site.announce()
	print site.needFile(inner_path, update=True)


def sitePublish(address):
	from Site import Site
	from File import FileServer # We need fileserver to handle incoming file requests
	logging.info("Creating FileServer....")
	file_server = FileServer()
	file_server_thread = gevent.spawn(file_server.start, check_sites=False) # Dont check every site integrity
	file_server.openport()
	if file_server.port_opened == False:
		logging.info("Port not opened, passive publishing not supported yet :(")
		return
	site = file_server.sites[address]
	site.settings["serving"] = True # Serving the site even if its disabled
	site.announce() # Gather peers
	site.publish(10) # Push to 10 peers
	logging.info("Serving files....")
	gevent.joinall([file_server_thread])


# Crypto commands

def cryptoPrivatekeyToAddress(privatekey=None):
	from src.Crypt import CryptBitcoin
	if not privatekey: # If no privatekey in args then ask it now
		import getpass
		privatekey = getpass.getpass("Private key (input hidden):")

	print CryptBitcoin.privatekeyToAddress(privatekey)


# Peer

def peerPing(ip, port):
	from Peer import Peer
	logging.info("Pinging 5 times peer: %s:%s..." % (ip, port))
	peer = Peer(ip, port)
	for i in range(5):
		s = time.time()
		print peer.ping(),
		print "Response time: %.3fs" % (time.time()-s)
		time.sleep(1)


def peerGetFile(ip, port, site, filename=None):
	from Peer import Peer
	if not site: site = config.homepage
	if not filename: filename = "content.json"
	logging.info("Getting %s/%s from peer: %s:%s..." % (site, filename, ip, port))
	peer = Peer(ip, port)
	s = time.time()
	print peer.getFile(site, filename).read()
	print "Response time: %.3fs" % (time.time()-s)


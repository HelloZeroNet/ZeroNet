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

# Console logger
console_log = logging.StreamHandler()
if config.action == "main": # Add time if main action
	console_log.setFormatter(logging.Formatter('[%(asctime)s] %(name)s %(message)s', "%H:%M:%S"))
else:
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

def siteCreate(sss):
        if sss:
                from Crypt.SecretSharing import PlaintextToHexSecretSharer as PTHSS
                if ":" not in sss or sss.count(":") > 1: raise Exception("Incorrect secret sharing format")
                k=int(sss.split(":")[0])
                n=int(sss.split(":")[1])
                if k>n: raise Exception("Required parts can't be bigger than parts amount.")
                
	logging.info("Generating new privatekey...")
	from src.Crypt import CryptBitcoin
	privatekey = CryptBitcoin.newPrivatekey()
	logging.info("----------------------------------------------------------------------")
	if sss:
                sharedkey  = PTHSS.split_secret(privatekey,k,n)
                for key in sharedkey: logging.info(key)
        else: logging.info("Site private key: %s" % privatekey)
	logging.info("                  !!! ^ Save it now, required to modify the site ^ !!!")
	address = CryptBitcoin.privatekeyToAddress(privatekey)
	logging.info("Site address:     %s" % address)
	logging.info("----------------------------------------------------------------------")

	while True:
		if raw_input("? Have you secured your private key? (yes, no) > ").lower() == "yes": break
		else: logging.info("Please, secure it now, you going to need it to modify your site!")

	logging.info("Creating directory structure...")
	from Site import Site
	os.mkdir("data/%s" % address)
	open("data/%s/index.html" % address, "w").write("Hello %s!" % address)

	logging.info("Creating content.json...")
	site = Site(address)
	site.signContent(privatekey)
	site.settings["own"] = True
	site.saveSettings()

	logging.info("Site created!")


def siteSign(address,sss, privatekey=None):
        if sss and privatekey==None:
                from Crypt.SecretSharing import PlaintextToHexSecretSharer as PTHSS
                if ":" not in sss: raise Exception("Incorrect secret sharing format")
                sss = sss.split(":")

                privatekey = PTHSS.recover_secret(sss)

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
		logging.info("[OK] All file sha512sum matches!")
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


def sitePublish(address, peer_ip=None, peer_port=15441):
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
	if peer_ip: # Announce ip specificed
		site.addPeer(peer_ip, peer_port)
	else: # Just ask the tracker
		logging.info("Gathering peers from tracker")
		site.announce() # Gather peers
	site.publish(20) # Push to 20 peers
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


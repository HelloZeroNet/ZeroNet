# Included modules
import os
import sys
import stat
import time
import logging

# Third party modules
import gevent

from gevent import monkey
if "patch_subprocess" in dir(monkey):  # New gevent
    monkey.patch_all(thread=False, subprocess=False)
else:  # Old gevent
    import ssl
    # Fix PROTOCOL_SSLv3 not defined
    if "PROTOCOL_SSLv3" not in dir(ssl):
        ssl.PROTOCOL_SSLv3 = ssl.PROTOCOL_SSLv23
    monkey.patch_all(thread=False)
# Not thread: pyfilesystem and systray icon, Not subprocess: Gevent 1.1+

update_after_shutdown = False  # If set True then update and restart zeronet after main loop ended

# Load config
from Config import config
config.parse(silent=True)  # Plugins need to access the configuration
if not config.arguments:  # Config parse failed, show the help screen and exit
    config.parse()

# Create necessary files and dirs
if not os.path.isdir(config.log_dir):
    os.mkdir(config.log_dir)
    try:
        os.chmod(config.log_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except Exception, err:
        print "Can't change permission of %s: %s" % (config.log_dir, err)

if not os.path.isdir(config.data_dir):
    os.mkdir(config.data_dir)
    try:
        os.chmod(config.data_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except Exception, err:
        print "Can't change permission of %s: %s" % (config.data_dir, err)

if not os.path.isfile("%s/sites.json" % config.data_dir):
    open("%s/sites.json" % config.data_dir, "w").write("{}")
if not os.path.isfile("%s/users.json" % config.data_dir):
    open("%s/users.json" % config.data_dir, "w").write("{}")

# Setup logging
if config.action == "main":
    from util import helper
    log_file_path = "%s/debug.log" % config.log_dir
    try:
        lock = helper.openLocked("%s/lock.pid" % config.data_dir, "w")
        lock.write("%s" % os.getpid())
    except IOError as err:
        print "Can't open lock file, your ZeroNet client is probably already running, exiting... (%s)" % err
        if config.open_browser:
            print "Opening browser: %s...", config.open_browser
            import webbrowser
            if config.open_browser == "default_browser":
                browser = webbrowser.get()
            else:
                browser = webbrowser.get(config.open_browser)
            browser.open("http://%s:%s/%s" % (config.ui_ip if config.ui_ip != "*" else "127.0.0.1", config.ui_port, config.homepage), new=2)
        sys.exit()

    if os.path.isfile("%s/debug.log" % config.log_dir):  # Simple logrotate
        if os.path.isfile("%s/debug-last.log" % config.log_dir):
            os.unlink("%s/debug-last.log" % config.log_dir)
        os.rename("%s/debug.log" % config.log_dir, "%s/debug-last.log" % config.log_dir)
    logging.basicConfig(
        format='[%(asctime)s] %(levelname)-8s %(name)s %(message)s',
        level=logging.DEBUG, stream=open(log_file_path, "a")
    )
else:
    log_file_path = "%s/cmd.log" % config.log_dir
    logging.basicConfig(
        format='[%(asctime)s] %(levelname)-8s %(name)s %(message)s',
        level=logging.DEBUG, stream=open(log_file_path, "w")
    )

# Console logger
console_log = logging.StreamHandler()
if config.action == "main":  # Add time if main action
    console_log.setFormatter(logging.Formatter('[%(asctime)s] %(name)s %(message)s', "%H:%M:%S"))
else:
    console_log.setFormatter(logging.Formatter('%(name)s %(message)s', "%H:%M:%S"))

logging.getLogger('').addHandler(console_log)  # Add console logger
logging.getLogger('').name = "-"  # Remove root prefix

# Debug dependent configuration
from Debug import DebugHook
if config.debug:
    console_log.setLevel(logging.DEBUG)  # Display everything to console
else:
    console_log.setLevel(logging.INFO)  # Display only important info to console

# Load plugins
from Plugin import PluginManager
PluginManager.plugin_manager.loadPlugins()
config.loadPlugins()
config.parse()  # Parse again to add plugin configuration options

# Log current config
logging.debug("Config: %s" % config)

# Modify stack size on special hardwares
if config.stack_size:
    import threading
    threading.stack_size(config.stack_size)

# Use pure-python implementation of msgpack to save CPU
if config.msgpack_purepython:
    os.environ["MSGPACK_PUREPYTHON"] = "True"

# Socks Proxy monkey patch
if config.proxy:
    from util import SocksProxy
    import urllib2
    logging.info("Patching sockets to socks proxy: %s" % config.proxy)
    if config.fileserver_ip == "*":
        config.fileserver_ip = '127.0.0.1'  # Do not accept connections anywhere but localhost
    SocksProxy.monkeyPatch(*config.proxy.split(":"))
elif config.tor == "always":
    from util import SocksProxy
    import urllib2
    logging.info("Patching sockets to tor socks proxy: %s" % config.tor_proxy)
    if config.fileserver_ip == "*":
        config.fileserver_ip = '127.0.0.1'  # Do not accept connections anywhere but localhost
    SocksProxy.monkeyPatch(*config.tor_proxy.split(":"))
    config.disable_udp = True
# -- Actions --


@PluginManager.acceptPlugins
class Actions(object):
    def call(self, function_name, kwargs):
        logging.info("Version: %s r%s, Python %s, Gevent: %s" % (config.version, config.rev, sys.version, gevent.__version__))

        func = getattr(self, function_name, None)
        func(**kwargs)

    # Default action: Start serving UiServer and FileServer
    def main(self):
        global ui_server, file_server
        from File import FileServer
        from Ui import UiServer
        logging.info("Creating FileServer....")
        file_server = FileServer()
        logging.info("Creating UiServer....")
        ui_server = UiServer()

        logging.info("Removing old SSL certs...")
        from Crypt import CryptConnection
        CryptConnection.manager.removeCerts()

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

        while True and not config.batch:
            if raw_input("? Have you secured your private key? (yes, no) > ").lower() == "yes":
                break
            else:
                logging.info("Please, secure it now, you going to need it to modify your site!")

        logging.info("Creating directory structure...")
        from Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        os.mkdir("%s/%s" % (config.data_dir, address))
        open("%s/%s/index.html" % (config.data_dir, address), "w").write("Hello %s!" % address)

        logging.info("Creating content.json...")
        site = Site(address)
        site.content_manager.sign(privatekey=privatekey, extend={"postmessage_nonce_security": True})
        site.settings["own"] = True
        site.saveSettings()

        logging.info("Site created!")

    def siteSign(self, address, privatekey=None, inner_path="content.json", publish=False, remove_missing_optional=False):
        from Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()
        logging.info("Signing site: %s..." % address)
        site = Site(address, allow_create=False)

        if not privatekey:  # If no privatekey defined
            from User import UserManager
            user = UserManager.user_manager.get()
            if user:
                site_data = user.getSiteData(address)
                privatekey = site_data.get("privatekey")
            else:
                privatekey = None
            if not privatekey:
                # Not found in users.json, ask from console
                import getpass
                privatekey = getpass.getpass("Private key (input hidden):")
        diffs = site.content_manager.getDiffs(inner_path)
        succ = site.content_manager.sign(inner_path=inner_path, privatekey=privatekey, update_changed_files=True, remove_missing_optional=remove_missing_optional)
        if succ and publish:
            self.sitePublish(address, inner_path=inner_path, diffs=diffs)

    def siteVerify(self, address):
        import time
        from Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        s = time.time()
        logging.info("Verifing site: %s..." % address)
        site = Site(address)
        bad_files = []

        for content_inner_path in site.content_manager.contents:
            s = time.time()
            logging.info("Verifing %s signature..." % content_inner_path)
            file_correct = site.content_manager.verifyFile(
                content_inner_path, site.storage.open(content_inner_path, "rb"), ignore_same=False
            )
            if file_correct is True:
                logging.info("[OK] %s (Done in %.3fs)" % (content_inner_path, time.time() - s))
            else:
                logging.error("[ERROR] %s: invalid file!" % content_inner_path)
                raw_input("Continue?")
                bad_files += content_inner_path

        logging.info("Verifying site files...")
        bad_files += site.storage.verifyFiles()
        if not bad_files:
            logging.info("[OK] All file sha512sum matches! (%.3fs)" % (time.time() - s))
        else:
            logging.error("[ERROR] Error during verifying site files!")

    def dbRebuild(self, address):
        from Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        logging.info("Rebuilding site sql cache: %s..." % address)
        site = SiteManager.site_manager.get(address)
        s = time.time()
        site.storage.rebuildDb()
        logging.info("Done in %.3fs" % (time.time() - s))

    def dbQuery(self, address, query):
        from Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        import json
        site = Site(address)
        result = []
        for row in site.storage.query(query):
            result.append(dict(row))
        print json.dumps(result, indent=4)

    def siteAnnounce(self, address):
        from Site.Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        logging.info("Announcing site %s to tracker..." % address)
        site = Site(address)

        s = time.time()
        site.announce()
        print "Response time: %.3fs" % (time.time() - s)
        print site.peers

    def siteDownload(self, address):
        from Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        logging.info("Opening a simple connection server")
        global file_server
        from Connection import ConnectionServer
        file_server = ConnectionServer("127.0.0.1", 1234)

        site = Site(address)

        on_completed = gevent.event.AsyncResult()

        def onComplete(evt):
            evt.set(True)

        site.onComplete.once(lambda: onComplete(on_completed))
        print "Announcing..."
        site.announce()

        s = time.time()
        print "Downloading..."
        site.downloadContent("content.json", check_modifications=True)

        print on_completed.get()
        print "Downloaded in %.3fs" % (time.time()-s)


    def siteNeedFile(self, address, inner_path):
        from Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        def checker():
            while 1:
                s = time.time()
                time.sleep(1)
                print "Switch time:", time.time() - s
        gevent.spawn(checker)

        logging.info("Opening a simple connection server")
        global file_server
        from Connection import ConnectionServer
        file_server = ConnectionServer("127.0.0.1", 1234)

        site = Site(address)
        site.announce()
        print site.needFile(inner_path, update=True)

    def sitePublish(self, address, peer_ip=None, peer_port=15441, inner_path="content.json", diffs={}):
        global file_server
        from Site import Site
        from Site import SiteManager
        from File import FileServer  # We need fileserver to handle incoming file requests
        from Peer import Peer
        SiteManager.site_manager.load()

        logging.info("Loading site...")
        site = Site(address, allow_create=False)
        site.settings["serving"] = True  # Serving the site even if its disabled

        logging.info("Creating FileServer....")
        file_server = FileServer()
        site.connection_server = file_server
        file_server_thread = gevent.spawn(file_server.start, check_sites=False)  # Dont check every site integrity
        time.sleep(0.001)

        if not file_server_thread.ready():
            # Started fileserver
            file_server.openport()
            if peer_ip:  # Announce ip specificed
                site.addPeer(peer_ip, peer_port)
            else:  # Just ask the tracker
                logging.info("Gathering peers from tracker")
                site.announce()  # Gather peers
            published = site.publish(5, inner_path, diffs=diffs)  # Push to peers
            if published > 0:
                time.sleep(3)
                logging.info("Serving files (max 60s)...")
                gevent.joinall([file_server_thread], timeout=60)
                logging.info("Done.")
            else:
                logging.info("No peers found, sitePublish command only works if you already have visitors serving your site")
        else:
            # Already running, notify local client on new content
            logging.info("Sending siteReload")
            if config.fileserver_ip == "*":
                my_peer = Peer("127.0.0.1", config.fileserver_port)
            else:
                my_peer = Peer(config.fileserver_ip, config.fileserver_port)

            logging.info(my_peer.request("siteReload", {"site": site.address, "inner_path": inner_path}))
            logging.info("Sending sitePublish")
            logging.info(my_peer.request("sitePublish", {"site": site.address, "inner_path": inner_path, "diffs": diffs}))
            logging.info("Done.")

    # Crypto commands
    def cryptPrivatekeyToAddress(self, privatekey=None):
        from Crypt import CryptBitcoin
        if not privatekey:  # If no privatekey in args then ask it now
            import getpass
            privatekey = getpass.getpass("Private key (input hidden):")

        print CryptBitcoin.privatekeyToAddress(privatekey)

    def cryptSign(self, message, privatekey):
        from Crypt import CryptBitcoin
        print CryptBitcoin.sign(message, privatekey)

    # Peer
    def peerPing(self, peer_ip, peer_port=None):
        if not peer_port:
            peer_port = config.fileserver_port
        logging.info("Opening a simple connection server")
        global file_server
        from Connection import ConnectionServer
        file_server = ConnectionServer("127.0.0.1", 1234)
        from Crypt import CryptConnection
        CryptConnection.manager.loadCerts()

        from Peer import Peer
        logging.info("Pinging 5 times peer: %s:%s..." % (peer_ip, int(peer_port)))
        peer = Peer(peer_ip, peer_port)
        for i in range(5):
            print "Response time: %.3fs (crypt: %s)" % (peer.ping(), peer.connection.crypt)
            time.sleep(1)
        peer.remove()
        print "Reconnect test..."
        peer = Peer(peer_ip, peer_port)
        for i in range(5):
            print "Response time: %.3fs (crypt: %s)" % (peer.ping(), peer.connection.crypt)
            time.sleep(1)

    def peerGetFile(self, peer_ip, peer_port, site, filename, benchmark=False):
        logging.info("Opening a simple connection server")
        global file_server
        from Connection import ConnectionServer
        file_server = ConnectionServer("127.0.0.1", 1234)
        from Crypt import CryptConnection
        CryptConnection.manager.loadCerts()

        from Peer import Peer
        logging.info("Getting %s/%s from peer: %s:%s..." % (site, filename, peer_ip, peer_port))
        peer = Peer(peer_ip, peer_port)
        s = time.time()
        if benchmark:
            for i in range(10):
                peer.getFile(site, filename),
            print "Response time: %.3fs" % (time.time() - s)
            raw_input("Check memory")
        else:
            print peer.getFile(site, filename).read()

    def peerCmd(self, peer_ip, peer_port, cmd, parameters):
        logging.info("Opening a simple connection server")
        global file_server
        from Connection import ConnectionServer
        file_server = ConnectionServer()
        from Crypt import CryptConnection
        CryptConnection.manager.loadCerts()

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
    action_kwargs = config.getActionArguments()
    actions.call(config.action, action_kwargs)

# Included modules
import os
import sys
import stat
import time
import logging

# Third party modules
import gevent

import gevent.monkey
gevent.monkey.patch_all(thread=False, subprocess=False)

update_after_shutdown = False  # If set True then update and restart zeronet after main loop ended
restart_after_shutdown = False  # If set True then restart zeronet after main loop ended

# Load config
from Config import config
config.parse(silent=True)  # Plugins need to access the configuration
if not config.arguments:  # Config parse failed, show the help screen and exit
    config.parse()

if not os.path.isdir(config.data_dir):
    os.mkdir(config.data_dir)
    try:
        os.chmod(config.data_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except Exception as err:
        print("Can't change permission of %s: %s" % (config.data_dir, err))

if not os.path.isfile("%s/sites.json" % config.data_dir):
    open("%s/sites.json" % config.data_dir, "w").write("{}")
if not os.path.isfile("%s/users.json" % config.data_dir):
    open("%s/users.json" % config.data_dir, "w").write("{}")

if config.action == "main":
    from util import helper
    try:
        lock = helper.openLocked("%s/lock.pid" % config.data_dir, "w")
        lock.write("%s" % os.getpid())
    except BlockingIOError as err:
        print("Can't open lock file, your ZeroNet client is probably already running, exiting... (%s)" % err)
        if config.open_browser and config.open_browser != "False":
            print("Opening browser: %s...", config.open_browser)
            import webbrowser
            try:
                if config.open_browser == "default_browser":
                    browser = webbrowser.get()
                else:
                    browser = webbrowser.get(config.open_browser)
                browser.open("http://%s:%s/%s" % (config.ui_ip if config.ui_ip != "*" else "127.0.0.1", config.ui_port, config.homepage), new=2)
            except Exception as err:
                print("Error starting browser: %s" % err)
        sys.exit()

config.initLogging()


# Debug dependent configuration
from Debug import DebugHook

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

# Socket monkey patch
if config.proxy:
    from util import SocksProxy
    import urllib.request
    logging.info("Patching sockets to socks proxy: %s" % config.proxy)
    if config.fileserver_ip == "*":
        config.fileserver_ip = '127.0.0.1'  # Do not accept connections anywhere but localhost
    SocksProxy.monkeyPatch(*config.proxy.split(":"))
elif config.tor == "always":
    from util import SocksProxy
    import urllib.request
    logging.info("Patching sockets to tor socks proxy: %s" % config.tor_proxy)
    if config.fileserver_ip == "*":
        config.fileserver_ip = '127.0.0.1'  # Do not accept connections anywhere but localhost
    SocksProxy.monkeyPatch(*config.tor_proxy.split(":"))
    config.disable_udp = True
elif config.bind:
    bind = config.bind
    if ":" not in config.bind:
        bind += ":0"
    from util import helper
    helper.socketBindMonkeyPatch(*bind.split(":"))

# -- Actions --


@PluginManager.acceptPlugins
class Actions(object):
    def call(self, function_name, kwargs):
        logging.info("Version: %s r%s, Python %s, Gevent: %s" % (config.version, config.rev, sys.version, gevent.__version__))

        func = getattr(self, function_name, None)
        back = func(**kwargs)
        if back:
            print(back)

    # Default action: Start serving UiServer and FileServer
    def main(self):
        global ui_server, file_server
        from File import FileServer
        from Ui import UiServer
        logging.info("Creating FileServer....")
        file_server = FileServer()
        logging.info("Creating UiServer....")
        ui_server = UiServer()
        file_server.ui_server = ui_server

        logging.info("Removing old SSL certs...")
        from Crypt import CryptConnection
        CryptConnection.manager.removeCerts()

        logging.info("Starting servers....")
        gevent.joinall([gevent.spawn(ui_server.start), gevent.spawn(file_server.start)])
        logging.info("All server stopped")

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
            if input("? Have you secured your private key? (yes, no) > ").lower() == "yes":
                break
            else:
                logging.info("Please, secure it now, you going to need it to modify your site!")

        logging.info("Creating directory structure...")
        from Site.Site import Site
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
        from Site.Site import Site
        from Site import SiteManager
        from Debug import Debug
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
        try:
            succ = site.content_manager.sign(inner_path=inner_path, privatekey=privatekey, update_changed_files=True, remove_missing_optional=remove_missing_optional)
        except Exception as err:
            logging.error("Sign error: %s" % Debug.formatException(err))
            succ = False
        if succ and publish:
            self.sitePublish(address, inner_path=inner_path)

    def siteVerify(self, address):
        import time
        from Site.Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        s = time.time()
        logging.info("Verifing site: %s..." % address)
        site = Site(address)
        bad_files = []

        for content_inner_path in site.content_manager.contents:
            s = time.time()
            logging.info("Verifing %s signature..." % content_inner_path)
            err = None
            try:
                file_correct = site.content_manager.verifyFile(
                    content_inner_path, site.storage.open(content_inner_path, "rb"), ignore_same=False
                )
            except Exception as err:
                file_correct = False

            if file_correct is True:
                logging.info("[OK] %s (Done in %.3fs)" % (content_inner_path, time.time() - s))
            else:
                logging.error("[ERROR] %s: invalid file: %s!" % (content_inner_path, err))
                input("Continue?")
                bad_files += content_inner_path

        logging.info("Verifying site files...")
        bad_files += site.storage.verifyFiles()["bad_files"]
        if not bad_files:
            logging.info("[OK] All file sha512sum matches! (%.3fs)" % (time.time() - s))
        else:
            logging.error("[ERROR] Error during verifying site files!")

    def dbRebuild(self, address):
        from Site.Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        logging.info("Rebuilding site sql cache: %s..." % address)
        site = SiteManager.site_manager.get(address)
        s = time.time()
        try:
            site.storage.rebuildDb()
            logging.info("Done in %.3fs" % (time.time() - s))
        except Exception as err:
            logging.error(err)

    def dbQuery(self, address, query):
        from Site.Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        import json
        site = Site(address)
        result = []
        for row in site.storage.query(query):
            result.append(dict(row))
        print(json.dumps(result, indent=4))

    def siteAnnounce(self, address):
        from Site.Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        logging.info("Opening a simple connection server")
        global file_server
        from File import FileServer
        file_server = FileServer("127.0.0.1", 1234)
        file_server.start()

        logging.info("Announcing site %s to tracker..." % address)
        site = Site(address)

        s = time.time()
        site.announce()
        print("Response time: %.3fs" % (time.time() - s))
        print(site.peers)

    def siteDownload(self, address):
        from Site.Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        logging.info("Opening a simple connection server")
        global file_server
        from File import FileServer
        file_server = FileServer("127.0.0.1", 1234)
        file_server_thread = gevent.spawn(file_server.start, check_sites=False)

        site = Site(address)

        on_completed = gevent.event.AsyncResult()

        def onComplete(evt):
            evt.set(True)

        site.onComplete.once(lambda: onComplete(on_completed))
        print("Announcing...")
        site.announce()

        s = time.time()
        print("Downloading...")
        site.downloadContent("content.json", check_modifications=True)

        print("Downloaded in %.3fs" % (time.time()-s))


    def siteNeedFile(self, address, inner_path):
        from Site.Site import Site
        from Site import SiteManager
        SiteManager.site_manager.load()

        def checker():
            while 1:
                s = time.time()
                time.sleep(1)
                print("Switch time:", time.time() - s)
        gevent.spawn(checker)

        logging.info("Opening a simple connection server")
        global file_server
        from File import FileServer
        file_server = FileServer("127.0.0.1", 1234)
        file_server_thread = gevent.spawn(file_server.start, check_sites=False)

        site = Site(address)
        site.announce()
        print(site.needFile(inner_path, update=True))

    def siteCmd(self, address, cmd, parameters):
        import json
        from Site import SiteManager

        site = SiteManager.site_manager.get(address)

        if not site:
            logging.error("Site not found: %s" % address)
            return None

        ws = self.getWebsocket(site)

        ws.send(json.dumps({"cmd": cmd, "params": parameters, "id": 1}))
        res_raw = ws.recv()

        try:
            res = json.loads(res_raw)
        except Exception as err:
            return {"error": "Invalid result: %s" % err, "res_raw": res_raw}

        if "result" in res:
            return res["result"]
        else:
            return res

    def getWebsocket(self, site):
        import websocket

        ws_address = "ws://%s:%s/Websocket?wrapper_key=%s" % (config.ui_ip, config.ui_port, site.settings["wrapper_key"])
        logging.info("Connecting to %s" % ws_address)
        ws = websocket.create_connection(ws_address)
        return ws

    def sitePublish(self, address, peer_ip=None, peer_port=15441, inner_path="content.json"):
        global file_server
        from Site.Site import Site
        from Site import SiteManager
        from File import FileServer  # We need fileserver to handle incoming file requests
        from Peer import Peer
        file_server = FileServer()
        site = SiteManager.site_manager.get(address)
        logging.info("Loading site...")
        site.settings["serving"] = True  # Serving the site even if its disabled

        try:
            ws = self.getWebsocket(site)
            logging.info("Sending siteReload")
            self.siteCmd(address, "siteReload", inner_path)

            logging.info("Sending sitePublish")
            self.siteCmd(address, "sitePublish", {"inner_path": inner_path, "sign": False})
            logging.info("Done.")

        except Exception as err:
            logging.info("Can't connect to local websocket client: %s" % err)
            logging.info("Creating FileServer....")
            file_server_thread = gevent.spawn(file_server.start, check_sites=False)  # Dont check every site integrity
            time.sleep(0.001)

            # Started fileserver
            file_server.portCheck()
            if peer_ip:  # Announce ip specificed
                site.addPeer(peer_ip, peer_port)
            else:  # Just ask the tracker
                logging.info("Gathering peers from tracker")
                site.announce()  # Gather peers
            published = site.publish(5, inner_path)  # Push to peers
            if published > 0:
                time.sleep(3)
                logging.info("Serving files (max 60s)...")
                gevent.joinall([file_server_thread], timeout=60)
                logging.info("Done.")
            else:
                logging.info("No peers found, sitePublish command only works if you already have visitors serving your site")

    # Crypto commands
    def cryptPrivatekeyToAddress(self, privatekey=None):
        from Crypt import CryptBitcoin
        if not privatekey:  # If no privatekey in args then ask it now
            import getpass
            privatekey = getpass.getpass("Private key (input hidden):")

        print(CryptBitcoin.privatekeyToAddress(privatekey))

    def cryptSign(self, message, privatekey):
        from Crypt import CryptBitcoin
        print(CryptBitcoin.sign(message, privatekey))

    def cryptVerify(self, message, sign, address):
        from Crypt import CryptBitcoin
        print(CryptBitcoin.verify(message, address, sign))

    def cryptGetPrivatekey(self, master_seed, site_address_index=None):
        from Crypt import CryptBitcoin
        if len(master_seed) != 64:
            logging.error("Error: Invalid master seed length: %s (required: 64)" % len(master_seed))
            return False
        privatekey = CryptBitcoin.hdPrivatekey(master_seed, site_address_index)
        print("Requested private key: %s" % privatekey)

    # Peer
    def peerPing(self, peer_ip, peer_port=None):
        if not peer_port:
            peer_port = 15441
        logging.info("Opening a simple connection server")
        global file_server
        from Connection import ConnectionServer
        file_server = ConnectionServer("127.0.0.1", 1234)
        file_server.start(check_connections=False)
        from Crypt import CryptConnection
        CryptConnection.manager.loadCerts()

        from Peer import Peer
        logging.info("Pinging 5 times peer: %s:%s..." % (peer_ip, int(peer_port)))
        s = time.time()
        peer = Peer(peer_ip, peer_port)
        peer.connect()

        if not peer.connection:
            print("Error: Can't connect to peer (connection error: %s)" % peer.connection_error)
            return False
        print("Connection time: %.3fs  (connection error: %s)" % (time.time() - s, peer.connection_error))

        for i in range(5):
            ping_delay = peer.ping()
            if "cipher" in dir(peer.connection.sock):
                cipher = peer.connection.sock.cipher()[0]
                tls_version = peer.connection.sock.version()
            else:
                cipher = peer.connection.crypt
                tls_version = None
            print("Response time: %.3fs (crypt: %s %s %s)" % (ping_delay, peer.connection.crypt, cipher, tls_version))
            time.sleep(1)
        peer.remove()
        print("Reconnect test...")
        peer = Peer(peer_ip, peer_port)
        for i in range(5):
            ping_delay = peer.ping()
            if "cipher" in dir(peer.connection.sock):
                cipher = peer.connection.sock.cipher()[0]
                tls_version = peer.connection.sock.version()
            else:
                cipher = peer.connection.crypt
                tls_version = None
            print("Response time: %.3fs (crypt: %s %s %s)" % (ping_delay, peer.connection.crypt, cipher, tls_version))
            time.sleep(1)

    def peerGetFile(self, peer_ip, peer_port, site, filename, benchmark=False):
        logging.info("Opening a simple connection server")
        global file_server
        from Connection import ConnectionServer
        file_server = ConnectionServer("127.0.0.1", 1234)
        file_server.start(check_connections=False)
        from Crypt import CryptConnection
        CryptConnection.manager.loadCerts()

        from Peer import Peer
        logging.info("Getting %s/%s from peer: %s:%s..." % (site, filename, peer_ip, peer_port))
        peer = Peer(peer_ip, peer_port)
        s = time.time()
        if benchmark:
            for i in range(10):
                peer.getFile(site, filename),
            print("Response time: %.3fs" % (time.time() - s))
            input("Check memory")
        else:
            print(peer.getFile(site, filename).read())

    def peerCmd(self, peer_ip, peer_port, cmd, parameters):
        logging.info("Opening a simple connection server")
        global file_server
        from Connection import ConnectionServer
        file_server = ConnectionServer()
        file_server.start(check_connections=False)
        from Crypt import CryptConnection
        CryptConnection.manager.loadCerts()

        from Peer import Peer
        peer = Peer(peer_ip, peer_port)

        import json
        if parameters:
            parameters = json.loads(parameters.replace("'", '"'))
        else:
            parameters = {}
        try:
            res = peer.request(cmd, parameters)
            print(json.dumps(res, indent=2, ensure_ascii=False))
        except Exception as err:
            print("Unknown response (%s): %s" % (err, res))

    def getConfig(self):
        import json
        print(json.dumps(config.getServerInfo(), indent=2, ensure_ascii=False))



actions = Actions()
# Starts here when running zeronet.py


def start():
    # Call function
    action_kwargs = config.getActionArguments()
    actions.call(config.action, action_kwargs)

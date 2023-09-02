import argparse
import sys
import os
import locale
import re
import configparser
import logging
import logging.handlers
import stat
import time


class Config(object):

    def __init__(self, argv):
        self.version = "0.7.2"
        self.rev = 4555
        self.argv = argv
        self.action = None
        self.test_parser = None
        self.pending_changes = {}
        self.need_restart = False
        self.keys_api_change_allowed = set([
            "tor", "fileserver_port", "language", "tor_use_bridges", "trackers_proxy", "trackers",
            "trackers_file", "open_browser", "log_level", "fileserver_ip_type", "ip_external", "offline",
            "threads_fs_read", "threads_fs_write", "threads_crypt", "threads_db"
        ])
        self.keys_restart_need = set([
            "tor", "fileserver_port", "fileserver_ip_type", "threads_fs_read", "threads_fs_write", "threads_crypt", "threads_db"
        ])
        self.start_dir = self.getStartDir()

        self.config_file = self.start_dir + "/zeronet.conf"
        self.data_dir = self.start_dir + "/data"
        self.log_dir = self.start_dir + "/log"
        self.openssl_lib_file = None
        self.openssl_bin_file = None

        self.trackers_file = False
        self.createParser()
        self.createArguments()

    def createParser(self):
        # Create parser
        self.parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        self.parser.register('type', 'bool', self.strToBool)
        self.subparsers = self.parser.add_subparsers(title="Action to perform", dest="action")

    def __str__(self):
        return str(self.arguments).replace("Namespace", "Config")  # Using argparse str output

    # Convert string to bool
    def strToBool(self, v):
        return v.lower() in ("yes", "true", "t", "1")

    def getStartDir(self):
        this_file = os.path.abspath(__file__).replace("\\", "/").rstrip("cd")

        if "--start_dir" in self.argv:
            start_dir = self.argv[self.argv.index("--start_dir") + 1]
        elif this_file.endswith("/Contents/Resources/core/src/Config.py"):
            # Running as ZeroNet.app
            if this_file.startswith("/Application") or this_file.startswith("/private") or this_file.startswith(os.path.expanduser("~/Library")):
                # Runnig from non-writeable directory, put data to Application Support
                start_dir = os.path.expanduser("~/Library/Application Support/ZeroNet")
            else:
                # Running from writeable directory put data next to .app
                start_dir = re.sub("/[^/]+/Contents/Resources/core/src/Config.py", "", this_file)
        elif this_file.endswith("/core/src/Config.py"):
            # Running as exe or source is at Application Support directory, put var files to outside of core dir
            start_dir = this_file.replace("/core/src/Config.py", "")
        elif this_file.endswith("usr/share/zeronet/src/Config.py"):
            # Running from non-writeable location, e.g., AppImage
            start_dir = os.path.expanduser("~/ZeroNet")
        else:
            start_dir = "."

        return start_dir

    # Create command line arguments
    def createArguments(self):
        trackers = [
            # by zeroseed at http://127.0.0.1:43110/19HKdTAeBh5nRiKn791czY7TwRB1QNrf1Q/?:users/1HvNGwHKqhj3ZMEM53tz6jbdqe4LRpanEu:zn:dc17f896-bf3f-4962-bdd4-0a470040c9c5
            "zero://k5w77dozo3hy5zualyhni6vrh73iwfkaofa64abbilwyhhd3wgenbjqd.onion:15441",
            "zero://2kcb2fqesyaevc4lntogupa4mkdssth2ypfwczd2ov5a3zo6ytwwbayd.onion:15441",
            "zero://my562dxpjropcd5hy3nd5pemsc4aavbiptci5amwxzbelmzgkkuxpvid.onion:15441",
            "zero://pn4q2zzt2pw4nk7yidxvsxmydko7dfibuzxdswi6gu6ninjpofvqs2id.onion:15441",
            "zero://6i54dd5th73oelv636ivix6sjnwfgk2qsltnyvswagwphub375t3xcad.onion:15441",
            "zero://tl74auz4tyqv4bieeclmyoe4uwtoc2dj7fdqv4nc4gl5j2bwg2r26bqd.onion:15441",
            "zero://wlxav3szbrdhest4j7dib2vgbrd7uj7u7rnuzg22cxbih7yxyg2hsmid.onion:15441",
            "zero://zy7wttvjtsijt5uwmlar4yguvjc2gppzbdj4v6bujng6xwjmkdg7uvqd.onion:15441",

            # ZeroNet 0.7.2 defaults:
            "zero://boot3rdez4rzn36x.onion:15441",
            "zero://zero.booth.moe#f36ca555bee6ba216b14d10f38c16f7769ff064e0e37d887603548cc2e64191d:443",  # US/NY
            "udp://tracker.coppersurfer.tk:6969",  # DE
            "udp://104.238.198.186:8000",  # US/LA
            "udp://retracker.akado-ural.ru:80",  # RU
            "http://h4.trakx.nibba.trade:80/announce",  # US/VA
            "http://open.acgnxtracker.com:80/announce",  # DE
            "http://tracker.bt4g.com:2095/announce",  # Cloudflare
            "zero://2602:ffc5::c5b2:5360:26312"  # US/ATL
        ]
        # Platform specific
        if sys.platform.startswith("win"):
            coffeescript = "type %s | tools\\coffee\\coffee.cmd"
        else:
            coffeescript = None

        try:
            language, enc = locale.getdefaultlocale()
            language = language.lower().replace("_", "-")
            if language not in ["pt-br", "zh-tw"]:
                language = language.split("-")[0]
        except Exception:
            language = "en"

        use_openssl = True

        if repr(1483108852.565) != "1483108852.565":  # Fix for weird Android issue
            fix_float_decimals = True
        else:
            fix_float_decimals = False

        config_file = self.start_dir + "/zeronet.conf"
        data_dir = self.start_dir + "/data"
        log_dir = self.start_dir + "/log"

        ip_local = ["127.0.0.1", "::1"]

        # Main
        action = self.subparsers.add_parser("main", help='Start UiServer and FileServer (default)')

        # SiteCreate
        action = self.subparsers.add_parser("siteCreate", help='Create a new site')
        action.register('type', 'bool', self.strToBool)
        action.add_argument('--use_master_seed', help="Allow created site's private key to be recovered using the master seed in users.json (default: True)", type="bool", choices=[True, False], default=True)

        # SiteNeedFile
        action = self.subparsers.add_parser("siteNeedFile", help='Get a file from site')
        action.add_argument('address', help='Site address')
        action.add_argument('inner_path', help='File inner path')

        # SiteDownload
        action = self.subparsers.add_parser("siteDownload", help='Download a new site')
        action.add_argument('address', help='Site address')

        # SiteSign
        action = self.subparsers.add_parser("siteSign", help='Update and sign content.json: address [privatekey]')
        action.add_argument('address', help='Site to sign')
        action.add_argument('privatekey', help='Private key (default: ask on execute)', nargs='?')
        action.add_argument('--inner_path', help='File you want to sign (default: content.json)',
                            default="content.json", metavar="inner_path")
        action.add_argument('--remove_missing_optional', help='Remove optional files that is not present in the directory', action='store_true')
        action.add_argument('--publish', help='Publish site after the signing', action='store_true')

        # SitePublish
        action = self.subparsers.add_parser("sitePublish", help='Publish site to other peers: address')
        action.add_argument('address', help='Site to publish')
        action.add_argument('peer_ip', help='Peer ip to publish (default: random peers ip from tracker)',
                            default=None, nargs='?')
        action.add_argument('peer_port', help='Peer port to publish (default: random peer port from tracker)',
                            default=15441, nargs='?')
        action.add_argument('--inner_path', help='Content.json you want to publish (default: content.json)',
                            default="content.json", metavar="inner_path")

        # SiteVerify
        action = self.subparsers.add_parser("siteVerify", help='Verify site files using sha512: address')
        action.add_argument('address', help='Site to verify')

        # SiteCmd
        action = self.subparsers.add_parser("siteCmd", help='Execute a ZeroFrame API command on a site')
        action.add_argument('address', help='Site address')
        action.add_argument('cmd', help='API command name')
        action.add_argument('parameters', help='Parameters of the command', nargs='?')

        # dbRebuild
        action = self.subparsers.add_parser("dbRebuild", help='Rebuild site database cache')
        action.add_argument('address', help='Site to rebuild')

        # dbQuery
        action = self.subparsers.add_parser("dbQuery", help='Query site sql cache')
        action.add_argument('address', help='Site to query')
        action.add_argument('query', help='Sql query')

        # PeerPing
        action = self.subparsers.add_parser("peerPing", help='Send Ping command to peer')
        action.add_argument('peer_ip', help='Peer ip')
        action.add_argument('peer_port', help='Peer port', nargs='?')

        # PeerGetFile
        action = self.subparsers.add_parser("peerGetFile", help='Request and print a file content from peer')
        action.add_argument('peer_ip', help='Peer ip')
        action.add_argument('peer_port', help='Peer port')
        action.add_argument('site', help='Site address')
        action.add_argument('filename', help='File name to request')
        action.add_argument('--benchmark', help='Request file 10x then displays the total time', action='store_true')

        # PeerCmd
        action = self.subparsers.add_parser("peerCmd", help='Request and print a file content from peer')
        action.add_argument('peer_ip', help='Peer ip')
        action.add_argument('peer_port', help='Peer port')
        action.add_argument('cmd', help='Command to execute')
        action.add_argument('parameters', help='Parameters to command', nargs='?')

        # CryptSign
        action = self.subparsers.add_parser("cryptSign", help='Sign message using Bitcoin private key')
        action.add_argument('message', help='Message to sign')
        action.add_argument('privatekey', help='Private key')

        # Crypt Verify
        action = self.subparsers.add_parser("cryptVerify", help='Verify message using Bitcoin public address')
        action.add_argument('message', help='Message to verify')
        action.add_argument('sign', help='Signiture for message')
        action.add_argument('address', help='Signer\'s address')

        # Crypt GetPrivatekey
        action = self.subparsers.add_parser("cryptGetPrivatekey", help='Generate a privatekey from master seed')
        action.add_argument('master_seed', help='Source master seed')
        action.add_argument('site_address_index', help='Site address index', type=int)

        action = self.subparsers.add_parser("getConfig", help='Return json-encoded info')
        action = self.subparsers.add_parser("testConnection", help='Testing')
        action = self.subparsers.add_parser("testAnnounce", help='Testing')

        self.test_parser = self.subparsers.add_parser("test", help='Run a test')
        self.test_parser.add_argument('test_name', help='Test name', nargs="?")
        # self.test_parser.add_argument('--benchmark', help='Run the tests multiple times to measure the performance', action='store_true')

        # Config parameters
        self.parser.add_argument('--verbose', help='More detailed logging', action='store_true')
        self.parser.add_argument('--debug', help='Debug mode', action='store_true')
        self.parser.add_argument('--silent', help='Only log errors to terminal output', action='store_true')
        self.parser.add_argument('--debug_socket', help='Debug socket connections', action='store_true')
        self.parser.add_argument('--merge_media', help='Merge all.js and all.css', action='store_true')

        self.parser.add_argument('--batch', help="Batch mode (No interactive input for commands)", action='store_true')

        self.parser.add_argument('--start_dir', help='Path of working dir for variable content (data, log, .conf)', default=self.start_dir, metavar="path")
        self.parser.add_argument('--config_file', help='Path of config file', default=config_file, metavar="path")
        self.parser.add_argument('--data_dir', help='Path of data directory', default=data_dir, metavar="path")

        self.parser.add_argument('--console_log_level', help='Level of logging to console', default="default", choices=["default", "DEBUG", "INFO", "ERROR", "off"])

        self.parser.add_argument('--log_dir', help='Path of logging directory', default=log_dir, metavar="path")
        self.parser.add_argument('--log_level', help='Level of logging to file', default="DEBUG", choices=["DEBUG", "INFO", "ERROR", "off"])
        self.parser.add_argument('--log_rotate', help='Log rotate interval', default="daily", choices=["hourly", "daily", "weekly", "off"])
        self.parser.add_argument('--log_rotate_backup_count', help='Log rotate backup count', default=5, type=int)

        self.parser.add_argument('--language', help='Web interface language', default=language, metavar='language')
        self.parser.add_argument('--ui_ip', help='Web interface bind address', default="127.0.0.1", metavar='ip')
        self.parser.add_argument('--ui_port', help='Web interface bind port', default=43110, type=int, metavar='port')
        self.parser.add_argument('--ui_restrict', help='Restrict web access', default=False, metavar='ip', nargs='*')
        self.parser.add_argument('--ui_host', help='Allow access using this hosts', metavar='host', nargs='*')
        self.parser.add_argument('--ui_trans_proxy', help='Allow access using a transparent proxy', action='store_true')

        self.parser.add_argument('--open_browser', help='Open homepage in web browser automatically',
                                 nargs='?', const="default_browser", metavar='browser_name')
        self.parser.add_argument('--homepage', help='Web interface Homepage', default='1HeLLoPVbqF3UEj8aWXErwTxrwkyjwGtZN',
                                 metavar='address')
        self.parser.add_argument('--updatesite', help='Source code update site', default='1uPDaT3uSyWAPdCv1WkMb5hBQjWSNNACf',
                                 metavar='address')
        self.parser.add_argument('--dist_type', help='Type of installed distribution', default='source')

        self.parser.add_argument('--size_limit', help='Default site size limit in MB', default=10, type=int, metavar='limit')
        self.parser.add_argument('--file_size_limit', help='Maximum per file size limit in MB', default=10, type=int, metavar='limit')
        self.parser.add_argument('--connected_limit', help='Max number of connected peers per site. Soft limit.', default=10, type=int, metavar='connected_limit')
        self.parser.add_argument('--global_connected_limit', help='Max number of connections. Soft limit.', default=512, type=int, metavar='global_connected_limit')
        self.parser.add_argument('--workers', help='Download workers per site', default=5, type=int, metavar='workers')

        self.parser.add_argument('--site_announce_interval_min', help='Site announce interval for the most active sites, in minutes.', default=4, type=int, metavar='site_announce_interval_min')
        self.parser.add_argument('--site_announce_interval_max', help='Site announce interval for inactive sites, in minutes.', default=30, type=int, metavar='site_announce_interval_max')

        self.parser.add_argument('--site_peer_check_interval_min', help='Connectable peers check interval for the most active sites, in minutes.', default=5, type=int, metavar='site_peer_check_interval_min')
        self.parser.add_argument('--site_peer_check_interval_max', help='Connectable peers check interval for inactive sites, in minutes.', default=20, type=int, metavar='site_peer_check_interval_max')

        self.parser.add_argument('--site_update_check_interval_min', help='Site update check interval for the most active sites, in minutes.', default=5, type=int, metavar='site_update_check_interval_min')
        self.parser.add_argument('--site_update_check_interval_max', help='Site update check interval for inactive sites, in minutes.', default=45, type=int, metavar='site_update_check_interval_max')

        self.parser.add_argument('--site_connectable_peer_count_max', help='Search for as many connectable peers for the most active sites', default=10, type=int, metavar='site_connectable_peer_count_max')
        self.parser.add_argument('--site_connectable_peer_count_min', help='Search for as many connectable peers for inactive sites', default=2, type=int, metavar='site_connectable_peer_count_min')

        self.parser.add_argument('--send_back_lru_size', help='Size of the send back LRU cache', default=5000, type=int, metavar='send_back_lru_size')
        self.parser.add_argument('--send_back_limit', help='Send no more than so many files at once back to peer, when we discovered that the peer held older file versions', default=3, type=int, metavar='send_back_limit')

        self.parser.add_argument('--expose_no_ownership', help='By default, ZeroNet tries checking updates for own sites more frequently. This can be used by a third party for revealing the network addresses of a site owner. If this option is enabled, ZeroNet performs the checks in the same way for any sites.', type='bool', choices=[True, False], default=False)

        self.parser.add_argument('--simultaneous_connection_throttle_threshold', help='Throttle opening new connections when the number of outgoing connections in not fully established state exceeds the threshold.', default=15, type=int, metavar='simultaneous_connection_throttle_threshold')

        self.parser.add_argument('--fileserver_ip', help='FileServer bind address', default="*", metavar='ip')
        self.parser.add_argument('--fileserver_port', help='FileServer bind port (0: randomize)', default=0, type=int, metavar='port')
        self.parser.add_argument('--fileserver_port_range', help='FileServer randomization range', default="10000-40000", metavar='port')
        self.parser.add_argument('--fileserver_ip_type', help='FileServer ip type', default="dual", choices=["ipv4", "ipv6", "dual"])
        self.parser.add_argument('--ip_local', help='My local ips', default=ip_local, type=int, metavar='ip', nargs='*')
        self.parser.add_argument('--ip_external', help='Set reported external ip (tested on start if None)', metavar='ip', nargs='*')
        self.parser.add_argument('--offline', help='Disable network communication', action='store_true')

        self.parser.add_argument('--disable_udp', help='Disable UDP connections', action='store_true')
        self.parser.add_argument('--proxy', help='Socks proxy address', metavar='ip:port')
        self.parser.add_argument('--bind', help='Bind outgoing sockets to this address', metavar='ip')
        self.parser.add_argument('--trackers', help='Bootstraping torrent trackers', default=trackers, metavar='protocol://address', nargs='*')
        self.parser.add_argument('--trackers_file', help='Load torrent trackers dynamically from a file', metavar='path', nargs='*')
        self.parser.add_argument('--trackers_proxy', help='Force use proxy to connect to trackers (disable, tor, ip:port)', default="disable")
        self.parser.add_argument('--use_libsecp256k1', help='Use Libsecp256k1 liblary for speedup', type='bool', choices=[True, False], default=True)
        self.parser.add_argument('--use_openssl', help='Use OpenSSL liblary for speedup', type='bool', choices=[True, False], default=True)
        self.parser.add_argument('--openssl_lib_file', help='Path for OpenSSL library file (default: detect)', default=argparse.SUPPRESS, metavar="path")
        self.parser.add_argument('--openssl_bin_file', help='Path for OpenSSL binary file (default: detect)', default=argparse.SUPPRESS, metavar="path")
        self.parser.add_argument('--disable_db', help='Disable database updating', action='store_true')
        self.parser.add_argument('--disable_encryption', help='Disable connection encryption', action='store_true')
        self.parser.add_argument('--force_encryption', help="Enforce encryption to all peer connections", action='store_true')
        self.parser.add_argument('--disable_sslcompression', help='Disable SSL compression to save memory',
                                 type='bool', choices=[True, False], default=True)
        self.parser.add_argument('--keep_ssl_cert', help='Disable new SSL cert generation on startup', action='store_true')
        self.parser.add_argument('--max_files_opened', help='Change maximum opened files allowed by OS to this value on startup',
                                 default=2048, type=int, metavar='limit')
        self.parser.add_argument('--stack_size', help='Change thread stack size', default=None, type=int, metavar='thread_stack_size')
        self.parser.add_argument('--use_tempfiles', help='Use temporary files when downloading (experimental)',
                                 type='bool', choices=[True, False], default=False)
        self.parser.add_argument('--stream_downloads', help='Stream download directly to files (experimental)',
                                 type='bool', choices=[True, False], default=False)
        self.parser.add_argument("--msgpack_purepython", help='Use less memory, but a bit more CPU power',
                                 type='bool', choices=[True, False], default=False)
        self.parser.add_argument("--fix_float_decimals", help='Fix content.json modification date float precision on verification',
                                 type='bool', choices=[True, False], default=fix_float_decimals)
        self.parser.add_argument("--db_mode", choices=["speed", "security"], default="speed")

        self.parser.add_argument('--threads_fs_read', help='Number of threads for file read operations', default=1, type=int)
        self.parser.add_argument('--threads_fs_write', help='Number of threads for file write operations', default=1, type=int)
        self.parser.add_argument('--threads_crypt', help='Number of threads for cryptographic operations', default=2, type=int)
        self.parser.add_argument('--threads_db', help='Number of threads for database operations', default=1, type=int)

        self.parser.add_argument("--download_optional", choices=["manual", "auto"], default="manual")

        self.parser.add_argument('--coffeescript_compiler', help='Coffeescript compiler for developing', default=coffeescript,
                                 metavar='executable_path')

        self.parser.add_argument('--tor', help='enable: Use only for Tor peers, always: Use Tor for every connection', choices=["disable", "enable", "always"], default='enable')
        self.parser.add_argument('--tor_controller', help='Tor controller address', metavar='ip:port', default='127.0.0.1:9051')
        self.parser.add_argument('--tor_proxy', help='Tor proxy address', metavar='ip:port', default='127.0.0.1:9050')
        self.parser.add_argument('--tor_password', help='Tor controller password', metavar='password')
        self.parser.add_argument('--tor_use_bridges', help='Use obfuscated bridge relays to avoid Tor block', action='store_true')
        self.parser.add_argument('--tor_hs_limit', help='Maximum number of hidden services in Tor always mode', metavar='limit', type=int, default=10)
        self.parser.add_argument('--tor_hs_port', help='Hidden service port in Tor always mode', metavar='limit', type=int, default=15441)

        self.parser.add_argument('--version', action='version', version='ZeroNet %s r%s' % (self.version, self.rev))
        self.parser.add_argument('--end', help='Stop multi value argument parsing', action='store_true')

        return self.parser

    def loadTrackersFile(self):
        if not self.trackers_file:
            return None

        self.trackers = self.arguments.trackers[:]

        for trackers_file in self.trackers_file:
            try:
                if trackers_file.startswith("/"):  # Absolute
                    trackers_file_path = trackers_file
                elif trackers_file.startswith("{data_dir}"):  # Relative to data_dir
                    trackers_file_path = trackers_file.replace("{data_dir}", self.data_dir)
                else:  # Relative to zeronet.py
                    trackers_file_path = self.start_dir + "/" + trackers_file

                for line in open(trackers_file_path):
                    tracker = line.strip()
                    if "://" in tracker and tracker not in self.trackers:
                        self.trackers.append(tracker)
            except Exception as err:
                print("Error loading trackers file: %s" % err)

    # Find arguments specified for current action
    def getActionArguments(self):
        back = {}
        arguments = self.parser._subparsers._group_actions[0].choices[self.action]._actions[1:]  # First is --version
        for argument in arguments:
            back[argument.dest] = getattr(self, argument.dest)
        return back

    # Try to find action from argv
    def getAction(self, argv):
        actions = [list(action.choices.keys()) for action in self.parser._actions if action.dest == "action"][0]  # Valid actions
        found_action = False
        for action in actions:  # See if any in argv
            if action in argv:
                found_action = action
                break
        return found_action

    # Move plugin parameters to end of argument list
    def moveUnknownToEnd(self, argv, default_action):
        valid_actions = sum([action.option_strings for action in self.parser._actions], [])
        valid_parameters = []
        plugin_parameters = []
        plugin = False
        for arg in argv:
            if arg.startswith("--"):
                if arg not in valid_actions:
                    plugin = True
                else:
                    plugin = False
            elif arg == default_action:
                plugin = False

            if plugin:
                plugin_parameters.append(arg)
            else:
                valid_parameters.append(arg)
        return valid_parameters + plugin_parameters

    def getParser(self, argv):
        action = self.getAction(argv)
        if not action:
            return self.parser
        else:
            return self.subparsers.choices[action]

    # Parse arguments from config file and command line
    def parse(self, silent=False, parse_config=True):
        argv = self.argv[:]  # Copy command line arguments
        current_parser = self.getParser(argv)
        if silent:  # Don't display messages or quit on unknown parameter
            original_print_message = self.parser._print_message
            original_exit = self.parser.exit

            def silencer(parser, function_name):
                parser.exited = True
                return None
            current_parser.exited = False
            current_parser._print_message = lambda *args, **kwargs: silencer(current_parser, "_print_message")
            current_parser.exit = lambda *args, **kwargs: silencer(current_parser, "exit")

        self.parseCommandline(argv, silent)  # Parse argv
        self.setAttributes()
        if parse_config:
            argv = self.parseConfig(argv)  # Add arguments from config file

        self.parseCommandline(argv, silent)  # Parse argv
        self.setAttributes()

        if not silent:
            if self.fileserver_ip != "*" and self.fileserver_ip not in self.ip_local:
                self.ip_local.append(self.fileserver_ip)

        if silent:  # Restore original functions
            if current_parser.exited and self.action == "main":  # Argument parsing halted, don't start ZeroNet with main action
                self.action = None
            current_parser._print_message = original_print_message
            current_parser.exit = original_exit

        self.loadTrackersFile()

    # Parse command line arguments
    def parseCommandline(self, argv, silent=False):
        # Find out if action is specificed on start
        action = self.getAction(argv)
        if not action:
            argv.append("--end")
            argv.append("main")
            action = "main"
        argv = self.moveUnknownToEnd(argv, action)
        if silent:
            res = self.parser.parse_known_args(argv[1:])
            if res:
                self.arguments = res[0]
            else:
                self.arguments = {}
        else:
            self.arguments = self.parser.parse_args(argv[1:])

    # Parse config file
    def parseConfig(self, argv):
        # Find config file path from parameters
        if "--config_file" in argv:
            self.config_file = argv[argv.index("--config_file") + 1]
        # Load config file
        if os.path.isfile(self.config_file):
            config = configparser.RawConfigParser(allow_no_value=True, strict=False)
            config.read(self.config_file)
            for section in config.sections():
                for key, val in config.items(section):
                    if val == "True":
                        val = None
                    if section != "global":  # If not global prefix key with section
                        key = section + "_" + key

                    if key == "open_browser":  # Prefer config file value over cli argument
                        while "--%s" % key in argv:
                            pos = argv.index("--open_browser")
                            del argv[pos:pos + 2]

                    argv_extend = ["--%s" % key]
                    if val:
                        for line in val.strip().split("\n"):  # Allow multi-line values
                            argv_extend.append(line)
                        if "\n" in val:
                            argv_extend.append("--end")

                    argv = argv[:1] + argv_extend + argv[1:]
        return argv

    # Return command line value of given argument
    def getCmdlineValue(self, key):
        if key not in self.argv:
            return None
        argv_index = self.argv.index(key)
        if argv_index == len(self.argv) - 1:  # last arg, test not specified
            return None

        return self.argv[argv_index + 1]

    # Expose arguments as class attributes
    def setAttributes(self):
        # Set attributes from arguments
        if self.arguments:
            args = vars(self.arguments)
            for key, val in args.items():
                if type(val) is list:
                    val = val[:]
                if key in ("data_dir", "log_dir", "start_dir", "openssl_bin_file", "openssl_lib_file"):
                    if val:
                        val = val.replace("\\", "/")
                setattr(self, key, val)

    def loadPlugins(self):
        from Plugin import PluginManager

        @PluginManager.acceptPlugins
        class ConfigPlugin(object):
            def __init__(self, config):
                self.argv = config.argv
                self.parser = config.parser
                self.subparsers = config.subparsers
                self.test_parser = config.test_parser
                self.getCmdlineValue = config.getCmdlineValue
                self.createArguments()

            def createArguments(self):
                pass

        ConfigPlugin(self)

    def saveValue(self, key, value):
        if not os.path.isfile(self.config_file):
            content = ""
        else:
            content = open(self.config_file).read()
        lines = content.splitlines()

        global_line_i = None
        key_line_i = None
        i = 0
        for line in lines:
            if line.strip() == "[global]":
                global_line_i = i
            if line.startswith(key + " =") or line == key:
                key_line_i = i
            i += 1

        if key_line_i and len(lines) > key_line_i + 1:
            while True:  # Delete previous multiline values
                is_value_line = lines[key_line_i + 1].startswith(" ") or lines[key_line_i + 1].startswith("\t")
                if not is_value_line:
                    break
                del lines[key_line_i + 1]

        if value is None:  # Delete line
            if key_line_i:
                del lines[key_line_i]

        else:  # Add / update
            if type(value) is list:
                value_lines = [""] + [str(line).replace("\n", "").replace("\r", "") for line in value]
            else:
                value_lines = [str(value).replace("\n", "").replace("\r", "")]
            new_line = "%s = %s" % (key, "\n ".join(value_lines))
            if key_line_i:  # Already in the config, change the line
                lines[key_line_i] = new_line
            elif global_line_i is None:  # No global section yet, append to end of file
                lines.append("[global]")
                lines.append(new_line)
            else:  # Has global section, append the line after it
                lines.insert(global_line_i + 1, new_line)

        open(self.config_file, "w").write("\n".join(lines))

    def getServerInfo(self):
        from Plugin import PluginManager
        import main

        info = {
            "platform": sys.platform,
            "fileserver_ip": self.fileserver_ip,
            "fileserver_port": self.fileserver_port,
            "ui_ip": self.ui_ip,
            "ui_port": self.ui_port,
            "version": self.version,
            "rev": self.rev,
            "language": self.language,
            "debug": self.debug,
            "plugins": PluginManager.plugin_manager.plugin_names,

            "log_dir": os.path.abspath(self.log_dir),
            "data_dir": os.path.abspath(self.data_dir),
            "src_dir": os.path.dirname(os.path.abspath(__file__))
        }

        try:
            info["ip_external"] = main.file_server.port_opened
            info["tor_enabled"] = main.file_server.tor_manager.enabled
            info["tor_status"] = main.file_server.tor_manager.status
        except Exception:
            pass

        return info

    def initConsoleLogger(self):
        if self.action == "main":
            format = '[%(asctime)s] %(name)s %(message)s'
        else:
            format = '%(name)s %(message)s'

        if self.console_log_level == "default":
            if self.silent:
                level = logging.ERROR
            elif self.debug:
                level = logging.DEBUG
            else:
                level = logging.INFO
        else:
            level = logging.getLevelName(self.console_log_level)

        console_logger = logging.StreamHandler()
        console_logger.setFormatter(logging.Formatter(format, "%H:%M:%S"))
        console_logger.setLevel(level)
        logging.getLogger('').addHandler(console_logger)

    def initFileLogger(self):
        if self.action == "main":
            log_file_path = "%s/debug.log" % self.log_dir
        else:
            log_file_path = "%s/cmd.log" % self.log_dir

        if self.log_rotate == "off":
            file_logger = logging.FileHandler(log_file_path, "w", "utf-8")
        else:
            when_names = {"weekly": "w", "daily": "d", "hourly": "h"}
            file_logger = logging.handlers.TimedRotatingFileHandler(
                log_file_path, when=when_names[self.log_rotate], interval=1, backupCount=self.log_rotate_backup_count,
                encoding="utf8"
            )

            if os.path.isfile(log_file_path):
                file_logger.doRollover()  # Always start with empty log file
        file_logger.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)-8s %(name)s %(message)s'))
        file_logger.setLevel(logging.getLevelName(self.log_level))
        logging.getLogger('').setLevel(logging.getLevelName(self.log_level))
        logging.getLogger('').addHandler(file_logger)

    def initLogging(self, console_logging=None, file_logging=None):
        if console_logging == None:
            console_logging = self.console_log_level != "off"

        if file_logging == None:
            file_logging = self.log_level != "off"

        # Create necessary files and dirs
        if not os.path.isdir(self.log_dir):
            os.mkdir(self.log_dir)
            try:
                os.chmod(self.log_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            except Exception as err:
                print("Can't change permission of %s: %s" % (self.log_dir, err))

        # Make warning hidden from console
        logging.WARNING = 15  # Don't display warnings if not in debug mode
        logging.addLevelName(15, "WARNING")

        logging.getLogger('').name = "-"  # Remove root prefix

        self.error_logger = ErrorLogHandler()
        self.error_logger.setLevel(logging.getLevelName("ERROR"))
        logging.getLogger('').addHandler(self.error_logger)

        if console_logging:
            self.initConsoleLogger()
        if file_logging:
            self.initFileLogger()


class ErrorLogHandler(logging.StreamHandler):
    def __init__(self):
        self.lines = []
        return super().__init__()

    def emit(self, record):
        self.lines.append([time.time(), record.levelname, self.format(record)])

    def onNewRecord(self, record):
        pass


config = Config(sys.argv)

import argparse
import sys
import os
import locale
import re
import ConfigParser


class Config(object):

    def __init__(self, argv):
        self.version = "0.5.3"
        self.rev = 1988
        self.argv = argv
        self.action = None
        self.config_file = "zeronet.conf"
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

    # Create command line arguments
    def createArguments(self):
        trackers = [
            "zero://boot3rdez4rzn36x.onion:15441",
            "zero://boot.zeronet.io#f36ca555bee6ba216b14d10f38c16f7769ff064e0e37d887603548cc2e64191d:15441",
            "udp://tracker.coppersurfer.tk:6969",
            "udp://tracker.leechers-paradise.org:6969",
            "udp://9.rarbg.com:2710",
            "http://tracker.opentrackr.org:1337/announce",
            "http://explodie.org:6969/announce",
            "http://tracker1.wasabii.com.tw:6969/announce"
        ]
        # Platform specific
        if sys.platform.startswith("win"):
            coffeescript = "type %s | tools\\coffee\\coffee.cmd"
        else:
            coffeescript = None

        try:
            language, enc = locale.getdefaultlocale()
            language = language.split("_")[0]
        except Exception:
            language = "en"

        use_openssl = True

        if repr(1483108852.565) != "1483108852.565":
            fix_float_decimals = True
        else:
            fix_float_decimals = False

        this_file = os.path.abspath(__file__).replace("\\", "/")

        if this_file.endswith("/Contents/Resources/core/src/Config.py"):
            # Running as ZeroNet.app
            if this_file.startswith("/Application") or this_file.startswith("/private") or this_file.startswith(os.path.expanduser("~/Library")):
                # Runnig from non-writeable directory, put data to Application Support
                start_dir = os.path.expanduser("~/Library/Application Support/ZeroNet").decode(sys.getfilesystemencoding())
            else:
                # Running from writeable directory put data next to .app
                start_dir = re.sub("/[^/]+/Contents/Resources/core/src/Config.py", "", this_file).decode(sys.getfilesystemencoding())
            config_file = start_dir + "/zeronet.conf"
            data_dir = start_dir + "/data"
            log_dir = start_dir + "/log"
        elif this_file.endswith("/core/src/Config.py"):
            # Running as exe or source is at Application Support directory, put var files to outside of core dir
            start_dir = this_file.replace("/core/src/Config.py", "").decode(sys.getfilesystemencoding())
            config_file = start_dir + "/zeronet.conf"
            data_dir = start_dir + "/data"
            log_dir = start_dir + "/log"
        else:
            config_file = "zeronet.conf"
            data_dir = "data"
            log_dir = "log"

        ip_local = ["127.0.0.1"]

        # Main
        action = self.subparsers.add_parser("main", help='Start UiServer and FileServer (default)')

        # SiteCreate
        action = self.subparsers.add_parser("siteCreate", help='Create a new site')

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

        # Config parameters
        self.parser.add_argument('--verbose', help='More detailed logging', action='store_true')
        self.parser.add_argument('--debug', help='Debug mode', action='store_true')
        self.parser.add_argument('--debug_socket', help='Debug socket connections', action='store_true')
        self.parser.add_argument('--debug_gevent', help='Debug gevent functions', action='store_true')

        self.parser.add_argument('--batch', help="Batch mode (No interactive input for commands)", action='store_true')

        self.parser.add_argument('--config_file', help='Path of config file', default=config_file, metavar="path")
        self.parser.add_argument('--data_dir', help='Path of data directory', default=data_dir, metavar="path")
        self.parser.add_argument('--log_dir', help='Path of logging directory', default=log_dir, metavar="path")

        self.parser.add_argument('--language', help='Web interface language', default=language, metavar='language')
        self.parser.add_argument('--ui_ip', help='Web interface bind address', default="127.0.0.1", metavar='ip')
        self.parser.add_argument('--ui_port', help='Web interface bind port', default=43110, type=int, metavar='port')
        self.parser.add_argument('--ui_restrict', help='Restrict web access', default=False, metavar='ip', nargs='*')
        self.parser.add_argument('--open_browser', help='Open homepage in web browser automatically',
                                 nargs='?', const="default_browser", metavar='browser_name')
        self.parser.add_argument('--homepage', help='Web interface Homepage', default='1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D',
                                 metavar='address')
        self.parser.add_argument('--updatesite', help='Source code update site', default='1UPDatEDxnvHDo7TXvq6AEBARfNkyfxsp',
                                 metavar='address')
        self.parser.add_argument('--size_limit', help='Default site size limit in MB', default=10, type=int, metavar='size')
        self.parser.add_argument('--connected_limit', help='Max connected peer per site', default=8, type=int, metavar='connected_limit')
        self.parser.add_argument('--workers', help='Download workers per site', default=5, type=int, metavar='workers')

        self.parser.add_argument('--fileserver_ip', help='FileServer bind address', default="*", metavar='ip')
        self.parser.add_argument('--fileserver_port', help='FileServer bind port', default=15441, type=int, metavar='port')
        self.parser.add_argument('--ip_local', help='My local ips', default=ip_local, type=int, metavar='ip', nargs='*')

        self.parser.add_argument('--disable_udp', help='Disable UDP connections', action='store_true')
        self.parser.add_argument('--proxy', help='Socks proxy address', metavar='ip:port')
        self.parser.add_argument('--ip_external', help='Set reported external ip (tested on start if None)', metavar='ip')
        self.parser.add_argument('--trackers', help='Bootstraping torrent trackers', default=trackers, metavar='protocol://address', nargs='*')
        self.parser.add_argument('--trackers_file', help='Load torrent trackers dynamically from a file', default=False, metavar='path')
        self.parser.add_argument('--use_openssl', help='Use OpenSSL liblary for speedup',
                                 type='bool', choices=[True, False], default=use_openssl)
        self.parser.add_argument('--disable_db', help='Disable database updating', action='store_true')
        self.parser.add_argument('--disable_encryption', help='Disable connection encryption', action='store_true')
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
                                 type='bool', choices=[True, False], default=True)
        self.parser.add_argument("--fix_float_decimals", help='Fix content.json modification date float precision on verification',
                                 type='bool', choices=[True, False], default=fix_float_decimals)
        self.parser.add_argument("--db_mode", choices=["speed", "security"], default="speed")

        self.parser.add_argument('--coffeescript_compiler', help='Coffeescript compiler for developing', default=coffeescript,
                                 metavar='executable_path')

        self.parser.add_argument('--tor', help='enable: Use only for Tor peers, always: Use Tor for every connection', choices=["disable", "enable", "always"], default='enable')
        self.parser.add_argument('--tor_controller', help='Tor controller address', metavar='ip:port', default='127.0.0.1:9051')
        self.parser.add_argument('--tor_proxy', help='Tor proxy address', metavar='ip:port', default='127.0.0.1:9050')
        self.parser.add_argument('--tor_password', help='Tor controller password', metavar='password')

        self.parser.add_argument('--version', action='version', version='ZeroNet %s r%s' % (self.version, self.rev))

        return self.parser

    def loadTrackersFile(self):
        self.trackers = []
        for tracker in open(self.trackers_file):
            if "://" in tracker:
                self.trackers.append(tracker.strip())

    # Find arguments specified for current action
    def getActionArguments(self):
        back = {}
        arguments = self.parser._subparsers._group_actions[0].choices[self.action]._actions[1:]  # First is --version
        for argument in arguments:
            back[argument.dest] = getattr(self, argument.dest)
        return back

    # Try to find action from argv
    def getAction(self, argv):
        actions = [action.choices.keys() for action in self.parser._actions if action.dest == "action"][0]  # Valid actions
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

    # Parse arguments from config file and command line
    def parse(self, silent=False, parse_config=True):
        if silent:  # Don't display messages or quit on unknown parameter
            original_print_message = self.parser._print_message
            original_exit = self.parser.exit

            def silencer(parser, function_name):
                parser.exited = True
                return None
            self.parser.exited = False
            self.parser._print_message = lambda *args, **kwargs: silencer(self.parser, "_print_message")
            self.parser.exit = lambda *args, **kwargs: silencer(self.parser, "exit")

        argv = self.argv[:]  # Copy command line arguments
        if parse_config:
            argv = self.parseConfig(argv)  # Add arguments from config file
        self.parseCommandline(argv, silent)  # Parse argv
        self.setAttributes()

        if not silent:
            if self.fileserver_ip != "*" and self.fileserver_ip not in self.ip_local:
                self.ip_local.append(self.fileserver_ip)

        if silent:  # Restore original functions
            if self.parser.exited and self.action == "main":  # Argument parsing halted, don't start ZeroNet with main action
                self.action = None
            self.parser._print_message = original_print_message
            self.parser.exit = original_exit

    # Parse command line arguments
    def parseCommandline(self, argv, silent=False):
        # Find out if action is specificed on start
        action = self.getAction(argv)
        if not action:
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
            config = ConfigParser.ConfigParser(allow_no_value=True)
            config.read(self.config_file)
            for section in config.sections():
                for key, val in config.items(section):
                    if section != "global":  # If not global prefix key with section
                        key = section + "_" + key
                    if val:
                        for line in val.strip().split("\n"):  # Allow multi-line values
                            argv.insert(1, line)
                    argv.insert(1, "--%s" % key)
        return argv

    # Expose arguments as class attributes
    def setAttributes(self):
        # Set attributes from arguments
        if self.arguments:
            args = vars(self.arguments)
            for key, val in args.items():
                setattr(self, key, val)

    def loadPlugins(self):
        from Plugin import PluginManager

        @PluginManager.acceptPlugins
        class ConfigPlugin(object):
            def __init__(self, config):
                self.parser = config.parser
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
            if line.startswith(key + " = "):
                key_line_i = i
            i += 1

        if value is None:  # Delete line
            if key_line_i:
                del lines[key_line_i]
        else:  # Add / update
            new_line = "%s = %s" % (key, str(value).replace("\n", "").replace("\r", ""))
            if key_line_i:  # Already in the config, change the line
                lines[key_line_i] = new_line
            elif global_line_i is None:  # No global section yet, append to end of file
                lines.append("[global]")
                lines.append(new_line)
            else:  # Has global section, append the line after it
                lines.insert(global_line_i + 1, new_line)

        open(self.config_file, "w").write("\n".join(lines))

config = Config(sys.argv)

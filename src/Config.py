import argparse, sys, os, time
import ConfigParser

class Config(object):
	def __init__(self):
		self.version = "0.1.5"
		self.parser = self.createArguments()
		argv = sys.argv[:] # Copy command line arguments
		argv = self.parseConfig(argv) # Add arguments from config file
		self.parseCommandline(argv) # Parse argv
		self.setAttributes()


	def __str__(self):
		return str(self.arguments).replace("Namespace", "Config") # Using argparse str output


	# Create command line arguments
	def createArguments(self):
		# Platform specific
		if sys.platform.startswith("win"):
			upnpc = "tools\\upnpc\\upnpc-static.exe"
			coffeescript = "type %s | tools\\coffee\\coffee.cmd"
		else:
			upnpc = None
			coffeescript = None

		# Create parser
		parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
		subparsers = parser.add_subparsers(title="Action to perform", dest="action")

		# Main
		action = subparsers.add_parser("main", help='Start UiServer and FileServer (default)')

		# SiteCreate
		action = subparsers.add_parser("siteCreate", help='Create a new site')

		# SiteSign
		action = subparsers.add_parser("siteSign", help='Update and sign content.json: address [privatekey]')
		action.add_argument('address', 		help='Site to sign')
		action.add_argument('privatekey',	help='Private key (default: ask on execute)', nargs='?')

		# SitePublish
		action = subparsers.add_parser("sitePublish", help='Publish site to other peers: address')
		action.add_argument('address', 		help='Site to publish')
		action.add_argument('peer_ip',		help='Peer ip to publish (default: random peers ip from tracker)', default=None, nargs='?')
		action.add_argument('peer_port',	help='Peer port to publish (default: random peer port from tracker)', default=15441, nargs='?')

		# SiteVerify
		action = subparsers.add_parser("siteVerify", help='Verify site files using sha512: address')
		action.add_argument('address', 		help='Site to verify')


		# Config parameters
		parser.add_argument('--debug', 			help='Debug mode', action='store_true')
		parser.add_argument('--debug_socket', 	help='Debug socket connections', action='store_true')

		parser.add_argument('--ui_ip', 			help='Web interface bind address', default="127.0.0.1", metavar='ip')
		parser.add_argument('--ui_port', 		help='Web interface bind port', default=43110, type=int, metavar='port')
		parser.add_argument('--ui_restrict',	help='Restrict web access', default=False, metavar='ip')
		parser.add_argument('--homepage',		help='Web interface Homepage', default='1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr', metavar='address')

		parser.add_argument('--fileserver_ip', 	help='FileServer bind address', default="*", metavar='ip')
		parser.add_argument('--fileserver_port',help='FileServer bind port', default=15441, type=int, metavar='port')

		parser.add_argument('--ip_external',	help='External ip (tested on start if None)', metavar='ip')
		parser.add_argument('--upnpc',			help='MiniUPnP binary for open port on router', default=upnpc, metavar='executable_path')

		parser.add_argument('--coffeescript_compiler',	help='Coffeescript compiler for developing', default=coffeescript, metavar='executable_path')

		parser.add_argument('--version', 	action='version', version='ZeroNet %s' % self.version)

		return parser


	# Find arguments specificed for current action
	def getActionArguments(self):
		back = {}
		arguments = self.parser._subparsers._group_actions[0].choices[self.action]._actions[1:] # First is --version
		for argument in arguments:
			back[argument.dest] = getattr(self, argument.dest)
		return back



	# Try to find action from sys.argv
	def getAction(self, argv):
		actions = [action.choices.keys() for action in self.parser._actions if action.dest == "action"][0] # Valid actions
		found_action = False
		for action in actions: # See if any in sys.argv
			if action in argv:
				found_action = action
				break
		return found_action


	# Parse command line arguments
	def parseCommandline(self, argv):
		# Find out if action is specificed on start
		action = self.getAction(argv)
		if len(argv) == 1 or not action: # If no action specificed set the main action
			argv.append("main")
		if "zeronet.py" in argv[0]:
			self.arguments = self.parser.parse_args(argv[1:])
		else: # Silent errors if not started with zeronet.py
			self.arguments = self.parser.parse_args(argv[1:])


	# Parse config file
	def parseConfig(self, argv):
		if os.path.isfile("zeronet.conf"):
			config = ConfigParser.ConfigParser(allow_no_value=True)
			config.read('zeronet.conf')
			for section in config.sections():
				for key, val in config.items(section):
					if section != "global": # If not global prefix key with section
						key = section+"_"+key
					if val: argv.insert(1, val)
					argv.insert(1, "--%s" % key)
		return argv



	# Expose arguments as class attributes
	def setAttributes(self):
		# Set attributes from arguments
		args = vars(self.arguments)
		for key, val in args.items():
			setattr(self, key, val)


config = Config()

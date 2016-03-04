import sys

if sys.platform == 'win32':
	import TrayiconPlugin
elif sys.platform == 'darwin':
	import TrayiconOSXPlugin

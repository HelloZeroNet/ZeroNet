import logging, os, sys, time
import threading
from Config import config

if config.debug: # Only load pyfilesytem if using debug mode
	try:
		from fs.osfs import OSFS 
		pyfilesystem = OSFS("src")
		pyfilesystem_plugins = OSFS("plugins")
	except Exception, err:
		logging.debug("%s: For autoreload please download pyfilesystem (https://code.google.com/p/pyfilesystem/)" % err)
		pyfilesystem = False
else:
	pyfilesystem = False

class DebugReloader:
	def __init__ (self, callback, directory = "/"):
		self.last_chaged = 0
		if pyfilesystem:
			self.directory = directory
			self.callback = callback
			logging.debug("Adding autoreload: %s, cb: %s" % (directory, callback))
			thread = threading.Thread(target=self.addWatcher)
			thread.daemon = True
			thread.start()


	def addWatcher(self, recursive=True):
		try:
			time.sleep(1) # Wait for .pyc compiles
			pyfilesystem.add_watcher(self.changed, path=self.directory, events=None, recursive=recursive)
			pyfilesystem_plugins.add_watcher(self.changed, path=self.directory, events=None, recursive=recursive)
		except Exception, err:
			print "File system watcher failed: %s (on linux pyinotify not gevent compatible yet :( )" % err


	def changed(self, evt):
		if not evt.path or evt.path.endswith("pyc") or time.time()-self.last_chaged < 1: return False # Ignore *.pyc changes and no reload within 1 sec
		#logging.debug("Changed: %s" % evt)
		time.sleep(0.1) # Wait for lock release
		self.callback()
		self.last_chaged = time.time()

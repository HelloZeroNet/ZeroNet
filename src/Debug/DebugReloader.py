import logging, os, sys, time
import threading

try:
	from fs.osfs import OSFS 
	pyfilesystem = OSFS("src")
except Exception, err:
	logging.info("%s: For autoreload please download pyfilesystem (https://code.google.com/p/pyfilesystem/)" % err)
	pyfilesystem = False


class DebugReloader:
	def __init__ (self, callback, directory = "/"):
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
		except Exception, err:
			print "File system watcher failed: %s (on linux pyinotify not gevent compatible yet :( )" % err


	def changed(self, evt):
		if not evt.path or evt.path.endswith("pyc"): return False # Ignore *.pyc changes
		#logging.debug("Changed: %s" % evt)
		time.sleep(0.1) # Wait for lock release
		self.callback()

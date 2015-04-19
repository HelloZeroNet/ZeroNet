import gevent, sys, logging
from Config import config

last_error = None

# Store last error, ignore notify, allow manual error logging
def handleError(*args):
	global last_error
	if not args: # Manual called
		args = sys.exc_info()
		silent = True
	else:
		silent = False
	if args[0].__name__ != "Notify": last_error = args
	if not silent and args[0].__name__ != "Notify": 
		logging.exception("Unhandled exception")
		sys.__excepthook__(*args)


# Ignore notify errors
def handleErrorNotify(*args):
	if args[0].__name__ != "Notify": 
		logging.exception("Unhandled exception")
		sys.__excepthook__(*args)


OriginalGreenlet = gevent.Greenlet
class ErrorhookedGreenlet(OriginalGreenlet):
	def _report_error(self, exc_info):
		sys.excepthook(exc_info[0], exc_info[1], exc_info[2])

if config.debug:
	sys.excepthook = handleError
else:
	sys.excepthook = handleErrorNotify

gevent.Greenlet = gevent.greenlet.Greenlet = ErrorhookedGreenlet
reload(gevent)

if __name__ == "__main__":
	import time
	from gevent import monkey; monkey.patch_all(thread=False, ssl=False)
	import Debug
	def sleeper():
		print "started"
		time.sleep(3)
		print "stopped"
	thread1 = gevent.spawn(sleeper)
	thread2 = gevent.spawn(sleeper)
	time.sleep(1)
	print "killing..."
	thread1.throw(Exception("Hello"))
	thread2.throw(Debug.Notify("Throw"))
	print "killed"


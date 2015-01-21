import gevent, sys

last_error = None
def handleError(*args):
	global last_error
	if not args: # Called explicitly
		args = sys.exc_info()
		silent = True
	else:
		silent = False
	print "Error catched", args
	last_error = args
	if not silent and args[0].__name__ != "Notify": sys.__excepthook__(*args)

OriginalGreenlet = gevent.Greenlet
class ErrorhookedGreenlet(OriginalGreenlet):
	def _report_error(self, exc_info):
		handleError(exc_info[0], exc_info[1], exc_info[2])

sys.excepthook = handleError
gevent.Greenlet = gevent.greenlet.Greenlet = ErrorhookedGreenlet
reload(gevent)
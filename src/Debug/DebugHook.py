import sys
import logging

import gevent
import gevent.hub

from Config import config

last_error = None

def shutdown():
    try:
        gevent.spawn(sys.modules["main"].file_server.stop)
        gevent.spawn(sys.modules["main"].ui_server.stop)
    except Exception, err:
        print "Proper shutdown error: %s" % err
        sys.exit(0)

# Store last error, ignore notify, allow manual error logging
def handleError(*args):
    global last_error
    if not args:  # Manual called
        args = sys.exc_info()
        silent = True
    else:
        silent = False
    if args[0].__name__ != "Notify":
        last_error = args
    if args[0].__name__ == "KeyboardInterrupt":
        shutdown()
    if not silent and args[0].__name__ != "Notify":
        logging.exception("Unhandled exception")
        sys.__excepthook__(*args)


# Ignore notify errors
def handleErrorNotify(*args):
    if args[0].__name__ == "KeyboardInterrupt":
        shutdown()
    if args[0].__name__ != "Notify":
        logging.exception("Unhandled exception")
        sys.__excepthook__(*args)


if config.debug:  # Keep last error for /Debug
    sys.excepthook = handleError
else:
    sys.excepthook = handleErrorNotify


# Override default error handler to allow silent killing / custom logging
gevent.hub.Hub._original_handle_error = gevent.hub.Hub.handle_error

def handleGreenletError(self, context, type, value, tb):
    if isinstance(value, str):
        # Cython can raise errors where the value is a plain string
        # e.g., AttributeError, "_semaphore.Semaphore has no attr", <traceback>
        value = type(value)
    if not issubclass(type, self.NOT_ERROR):
        sys.excepthook(type, value, tb)

gevent.hub.Hub.handle_error = handleGreenletError

if __name__ == "__main__":
    import time
    from gevent import monkey
    monkey.patch_all(thread=False, ssl=False)
    import Debug

    def sleeper(num):
        print "started", num
        time.sleep(3)
        raise Exception("Error")
        print "stopped", num
    thread1 = gevent.spawn(sleeper, 1)
    thread2 = gevent.spawn(sleeper, 2)
    time.sleep(1)
    print "killing..."
    thread1.kill(exception=Debug.Notify("Worker stopped"))
    #thread2.throw(Debug.Notify("Throw"))
    print "killed"
    gevent.joinall([thread1,thread2])

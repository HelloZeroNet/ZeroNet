import sys
import os
from Config import config


# Non fatal exception
class Notify(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


def formatException(err=None, format="text"):
    import traceback
    if type(err) == Notify:
        return err
    elif type(err) == tuple and err[0] is not None:  # Passed trackeback info
        exc_type, exc_obj, exc_tb = err
        err = None
    else:  # No trackeback info passed, get latest
        exc_type, exc_obj, exc_tb = sys.exc_info()

    if not err:
        err = exc_obj.message
    tb = []
    for frame in traceback.extract_tb(exc_tb):
        path, line, function, text = frame
        file = os.path.split(path)[1]
        tb.append("%s line %s" % (file, line))
    if format == "html":
        return "%s: %s<br><small>%s</small>" % (exc_type.__name__, err, " > ".join(tb))
    else:
        return "%s: %s in %s" % (exc_type.__name__, err, " > ".join(tb))


def formatStack():
    import inspect
    back = []
    for stack in inspect.stack():
        frame, path, line, function, source, index = stack
        file = os.path.split(path)[1]
        back.append("%s line %s" % (file, line))
    return " > ".join(back)


# Test if gevent eventloop blocks
if config.debug_gevent:
    import logging
    import gevent
    import time

    def testBlock():
        logging.debug("Gevent block checker started")
        last_time = time.time()
        while 1:
            time.sleep(1)
            if time.time() - last_time > 1.1:
                logging.debug("Gevent block detected: %s" % (time.time() - last_time - 1))
            last_time = time.time()
    gevent.spawn(testBlock)


if __name__ == "__main__":
    try:
        print 1 / 0
    except Exception, err:
        print type(err).__name__
        print "1/0 error: %s" % formatException(err)

    def loadJson():
        json.loads("Errr")

    import json
    try:
        loadJson()
    except Exception, err:
        print err
        print "Json load error: %s" % formatException(err)

    try:
        raise Notify("nothing...")
    except Exception, err:
        print "Notify: %s" % formatException(err)

    loadJson()

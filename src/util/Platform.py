import sys
import logging


def setMaxfilesopened(limit):
    try:
        if sys.platform == "win32":
            import win32file
            maxstdio = win32file._getmaxstdio()
            if maxstdio < limit:
                logging.debug("Current maxstdio: %s, changing to %s..." % (maxstdio, limit))
                win32file._setmaxstdio(limit)
                return True
        else:
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            if soft < limit:
                logging.debug("Current RLIMIT_NOFILE: %s (max: %s), changing to %s..." % (soft, hard, limit))
                resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))
                return True

    except Exception, err:
        logging.error("Failed to modify max files open limit: %s" % err)
        return False

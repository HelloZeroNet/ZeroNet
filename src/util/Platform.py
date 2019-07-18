import sys
import logging


def setMaxfilesopened(limit):
    try:
        if sys.platform == "win32":
            import ctypes
            maxstdio = ctypes.cdll.msvcr100._getmaxstdio()
            if maxstdio < limit:
                logging.debug("Current maxstdio: %s, changing to %s..." % (maxstdio, limit))
                ctypes.cdll.msvcr100._setmaxstdio(limit)
                return True
        else:
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            if soft < limit:
                logging.debug("Current RLIMIT_NOFILE: %s (max: %s), changing to %s..." % (soft, hard, limit))
                resource.setrlimit(resource.RLIMIT_NOFILE, (limit, hard))
                return True

    except Exception as err:
        logging.error("Failed to modify max files open limit: %s" % err)
        return False

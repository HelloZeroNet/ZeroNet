import sys
import logging


def setMaxfilesopened(limit):
    try:
        if sys.platform == "win32":
            import ctypes
            dll = None
            last_err = None
            for dll_name in ["msvcr100", "msvcr110", "msvcr120"]:
                try:
                    dll = getattr(ctypes.cdll, dll_name)
                    break
                except OSError as err:
                    last_err = err

            if not dll:
                raise last_err

            maxstdio = dll._getmaxstdio()
            if maxstdio < limit:
                logging.debug("%s: Current maxstdio: %s, changing to %s..." % (dll, maxstdio, limit))
                dll._setmaxstdio(limit)
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

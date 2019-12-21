import time
import logging

import gevent.lock

from Debug import Debug


class DebugLock:
    def __init__(self, log_after=0.01, name="Lock"):
        self.name = name
        self.log_after = log_after
        self.lock = gevent.lock.Semaphore(1)
        self.release = self.lock.release

    def acquire(self, *args, **kwargs):
        s = time.time()
        res = self.lock.acquire(*args, **kwargs)
        time_taken = time.time() - s
        if time_taken >= self.log_after:
            logging.debug("%s: Waited %.3fs after called by %s" %
                (self.name, time_taken, Debug.formatStack())
            )
        return res

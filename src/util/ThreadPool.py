import gevent.threadpool
import gevent._threading
import threading


class ThreadPool:
    def __init__(self, max_size, name=None):
        self.setMaxSize(max_size)
        if name:
            self.name = name
        else:
            self.name = "ThreadPool#%s" % id(self)

    def setMaxSize(self, max_size):
        self.max_size = max_size
        if max_size > 0:
            self.pool = gevent.threadpool.ThreadPool(max_size)
        else:
            self.pool = None

    def wrap(self, func):
        if self.pool is None:
            return func

        def wrapper(*args, **kwargs):
            res = self.pool.apply(func, args, kwargs)
            return res

        return wrapper


main_thread_id = threading.current_thread().ident
lock_pool = gevent.threadpool.ThreadPool(10)


class Lock:
    def __init__(self):
        self.lock = gevent._threading.Lock()
        self.locked = self.lock.locked
        self.release = self.lock.release

    def acquire(self, *args, **kwargs):
        if self.locked() and threading.current_thread().ident == main_thread_id:
            return lock_pool.apply(self.lock.acquire, args, kwargs)
        else:
            return self.lock.acquire(*args, **kwargs)

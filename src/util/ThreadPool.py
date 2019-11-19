import gevent.threadpool


class ThreadPool:
    def __init__(self, max_size):
        self.setMaxSize(max_size)

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
            return self.pool.apply(func, args, kwargs)

        return wrapper

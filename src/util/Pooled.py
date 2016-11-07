import gevent.pool


class Pooled(object):
    def __init__(self, size=100):
        self.pool = gevent.pool.Pool(size)
        self.pooler_running = False
        self.queue = []
        self.func = None

    def waiter(self, evt, args, kwargs):
        res = self.func(*args, **kwargs)
        if type(res) == gevent.event.AsyncResult:
            evt.set(res.get())
        else:
            evt.set(res)

    def pooler(self):
        while self.queue:
            evt, args, kwargs = self.queue.pop(0)
            self.pool.spawn(self.waiter, evt, args, kwargs)
        self.pooler_running = False

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            evt = gevent.event.AsyncResult()
            self.queue.append((evt, args, kwargs))
            if not self.pooler_running:
                self.pooler_running = True
                gevent.spawn(self.pooler)
            return evt
        wrapper.func_name = func.func_name
        self.func = func

        return wrapper

if __name__ == "__main__":
    import gevent
    import gevent.pool
    import gevent.queue
    import gevent.event
    import gevent.monkey
    import time

    gevent.monkey.patch_all()

    def addTask(inner_path):
        evt = gevent.event.AsyncResult()
        gevent.spawn_later(1, lambda: evt.set(True))
        return evt

    def needFile(inner_path):
        return addTask(inner_path)

    @Pooled(10)
    def pooledNeedFile(inner_path):
        return needFile(inner_path)

    threads = []
    for i in range(100):
        threads.append(pooledNeedFile(i))

    s = time.time()
    gevent.joinall(threads)  # Should take 10 second
    print time.time() - s

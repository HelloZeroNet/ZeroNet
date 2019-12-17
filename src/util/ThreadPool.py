import threading
import time

import gevent
import gevent.monkey
import gevent.threadpool
import gevent._threading


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


lock_pool = gevent.threadpool.ThreadPool(50)
main_thread_id = threading.current_thread().ident


def isMainThread():
    return threading.current_thread().ident == main_thread_id


class Lock:
    def __init__(self):
        self.lock = gevent._threading.Lock()
        self.locked = self.lock.locked
        self.release = self.lock.release

    def acquire(self, *args, **kwargs):
        if self.locked() and isMainThread():
            # Start in new thread to avoid blocking gevent loop
            return lock_pool.apply(self.lock.acquire, args, kwargs)
        else:
            return self.lock.acquire(*args, **kwargs)

    def __del__(self):
        while self.locked():
            self.release()


class Event:
    def __init__(self):
        self.get_lock = Lock()
        self.res = None
        self.get_lock.acquire(False)
        self.done = False

    def set(self, res):
        if self.done:
            raise Exception("Event already has value")
        self.res = res
        self.get_lock.release()
        self.done = True

    def get(self):
        if not self.done:
            self.get_lock.acquire(True)
        if self.get_lock.locked():
            self.get_lock.release()
        back = self.res
        return back

    def __del__(self):
        self.res = None
        while self.get_lock.locked():
            self.get_lock.release()


# Execute function calls in main loop from other threads
class MainLoopCaller():
    def __init__(self):
        self.queue_call = gevent._threading.Queue()

        self.pool = gevent.threadpool.ThreadPool(1)
        self.num_direct = 0

    def caller(self, func, args, kwargs, event_done):
        try:
            res = func(*args, **kwargs)
            event_done.set((True, res))
        except Exception as err:
            event_done.set((False, err))

    def start(self):
        gevent.spawn(self.run)
        time.sleep(0.001)

    def run(self):
        while 1:
            if self.queue_call.qsize() == 0:  # Get queue in new thread to avoid gevent blocking
                func, args, kwargs, event_done = self.pool.apply(self.queue_call.get)
            else:
                func, args, kwargs, event_done = self.queue_call.get()
            gevent.spawn(self.caller, func, args, kwargs, event_done)
            del func, args, kwargs, event_done

    def call(self, func, *args, **kwargs):
        if threading.current_thread().ident == main_thread_id:
            return func(*args, **kwargs)
        else:
            event_done = Event()
            self.queue_call.put((func, args, kwargs, event_done))
            success, res = event_done.get()
            del event_done
            self.queue_call.task_done()
            if success:
                return res
            else:
                raise res
main_loop = MainLoopCaller()
main_loop.start()
patchSleep()

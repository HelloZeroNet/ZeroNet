import gevent
import time
from gevent.event import AsyncResult


class Noparallel(object):  # Only allow function running once in same time

    def __init__(self, blocking=True, ignore_args=False, ignore_class=False, queue=False):
        self.threads = {}
        self.blocking = blocking  # Blocking: Acts like normal function else thread returned
        self.queue = queue
        self.queued = False
        self.ignore_args = ignore_args
        self.ignore_class = ignore_class

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            if self.ignore_class:
                key = func  # Unique key only by function and class object
            elif self.ignore_args:
                key = (func, args[0])  # Unique key only by function and class object
            else:
                key = (func, tuple(args), str(kwargs))  # Unique key for function including parameters
            if key in self.threads:  # Thread already running (if using blocking mode)
                if self.queue:
                    self.queued = True
                thread = self.threads[key]
                if self.blocking:
                    if self.queued:
                        res = thread.get()  # Blocking until its finished
                        if key in self.threads:
                            return self.threads[key].get()  # Queue finished since started running
                        self.queued = False
                        return wrapper(*args, **kwargs)  # Run again after the end
                    else:
                        return thread.get()  # Return the value

                else:  # No blocking
                    if thread.ready():  # Its finished, create a new
                        thread = gevent.spawn(func, *args, **kwargs)
                        self.threads[key] = thread
                        return thread
                    else:  # Still running
                        return thread
            else:  # Thread not running
                if self.blocking:  # Wait for finish
                    asyncres = AsyncResult()
                    self.threads[key] = asyncres
                    try:
                        res = func(*args, **kwargs)
                        asyncres.set(res)
                        self.cleanup(key, asyncres)
                        return res
                    except Exception as err:
                        asyncres.set_exception(err)
                        self.cleanup(key, asyncres)
                        raise(err)
                else:  # No blocking just return the thread
                    thread = gevent.spawn(func, *args, **kwargs)  # Spawning new thread
                    thread.link(lambda thread: self.cleanup(key, thread))
                    self.threads[key] = thread
                    return thread
        wrapper.__name__ = func.__name__

        return wrapper

    # Cleanup finished threads
    def cleanup(self, key, thread):
        if key in self.threads:
            del(self.threads[key])


if __name__ == "__main__":


    class Test():

        @Noparallel()
        def count(self, num=5):
            for i in range(num):
                print(self, i)
                time.sleep(1)
            return "%s return:%s" % (self, i)

    class TestNoblock():

        @Noparallel(blocking=False)
        def count(self, num=5):
            for i in range(num):
                print(self, i)
                time.sleep(1)
            return "%s return:%s" % (self, i)

    def testBlocking():
        test = Test()
        test2 = Test()
        print("Counting...")
        print("Creating class1/thread1")
        thread1 = gevent.spawn(test.count)
        print("Creating class1/thread2 (ignored)")
        thread2 = gevent.spawn(test.count)
        print("Creating class2/thread3")
        thread3 = gevent.spawn(test2.count)

        print("Joining class1/thread1")
        thread1.join()
        print("Joining class1/thread2")
        thread2.join()
        print("Joining class2/thread3")
        thread3.join()

        print("Creating class1/thread4 (its finished, allowed again)")
        thread4 = gevent.spawn(test.count)
        print("Joining thread4")
        thread4.join()

        print(thread1.value, thread2.value, thread3.value, thread4.value)
        print("Done.")

    def testNoblocking():
        test = TestNoblock()
        test2 = TestNoblock()
        print("Creating class1/thread1")
        thread1 = test.count()
        print("Creating class1/thread2 (ignored)")
        thread2 = test.count()
        print("Creating class2/thread3")
        thread3 = test2.count()
        print("Joining class1/thread1")
        thread1.join()
        print("Joining class1/thread2")
        thread2.join()
        print("Joining class2/thread3")
        thread3.join()

        print("Creating class1/thread4 (its finished, allowed again)")
        thread4 = test.count()
        print("Joining thread4")
        thread4.join()

        print(thread1.value, thread2.value, thread3.value, thread4.value)
        print("Done.")

    def testBenchmark():
        import time

        def printThreadNum():
            import gc
            from greenlet import greenlet
            objs = [obj for obj in gc.get_objects() if isinstance(obj, greenlet)]
            print("Greenlets: %s" % len(objs))

        printThreadNum()
        test = TestNoblock()
        s = time.time()
        for i in range(3):
            gevent.spawn(test.count, i + 1)
        print("Created in %.3fs" % (time.time() - s))
        printThreadNum()
        time.sleep(5)

    def testException():
        import time
        @Noparallel(blocking=True, queue=True)
        def count(self, num=5):
            s = time.time()
            # raise Exception("err")
            for i in range(num):
                print(self, i)
                time.sleep(1)
            return "%s return:%s" % (s, i)
        def caller():
            try:
                print("Ret:", count(5))
            except Exception as err:
                print("Raised:", repr(err))

        gevent.joinall([
            gevent.spawn(caller),
            gevent.spawn(caller),
            gevent.spawn(caller),
            gevent.spawn(caller)
        ])


    from gevent import monkey
    monkey.patch_all()

    testException()

    """
    testBenchmark()
    print("Testing blocking mode...")
    testBlocking()
    print("Testing noblocking mode...")
    testNoblocking()
    """

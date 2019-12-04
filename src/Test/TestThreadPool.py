import time

import gevent

from util import ThreadPool


class TestThreadPool:
    def testExecutionOrder(self):
        pool = ThreadPool.ThreadPool(4)

        events = []

        @pool.wrap
        def blocker():
            events.append("S")
            out = 0
            for i in range(10000000):
                if i == 1000000:
                    events.append("M")
                out += 1
            events.append("D")
            return out

        threads = []
        for i in range(4):
            threads.append(gevent.spawn(blocker))
        gevent.joinall(threads)

        assert events == ["S"] * 4 + ["M"] * 4 + ["D"] * 4

        res = blocker()
        assert res == 10000000

    def testLockBlockingSameThread(self):
        from gevent.lock import Semaphore

        lock = Semaphore()

        s = time.time()

        def unlocker():
            time.sleep(1)
            lock.release()

        gevent.spawn(unlocker)
        lock.acquire(True)
        lock.acquire(True, timeout=2)

        unlock_taken = time.time() - s

        assert 1.0 < unlock_taken < 1.5

    def testLockBlockingDifferentThread(self):
        lock = ThreadPool.Lock()

        s = time.time()

        def locker():
            lock.acquire(True)
            time.sleep(1)
            lock.release()

        pool = gevent.threadpool.ThreadPool(10)
        pool.spawn(locker)
        threads = [
            pool.spawn(locker),
        ]
        time.sleep(0.1)

        lock.acquire(True, 5.0)

        unlock_taken = time.time() - s

        assert 2.0 < unlock_taken < 2.5

        gevent.joinall(threads)

import time
import threading

import gevent
import pytest

from util import ThreadPool


class TestThreadPool:
    def testExecutionOrder(self):
        with ThreadPool.ThreadPool(4) as pool:
            events = []

            @pool.wrap
            def blocker():
                events.append("S")
                out = 0
                for i in range(10000000):
                    if i == 3000000:
                        events.append("M")
                    out += 1
                events.append("D")
                return out

            threads = []
            for i in range(3):
                threads.append(gevent.spawn(blocker))
            gevent.joinall(threads)

            assert events == ["S"] * 3 + ["M"] * 3 + ["D"] * 3

            res = blocker()
            assert res == 10000000

    def testLockBlockingSameThread(self):
        lock = ThreadPool.Lock()

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

        def locker():
            lock.acquire(True)
            time.sleep(0.5)
            lock.release()

        with ThreadPool.ThreadPool(10) as pool:
            threads = [
                pool.spawn(locker),
                pool.spawn(locker),
                gevent.spawn(locker),
                pool.spawn(locker)
            ]
            time.sleep(0.1)

            s = time.time()

            lock.acquire(True, 5.0)

            unlock_taken = time.time() - s

            assert 1.8 < unlock_taken < 2.2

            gevent.joinall(threads)

    def testMainLoopCallerThreadId(self):
        main_thread_id = threading.current_thread().ident
        with ThreadPool.ThreadPool(5) as pool:
            def getThreadId(*args, **kwargs):
                return threading.current_thread().ident

            t = pool.spawn(getThreadId)
            assert t.get() != main_thread_id

            t = pool.spawn(lambda: ThreadPool.main_loop.call(getThreadId))
            assert t.get() == main_thread_id

    def testMainLoopCallerGeventSpawn(self):
        main_thread_id = threading.current_thread().ident
        with ThreadPool.ThreadPool(5) as pool:
            def waiter():
                time.sleep(1)
                return threading.current_thread().ident

            def geventSpawner():
                event = ThreadPool.main_loop.call(gevent.spawn, waiter)

                with pytest.raises(Exception) as greenlet_err:
                    event.get()
                assert str(greenlet_err.value) == "cannot switch to a different thread"

                waiter_thread_id = ThreadPool.main_loop.call(event.get)
                return waiter_thread_id

            s = time.time()
            waiter_thread_id = pool.apply(geventSpawner)
            assert main_thread_id == waiter_thread_id
            time_taken = time.time() - s
            assert 0.9 < time_taken < 1.2

    def testEvent(self):
        with ThreadPool.ThreadPool(5) as pool:
            event = ThreadPool.Event()

            def setter():
                time.sleep(1)
                event.set("done!")

            def getter():
                return event.get()

            pool.spawn(setter)
            t_gevent = gevent.spawn(getter)
            t_pool = pool.spawn(getter)
            s = time.time()
            assert event.get() == "done!"
            time_taken = time.time() - s
            gevent.joinall([t_gevent, t_pool])

            assert t_gevent.get() == "done!"
            assert t_pool.get() == "done!"

            assert 0.9 < time_taken < 1.2

            with pytest.raises(Exception) as err:
                event.set("another result")

            assert "Event already has value" in str(err.value)

    def testMemoryLeak(self):
        import gc
        thread_objs_before = [id(obj) for obj in gc.get_objects() if "threadpool" in str(type(obj))]

        def worker():
            time.sleep(0.1)
            return "ok"

        def poolTest():
            with ThreadPool.ThreadPool(5) as pool:
                for i in range(20):
                    pool.spawn(worker)

        for i in range(5):
            poolTest()
            new_thread_objs = [obj for obj in gc.get_objects() if "threadpool" in str(type(obj)) and id(obj) not in thread_objs_before]
            #print("New objs:", new_thread_objs, "run:", num_run)

        # Make sure no threadpool object left behind
        assert not new_thread_objs

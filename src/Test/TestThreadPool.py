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
            for i in range(1000000):
                out += 1
            events.append("D")
            return out

        threads = []
        for i in range(4):
            threads.append(gevent.spawn(blocker))
        gevent.joinall(threads)

        assert events == ["S"] * 4 + ["D"] * 4, events

        res = blocker()
        assert res == 1000000

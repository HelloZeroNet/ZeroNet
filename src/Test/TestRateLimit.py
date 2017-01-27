import time

import gevent

from util import RateLimit


# Time is around limit +/- 0.05 sec
def around(t, limit):
    return t >= limit - 0.05 and t <= limit + 0.05


class ExampleClass(object):
    def __init__(self):
        self.counted = 0
        self.last_called = None

    def count(self, back="counted"):
        self.counted += 1
        self.last_called = back
        return back


class TestRateLimit:
    def testCall(self):
        obj1 = ExampleClass()
        obj2 = ExampleClass()

        s = time.time()
        assert RateLimit.call("counting", allowed_again=0.1, func=obj1.count) == "counted"
        assert around(time.time() - s, 0.0)  # First allow to call instantly
        assert obj1.counted == 1

        # Call again
        assert not RateLimit.isAllowed("counting", 0.1)
        assert RateLimit.isAllowed("something else", 0.1)
        assert RateLimit.call("counting", allowed_again=0.1, func=obj1.count) == "counted"
        assert around(time.time() - s, 0.1)  # Delays second call within interval
        assert obj1.counted == 2

        # Call 3 times async
        s = time.time()
        assert obj2.counted == 0
        threads = [
            gevent.spawn(lambda: RateLimit.call("counting", allowed_again=0.1, func=obj2.count)),  # Instant
            gevent.spawn(lambda: RateLimit.call("counting", allowed_again=0.1, func=obj2.count)),  # 0.1s delay
            gevent.spawn(lambda: RateLimit.call("counting", allowed_again=0.1, func=obj2.count))   # 0.2s delay
        ]
        gevent.joinall(threads)
        assert [thread.value for thread in threads] == ["counted", "counted", "counted"]
        assert around(time.time() - s, 0.2)

        # No queue = instant again
        s = time.time()
        assert RateLimit.isAllowed("counting", 0.1)
        assert RateLimit.call("counting", allowed_again=0.1, func=obj2.count) == "counted"
        assert around(time.time() - s, 0.0)

        assert obj2.counted == 4

    def testCallAsync(self):
        obj1 = ExampleClass()
        obj2 = ExampleClass()

        s = time.time()
        RateLimit.callAsync("counting async", allowed_again=0.1, func=obj1.count, back="call #1").join()
        assert obj1.counted == 1  # First instant
        assert around(time.time() - s, 0.0)

        # After that the calls delayed
        s = time.time()
        t1 = RateLimit.callAsync("counting async", allowed_again=0.1, func=obj1.count, back="call #2")  # Dumped by the next call
        time.sleep(0.03)
        t2 = RateLimit.callAsync("counting async", allowed_again=0.1, func=obj1.count, back="call #3")  # Dumped by the next call
        time.sleep(0.03)
        t3 = RateLimit.callAsync("counting async", allowed_again=0.1, func=obj1.count, back="call #4")  # Will be called
        assert obj1.counted == 1  # Delay still in progress: Not called yet
        t3.join()
        assert t3.value == "call #4"
        assert around(time.time() - s, 0.1)

        # Only the last one called
        assert obj1.counted == 2
        assert obj1.last_called == "call #4"

        # Allowed again instantly
        assert RateLimit.isAllowed("counting async", 0.1)
        s = time.time()
        RateLimit.callAsync("counting async", allowed_again=0.1, func=obj1.count, back="call #5").join()
        assert obj1.counted == 3
        assert around(time.time() - s, 0.0)
        assert not RateLimit.isAllowed("counting async", 0.1)
        time.sleep(0.11)
        assert RateLimit.isAllowed("counting async", 0.1)

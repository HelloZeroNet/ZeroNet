import time

import gevent
import pytest

import util


class ExampleClass(object):
    def __init__(self):
        self.counted = 0

    @util.Noparallel()
    def countBlocking(self, num=5):
        for i in range(1, num + 1):
            time.sleep(0.01)
            self.counted += 1
        return "counted:%s" % i

    @util.Noparallel(queue=True, ignore_class=True)
    def countQueue(self, num=5):
        for i in range(1, num + 1):
            time.sleep(0.1)
            self.counted += 1
        return "counted:%s" % i

    @util.Noparallel(blocking=False)
    def countNoblocking(self, num=5):
        for i in range(1, num + 1):
            time.sleep(0.01)
            self.counted += 1
        return "counted:%s" % i


class TestNoparallel:
    def testBlocking(self):
        obj1 = ExampleClass()
        obj2 = ExampleClass()

        # Dont allow to call again until its running and wait until its running
        threads = [
            gevent.spawn(obj1.countBlocking),
            gevent.spawn(obj1.countBlocking),
            gevent.spawn(obj1.countBlocking),
            gevent.spawn(obj2.countBlocking)
        ]
        assert obj2.countBlocking() == "counted:5"  # The call is ignored as obj2.countBlocking already counting, but block until its finishes
        gevent.joinall(threads)
        assert [thread.value for thread in threads] == ["counted:5", "counted:5", "counted:5", "counted:5"]  # Check the return value for every call
        obj2.countBlocking()  # Allow to call again as obj2.countBlocking finished

        assert obj1.counted == 5
        assert obj2.counted == 10

    def testNoblocking(self):
        obj1 = ExampleClass()
        obj2 = ExampleClass()

        thread1 = obj1.countNoblocking()
        thread2 = obj1.countNoblocking()  # Ignored

        assert obj1.counted == 0
        time.sleep(0.1)
        assert thread1.value == "counted:5"
        assert thread2.value == "counted:5"
        assert obj1.counted == 5

        obj1.countNoblocking().join()  # Allow again and wait until finishes
        assert obj1.counted == 10

    def testQueue(self):
        obj1 = ExampleClass()

        gevent.spawn(obj1.countQueue, num=10)
        gevent.spawn(obj1.countQueue, num=10)
        gevent.spawn(obj1.countQueue, num=10)

        time.sleep(3.0)
        assert obj1.counted == 20  # No multi-queue supported

        obj2 = ExampleClass()
        gevent.spawn(obj2.countQueue, num=10)
        gevent.spawn(obj2.countQueue, num=10)

        time.sleep(1.5)  # Call 1 finished, call 2 still working
        assert 10 < obj2.counted < 20

        gevent.spawn(obj2.countQueue, num=10)
        time.sleep(2.0)

        assert obj2.counted == 30

    def testQueueOverload(self):
        obj1 = ExampleClass()

        threads = []
        for i in range(1000):
            thread = gevent.spawn(obj1.countQueue, num=5)
            threads.append(thread)

        gevent.joinall(threads)
        assert obj1.counted == 5 * 2  # Only called twice (no multi-queue allowed)

    def testIgnoreClass(self):
        obj1 = ExampleClass()
        obj2 = ExampleClass()

        threads = [
            gevent.spawn(obj1.countQueue),
            gevent.spawn(obj1.countQueue),
            gevent.spawn(obj1.countQueue),
            gevent.spawn(obj2.countQueue),
            gevent.spawn(obj2.countQueue)
        ]
        s = time.time()
        time.sleep(0.001)
        gevent.joinall(threads)

        # Queue limited to 2 calls (every call takes counts to 5 and takes 0.05 sec)
        assert obj1.counted + obj2.counted == 10

        taken = time.time() - s
        assert 1.2 > taken >= 1.0  # 2 * 0.5s count = ~1s

    def testException(self):
        @util.Noparallel()
        def raiseException():
            raise Exception("Test error!")

        with pytest.raises(Exception) as err:
            raiseException()
        assert str(err.value) == "Test error!"

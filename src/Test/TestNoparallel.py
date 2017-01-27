import time

import util
import gevent

class ExampleClass(object):
    def __init__(self):
        self.counted = 0

    @util.Noparallel()
    def countBlocking(self, num=5):
        for i in range(1, num+1):
            time.sleep(0.01)
            self.counted += 1
        return "counted:%s" % i

    @util.Noparallel(blocking=False)
    def countNoblocking(self, num=5):
        for i in range(1, num+1):
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
        assert [thread.value for thread in threads] == ["counted:5","counted:5","counted:5","counted:5"]  # Check the return value for every call
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

import time

from util import Cached


class CachedObject:
    def __init__(self):
        self.num_called_add = 0
        self.num_called_multiply = 0
        self.num_called_none = 0

    @Cached(timeout=1)
    def calcAdd(self, a, b):
        self.num_called_add += 1
        return a + b

    @Cached(timeout=1)
    def calcMultiply(self, a, b):
        self.num_called_multiply += 1
        return a * b

    @Cached(timeout=1)
    def none(self):
        self.num_called_none += 1
        return None


class TestCached:
    def testNoneValue(self):
        cached_object = CachedObject()
        assert cached_object.none() is None
        assert cached_object.none() is None
        assert cached_object.num_called_none == 1
        time.sleep(2)
        assert cached_object.none() is None
        assert cached_object.num_called_none == 2

    def testCall(self):
        cached_object = CachedObject()

        assert cached_object.calcAdd(1, 2) == 3
        assert cached_object.calcAdd(1, 2) == 3
        assert cached_object.calcMultiply(1, 2) == 2
        assert cached_object.calcMultiply(1, 2) == 2
        assert cached_object.num_called_add == 1
        assert cached_object.num_called_multiply == 1

        assert cached_object.calcAdd(2, 3) == 5
        assert cached_object.calcAdd(2, 3) == 5
        assert cached_object.num_called_add == 2

        assert cached_object.calcAdd(1, 2) == 3
        assert cached_object.calcMultiply(2, 3) == 6
        assert cached_object.num_called_add == 2
        assert cached_object.num_called_multiply == 2

        time.sleep(2)
        assert cached_object.calcAdd(1, 2) == 3
        assert cached_object.num_called_add == 3

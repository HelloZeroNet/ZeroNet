import time


class Cached(object):
    def __init__(self, timeout):
        self.cache_db = {}
        self.timeout = timeout

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            key = "%s %s" % (args, kwargs)
            cached_value = None
            cache_hit = False
            if key in self.cache_db:
                cache_hit = True
                cached_value, time_cached_end = self.cache_db[key]
                if time.time() > time_cached_end:
                    self.cleanupExpired()
                    cached_value = None
                    cache_hit = False

            if cache_hit:
                return cached_value
            else:
                cached_value = func(*args, **kwargs)
                time_cached_end = time.time() + self.timeout
                self.cache_db[key] = (cached_value, time_cached_end)
                return cached_value

        wrapper.emptyCache = self.emptyCache

        return wrapper

    def cleanupExpired(self):
        for key in list(self.cache_db.keys()):
            cached_value, time_cached_end = self.cache_db[key]
            if time.time() > time_cached_end:
                del(self.cache_db[key])

    def emptyCache(self):
        num = len(self.cache_db)
        self.cache_db.clear()
        return num


if __name__ == "__main__":
    from gevent import monkey
    monkey.patch_all()

    @Cached(timeout=2)
    def calcAdd(a, b):
        print("CalcAdd", a, b)
        return a + b

    @Cached(timeout=1)
    def calcMultiply(a, b):
        print("calcMultiply", a, b)
        return a * b

    for i in range(5):
        print("---")
        print("Emptied", calcAdd.emptyCache())
        assert calcAdd(1, 2) == 3
        print("Emptied", calcAdd.emptyCache())
        assert calcAdd(1, 2) == 3
        assert calcAdd(2, 3) == 5
        assert calcMultiply(2, 3) == 6
        time.sleep(1)

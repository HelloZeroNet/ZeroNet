# Based on http://stackoverflow.com/a/2022629


class Event(list):

    def __call__(self, *args, **kwargs):
        for f in self[:]:
            if "once" in dir(f) and f in self:
                self.remove(f)
            f(*args, **kwargs)

    def __repr__(self):
        return "Event(%s)" % list.__repr__(self)

    def once(self, func, name=None):
        func.once = True
        func.name = None
        if name:  # Dont function with same name twice
            names = [f.name for f in self if "once" in dir(f)]
            if name not in names:
                func.name = name
                self.append(func)
        else:
            self.append(func)
        return self


if __name__ == "__main__":
    def testBenchmark():
        def say(pre, text):
            print "%s Say: %s" % (pre, text)

        import time
        s = time.time()
        on_changed = Event()
        for i in range(1000):
            on_changed.once(lambda pre: say(pre, "once"), "once")
        print "Created 1000 once in %.3fs" % (time.time() - s)
        on_changed("#1")

    def testUsage():
        def say(pre, text):
            print "%s Say: %s" % (pre, text)

        on_changed = Event()
        on_changed.once(lambda pre: say(pre, "once"))
        on_changed.once(lambda pre: say(pre, "once"))
        on_changed.once(lambda pre: say(pre, "namedonce"), "namedonce")
        on_changed.once(lambda pre: say(pre, "namedonce"), "namedonce")
        on_changed.append(lambda pre: say(pre, "always"))
        on_changed("#1")
        on_changed("#2")
        on_changed("#3")

    testBenchmark()

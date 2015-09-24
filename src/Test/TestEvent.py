import util


class ExampleClass(object):
    def __init__(self):
        self.called = []
        self.onChanged = util.Event()

    def increment(self, title):
        self.called.append(title)


class TestEvent:
    def testEvent(self):
        test_obj = ExampleClass()
        test_obj.onChanged.append(lambda: test_obj.increment("Called #1"))
        test_obj.onChanged.append(lambda: test_obj.increment("Called #2"))
        test_obj.onChanged.once(lambda: test_obj.increment("Once"))

        assert test_obj.called == []
        test_obj.onChanged()
        assert test_obj.called == ["Called #1", "Called #2", "Once"]
        test_obj.onChanged()
        test_obj.onChanged()
        assert test_obj.called == ["Called #1", "Called #2", "Once", "Called #1", "Called #2", "Called #1", "Called #2"]

    def testOnce(self):
        test_obj = ExampleClass()
        test_obj.onChanged.once(lambda: test_obj.increment("Once test #1"))

        # It should be called only once
        assert test_obj.called == []
        test_obj.onChanged()
        assert test_obj.called == ["Once test #1"]
        test_obj.onChanged()
        test_obj.onChanged()
        assert test_obj.called == ["Once test #1"]

    def testOnceMultiple(self):
        test_obj = ExampleClass()
        # Allow queue more than once
        test_obj.onChanged.once(lambda: test_obj.increment("Once test #1"))
        test_obj.onChanged.once(lambda: test_obj.increment("Once test #2"))
        test_obj.onChanged.once(lambda: test_obj.increment("Once test #3"))

        assert test_obj.called == []
        test_obj.onChanged()
        assert test_obj.called == ["Once test #1", "Once test #2", "Once test #3"]
        test_obj.onChanged()
        test_obj.onChanged()
        assert test_obj.called == ["Once test #1", "Once test #2", "Once test #3"]

    def testOnceNamed(self):
        test_obj = ExampleClass()
        # Dont store more that one from same type
        test_obj.onChanged.once(lambda: test_obj.increment("Once test #1/1"), "type 1")
        test_obj.onChanged.once(lambda: test_obj.increment("Once test #1/2"), "type 1")
        test_obj.onChanged.once(lambda: test_obj.increment("Once test #2"), "type 2")

        assert test_obj.called == []
        test_obj.onChanged()
        assert test_obj.called == ["Once test #1/1", "Once test #2"]
        test_obj.onChanged()
        test_obj.onChanged()
        assert test_obj.called == ["Once test #1/1", "Once test #2"]

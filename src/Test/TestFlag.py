import os

import pytest

from util.Flag import Flag

class TestFlag:
    def testFlagging(self):
        flag = Flag()
        @flag.admin
        @flag.no_multiuser
        def testFn(anything):
            return anything

        assert "admin" in flag.db["testFn"]
        assert "no_multiuser" in flag.db["testFn"]

    def testSubclassedFlagging(self):
        flag = Flag()
        class Test:
            @flag.admin
            @flag.no_multiuser
            def testFn(anything):
                return anything

        class SubTest(Test):
            pass

        assert "admin" in flag.db["testFn"]
        assert "no_multiuser" in flag.db["testFn"]

    def testInvalidFlag(self):
        flag = Flag()
        with pytest.raises(Exception) as err:
            @flag.no_multiuser
            @flag.unknown_flag
            def testFn(anything):
                return anything
        assert "Invalid flag" in str(err.value)

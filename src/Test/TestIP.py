import pytest

from util.IP import is_private_address

@pytest.mark.usefixtures("resetSettings")
class TestIP:

    def testPrivateRangeAcceptable(self):
        assert is_private_address("127.0.0.1")
        assert is_private_address("127.84.2.1")
        assert is_private_address("10.55.1.56")

    def testPrivateRangeUnacceptable(self):
        assert not is_private_address('10.1111.15.1')
        assert not is_private_address('127.a.15.1')
        assert not is_private_address('10.10.15.asd')
        assert not is_private_address("google.com")

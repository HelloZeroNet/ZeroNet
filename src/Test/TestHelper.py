import socket

import pytest
from util import helper


@pytest.mark.usefixtures("resetSettings")
class TestHelper:
    def testShellquote(self):
        assert helper.shellquote("hel'lo") == "\"hel'lo\""  # Allow '
        assert helper.shellquote('hel"lo') == '"hello"'  # Remove "
        assert helper.shellquote("hel'lo", 'hel"lo') == ('"hel\'lo"', '"hello"')

    def testPackAddress(self):
        assert len(helper.packAddress("1.1.1.1", 1)) == 6
        assert helper.unpackAddress(helper.packAddress("1.1.1.1", 1)) == ("1.1.1.1", 1)

        with pytest.raises(socket.error):
            helper.packAddress("999.1.1.1", 1)

        with pytest.raises(AssertionError):
            helper.unpackAddress("X")

    def testGetDirname(self):
        assert helper.getDirname("data/users/content.json") == "data/users/"
        assert helper.getDirname("data/users") == "data/"
        assert helper.getDirname("") == ""
        assert helper.getDirname("content.json") == ""
        assert helper.getDirname("data/users/") == "data/users/"
        assert helper.getDirname("/data/users/content.json") == "/data/users/"


    def testGetFilename(self):
        assert helper.getFilename("data/users/content.json") == "content.json"
        assert helper.getFilename("data/users") == "users"
        assert helper.getFilename("") == ""
        assert helper.getFilename("content.json") == "content.json"
        assert helper.getFilename("data/users/") == ""
        assert helper.getFilename("/data/users/content.json") == "content.json"
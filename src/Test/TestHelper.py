import socket
import struct
import os

import pytest
from util import helper
from Config import config


@pytest.mark.usefixtures("resetSettings")
class TestHelper:
    def testShellquote(self):
        assert helper.shellquote("hel'lo") == "\"hel'lo\""  # Allow '
        assert helper.shellquote('hel"lo') == '"hello"'  # Remove "
        assert helper.shellquote("hel'lo", 'hel"lo') == ('"hel\'lo"', '"hello"')

    def testPackAddress(self):
        for port in [1, 1000, 65535]:
            for ip in ["1.1.1.1", "127.0.0.1", "0.0.0.0", "255.255.255.255", "192.168.1.1"]:
                assert len(helper.packAddress(ip, port)) == 6
                assert helper.unpackAddress(helper.packAddress(ip, port)) == (ip, port)

            for ip in ["1:2:3:4:5:6:7:8", "::1", "2001:19f0:6c01:e76:5400:1ff:fed6:3eca", "2001:4860:4860::8888"]:
                assert len(helper.packAddress(ip, port)) == 18
                assert helper.unpackAddress(helper.packAddress(ip, port)) == (ip, port)

            assert len(helper.packOnionAddress("boot3rdez4rzn36x.onion", port)) == 12
            assert helper.unpackOnionAddress(helper.packOnionAddress("boot3rdez4rzn36x.onion", port)) == ("boot3rdez4rzn36x.onion", port)

        with pytest.raises(struct.error):
            helper.packAddress("1.1.1.1", 100000)

        with pytest.raises(socket.error):
            helper.packAddress("999.1.1.1", 1)

        with pytest.raises(Exception):
            helper.unpackAddress("X")

    def testGetDirname(self):
        assert helper.getDirname("data/users/content.json") == "data/users/"
        assert helper.getDirname("data/users") == "data/"
        assert helper.getDirname("") == ""
        assert helper.getDirname("content.json") == ""
        assert helper.getDirname("data/users/") == "data/users/"
        assert helper.getDirname("/data/users/content.json") == "data/users/"

    def testGetFilename(self):
        assert helper.getFilename("data/users/content.json") == "content.json"
        assert helper.getFilename("data/users") == "users"
        assert helper.getFilename("") == ""
        assert helper.getFilename("content.json") == "content.json"
        assert helper.getFilename("data/users/") == ""
        assert helper.getFilename("/data/users/content.json") == "content.json"

    def testIsIp(self):
        assert helper.isIp("1.2.3.4")
        assert helper.isIp("255.255.255.255")
        assert not helper.isIp("any.host")
        assert not helper.isIp("1.2.3.4.com")
        assert not helper.isIp("1.2.3.4.any.host")

    def testIsPrivateIp(self):
        assert helper.isPrivateIp("192.168.1.1")
        assert not helper.isPrivateIp("1.1.1.1")
        assert helper.isPrivateIp("fe80::44f0:3d0:4e6:637c")
        assert not helper.isPrivateIp("fca5:95d6:bfde:d902:8951:276e:1111:a22c")  # cjdns

    def testOpenLocked(self):
        locked_f = helper.openLocked(config.data_dir + "/locked.file")
        assert locked_f
        with pytest.raises(BlockingIOError):
            locked_f_again = helper.openLocked(config.data_dir + "/locked.file")
        locked_f_different = helper.openLocked(config.data_dir + "/locked_different.file")

        locked_f.close()
        locked_f_different.close()

        os.unlink(locked_f.name)
        os.unlink(locked_f_different.name)

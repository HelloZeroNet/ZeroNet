import time
import copy

import gevent
import pytest
import mock

from AnnounceLocal import AnnounceLocalPlugin
from File import FileServer
from Test import Spy

@pytest.fixture
def announcer(file_server, site):
    file_server.sites[site.address] = site
    announcer = AnnounceLocalPlugin.LocalAnnouncer(file_server, listen_port=1100)
    file_server.local_announcer = announcer
    announcer.listen_port = 1100
    announcer.sender_info["broadcast_port"] = 1100
    announcer.getMyIps = mock.MagicMock(return_value=["127.0.0.1"])
    announcer.discover = mock.MagicMock(return_value=False)  # Don't send discover requests automatically
    gevent.spawn(announcer.start)
    time.sleep(0.5)

    assert file_server.local_announcer.running
    return file_server.local_announcer

@pytest.fixture
def announcer_remote(request, site_temp):
    file_server_remote = FileServer("127.0.0.1", 1545)
    file_server_remote.sites[site_temp.address] = site_temp
    announcer = AnnounceLocalPlugin.LocalAnnouncer(file_server_remote, listen_port=1101)
    file_server_remote.local_announcer = announcer
    announcer.listen_port = 1101
    announcer.sender_info["broadcast_port"] = 1101
    announcer.getMyIps = mock.MagicMock(return_value=["127.0.0.1"])
    announcer.discover = mock.MagicMock(return_value=False)  # Don't send discover requests automatically
    gevent.spawn(announcer.start)
    time.sleep(0.5)

    assert file_server_remote.local_announcer.running

    def cleanup():
        file_server_remote.stop()
    request.addfinalizer(cleanup)


    return file_server_remote.local_announcer

@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestAnnounce:
    def testSenderInfo(self, announcer):
        sender_info = announcer.sender_info
        assert sender_info["port"] > 0
        assert len(sender_info["peer_id"]) == 20
        assert sender_info["rev"] > 0

    def testIgnoreSelfMessages(self, announcer):
        # No response to messages that has same peer_id as server
        assert not announcer.handleMessage(("0.0.0.0", 123), {"cmd": "discoverRequest", "sender": announcer.sender_info, "params": {}})[1]

        # Response to messages with different peer id
        sender_info = copy.copy(announcer.sender_info)
        sender_info["peer_id"] += "-"
        addr, res = announcer.handleMessage(("0.0.0.0", 123), {"cmd": "discoverRequest", "sender": sender_info, "params": {}})
        assert res["params"]["sites_changed"] > 0

    def testDiscoverRequest(self, announcer, announcer_remote):
        assert len(announcer_remote.known_peers) == 0
        with Spy.Spy(announcer_remote, "handleMessage") as responses:
            announcer_remote.broadcast({"cmd": "discoverRequest", "params": {}}, port=announcer.listen_port)
            time.sleep(0.1)

        response_cmds = [response[1]["cmd"] for response in responses]
        assert response_cmds == ["discoverResponse", "siteListResponse"]
        assert len(responses[-1][1]["params"]["sites"]) == 1

        # It should only request siteList if sites_changed value is different from last response
        with Spy.Spy(announcer_remote, "handleMessage") as responses:
            announcer_remote.broadcast({"cmd": "discoverRequest", "params": {}}, port=announcer.listen_port)
            time.sleep(0.1)

        response_cmds = [response[1]["cmd"] for response in responses]
        assert response_cmds == ["discoverResponse"]

    def testPeerDiscover(self, announcer, announcer_remote, site):
        assert announcer.server.peer_id != announcer_remote.server.peer_id
        assert len(list(announcer.server.sites.values())[0].peers) == 0
        announcer.broadcast({"cmd": "discoverRequest"}, port=announcer_remote.listen_port)
        time.sleep(0.1)
        assert len(list(announcer.server.sites.values())[0].peers) == 1

    def testRecentPeerList(self, announcer, announcer_remote, site):
        assert len(site.peers_recent) == 0
        assert len(site.peers) == 0
        with Spy.Spy(announcer, "handleMessage") as responses:
            announcer.broadcast({"cmd": "discoverRequest", "params": {}}, port=announcer_remote.listen_port)
            time.sleep(0.1)
        assert [response[1]["cmd"] for response in responses] == ["discoverResponse", "siteListResponse"]
        assert len(site.peers_recent) == 1
        assert len(site.peers) == 1

        # It should update peer without siteListResponse
        last_time_found = list(site.peers.values())[0].time_found
        site.peers_recent.clear()
        with Spy.Spy(announcer, "handleMessage") as responses:
            announcer.broadcast({"cmd": "discoverRequest", "params": {}}, port=announcer_remote.listen_port)
            time.sleep(0.1)
        assert [response[1]["cmd"] for response in responses] == ["discoverResponse"]
        assert len(site.peers_recent) == 1
        assert list(site.peers.values())[0].time_found > last_time_found



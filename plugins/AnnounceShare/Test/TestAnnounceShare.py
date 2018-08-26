import time
import copy

import gevent
import pytest
import mock

from AnnounceShare import AnnounceSharePlugin
from File import FileServer
from Peer import Peer
from Test import Spy


@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestAnnounceShare:
    def testAnnounceList(self, file_server):
        peer = Peer("127.0.0.1", 1544, connection_server=file_server)
        assert peer.request("getTrackers")["trackers"] == []

        tracker_storage = AnnounceSharePlugin.tracker_storage
        tracker_storage.onTrackerFound("zero://127.0.0.1:15441")
        assert peer.request("getTrackers")["trackers"] == []

        # It needs to have at least one successfull announce to be shared to other peers
        tracker_storage.onTrackerSuccess("zero://127.0.0.1:15441", 1.0)
        assert peer.request("getTrackers")["trackers"] == ["zero://127.0.0.1:15441"]



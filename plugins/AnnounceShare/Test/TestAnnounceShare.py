import pytest

from AnnounceShare import AnnounceSharePlugin
from Peer import Peer
from Config import config


@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestAnnounceShare:
    def testAnnounceList(self, file_server):
        open("%s/trackers.json" % config.data_dir, "w").write("{}")
        tracker_storage = AnnounceSharePlugin.tracker_storage
        tracker_storage.load()
        peer = Peer(file_server.ip, 1544, connection_server=file_server)
        assert peer.request("getTrackers")["trackers"] == []

        tracker_storage.onTrackerFound("zero://%s:15441" % file_server.ip)
        assert peer.request("getTrackers")["trackers"] == []

        # It needs to have at least one successfull announce to be shared to other peers
        tracker_storage.onTrackerSuccess("zero://%s:15441" % file_server.ip, 1.0)
        assert peer.request("getTrackers")["trackers"] == ["zero://%s:15441" % file_server.ip]


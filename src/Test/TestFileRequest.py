import cStringIO as StringIO

import pytest
import time

from Connection import ConnectionServer
from Connection import Connection
from File import FileServer


@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestFileRequest:
    def testGetFile(self, file_server, site):
        file_server.ip_incoming = {}  # Reset flood protection
        client = ConnectionServer("127.0.0.1", 1545)

        connection = client.getConnection("127.0.0.1", 1544)
        file_server.sites[site.address] = site

        response = connection.request("getFile", {"site": site.address, "inner_path": "content.json", "location": 0})
        assert "sign" in response["body"]

        # Invalid file
        response = connection.request("getFile", {"site": site.address, "inner_path": "invalid.file", "location": 0})
        assert "No such file or directory" in response["error"]

        # Location over size
        response = connection.request("getFile", {"site": site.address, "inner_path": "content.json", "location": 1024 * 1024})
        assert "File read error" in response["error"]

        # Stream from parent dir
        response = connection.request("getFile", {"site": site.address, "inner_path": "../users.json", "location": 0})
        assert "File not allowed" in response["error"]

        connection.close()
        client.stop()

    def testStreamFile(self, file_server, site):
        file_server.ip_incoming = {}  # Reset flood protection
        client = ConnectionServer("127.0.0.1", 1545)
        connection = client.getConnection("127.0.0.1", 1544)
        file_server.sites[site.address] = site

        buff = StringIO.StringIO()
        response = connection.request("streamFile", {"site": site.address, "inner_path": "content.json", "location": 0}, buff)
        assert "stream_bytes" in response
        assert "sign" in buff.getvalue()

        # Invalid file
        buff = StringIO.StringIO()
        response = connection.request("streamFile", {"site": site.address, "inner_path": "invalid.file", "location": 0}, buff)
        assert "No such file or directory" in response["error"]

        # Location over size
        buff = StringIO.StringIO()
        response = connection.request(
            "streamFile", {"site": site.address, "inner_path": "content.json", "location": 1024 * 1024}, buff
        )
        assert "File read error" in response["error"]

        # Stream from parent dir
        buff = StringIO.StringIO()
        response = connection.request("streamFile", {"site": site.address, "inner_path": "../users.json", "location": 0}, buff)
        assert "File not allowed" in response["error"]

        connection.close()
        client.stop()

    def testPex(self, file_server, site, site_temp):
        file_server.sites[site.address] = site
        client = FileServer("127.0.0.1", 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client
        connection = client.getConnection("127.0.0.1", 1544)

        # Add new fake peer to site
        fake_peer = site.addPeer("1.2.3.4", 11337, return_peer=True)
        # Add fake connection to it
        fake_peer.connection = Connection(file_server, "1.2.3.4", 11337)
        fake_peer.connection.last_recv_time = time.time()
        assert fake_peer in site.getConnectablePeers()

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer("127.0.0.1", 1544)

        assert "1.2.3.4:11337" not in site_temp.peers
        assert peer_file_server.pex()
        assert "1.2.3.4:11337" in site_temp.peers

        connection.close()
        client.stop()

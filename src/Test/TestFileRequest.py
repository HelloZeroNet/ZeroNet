import io

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
        client = ConnectionServer(file_server.ip, 1545)

        connection = client.getConnection(file_server.ip, 1544)
        file_server.sites[site.address] = site

        # Normal request
        response = connection.request("getFile", {"site": site.address, "inner_path": "content.json", "location": 0})
        assert b"sign" in response["body"]

        response = connection.request("getFile", {"site": site.address, "inner_path": "content.json", "location": 0, "file_size": site.storage.getSize("content.json")})
        assert b"sign" in response["body"]

        # Invalid file
        response = connection.request("getFile", {"site": site.address, "inner_path": "invalid.file", "location": 0})
        assert "File read error" in response["error"]

        # Location over size
        response = connection.request("getFile", {"site": site.address, "inner_path": "content.json", "location": 1024 * 1024})
        assert "File read error" in response["error"]

        # Stream from parent dir
        response = connection.request("getFile", {"site": site.address, "inner_path": "../users.json", "location": 0})
        assert "File read exception" in response["error"]

        # Invalid site
        response = connection.request("getFile", {"site": "", "inner_path": "users.json", "location": 0})
        assert "Unknown site" in response["error"]

        response = connection.request("getFile", {"site": ".", "inner_path": "users.json", "location": 0})
        assert "Unknown site" in response["error"]

        # Invalid size
        response = connection.request("getFile", {"site": site.address, "inner_path": "content.json", "location": 0, "file_size": 1234})
        assert "File size does not match" in response["error"]

        # Invalid path
        for path in ["../users.json", "./../users.json", "data/../content.json", ".../users.json"]:
            for sep in ["/", "\\"]:
                response = connection.request("getFile", {"site": site.address, "inner_path": path.replace("/", sep), "location": 0})
                assert response["error"] == 'File read exception'

        connection.close()
        client.stop()

    def testStreamFile(self, file_server, site):
        file_server.ip_incoming = {}  # Reset flood protection
        client = ConnectionServer(file_server.ip, 1545)
        connection = client.getConnection(file_server.ip, 1544)
        file_server.sites[site.address] = site

        buff = io.BytesIO()
        response = connection.request("streamFile", {"site": site.address, "inner_path": "content.json", "location": 0}, buff)
        assert "stream_bytes" in response
        assert b"sign" in buff.getvalue()

        # Invalid file
        buff = io.BytesIO()
        response = connection.request("streamFile", {"site": site.address, "inner_path": "invalid.file", "location": 0}, buff)
        assert "File read error" in response["error"]

        # Location over size
        buff = io.BytesIO()
        response = connection.request(
            "streamFile", {"site": site.address, "inner_path": "content.json", "location": 1024 * 1024}, buff
        )
        assert "File read error" in response["error"]

        # Stream from parent dir
        buff = io.BytesIO()
        response = connection.request("streamFile", {"site": site.address, "inner_path": "../users.json", "location": 0}, buff)
        assert "File read exception" in response["error"]

        connection.close()
        client.stop()

    def testPex(self, file_server, site, site_temp):
        file_server.sites[site.address] = site
        client = FileServer(file_server.ip, 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client
        connection = client.getConnection(file_server.ip, 1544)

        # Add new fake peer to site
        fake_peer = site.addPeer(file_server.ip_external, 11337, return_peer=True)
        # Add fake connection to it
        fake_peer.connection = Connection(file_server, file_server.ip_external, 11337)
        fake_peer.connection.last_recv_time = time.time()
        assert fake_peer in site.getConnectablePeers()

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer(file_server.ip, 1544)

        assert "%s:11337" % file_server.ip_external not in site_temp.peers
        assert peer_file_server.pex()
        assert "%s:11337" % file_server.ip_external in site_temp.peers

        # Should not exchange private peers from local network
        fake_peer_private = site.addPeer("192.168.0.1", 11337, return_peer=True)
        assert fake_peer_private not in site.getConnectablePeers(allow_private=False)
        fake_peer_private.connection = Connection(file_server, "192.168.0.1", 11337)
        fake_peer_private.connection.last_recv_time = time.time()

        assert "192.168.0.1:11337" not in site_temp.peers
        assert not peer_file_server.pex()
        assert "192.168.0.1:11337" not in site_temp.peers


        connection.close()
        client.stop()

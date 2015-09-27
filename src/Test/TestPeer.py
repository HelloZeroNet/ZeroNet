import cStringIO as StringIO

import pytest
import time

from Connection import ConnectionServer
from Connection import Connection
from File import FileServer


@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestFileRequest:
    def testPing(self, file_server, site, site_temp):
        file_server.ip_incoming = {}  # Reset flood protection
        file_server.sites[site.address] = site
        client = FileServer("127.0.0.1", 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client
        connection = client.getConnection("127.0.0.1", 1544)

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer("127.0.0.1", 1544)

        assert peer_file_server.ping()

        assert peer_file_server in site_temp.peers.values()
        peer_file_server.remove()
        assert peer_file_server not in site_temp.peers.values()

        connection.close()
        client.stop()

    def testDownloadFile(self, file_server, site, site_temp):
        file_server.ip_incoming = {}  # Reset flood protection
        file_server.sites[site.address] = site
        client = FileServer("127.0.0.1", 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client
        connection = client.getConnection("127.0.0.1", 1544)

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer("127.0.0.1", 1544)

        # Testing streamFile
        buff = peer_file_server.streamFile(site_temp.address, "content.json")
        assert "sign" in buff.getvalue()

        # Testing getFile
        buff = peer_file_server.getFile(site_temp.address, "content.json")
        assert "sign" in buff.getvalue()

        connection.close()
        client.stop()

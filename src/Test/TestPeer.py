import time
from cStringIO import StringIO

import pytest

from File import FileServer
from File import FileRequest
from Crypt import CryptHash
import Spy


@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestPeer:
    def testPing(self, file_server, site, site_temp):
        file_server.ip_incoming = {}  # Reset flood protection
        file_server.sites[site.address] = site
        client = FileServer("127.0.0.1", 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client
        connection = client.getConnection("127.0.0.1", 1544)

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer("127.0.0.1", 1544)

        assert peer_file_server.ping() is not None

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

    def testHashfield(self, site):
        sample_hash = site.content_manager.contents["content.json"]["files_optional"].values()[0]["sha512"]

        site.storage.verifyFiles(quick_check=True)  # Find what optional files we have

        # Check if hashfield has any files
        assert site.content_manager.hashfield
        assert len(site.content_manager.hashfield) > 0

        # Check exsist hash
        assert site.content_manager.hashfield.getHashId(sample_hash) in site.content_manager.hashfield

        # Add new hash
        new_hash = CryptHash.sha512sum(StringIO("hello"))
        assert site.content_manager.hashfield.getHashId(new_hash) not in site.content_manager.hashfield
        assert site.content_manager.hashfield.appendHash(new_hash)
        assert not site.content_manager.hashfield.appendHash(new_hash)  # Don't add second time
        assert site.content_manager.hashfield.getHashId(new_hash) in site.content_manager.hashfield

        # Remove new hash
        assert site.content_manager.hashfield.removeHash(new_hash)
        assert site.content_manager.hashfield.getHashId(new_hash) not in site.content_manager.hashfield

    def testHashfieldExchange(self, file_server, site, site_temp):
        server1 = file_server
        server1.ip_incoming = {}  # Reset flood protection
        server1.sites[site.address] = site
        server2 = FileServer("127.0.0.1", 1545)
        server2.sites[site_temp.address] = site_temp
        site_temp.connection_server = server2
        site.storage.verifyFiles(quick_check=True)  # Find what optional files we have

        # Add file_server as peer to client
        server2_peer1 = site_temp.addPeer("127.0.0.1", 1544)

        # Check if hashfield has any files
        assert len(site.content_manager.hashfield) > 0

        # Testing hashfield sync
        assert len(server2_peer1.hashfield) == 0
        assert server2_peer1.updateHashfield()  # Query hashfield from peer
        assert len(server2_peer1.hashfield) > 0

        # Test force push new hashfield
        site_temp.content_manager.hashfield.appendHash("AABB")
        server1_peer2 = site.addPeer("127.0.0.1", 1545, return_peer=True)
        with Spy.Spy(FileRequest, "route") as requests:
            assert len(server1_peer2.hashfield) == 0
            server2_peer1.sendMyHashfield()
            assert len(server1_peer2.hashfield) == 1
            server2_peer1.sendMyHashfield()  # Hashfield not changed, should be ignored

            assert len(requests) == 1

            time.sleep(0.01)  # To make hashfield change date different

            site_temp.content_manager.hashfield.appendHash("AACC")
            server2_peer1.sendMyHashfield()  # Push hashfield

            assert len(server1_peer2.hashfield) == 2
            assert len(requests) == 2

            site_temp.content_manager.hashfield.appendHash("AADD")

            assert server1_peer2.updateHashfield(force=True)  # Request hashfield
            assert len(server1_peer2.hashfield) == 3
            assert len(requests) == 3

            assert not server2_peer1.sendMyHashfield()  # Not changed, should be ignored
            assert len(requests) == 3

        server2.stop()

    def testFindHash(self, file_server, site, site_temp):
        file_server.ip_incoming = {}  # Reset flood protection
        file_server.sites[site.address] = site
        client = FileServer("127.0.0.1", 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer("127.0.0.1", 1544)

        assert peer_file_server.findHashIds([1234]) == {}

        # Add fake peer with requred hash
        fake_peer_1 = site.addPeer("1.2.3.4", 1544)
        fake_peer_1.hashfield.append(1234)
        fake_peer_2 = site.addPeer("1.2.3.5", 1545)
        fake_peer_2.hashfield.append(1234)
        fake_peer_2.hashfield.append(1235)
        fake_peer_3 = site.addPeer("1.2.3.6", 1546)
        fake_peer_3.hashfield.append(1235)
        fake_peer_3.hashfield.append(1236)

        assert peer_file_server.findHashIds([1234, 1235]) == {
            1234: [('1.2.3.4', 1544), ('1.2.3.5', 1545)],
            1235: [('1.2.3.5', 1545), ('1.2.3.6', 1546)]
        }

        # Test my address adding
        site.content_manager.hashfield.append(1234)

        res = peer_file_server.findHashIds([1234, 1235])
        assert res[1234] == [('1.2.3.4', 1544), ('1.2.3.5', 1545), ("127.0.0.1", 1544)]
        assert res[1235] == [('1.2.3.5', 1545), ('1.2.3.6', 1546)]
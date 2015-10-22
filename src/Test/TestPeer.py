
import pytest

from File import FileServer
from Crypt import CryptHash
from cStringIO import StringIO


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

        assert not site.content_manager.hashfield

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
        file_server.ip_incoming = {}  # Reset flood protection
        file_server.sites[site.address] = site
        client = FileServer("127.0.0.1", 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client
        connection = client.getConnection("127.0.0.1", 1544)
        site.storage.verifyFiles(quick_check=True)  # Find what optional files we have

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer("127.0.0.1", 1544)

        # Check if hashfield has any files
        assert len(site.content_manager.hashfield) > 0

        # Testing hashfield sync
        assert len(peer_file_server.hashfield) == 0
        assert peer_file_server.updateHashfield()
        assert len(peer_file_server.hashfield) > 0

        connection.close()
        client.stop()

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

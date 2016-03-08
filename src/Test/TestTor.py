import pytest
import time

from File import FileServer
from Crypt import CryptRsa

@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestTor:
    def testDownload(self, tor_manager):
        for retry in range(15):
            time.sleep(1)
            if tor_manager.enabled and tor_manager.conn:
                break
        assert tor_manager.enabled

    def testManagerConnection(self, tor_manager):
        assert "250-version" in tor_manager.request("GETINFO version")

    def testAddOnion(self, tor_manager):
        # Add
        address = tor_manager.addOnion()
        assert address
        assert address in tor_manager.privatekeys

        # Delete
        assert tor_manager.delOnion(address)
        assert address not in tor_manager.privatekeys

    def testSignOnion(self, tor_manager):
        address = tor_manager.addOnion()

        # Sign
        sign = CryptRsa.sign("hello", tor_manager.getPrivatekey(address))
        assert len(sign) == 128

        # Verify
        publickey = CryptRsa.privatekeyToPublickey(tor_manager.getPrivatekey(address))
        assert len(publickey) == 140
        assert CryptRsa.verify("hello", publickey, sign)
        assert not CryptRsa.verify("not hello", publickey, sign)

        # Pub to address
        assert CryptRsa.publickeyToOnion(publickey) == address

        # Delete
        tor_manager.delOnion(address)

    @pytest.mark.skipif(not pytest.config.getvalue("slow"), reason="--slow not requested (takes around ~ 1min)")
    def testConnection(self, tor_manager, file_server, site, site_temp):
        file_server.tor_manager.start_onions = True
        address = file_server.tor_manager.getOnion(site.address)
        assert address
        print "Connecting to", address
        for retry in range(5):  # Wait for hidden service creation
            time.sleep(10)
            try:
                connection = file_server.getConnection(address+".onion", 1544)
                if connection:
                    break
            except Exception, err:
                continue
        assert connection.handshake
        assert not connection.handshake["peer_id"]  # No peer_id for Tor connections

        # Return the same connection without site specified
        assert file_server.getConnection(address+".onion", 1544) == connection
        # No reuse for different site
        assert file_server.getConnection(address+".onion", 1544, site=site) != connection
        assert file_server.getConnection(address+".onion", 1544, site=site) == file_server.getConnection(address+".onion", 1544, site=site)
        site_temp.address = "1OTHERSITE"
        assert file_server.getConnection(address+".onion", 1544, site=site) != file_server.getConnection(address+".onion", 1544, site=site_temp)

        # Only allow to query from the locked site
        file_server.sites[site.address] = site
        connection_locked = file_server.getConnection(address+".onion", 1544, site=site)
        assert "body" in connection_locked.request("getFile", {"site": site.address, "inner_path": "content.json", "location": 0})
        assert connection_locked.request("getFile", {"site": "1OTHERSITE", "inner_path": "content.json", "location": 0})["error"] == "Invalid site"

    def testPex(self, file_server, site, site_temp):
        # Register site to currently running fileserver
        site.connection_server = file_server
        file_server.sites[site.address] = site
        # Create a new file server to emulate new peer connecting to our peer
        file_server_temp = FileServer("127.0.0.1", 1545)
        site_temp.connection_server = file_server_temp
        file_server_temp.sites[site_temp.address] = site_temp
        # We will request peers from this
        peer_source = site_temp.addPeer("127.0.0.1", 1544)

        # Get ip4 peers from source site
        assert peer_source.pex(need_num=10) == 1  # Need >5 to return also return non-connected peers
        assert len(site_temp.peers) == 2  # Me, and the other peer
        site.addPeer("1.2.3.4", 1555)  # Add peer to source site
        assert peer_source.pex(need_num=10) == 1
        assert len(site_temp.peers) == 3
        assert "1.2.3.4:1555" in site_temp.peers

        # Get onion peers from source site
        site.addPeer("bka4ht2bzxchy44r.onion", 1555)
        assert "bka4ht2bzxchy44r.onion:1555" not in site_temp.peers
        assert peer_source.pex(need_num=10) == 1  # Need >5 to return also return non-connected peers
        assert "bka4ht2bzxchy44r.onion:1555" in site_temp.peers

    def testFindHash(self, tor_manager, file_server, site, site_temp):
        file_server.ip_incoming = {}  # Reset flood protection
        file_server.sites[site.address] = site
        file_server.tor_manager = tor_manager

        client = FileServer("127.0.0.1", 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer("127.0.0.1", 1544)

        assert peer_file_server.findHashIds([1234]) == {}

        # Add fake peer with requred hash
        fake_peer_1 = site.addPeer("bka4ht2bzxchy44r.onion", 1544)
        fake_peer_1.hashfield.append(1234)
        fake_peer_2 = site.addPeer("1.2.3.5", 1545)
        fake_peer_2.hashfield.append(1234)
        fake_peer_2.hashfield.append(1235)
        fake_peer_3 = site.addPeer("1.2.3.6", 1546)
        fake_peer_3.hashfield.append(1235)
        fake_peer_3.hashfield.append(1236)

        assert peer_file_server.findHashIds([1234, 1235]) == {
            1234: [('1.2.3.5', 1545), ("bka4ht2bzxchy44r.onion", 1544)],
            1235: [('1.2.3.6', 1546), ('1.2.3.5', 1545)]
        }

        # Test my address adding
        site.content_manager.hashfield.append(1234)
        my_onion_address = tor_manager.getOnion(site_temp.address)+".onion"

        res = peer_file_server.findHashIds([1234, 1235])
        assert res[1234] == [('1.2.3.5', 1545), ("bka4ht2bzxchy44r.onion", 1544), (my_onion_address, 1544)]
        assert res[1235] == [('1.2.3.6', 1546), ('1.2.3.5', 1545)]

    def testSiteOnion(self, tor_manager):
        assert tor_manager.getOnion("address1") != tor_manager.getOnion("address2")
        assert tor_manager.getOnion("address1") == tor_manager.getOnion("address1")

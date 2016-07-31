import pytest
import time

from File import FileServer

# stats.i2p
TEST_B64 = 'Okd5sN9hFWx-sr0HH8EFaxkeIMi6PC5eGTcjM1KB7uQ0ffCUJ2nVKzcsKZFHQc7pLONjOs2LmG5H-2SheVH504EfLZnoB7vxoamhOMENnDABkIRGGoRisc5AcJXQ759LraLRdiGSR0WTHQ0O1TU0hAz7vAv3SOaDp9OwNDr9u902qFzzTKjUTG5vMTayjTkLo2kOwi6NVchDeEj9M7mjj5ySgySbD48QpzBgcqw1R27oIoHQmjgbtbmV2sBL-2Tpyh3lRe1Vip0-K0Sf4D-Zv78MzSh8ibdxNcZACmZiVODpgMj2ejWJHxAEz41RsfBpazPV0d38Mfg4wzaS95R5hBBo6SdAM4h5vcZ5ESRiheLxJbW0vBpLRd4mNvtKOrcEtyCvtvsP3FpA-6IKVswyZpHgr3wn6ndDHiVCiLAQZws4MsIUE1nkfxKpKtAnFZtPrrB8eh7QO9CkH2JBhj7bG0ED6mV5~X5iqi52UpsZ8gnjZTgyG5pOF8RcFrk86kHxAAAA'

@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestI2P:
    def testAddDest(self, i2p_manager):
        # Add
        dest = i2p_manager.addDest()
        assert dest
        assert dest in i2p_manager.dest_conns

        # Delete
        assert i2p_manager.delDest(dest)
        assert dest not in i2p_manager.dest_conns

    def testSignDest(self, i2p_manager):
        dest = i2p_manager.addDest()

        # Sign
        sign = i2p_manager.getPrivateDest(dest).sign("hello")
        assert len(sign) == dest.signature_size()

        # Verify
        assert dest.verify("hello", sign)
        assert not dest.verify("not hello", sign)

        # Delete
        i2p_manager.delDest(dest)

    @pytest.mark.skipif(not pytest.config.getvalue("slow"), reason="--slow not requested (takes around ~ 1min)")
    def testConnection(self, i2p_manager, file_server, site, site_temp):
        file_server.i2p_manager.start_dests = True
        dest = file_server.i2p_manager.getDest(site.address)
        assert dest
        print "Connecting to", dest.base32()
        for retry in range(5):  # Wait for Destination creation
            time.sleep(10)
            try:
                connection = file_server.getConnection(dest.base64()+".i2p", 1544)
                if connection:
                    break
            except Exception, err:
                continue
        assert connection.handshake
        assert not connection.handshake["peer_id"]  # No peer_id for I2P connections

        # Return the same connection without site specified
        assert file_server.getConnection(dest.base64()+".i2p", 1544) == connection
        # No reuse for different site
        assert file_server.getConnection(dest.base64()+".i2p", 1544, site=site) != connection
        assert file_server.getConnection(dest.base64()+".i2p", 1544, site=site) == file_server.getConnection(dest.base64()+".i2p", 1544, site=site)
        site_temp.address = "1OTHERSITE"
        assert file_server.getConnection(dest.base64()+".i2p", 1544, site=site) != file_server.getConnection(dest.base64()+".i2p", 1544, site=site_temp)

        # Only allow to query from the locked site
        file_server.sites[site.address] = site
        connection_locked = file_server.getConnection(dest.base64()+".i2p", 1544, site=site)
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

        # Get I2P peers from source site
        site.addPeer(TEST_B64+".i2p", 1555)
        assert TEST_B64+".i2p:1555" not in site_temp.peers
        assert peer_source.pex(need_num=10) == 1  # Need >5 to return also return non-connected peers
        assert TEST_B64+".i2p:1555" in site_temp.peers

    def testFindHash(self, i2p_manager, file_server, site, site_temp):
        file_server.ip_incoming = {}  # Reset flood protection
        file_server.sites[site.address] = site
        assert file_server.i2p_manager == None
        file_server.i2p_manager = i2p_manager

        client = FileServer("127.0.0.1", 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer("127.0.0.1", 1544)

        assert peer_file_server.findHashIds([1234]) == {}

        # Add fake peer with requred hash
        fake_peer_1 = site.addPeer(TEST_B64+".i2p", 1544)
        fake_peer_1.hashfield.append(1234)
        fake_peer_2 = site.addPeer("1.2.3.5", 1545)
        fake_peer_2.hashfield.append(1234)
        fake_peer_2.hashfield.append(1235)
        fake_peer_3 = site.addPeer("1.2.3.6", 1546)
        fake_peer_3.hashfield.append(1235)
        fake_peer_3.hashfield.append(1236)

        assert peer_file_server.findHashIds([1234, 1235]) == {
            1234: [('1.2.3.5', 1545), (TEST_B64+".i2p", 1544)],
            1235: [('1.2.3.6', 1546), ('1.2.3.5', 1545)]
        }

        # Test my address adding
        site.content_manager.hashfield.append(1234)
        my_i2p_address = i2p_manager.getDest(site_temp.address).base64()+".i2p"

        res = peer_file_server.findHashIds([1234, 1235])
        assert res[1234] == [('1.2.3.5', 1545), (TEST_B64+".i2p", 1544), (my_i2p_address, 1544)]
        assert res[1235] == [('1.2.3.6', 1546), ('1.2.3.5', 1545)]

        # Reset
        file_server.i2p_manager = None

    def testSiteDest(self, i2p_manager):
        assert i2p_manager.getDest("address1") != i2p_manager.getDest("address2")
        assert i2p_manager.getDest("address1") == i2p_manager.getDest("address1")

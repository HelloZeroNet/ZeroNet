import hashlib
import os

import pytest

from Bootstrapper import BootstrapperPlugin
from Bootstrapper.BootstrapperDb import BootstrapperDb
from Peer import Peer
from Crypt import CryptRsa
from util import helper


@pytest.fixture()
def bootstrapper_db(request):
    BootstrapperPlugin.db.close()
    BootstrapperPlugin.db = BootstrapperDb()
    BootstrapperPlugin.db.createTables()  # Reset db
    BootstrapperPlugin.db.cur.logging = True

    def cleanup():
        BootstrapperPlugin.db.close()
        os.unlink(BootstrapperPlugin.db.db_path)

    request.addfinalizer(cleanup)
    return BootstrapperPlugin.db


@pytest.mark.usefixtures("resetSettings")
class TestBootstrapper:
    def testIp4(self, file_server, bootstrapper_db):
        peer = Peer("127.0.0.1", 1544, connection_server=file_server)
        hash1 = hashlib.sha256("site1").digest()
        hash2 = hashlib.sha256("site2").digest()
        hash3 = hashlib.sha256("site3").digest()

        # Verify empty result
        res = peer.request("announce", {
            "hashes": [hash1, hash2],
            "port": 15441, "need_types": ["ip4"], "need_num": 10, "add": ["ip4"]
        })

        assert len(res["peers"][0]["ip4"]) == 0  # Empty result

        # Verify added peer on previous request
        bootstrapper_db.peerAnnounce(ip4="1.2.3.4", port=15441, hashes=[hash1, hash2], delete_missing_hashes=True)

        res = peer.request("announce", {
            "hashes": [hash1, hash2],
            "port": 15441, "need_types": ["ip4"], "need_num": 10, "add": ["ip4"]
        })
        assert len(res["peers"][0]["ip4"]) == 1
        assert len(res["peers"][1]["ip4"]) == 1

        # hash2 deleted from 1.2.3.4
        bootstrapper_db.peerAnnounce(ip4="1.2.3.4", port=15441, hashes=[hash1], delete_missing_hashes=True)
        res = peer.request("announce", {
            "hashes": [hash1, hash2],
            "port": 15441, "need_types": ["ip4"], "need_num": 10, "add": ["ip4"]
        })
        assert len(res["peers"][0]["ip4"]) == 1
        assert len(res["peers"][1]["ip4"]) == 0

        # Announce 3 hash again
        bootstrapper_db.peerAnnounce(ip4="1.2.3.4", port=15441, hashes=[hash1, hash2, hash3], delete_missing_hashes=True)
        res = peer.request("announce", {
            "hashes": [hash1, hash2, hash3],
            "port": 15441, "need_types": ["ip4"], "need_num": 10, "add": ["ip4"]
        })
        assert len(res["peers"][0]["ip4"]) == 1
        assert len(res["peers"][1]["ip4"]) == 1
        assert len(res["peers"][2]["ip4"]) == 1

        # Single hash announce
        res = peer.request("announce", {
            "hashes": [hash1], "port": 15441, "need_types": ["ip4"], "need_num": 10, "add": ["ip4"]
        })
        assert len(res["peers"][0]["ip4"]) == 1

        # Test DB cleanup
        assert bootstrapper_db.execute("SELECT COUNT(*) AS num FROM peer").fetchone()["num"] == 1  # 127.0.0.1 never get added to db

        # Delete peers
        bootstrapper_db.execute("DELETE FROM peer WHERE ip4 = '1.2.3.4'")
        assert bootstrapper_db.execute("SELECT COUNT(*) AS num FROM peer_to_hash").fetchone()["num"] == 0

        assert bootstrapper_db.execute("SELECT COUNT(*) AS num FROM hash").fetchone()["num"] == 3  # 3 sites
        assert bootstrapper_db.execute("SELECT COUNT(*) AS num FROM peer").fetchone()["num"] == 0  # 0 peer

    def testPassive(self, file_server, bootstrapper_db):
        peer = Peer("127.0.0.1", 1544, connection_server=file_server)
        hash1 = hashlib.sha256("hash1").digest()

        bootstrapper_db.peerAnnounce(ip4=None, port=15441, hashes=[hash1])
        res = peer.request("announce", {
            "hashes": [hash1], "port": 15441, "need_types": ["ip4"], "need_num": 10, "add": []
        })

        assert len(res["peers"][0]["ip4"]) == 0  # Empty result

    def testAddOnion(self, file_server, site, bootstrapper_db, tor_manager):
        onion1 = tor_manager.addOnion()
        onion2 = tor_manager.addOnion()
        peer = Peer("127.0.0.1", 1544, connection_server=file_server)
        hash1 = hashlib.sha256("site1").digest()
        hash2 = hashlib.sha256("site2").digest()

        bootstrapper_db.peerAnnounce(ip4="1.2.3.4", port=1234, hashes=[hash1, hash2])
        res = peer.request("announce", {
            "onions": [onion1, onion2],
            "hashes": [hash1, hash2], "port": 15441, "need_types": ["ip4", "onion"], "need_num": 10, "add": ["onion"]
        })
        assert len(res["peers"][0]["ip4"]) == 1
        assert "onion_sign_this" in res

        # Onion address not added yet
        site_peers = bootstrapper_db.peerList(ip4="1.2.3.4", port=1234, hash=hash1)
        assert len(site_peers["onion"]) == 0
        assert "onion_sign_this" in res

        # Sign the nonces
        sign1 = CryptRsa.sign(res["onion_sign_this"], tor_manager.getPrivatekey(onion1))
        sign2 = CryptRsa.sign(res["onion_sign_this"], tor_manager.getPrivatekey(onion2))

        # Bad sign (different address)
        res = peer.request("announce", {
            "onions": [onion1], "onion_sign_this": res["onion_sign_this"],
            "onion_signs": {tor_manager.getPublickey(onion2): sign2},
            "hashes": [hash1], "port": 15441, "need_types": ["ip4", "onion"], "need_num": 10, "add": ["onion"]
        })
        assert "onion_sign_this" in res
        site_peers1 = bootstrapper_db.peerList(ip4="1.2.3.4", port=1234, hash=hash1)
        assert len(site_peers1["onion"]) == 0  # Not added

        # Bad sign (missing one)
        res = peer.request("announce", {
            "onions": [onion1, onion2], "onion_sign_this": res["onion_sign_this"],
            "onion_signs": {tor_manager.getPublickey(onion1): sign1},
            "hashes": [hash1, hash2], "port": 15441, "need_types": ["ip4", "onion"], "need_num": 10, "add": ["onion"]
        })
        assert "onion_sign_this" in res
        site_peers1 = bootstrapper_db.peerList(ip4="1.2.3.4", port=1234, hash=hash1)
        assert len(site_peers1["onion"]) == 0  # Not added

        # Good sign
        res = peer.request("announce", {
            "onions": [onion1, onion2], "onion_sign_this": res["onion_sign_this"],
            "onion_signs": {tor_manager.getPublickey(onion1): sign1, tor_manager.getPublickey(onion2): sign2},
            "hashes": [hash1, hash2], "port": 15441, "need_types": ["ip4", "onion"], "need_num": 10, "add": ["onion"]
        })
        assert "onion_sign_this" not in res

        # Onion addresses added
        site_peers1 = bootstrapper_db.peerList(ip4="1.2.3.4", port=1234, hash=hash1)
        assert len(site_peers1["onion"]) == 1
        site_peers2 = bootstrapper_db.peerList(ip4="1.2.3.4", port=1234, hash=hash2)
        assert len(site_peers2["onion"]) == 1

        assert site_peers1["onion"][0] != site_peers2["onion"][0]
        assert helper.unpackOnionAddress(site_peers1["onion"][0])[0] == onion1+".onion"
        assert helper.unpackOnionAddress(site_peers2["onion"][0])[0] == onion2+".onion"

        tor_manager.delOnion(onion1)
        tor_manager.delOnion(onion2)

    def testRequestPeers(self, file_server, site, bootstrapper_db, tor_manager):
        site.connection_server = file_server
        hash = hashlib.sha256(site.address).digest()

        # Request peers from tracker
        assert len(site.peers) == 0
        bootstrapper_db.peerAnnounce(ip4="1.2.3.4", port=1234, hashes=[hash])
        site.announceTracker("zero", "127.0.0.1:1544")
        assert len(site.peers) == 1

        # Test onion address store
        bootstrapper_db.peerAnnounce(onion="bka4ht2bzxchy44r", port=1234, hashes=[hash], onion_signed=True)
        site.announceTracker("zero", "127.0.0.1:1544")
        assert len(site.peers) == 2
        assert "bka4ht2bzxchy44r.onion:1234" in site.peers

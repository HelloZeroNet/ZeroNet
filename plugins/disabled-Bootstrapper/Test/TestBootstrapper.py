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
    def testHashCache(self, file_server, bootstrapper_db):
        ip_type = helper.getIpType(file_server.ip)
        peer = Peer(file_server.ip, 1544, connection_server=file_server)
        hash1 = hashlib.sha256(b"site1").digest()
        hash2 = hashlib.sha256(b"site2").digest()
        hash3 = hashlib.sha256(b"site3").digest()

        # Verify empty result
        res = peer.request("announce", {
            "hashes": [hash1, hash2],
            "port": 15441, "need_types": [ip_type], "need_num": 10, "add": [ip_type]
        })

        assert len(res["peers"][0][ip_type]) == 0  # Empty result

        hash_ids_before = bootstrapper_db.hash_ids.copy()

        bootstrapper_db.updateHashCache()

        assert hash_ids_before == bootstrapper_db.hash_ids


    def testBootstrapperDb(self, file_server, bootstrapper_db):
        ip_type = helper.getIpType(file_server.ip)
        peer = Peer(file_server.ip, 1544, connection_server=file_server)
        hash1 = hashlib.sha256(b"site1").digest()
        hash2 = hashlib.sha256(b"site2").digest()
        hash3 = hashlib.sha256(b"site3").digest()

        # Verify empty result
        res = peer.request("announce", {
            "hashes": [hash1, hash2],
            "port": 15441, "need_types": [ip_type], "need_num": 10, "add": [ip_type]
        })

        assert len(res["peers"][0][ip_type]) == 0  # Empty result

        # Verify added peer on previous request
        bootstrapper_db.peerAnnounce(ip_type, file_server.ip_external, port=15441, hashes=[hash1, hash2], delete_missing_hashes=True)

        res = peer.request("announce", {
            "hashes": [hash1, hash2],
            "port": 15441, "need_types": [ip_type], "need_num": 10, "add": [ip_type]
        })
        assert len(res["peers"][0][ip_type]) == 1
        assert len(res["peers"][1][ip_type]) == 1

        # hash2 deleted from 1.2.3.4
        bootstrapper_db.peerAnnounce(ip_type, file_server.ip_external, port=15441, hashes=[hash1], delete_missing_hashes=True)
        res = peer.request("announce", {
            "hashes": [hash1, hash2],
            "port": 15441, "need_types": [ip_type], "need_num": 10, "add": [ip_type]
        })
        assert len(res["peers"][0][ip_type]) == 1
        assert len(res["peers"][1][ip_type]) == 0

        # Announce 3 hash again
        bootstrapper_db.peerAnnounce(ip_type, file_server.ip_external, port=15441, hashes=[hash1, hash2, hash3], delete_missing_hashes=True)
        res = peer.request("announce", {
            "hashes": [hash1, hash2, hash3],
            "port": 15441, "need_types": [ip_type], "need_num": 10, "add": [ip_type]
        })
        assert len(res["peers"][0][ip_type]) == 1
        assert len(res["peers"][1][ip_type]) == 1
        assert len(res["peers"][2][ip_type]) == 1

        # Single hash announce
        res = peer.request("announce", {
            "hashes": [hash1], "port": 15441, "need_types": [ip_type], "need_num": 10, "add": [ip_type]
        })
        assert len(res["peers"][0][ip_type]) == 1

        # Test DB cleanup
        assert [row[0] for row in bootstrapper_db.execute("SELECT address FROM peer").fetchall()] == [file_server.ip_external]  # 127.0.0.1 never get added to db

        # Delete peers
        bootstrapper_db.execute("DELETE FROM peer WHERE address = ?", [file_server.ip_external])
        assert bootstrapper_db.execute("SELECT COUNT(*) AS num FROM peer_to_hash").fetchone()["num"] == 0

        assert bootstrapper_db.execute("SELECT COUNT(*) AS num FROM hash").fetchone()["num"] == 3  # 3 sites
        assert bootstrapper_db.execute("SELECT COUNT(*) AS num FROM peer").fetchone()["num"] == 0  # 0 peer

    def testPassive(self, file_server, bootstrapper_db):
        peer = Peer(file_server.ip, 1544, connection_server=file_server)
        ip_type = helper.getIpType(file_server.ip)
        hash1 = hashlib.sha256(b"hash1").digest()

        bootstrapper_db.peerAnnounce(ip_type, address=None, port=15441, hashes=[hash1])
        res = peer.request("announce", {
            "hashes": [hash1], "port": 15441, "need_types": [ip_type], "need_num": 10, "add": []
        })

        assert len(res["peers"][0]["ipv4"]) == 0  # Empty result

    def testAddOnion(self, file_server, site, bootstrapper_db, tor_manager):
        onion1 = tor_manager.addOnion()
        onion2 = tor_manager.addOnion()
        peer = Peer(file_server.ip, 1544, connection_server=file_server)
        hash1 = hashlib.sha256(b"site1").digest()
        hash2 = hashlib.sha256(b"site2").digest()
        hash3 = hashlib.sha256(b"site3").digest()

        bootstrapper_db.peerAnnounce(ip_type="ipv4", address="1.2.3.4", port=1234, hashes=[hash1, hash2, hash3])
        res = peer.request("announce", {
            "onions": [onion1, onion1, onion2],
            "hashes": [hash1, hash2, hash3], "port": 15441, "need_types": ["ipv4", "onion"], "need_num": 10, "add": ["onion"]
        })
        assert len(res["peers"][0]["ipv4"]) == 1

        # Onion address not added yet
        site_peers = bootstrapper_db.peerList(address="1.2.3.4", port=1234, hash=hash1)
        assert len(site_peers["onion"]) == 0
        assert "onion_sign_this" in res

        # Sign the nonces
        sign1 = CryptRsa.sign(res["onion_sign_this"].encode(), tor_manager.getPrivatekey(onion1))
        sign2 = CryptRsa.sign(res["onion_sign_this"].encode(), tor_manager.getPrivatekey(onion2))

        # Bad sign (different address)
        res = peer.request("announce", {
            "onions": [onion1], "onion_sign_this": res["onion_sign_this"],
            "onion_signs": {tor_manager.getPublickey(onion2): sign2},
            "hashes": [hash1], "port": 15441, "need_types": ["ipv4", "onion"], "need_num": 10, "add": ["onion"]
        })
        assert "onion_sign_this" in res
        site_peers1 = bootstrapper_db.peerList(address="1.2.3.4", port=1234, hash=hash1)
        assert len(site_peers1["onion"]) == 0  # Not added

        # Bad sign (missing one)
        res = peer.request("announce", {
            "onions": [onion1, onion1, onion2], "onion_sign_this": res["onion_sign_this"],
            "onion_signs": {tor_manager.getPublickey(onion1): sign1},
            "hashes": [hash1, hash2, hash3], "port": 15441, "need_types": ["ipv4", "onion"], "need_num": 10, "add": ["onion"]
        })
        assert "onion_sign_this" in res
        site_peers1 = bootstrapper_db.peerList(address="1.2.3.4", port=1234, hash=hash1)
        assert len(site_peers1["onion"]) == 0  # Not added

        # Good sign
        res = peer.request("announce", {
            "onions": [onion1, onion1, onion2], "onion_sign_this": res["onion_sign_this"],
            "onion_signs": {tor_manager.getPublickey(onion1): sign1, tor_manager.getPublickey(onion2): sign2},
            "hashes": [hash1, hash2, hash3], "port": 15441, "need_types": ["ipv4", "onion"], "need_num": 10, "add": ["onion"]
        })
        assert "onion_sign_this" not in res

        # Onion addresses added
        site_peers1 = bootstrapper_db.peerList(address="1.2.3.4", port=1234, hash=hash1)
        assert len(site_peers1["onion"]) == 1
        site_peers2 = bootstrapper_db.peerList(address="1.2.3.4", port=1234, hash=hash2)
        assert len(site_peers2["onion"]) == 1
        site_peers3 = bootstrapper_db.peerList(address="1.2.3.4", port=1234, hash=hash3)
        assert len(site_peers3["onion"]) == 1

        assert site_peers1["onion"][0] == site_peers2["onion"][0]
        assert site_peers2["onion"][0] != site_peers3["onion"][0]
        assert helper.unpackOnionAddress(site_peers1["onion"][0])[0] == onion1 + ".onion"
        assert helper.unpackOnionAddress(site_peers2["onion"][0])[0] == onion1 + ".onion"
        assert helper.unpackOnionAddress(site_peers3["onion"][0])[0] == onion2 + ".onion"

        tor_manager.delOnion(onion1)
        tor_manager.delOnion(onion2)

    def testRequestPeers(self, file_server, site, bootstrapper_db, tor_manager):
        site.connection_server = file_server
        file_server.tor_manager = tor_manager
        hash = hashlib.sha256(site.address.encode()).digest()

        # Request peers from tracker
        assert len(site.peers) == 0
        bootstrapper_db.peerAnnounce(ip_type="ipv4", address="1.2.3.4", port=1234, hashes=[hash])
        site.announcer.announceTracker("zero://%s:%s" % (file_server.ip, file_server.port))
        assert len(site.peers) == 1

        # Test onion address store
        bootstrapper_db.peerAnnounce(ip_type="onion", address="bka4ht2bzxchy44r", port=1234, hashes=[hash], onion_signed=True)
        site.announcer.announceTracker("zero://%s:%s" % (file_server.ip, file_server.port))
        assert len(site.peers) == 2
        assert "bka4ht2bzxchy44r.onion:1234" in site.peers

    @pytest.mark.slow
    def testAnnounce(self, file_server, tor_manager):
        file_server.tor_manager = tor_manager
        hash1 = hashlib.sha256(b"1Nekos4fiBqfcazyG1bAxdBT5oBvA76Z").digest()
        hash2 = hashlib.sha256(b"1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr").digest()
        peer = Peer("zero.booth.moe", 443, connection_server=file_server)
        assert peer.request("ping")
        peer = Peer("boot3rdez4rzn36x.onion", 15441, connection_server=file_server)
        assert peer.request("ping")
        res = peer.request("announce", {
            "hashes": [hash1, hash2],
            "port": 15441, "need_types": ["ip4", "onion"], "need_num": 100, "add": [""]
        })

        assert res

    def testBackwardCompatibility(self, file_server, bootstrapper_db):
        peer = Peer(file_server.ip, 1544, connection_server=file_server)
        hash1 = hashlib.sha256(b"site1").digest()

        bootstrapper_db.peerAnnounce("ipv4", file_server.ip_external, port=15441, hashes=[hash1], delete_missing_hashes=True)

        # Test with ipv4 need type
        res = peer.request("announce", {
            "hashes": [hash1],
            "port": 15441, "need_types": ["ipv4"], "need_num": 10, "add": []
        })

        assert len(res["peers"][0]["ipv4"]) == 1

        # Test with ip4 need type
        res = peer.request("announce", {
            "hashes": [hash1],
            "port": 15441, "need_types": ["ip4"], "need_num": 10, "add": []
        })

        assert len(res["peers"][0]["ip4"]) == 1

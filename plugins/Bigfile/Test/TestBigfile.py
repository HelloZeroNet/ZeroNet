import time
import io
import binascii

import pytest
import mock

from Connection import ConnectionServer
from Content.ContentManager import VerifyError
from File import FileServer
from File import FileRequest
from Worker import WorkerManager
from Peer import Peer
from Bigfile import BigfilePiecefield, BigfilePiecefieldPacked
from Test import Spy
from util import Msgpack


@pytest.mark.usefixtures("resetSettings")
@pytest.mark.usefixtures("resetTempSettings")
class TestBigfile:
    privatekey = "5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv"
    piece_size = 1024 * 1024

    def createBigfile(self, site, inner_path="data/optional.any.iso", pieces=10):
        f = site.storage.open(inner_path, "w")
        for i in range(pieces * 100):
            f.write(("Test%s" % i).ljust(10, "-") * 1000)
        f.close()
        assert site.content_manager.sign("content.json", self.privatekey)
        return inner_path

    def testPiecemapCreate(self, site):
        inner_path = self.createBigfile(site)
        content = site.storage.loadJson("content.json")
        assert "data/optional.any.iso" in content["files_optional"]
        file_node = content["files_optional"][inner_path]
        assert file_node["size"] == 10 * 1000 * 1000
        assert file_node["sha512"] == "47a72cde3be80b4a829e7674f72b7c6878cf6a70b0c58c6aa6c17d7e9948daf6"
        assert file_node["piecemap"] == inner_path + ".piecemap.msgpack"

        piecemap = Msgpack.unpack(site.storage.open(file_node["piecemap"], "rb").read())["optional.any.iso"]
        assert len(piecemap["sha512_pieces"]) == 10
        assert piecemap["sha512_pieces"][0] != piecemap["sha512_pieces"][1]
        assert binascii.hexlify(piecemap["sha512_pieces"][0]) == b"a73abad9992b3d0b672d0c2a292046695d31bebdcb1e150c8410bbe7c972eff3"

    def testVerifyPiece(self, site):
        inner_path = self.createBigfile(site)

        # Verify all 10 piece
        f = site.storage.open(inner_path, "rb")
        for i in range(10):
            piece = io.BytesIO(f.read(1024 * 1024))
            piece.seek(0)
            site.content_manager.verifyPiece(inner_path, i * 1024 * 1024, piece)
        f.close()

        # Try to verify piece 0 with piece 1 hash
        with pytest.raises(VerifyError) as err:
            i = 1
            f = site.storage.open(inner_path, "rb")
            piece = io.BytesIO(f.read(1024 * 1024))
            f.close()
            site.content_manager.verifyPiece(inner_path, i * 1024 * 1024, piece)
        assert "Invalid hash" in str(err.value)

    def testSparseFile(self, site):
        inner_path = "sparsefile"

        # Create a 100MB sparse file
        site.storage.createSparseFile(inner_path, 100 * 1024 * 1024)

        # Write to file beginning
        s = time.time()
        f = site.storage.write("%s|%s-%s" % (inner_path, 0, 1024 * 1024), b"hellostart" * 1024)
        time_write_start = time.time() - s

        # Write to file end
        s = time.time()
        f = site.storage.write("%s|%s-%s" % (inner_path, 99 * 1024 * 1024, 99 * 1024 * 1024 + 1024 * 1024), b"helloend" * 1024)
        time_write_end = time.time() - s

        # Verify writes
        f = site.storage.open(inner_path)
        assert f.read(10) == b"hellostart"
        f.seek(99 * 1024 * 1024)
        assert f.read(8) == b"helloend"
        f.close()

        site.storage.delete(inner_path)

        # Writing to end shold not take much longer, than writing to start
        assert time_write_end <= max(0.1, time_write_start * 1.1)

    def testRangedFileRequest(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        file_server.sites[site.address] = site
        client = FileServer(file_server.ip, 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client
        connection = client.getConnection(file_server.ip, 1544)

        # Add file_server as peer to client
        peer_file_server = site_temp.addPeer(file_server.ip, 1544)

        buff = peer_file_server.getFile(site_temp.address, "%s|%s-%s" % (inner_path, 5 * 1024 * 1024, 6 * 1024 * 1024))

        assert len(buff.getvalue()) == 1 * 1024 * 1024  # Correct block size
        assert buff.getvalue().startswith(b"Test524")  # Correct data
        buff.seek(0)
        assert site.content_manager.verifyPiece(inner_path, 5 * 1024 * 1024, buff)  # Correct hash

        connection.close()
        client.stop()

    def testRangedFileDownload(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Make sure the file and the piecemap in the optional hashfield
        file_info = site.content_manager.getFileInfo(inner_path)
        assert site.content_manager.hashfield.hasHash(file_info["sha512"])

        piecemap_hash = site.content_manager.getFileInfo(file_info["piecemap"])["sha512"]
        assert site.content_manager.hashfield.hasHash(piecemap_hash)

        # Init client server
        client = ConnectionServer(file_server.ip, 1545)
        site_temp.connection_server = client
        peer_client = site_temp.addPeer(file_server.ip, 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        bad_files = site_temp.storage.verifyFiles(quick_check=True)["bad_files"]
        assert not bad_files

        # client_piecefield = peer_client.piecefields[file_info["sha512"]].tostring()
        # assert client_piecefield == "1" * 10

        # Download 5. and 10. block

        site_temp.needFile("%s|%s-%s" % (inner_path, 5 * 1024 * 1024, 6 * 1024 * 1024))
        site_temp.needFile("%s|%s-%s" % (inner_path, 9 * 1024 * 1024, 10 * 1024 * 1024))

        # Verify 0. block not downloaded
        f = site_temp.storage.open(inner_path)
        assert f.read(10) == b"\0" * 10
        # Verify 5. and 10. block downloaded
        f.seek(5 * 1024 * 1024)
        assert f.read(7) == b"Test524"
        f.seek(9 * 1024 * 1024)
        assert f.read(7) == b"943---T"

        # Verify hashfield
        assert set(site_temp.content_manager.hashfield) == set([18343, 43727])  # 18343: data/optional.any.iso, 43727: data/optional.any.iso.hashmap.msgpack

    def testOpenBigfile(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = ConnectionServer(file_server.ip, 1545)
        site_temp.connection_server = client
        site_temp.addPeer(file_server.ip, 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        # Open virtual file
        assert not site_temp.storage.isFile(inner_path)

        with site_temp.storage.openBigfile(inner_path) as f:
            with Spy.Spy(FileRequest, "route") as requests:
                f.seek(5 * 1024 * 1024)
                assert f.read(7) == b"Test524"

                f.seek(9 * 1024 * 1024)
                assert f.read(7) == b"943---T"

            assert len(requests) == 4  # 1x peicemap + 1x getpiecefield + 2x for pieces

            assert set(site_temp.content_manager.hashfield) == set([18343, 43727])

            assert site_temp.storage.piecefields[f.sha512].tostring() == "0000010001"
            assert f.sha512 in site_temp.getSettingsCache()["piecefields"]

            # Test requesting already downloaded
            with Spy.Spy(FileRequest, "route") as requests:
                f.seek(5 * 1024 * 1024)
                assert f.read(7) == b"Test524"

            assert len(requests) == 0

            # Test requesting multi-block overflow reads
            with Spy.Spy(FileRequest, "route") as requests:
                f.seek(5 * 1024 * 1024)  # We already have this block
                data = f.read(1024 * 1024 * 3)  # Our read overflow to 6. and 7. block
                assert data.startswith(b"Test524")
                assert data.endswith(b"Test838-")
                assert b"\0" not in data  # No null bytes allowed

            assert len(requests) == 2  # Two block download

            # Test out of range request
            f.seek(5 * 1024 * 1024)
            data = f.read(1024 * 1024 * 30)
            assert len(data) == 10 * 1000 * 1000 - (5 * 1024 * 1024)

            f.seek(30 * 1024 * 1024)
            data = f.read(1024 * 1024 * 30)
            assert len(data) == 0

    @pytest.mark.parametrize("piecefield_obj", [BigfilePiecefield, BigfilePiecefieldPacked])
    def testPiecefield(self, piecefield_obj, site):
        testdatas = [
            b"\x01" * 100 + b"\x00" * 900 + b"\x01" * 4000 + b"\x00" * 4999 + b"\x01",
            b"\x00\x01\x00\x01\x00\x01" * 10 + b"\x00\x01" * 90 + b"\x01\x00" * 400 + b"\x00" * 4999,
            b"\x01" * 10000,
            b"\x00" * 10000
        ]
        for testdata in testdatas:
            piecefield = piecefield_obj()

            piecefield.frombytes(testdata)
            assert piecefield.tobytes() == testdata
            assert piecefield[0] == testdata[0]
            assert piecefield[100] == testdata[100]
            assert piecefield[1000] == testdata[1000]
            assert piecefield[len(testdata) - 1] == testdata[len(testdata) - 1]

            packed = piecefield.pack()
            piecefield_new = piecefield_obj()
            piecefield_new.unpack(packed)
            assert piecefield.tobytes() == piecefield_new.tobytes()
            assert piecefield_new.tobytes() == testdata

    def testFileGet(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        site_temp.connection_server = FileServer(file_server.ip, 1545)
        site_temp.connection_server.sites[site_temp.address] = site_temp
        site_temp.addPeer(file_server.ip, 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        # Download second block
        with site_temp.storage.openBigfile(inner_path) as f:
            f.seek(1024 * 1024)
            assert f.read(1024)[0:1] != b"\0"

        # Make sure first block not download
        with site_temp.storage.open(inner_path) as f:
            assert f.read(1024)[0:1] == b"\0"

        peer2 = site.addPeer(file_server.ip, 1545, return_peer=True)

        # Should drop error on first block request
        assert not peer2.getFile(site.address, "%s|0-%s" % (inner_path, 1024 * 1024 * 1))

        # Should not drop error for second block request
        assert peer2.getFile(site.address, "%s|%s-%s" % (inner_path, 1024 * 1024 * 1, 1024 * 1024 * 2))

    def benchmarkPeerMemory(self, site, file_server):
        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        import psutil, os
        meminfo = psutil.Process(os.getpid()).memory_info

        mem_s = meminfo()[0]
        s = time.time()
        for i in range(25000):
            site.addPeer(file_server.ip, i)
        print("%.3fs MEM: + %sKB" % (time.time() - s, (meminfo()[0] - mem_s) / 1024))  # 0.082s MEM: + 6800KB
        print(list(site.peers.values())[0].piecefields)

    def testUpdatePiecefield(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        server1 = file_server
        server1.sites[site.address] = site
        server2 = FileServer(file_server.ip, 1545)
        server2.sites[site_temp.address] = site_temp
        site_temp.connection_server = server2

        # Add file_server as peer to client
        server2_peer1 = site_temp.addPeer(file_server.ip, 1544)

        # Testing piecefield sync
        assert len(server2_peer1.piecefields) == 0
        assert server2_peer1.updatePiecefields()  # Query piecefields from peer
        assert len(server2_peer1.piecefields) > 0

    def testWorkerManagerPiecefieldDeny(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        server1 = file_server
        server1.sites[site.address] = site
        server2 = FileServer(file_server.ip, 1545)
        server2.sites[site_temp.address] = site_temp
        site_temp.connection_server = server2

        # Add file_server as peer to client
        server2_peer1 = site_temp.addPeer(file_server.ip, 1544)  # Working

        site_temp.downloadContent("content.json", download_files=False)
        site_temp.needFile("data/optional.any.iso.piecemap.msgpack")

        # Add fake peers with optional files downloaded
        for i in range(5):
            fake_peer = site_temp.addPeer("127.0.1.%s" % i, 1544)
            fake_peer.hashfield = site.content_manager.hashfield
            fake_peer.has_hashfield = True

        with Spy.Spy(WorkerManager, "addWorker") as requests:
            site_temp.needFile("%s|%s-%s" % (inner_path, 5 * 1024 * 1024, 6 * 1024 * 1024))
            site_temp.needFile("%s|%s-%s" % (inner_path, 6 * 1024 * 1024, 7 * 1024 * 1024))

        # It should only request parts from peer1 as the other peers does not have the requested parts in piecefields
        assert len([request[1] for request in requests if request[1] != server2_peer1]) == 0

    def testWorkerManagerPiecefieldDownload(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        server1 = file_server
        server1.sites[site.address] = site
        server2 = FileServer(file_server.ip, 1545)
        server2.sites[site_temp.address] = site_temp
        site_temp.connection_server = server2
        sha512 = site.content_manager.getFileInfo(inner_path)["sha512"]

        # Create 10 fake peer for each piece
        for i in range(10):
            peer = Peer(file_server.ip, 1544, site_temp, server2)
            peer.piecefields[sha512][i] = b"\x01"
            peer.updateHashfield = mock.MagicMock(return_value=False)
            peer.updatePiecefields = mock.MagicMock(return_value=False)
            peer.findHashIds = mock.MagicMock(return_value={"nope": []})
            peer.hashfield = site.content_manager.hashfield
            peer.has_hashfield = True
            peer.key = "Peer:%s" % i
            site_temp.peers["Peer:%s" % i] = peer

        site_temp.downloadContent("content.json", download_files=False)
        site_temp.needFile("data/optional.any.iso.piecemap.msgpack")

        with Spy.Spy(Peer, "getFile") as requests:
            for i in range(10):
                site_temp.needFile("%s|%s-%s" % (inner_path, i * 1024 * 1024, (i + 1) * 1024 * 1024))

        assert len(requests) == 10
        for i in range(10):
            assert requests[i][0] == site_temp.peers["Peer:%s" % i]  # Every part should be requested from piece owner peer

    def testDownloadStats(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = ConnectionServer(file_server.ip, 1545)
        site_temp.connection_server = client
        site_temp.addPeer(file_server.ip, 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        # Open virtual file
        assert not site_temp.storage.isFile(inner_path)

        # Check size before downloads
        assert site_temp.settings["size"] < 10 * 1024 * 1024
        assert site_temp.settings["optional_downloaded"] == 0
        size_piecemap = site_temp.content_manager.getFileInfo(inner_path + ".piecemap.msgpack")["size"]
        size_bigfile = site_temp.content_manager.getFileInfo(inner_path)["size"]

        with site_temp.storage.openBigfile(inner_path) as f:
            assert b"\0" not in f.read(1024)
            assert site_temp.settings["optional_downloaded"] == size_piecemap + size_bigfile

        with site_temp.storage.openBigfile(inner_path) as f:
            # Don't count twice
            assert b"\0" not in f.read(1024)
            assert site_temp.settings["optional_downloaded"] == size_piecemap + size_bigfile

            # Add second block
            assert b"\0" not in f.read(1024 * 1024)
            assert site_temp.settings["optional_downloaded"] == size_piecemap + size_bigfile

    def testPrebuffer(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = ConnectionServer(file_server.ip, 1545)
        site_temp.connection_server = client
        site_temp.addPeer(file_server.ip, 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        # Open virtual file
        assert not site_temp.storage.isFile(inner_path)

        with site_temp.storage.openBigfile(inner_path, prebuffer=1024 * 1024 * 2) as f:
            with Spy.Spy(FileRequest, "route") as requests:
                f.seek(5 * 1024 * 1024)
                assert f.read(7) == b"Test524"
            # assert len(requests) == 3  # 1x piecemap + 1x getpiecefield + 1x for pieces
            assert len([task for task in site_temp.worker_manager.tasks if task["inner_path"].startswith(inner_path)]) == 2

            time.sleep(0.5)  # Wait prebuffer download

            sha512 = site.content_manager.getFileInfo(inner_path)["sha512"]
            assert site_temp.storage.piecefields[sha512].tostring() == "0000011100"

            # No prebuffer beyond end of the file
            f.seek(9 * 1024 * 1024)
            assert b"\0" not in f.read(7)

            assert len([task for task in site_temp.worker_manager.tasks if task["inner_path"].startswith(inner_path)]) == 0

    def testDownloadAllPieces(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = ConnectionServer(file_server.ip, 1545)
        site_temp.connection_server = client
        site_temp.addPeer(file_server.ip, 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        # Open virtual file
        assert not site_temp.storage.isFile(inner_path)

        with Spy.Spy(FileRequest, "route") as requests:
            site_temp.needFile("%s|all" % inner_path)

        assert len(requests) == 12  # piecemap.msgpack, getPiecefields, 10 x piece

        # Don't re-download already got pieces
        with Spy.Spy(FileRequest, "route") as requests:
            site_temp.needFile("%s|all" % inner_path)

        assert len(requests) == 0

    def testFileSize(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = ConnectionServer(file_server.ip, 1545)
        site_temp.connection_server = client
        site_temp.addPeer(file_server.ip, 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        # Open virtual file
        assert not site_temp.storage.isFile(inner_path)

        # Download first block
        site_temp.needFile("%s|%s-%s" % (inner_path, 0 * 1024 * 1024, 1 * 1024 * 1024))
        assert site_temp.storage.getSize(inner_path) < 1000 * 1000 * 10  # Size on the disk should be smaller than the real size

        site_temp.needFile("%s|%s-%s" % (inner_path, 9 * 1024 * 1024, 10 * 1024 * 1024))
        assert site_temp.storage.getSize(inner_path) == site.storage.getSize(inner_path)

    def testFileRename(self, file_server, site, site_temp):
        inner_path = self.createBigfile(site)

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        site_temp.connection_server = FileServer(file_server.ip, 1545)
        site_temp.connection_server.sites[site_temp.address] = site_temp
        site_temp.addPeer(file_server.ip, 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        with Spy.Spy(FileRequest, "route") as requests:
            site_temp.needFile("%s|%s-%s" % (inner_path, 0, 1 * self.piece_size))

        assert len([req for req in requests if req[1] == "streamFile"]) == 2  # 1 piece + piecemap

        # Rename the file
        inner_path_new = inner_path.replace(".iso", "-new.iso")
        site.storage.rename(inner_path, inner_path_new)
        site.storage.delete("data/optional.any.iso.piecemap.msgpack")
        assert site.content_manager.sign("content.json", self.privatekey, remove_missing_optional=True)

        files_optional = site.content_manager.contents["content.json"]["files_optional"].keys()

        assert "data/optional.any-new.iso.piecemap.msgpack" in files_optional
        assert "data/optional.any.iso.piecemap.msgpack" not in files_optional
        assert "data/optional.any.iso" not in files_optional

        with Spy.Spy(FileRequest, "route") as requests:
            site.publish()
            time.sleep(0.1)
            site_temp.download(blind_includes=True).join(timeout=5)  # Wait for download

            assert len([req[1] for req in requests if req[1] == "streamFile"]) == 0

            with site_temp.storage.openBigfile(inner_path_new, prebuffer=0) as f:
                f.read(1024)

                # First piece already downloaded
                assert [req for req in requests if req[1] == "streamFile"] == []

                # Second piece needs to be downloaded + changed piecemap
                f.seek(self.piece_size)
                f.read(1024)
                assert [req[3]["inner_path"] for req in requests if req[1] == "streamFile"] == [inner_path_new + ".piecemap.msgpack", inner_path_new]

    @pytest.mark.parametrize("size", [1024 * 3, 1024 * 1024 * 3, 1024 * 1024 * 30])
    def testNullFileRead(self, file_server, site, site_temp, size):
        inner_path = "data/optional.iso"

        f = site.storage.open(inner_path, "w")
        f.write("\0" * size)
        f.close()
        assert site.content_manager.sign("content.json", self.privatekey)

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        site_temp.connection_server = FileServer(file_server.ip, 1545)
        site_temp.connection_server.sites[site_temp.address] = site_temp
        site_temp.addPeer(file_server.ip, 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        if "piecemap" in site.content_manager.getFileInfo(inner_path):  # Bigfile
            site_temp.needFile(inner_path + "|all")
        else:
            site_temp.needFile(inner_path)


        assert site_temp.storage.getSize(inner_path) == size

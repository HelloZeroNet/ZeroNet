import time

import pytest
import mock
import gevent

from Connection import ConnectionServer
from Config import config
from File import FileRequest
from File import FileServer
from Site import Site
import Spy


@pytest.mark.usefixtures("resetTempSettings")
@pytest.mark.usefixtures("resetSettings")
class TestSiteDownload:
    def testDownload(self, file_server, site, site_temp):
        file_server.ip_incoming = {}  # Reset flood protection

        assert site.storage.directory == config.data_dir + "/" + site.address
        assert site_temp.storage.directory == config.data_dir + "-temp/" + site.address

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = ConnectionServer("127.0.0.1", 1545)
        site_temp.connection_server = client
        site_temp.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net

        site_temp.addPeer("127.0.0.1", 1544)
        with Spy.Spy(FileRequest, "route") as requests:
            def boostRequest(inner_path):
                # I really want these file
                if inner_path == "index.html":
                    print "needFile"
                    site_temp.needFile("data/img/multiuser.png", priority=9, blocking=False)
                    site_temp.needFile("data/img/direct_domains.png", priority=10, blocking=False)
            site_temp.onFileDone.append(boostRequest)
            site_temp.download(blind_includes=True).join(timeout=5)
            file_requests = [request[2]["inner_path"] for request in requests if request[0] in ("getFile", "streamFile")]
            # Test priority
            assert file_requests[0:2] == ["content.json", "index.html"]  # Must-have files
            assert file_requests[2:4] == ["data/img/direct_domains.png", "data/img/multiuser.png"]  # Directly requested files
            assert file_requests[4:6] == ["css/all.css", "js/all.js"]  # Important assets
            assert file_requests[6] == "dbschema.json"  # Database map
            assert "-default" in file_requests[-1]  # Put default files for cloning to the end

        # Check files
        bad_files = site_temp.storage.verifyFiles(quick_check=True)

        # -1 because data/users/1J6... user has invalid cert
        assert len(site_temp.content_manager.contents) == len(site.content_manager.contents) - 1
        assert not bad_files

        [connection.close() for connection in file_server.connections]


    # Test when connected peer has the optional file
    def testOptionalDownload(self, file_server, site, site_temp):
        file_server.ip_incoming = {}  # Reset flood protection

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = ConnectionServer("127.0.0.1", 1545)
        site_temp.connection_server = client
        site_temp.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net

        site_temp.addPeer("127.0.0.1", 1544)

        # Download site
        site_temp.download(blind_includes=True).join(timeout=5)

        # Download optional data/optional.txt
        site.storage.verifyFiles(quick_check=True)  # Find what optional files we have
        optional_file_info = site_temp.content_manager.getFileInfo("data/optional.txt")
        assert site.content_manager.hashfield.hasHash(optional_file_info["sha512"])
        assert not site_temp.content_manager.hashfield.hasHash(optional_file_info["sha512"])

        assert not site_temp.storage.isFile("data/optional.txt")
        assert site.storage.isFile("data/optional.txt")
        site_temp.needFile("data/optional.txt")
        assert site_temp.storage.isFile("data/optional.txt")

        # Optional user file
        assert not site_temp.storage.isFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")
        optional_file_info = site_temp.content_manager.getFileInfo(
            "data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif"
        )
        assert site.content_manager.hashfield.hasHash(optional_file_info["sha512"])
        assert not site_temp.content_manager.hashfield.hasHash(optional_file_info["sha512"])

        site_temp.needFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")
        assert site_temp.storage.isFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")
        assert site_temp.content_manager.hashfield.hasHash(optional_file_info["sha512"])

        assert site_temp.storage.deleteFiles()
        [connection.close() for connection in file_server.connections]

    # Test when connected peer does not has the file, so ask him if he know someone who has it
    def testFindOptional(self, file_server, site, site_temp):
        file_server.ip_incoming = {}  # Reset flood protection

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init full source server (has optional files)
        site_full = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")
        file_server_full = FileServer("127.0.0.1", 1546)
        site_full.connection_server = file_server_full
        gevent.spawn(lambda: ConnectionServer.start(file_server_full))
        time.sleep(0.001)  # Port opening
        file_server_full.sites[site_full.address] = site_full  # Add site
        site_full.storage.verifyFiles(quick_check=True)  # Check optional files
        site_full_peer = site.addPeer("127.0.0.1", 1546)  # Add it to source server
        assert site_full_peer.updateHashfield()  # Update hashfield

        # Init client server
        site_temp.connection_server = ConnectionServer("127.0.0.1", 1545)
        site_temp.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net
        site_temp.addPeer("127.0.0.1", 1544)  # Add source server

        # Download normal files
        site_temp.download(blind_includes=True).join(timeout=5)

        # Download optional data/optional.txt
        optional_file_info = site_temp.content_manager.getFileInfo("data/optional.txt")
        assert not site_temp.storage.isFile("data/optional.txt")
        assert not site.content_manager.hashfield.hasHash(optional_file_info["sha512"])  # Source server don't know he has the file
        assert site_full_peer.hashfield.hasHash(optional_file_info["sha512"])  # Source full peer on source server has the file
        assert site_full.content_manager.hashfield.hasHash(optional_file_info["sha512"])  # Source full server he has the file

        with Spy.Spy(FileRequest, "route") as requests:
            # Request 2 file same time
            threads = []
            threads.append(site_temp.needFile("data/optional.txt", blocking=False))
            threads.append(site_temp.needFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif", blocking=False))
            gevent.joinall(threads)

            assert len([request for request in requests if request[0] == "findHashIds"]) == 1  # findHashids should call only once

        assert site_temp.storage.isFile("data/optional.txt")
        assert site_temp.storage.isFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")

        assert site_temp.storage.deleteFiles()
        file_server_full.stop()
        [connection.close() for connection in file_server.connections]

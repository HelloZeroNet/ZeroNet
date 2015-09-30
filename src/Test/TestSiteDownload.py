import pytest
import mock
import time

from Connection import ConnectionServer
from Config import config
from Site import Site
from File import FileRequest
import Spy

@pytest.mark.usefixtures("resetTempSettings")
@pytest.mark.usefixtures("resetSettings")
class TestWorker:
    def testDownload(self, file_server, site, site_temp):
        client = ConnectionServer("127.0.0.1", 1545)
        assert site.storage.directory == config.data_dir + "/" + site.address
        assert site_temp.storage.directory == config.data_dir + "-temp/" + site.address

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
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

        # Optional file
        assert not site_temp.storage.isFile("data/optional.txt")
        assert site.storage.isFile("data/optional.txt")
        site_temp.needFile("data/optional.txt")
        assert site_temp.storage.isFile("data/optional.txt")

        # Optional user file
        assert not site_temp.storage.isFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")
        site_temp.needFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")
        assert site_temp.storage.isFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")

        assert site_temp.storage.deleteFiles()

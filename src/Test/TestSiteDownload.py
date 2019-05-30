import time

import pytest
import mock
import gevent
import os

from Connection import ConnectionServer
from Config import config
from File import FileRequest
from File import FileServer
from Site.Site import Site
from . import Spy


@pytest.mark.usefixtures("resetTempSettings")
@pytest.mark.usefixtures("resetSettings")
class TestSiteDownload:
    def testRename(self, file_server, site, site_temp):
        assert site.storage.directory == config.data_dir + "/" + site.address
        assert site_temp.storage.directory == config.data_dir + "-temp/" + site.address

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = FileServer(file_server.ip, 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client
        site_temp.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net


        site_temp.addPeer(file_server.ip, 1544)

        site_temp.download(blind_includes=True).join(timeout=5)

        # Rename non-optional file
        os.rename(site.storage.getPath("data/img/domain.png"), site.storage.getPath("data/img/domain-new.png"))

        site.content_manager.sign("content.json", privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv")

        content = site.storage.loadJson("content.json")
        assert "data/img/domain-new.png" in content["files"]
        assert "data/img/domain.png" not in content["files"]
        assert not site_temp.storage.isFile("data/img/domain-new.png")
        assert site_temp.storage.isFile("data/img/domain.png")
        settings_before = site_temp.settings

        with Spy.Spy(FileRequest, "route") as requests:
            site.publish()
            time.sleep(0.1)
            site_temp.download(blind_includes=True).join(timeout=5)  # Wait for download
            assert "streamFile" not in [req[1] for req in requests]

        content = site_temp.storage.loadJson("content.json")
        assert "data/img/domain-new.png" in content["files"]
        assert "data/img/domain.png" not in content["files"]
        assert site_temp.storage.isFile("data/img/domain-new.png")
        assert not site_temp.storage.isFile("data/img/domain.png")

        assert site_temp.settings["size"] == settings_before["size"]
        assert site_temp.settings["size_optional"] == settings_before["size_optional"]

        assert site_temp.storage.deleteFiles()
        [connection.close() for connection in file_server.connections]

    def testRenameOptional(self, file_server, site, site_temp):
        assert site.storage.directory == config.data_dir + "/" + site.address
        assert site_temp.storage.directory == config.data_dir + "-temp/" + site.address

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = FileServer(file_server.ip, 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client
        site_temp.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net


        site_temp.addPeer(file_server.ip, 1544)

        site_temp.download(blind_includes=True).join(timeout=5)

        assert site_temp.settings["optional_downloaded"] == 0

        site_temp.needFile("data/optional.txt")

        assert site_temp.settings["optional_downloaded"] > 0
        settings_before = site_temp.settings
        hashfield_before = site_temp.content_manager.hashfield.tobytes()

        # Rename optional file
        os.rename(site.storage.getPath("data/optional.txt"), site.storage.getPath("data/optional-new.txt"))

        site.content_manager.sign("content.json", privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv", remove_missing_optional=True)

        content = site.storage.loadJson("content.json")
        assert "data/optional-new.txt" in content["files_optional"]
        assert "data/optional.txt" not in content["files_optional"]
        assert not site_temp.storage.isFile("data/optional-new.txt")
        assert site_temp.storage.isFile("data/optional.txt")

        with Spy.Spy(FileRequest, "route") as requests:
            site.publish()
            time.sleep(0.1)
            site_temp.download(blind_includes=True).join(timeout=5)  # Wait for download
            assert "streamFile" not in [req[1] for req in requests]

        content = site_temp.storage.loadJson("content.json")
        assert "data/optional-new.txt" in content["files_optional"]
        assert "data/optional.txt" not in content["files_optional"]
        assert site_temp.storage.isFile("data/optional-new.txt")
        assert not site_temp.storage.isFile("data/optional.txt")

        assert site_temp.settings["size"] == settings_before["size"]
        assert site_temp.settings["size_optional"] == settings_before["size_optional"]
        assert site_temp.settings["optional_downloaded"] == settings_before["optional_downloaded"]
        assert site_temp.content_manager.hashfield.tobytes() == hashfield_before

        assert site_temp.storage.deleteFiles()
        [connection.close() for connection in file_server.connections]


    def testArchivedDownload(self, file_server, site, site_temp):
        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = FileServer(file_server.ip, 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client

        # Download normally
        site_temp.addPeer(file_server.ip, 1544)
        site_temp.download(blind_includes=True).join(timeout=5)
        bad_files = site_temp.storage.verifyFiles(quick_check=True)["bad_files"]

        assert not bad_files
        assert "data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json" in site_temp.content_manager.contents
        assert site_temp.storage.isFile("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json")
        assert len(list(site_temp.storage.query("SELECT * FROM comment"))) == 2

        # Add archived data
        assert not "archived" in site.content_manager.contents["data/users/content.json"]["user_contents"]
        assert not site.content_manager.isArchived("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json", time.time()-1)

        site.content_manager.contents["data/users/content.json"]["user_contents"]["archived"] = {"1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q": time.time()}
        site.content_manager.sign("data/users/content.json", privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv")

        date_archived = site.content_manager.contents["data/users/content.json"]["user_contents"]["archived"]["1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q"]
        assert site.content_manager.isArchived("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json", date_archived-1)
        assert site.content_manager.isArchived("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json", date_archived)
        assert not site.content_manager.isArchived("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json", date_archived+1)  # Allow user to update archived data later

        # Push archived update
        assert not "archived" in site_temp.content_manager.contents["data/users/content.json"]["user_contents"]
        site.publish()
        time.sleep(0.1)
        site_temp.download(blind_includes=True).join(timeout=5)  # Wait for download

        # The archived content should disappear from remote client
        assert "archived" in site_temp.content_manager.contents["data/users/content.json"]["user_contents"]
        assert "data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json" not in site_temp.content_manager.contents
        assert not site_temp.storage.isDir("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q")
        assert len(list(site_temp.storage.query("SELECT * FROM comment"))) == 1
        assert len(list(site_temp.storage.query("SELECT * FROM json WHERE directory LIKE '%1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q%'"))) == 0

        assert site_temp.storage.deleteFiles()
        [connection.close() for connection in file_server.connections]

    def testArchivedBeforeDownload(self, file_server, site, site_temp):
        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = FileServer(file_server.ip, 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client

        # Download normally
        site_temp.addPeer(file_server.ip, 1544)
        site_temp.download(blind_includes=True).join(timeout=5)
        bad_files = site_temp.storage.verifyFiles(quick_check=True)["bad_files"]

        assert not bad_files
        assert "data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json" in site_temp.content_manager.contents
        assert site_temp.storage.isFile("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json")
        assert len(list(site_temp.storage.query("SELECT * FROM comment"))) == 2

        # Add archived data
        assert not "archived_before" in site.content_manager.contents["data/users/content.json"]["user_contents"]
        assert not site.content_manager.isArchived("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json", time.time()-1)

        content_modification_time = site.content_manager.contents["data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json"]["modified"]
        site.content_manager.contents["data/users/content.json"]["user_contents"]["archived_before"] = content_modification_time
        site.content_manager.sign("data/users/content.json", privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv")

        date_archived = site.content_manager.contents["data/users/content.json"]["user_contents"]["archived_before"]
        assert site.content_manager.isArchived("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json", date_archived-1)
        assert site.content_manager.isArchived("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json", date_archived)
        assert not site.content_manager.isArchived("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json", date_archived+1)  # Allow user to update archived data later

        # Push archived update
        assert not "archived_before" in site_temp.content_manager.contents["data/users/content.json"]["user_contents"]
        site.publish()
        time.sleep(0.1)
        site_temp.download(blind_includes=True).join(timeout=5)  # Wait for download

        # The archived content should disappear from remote client
        assert "archived_before" in site_temp.content_manager.contents["data/users/content.json"]["user_contents"]
        assert "data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json" not in site_temp.content_manager.contents
        assert not site_temp.storage.isDir("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q")
        assert len(list(site_temp.storage.query("SELECT * FROM comment"))) == 1
        assert len(list(site_temp.storage.query("SELECT * FROM json WHERE directory LIKE '%1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q%'"))) == 0

        assert site_temp.storage.deleteFiles()
        [connection.close() for connection in file_server.connections]


    # Test when connected peer has the optional file
    def testOptionalDownload(self, file_server, site, site_temp):
        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = ConnectionServer(file_server.ip, 1545)
        site_temp.connection_server = client
        site_temp.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net

        site_temp.addPeer(file_server.ip, 1544)

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
        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init full source server (has optional files)
        site_full = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")
        file_server_full = FileServer(file_server.ip, 1546)
        site_full.connection_server = file_server_full

        def listen():
            ConnectionServer.start(file_server_full)
            ConnectionServer.listen(file_server_full)

        gevent.spawn(listen)
        time.sleep(0.001)  # Port opening
        file_server_full.sites[site_full.address] = site_full  # Add site
        site_full.storage.verifyFiles(quick_check=True)  # Check optional files
        site_full_peer = site.addPeer(file_server.ip, 1546)  # Add it to source server
        hashfield = site_full_peer.updateHashfield()  # Update hashfield
        assert len(site_full.content_manager.hashfield) == 8
        assert hashfield
        assert site_full.storage.isFile("data/optional.txt")
        assert site_full.storage.isFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")
        assert len(site_full_peer.hashfield) == 8

        # Remove hashes from source server
        for hash in list(site.content_manager.hashfield):
            site.content_manager.hashfield.remove(hash)

        # Init client server
        site_temp.connection_server = ConnectionServer(file_server.ip, 1545)
        site_temp.addPeer(file_server.ip, 1544)  # Add source server

        # Download normal files
        site_temp.log.info("Start Downloading site")
        site_temp.download(blind_includes=True).join(timeout=5)

        # Download optional data/optional.txt
        optional_file_info = site_temp.content_manager.getFileInfo("data/optional.txt")
        optional_file_info2 = site_temp.content_manager.getFileInfo("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")
        assert not site_temp.storage.isFile("data/optional.txt")
        assert not site_temp.storage.isFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")
        assert not site.content_manager.hashfield.hasHash(optional_file_info["sha512"])  # Source server don't know he has the file
        assert not site.content_manager.hashfield.hasHash(optional_file_info2["sha512"])  # Source server don't know he has the file
        assert site_full_peer.hashfield.hasHash(optional_file_info["sha512"])  # Source full peer on source server has the file
        assert site_full_peer.hashfield.hasHash(optional_file_info2["sha512"])  # Source full peer on source server has the file
        assert site_full.content_manager.hashfield.hasHash(optional_file_info["sha512"])  # Source full server he has the file
        assert site_full.content_manager.hashfield.hasHash(optional_file_info2["sha512"])  # Source full server he has the file

        site_temp.log.info("Request optional files")
        with Spy.Spy(FileRequest, "route") as requests:
            # Request 2 file same time
            threads = []
            threads.append(site_temp.needFile("data/optional.txt", blocking=False))
            threads.append(site_temp.needFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif", blocking=False))
            gevent.joinall(threads)

            assert len([request for request in requests if request[1] == "findHashIds"]) == 1  # findHashids should call only once

        assert site_temp.storage.isFile("data/optional.txt")
        assert site_temp.storage.isFile("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")

        assert site_temp.storage.deleteFiles()
        file_server_full.stop()
        [connection.close() for connection in file_server.connections]
        site_full.content_manager.contents.db.close()

    def testUpdate(self, file_server, site, site_temp):
        assert site.storage.directory == config.data_dir + "/" + site.address
        assert site_temp.storage.directory == config.data_dir + "-temp/" + site.address

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = FileServer(file_server.ip, 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client

        # Don't try to find peers from the net
        site.announce = mock.MagicMock(return_value=True)
        site_temp.announce = mock.MagicMock(return_value=True)

        # Connect peers
        site_temp.addPeer(file_server.ip, 1544)

        # Download site from site to site_temp
        site_temp.download(blind_includes=True).join(timeout=5)

        # Update file
        data_original = site.storage.open("data/data.json").read()
        data_new = data_original.replace(b'"ZeroBlog"', b'"UpdatedZeroBlog"')
        assert data_original != data_new

        site.storage.open("data/data.json", "wb").write(data_new)

        assert site.storage.open("data/data.json").read() == data_new
        assert site_temp.storage.open("data/data.json").read() == data_original

        site.log.info("Publish new data.json without patch")
        # Publish without patch
        with Spy.Spy(FileRequest, "route") as requests:
            site.content_manager.sign("content.json", privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv")
            site.publish()
            time.sleep(0.1)
            site_temp.download(blind_includes=True).join(timeout=5)
            assert len([request for request in requests if request[1] in ("getFile", "streamFile")]) == 1

        assert site_temp.storage.open("data/data.json").read() == data_new

        # Close connection to avoid update spam limit
        list(site.peers.values())[0].remove()
        site.addPeer(file_server.ip, 1545)
        list(site_temp.peers.values())[0].ping()  # Connect back
        time.sleep(0.1)

        # Update with patch
        data_new = data_original.replace(b'"ZeroBlog"', b'"PatchedZeroBlog"')
        assert data_original != data_new

        site.storage.open("data/data.json-new", "wb").write(data_new)

        assert site.storage.open("data/data.json-new").read() == data_new
        assert site_temp.storage.open("data/data.json").read() != data_new

        # Generate diff
        diffs = site.content_manager.getDiffs("content.json")
        assert not site.storage.isFile("data/data.json-new")  # New data file removed
        assert site.storage.open("data/data.json").read() == data_new  # -new postfix removed
        assert "data/data.json" in diffs
        assert diffs["data/data.json"] == [('=', 2), ('-', 29), ('+', [b'\t"title": "PatchedZeroBlog",\n']), ('=', 31102)]

        # Publish with patch
        site.log.info("Publish new data.json with patch")
        with Spy.Spy(FileRequest, "route") as requests:
            site.content_manager.sign("content.json", privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv")
            site.publish(diffs=diffs)
            site_temp.download(blind_includes=True).join(timeout=5)
            assert len([request for request in requests if request[1] in ("getFile", "streamFile")]) == 0

        assert site_temp.storage.open("data/data.json").read() == data_new

        assert site_temp.storage.deleteFiles()
        [connection.close() for connection in file_server.connections]

    def testBigUpdate(self, file_server, site, site_temp):
        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        client = FileServer(file_server.ip, 1545)
        client.sites[site_temp.address] = site_temp
        site_temp.connection_server = client

        # Connect peers
        site_temp.addPeer(file_server.ip, 1544)

        # Download site from site to site_temp
        site_temp.download(blind_includes=True).join(timeout=5)

        # Update file
        data_original = site.storage.open("data/data.json").read()
        data_new = data_original.replace(b'"ZeroBlog"', b'"PatchedZeroBlog"')
        assert data_original != data_new

        site.storage.open("data/data.json-new", "wb").write(data_new)

        assert site.storage.open("data/data.json-new").read() == data_new
        assert site_temp.storage.open("data/data.json").read() != data_new

        # Generate diff
        diffs = site.content_manager.getDiffs("content.json")
        assert not site.storage.isFile("data/data.json-new")  # New data file removed
        assert site.storage.open("data/data.json").read() == data_new  # -new postfix removed
        assert "data/data.json" in diffs

        content_json = site.storage.loadJson("content.json")
        content_json["title"] = "BigZeroBlog" * 1024 * 10
        site.storage.writeJson("content.json", content_json)
        site.content_manager.loadContent("content.json", force=True)

        # Publish with patch
        site.log.info("Publish new data.json with patch")
        with Spy.Spy(FileRequest, "route") as requests:
            site.content_manager.sign("content.json", privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv")
            assert site.storage.getSize("content.json") > 10 * 1024  # Make it a big content.json
            site.publish(diffs=diffs)
            site_temp.download(blind_includes=True).join(timeout=5)
            file_requests = [request for request in requests if request[1] in ("getFile", "streamFile")]
            assert len(file_requests) == 1

        assert site_temp.storage.open("data/data.json").read() == data_new

import hashlib
import os
import copy

import pytest

from OptionalManager import OptionalManagerPlugin
from util import helper


@pytest.mark.usefixtures("resetSettings")
class TestOptionalManager:
    def testDbFill(self, site):
        contents = site.content_manager.contents
        assert len(site.content_manager.hashfield) > 0
        assert contents.db.execute("SELECT COUNT(*) FROM file_optional WHERE is_downloaded = 1").fetchone()[0] == len(site.content_manager.hashfield)

    def testSetContent(self, site):
        contents = site.content_manager.contents

        # Add new file
        new_content = copy.deepcopy(contents["content.json"])
        new_content["files_optional"]["testfile"] = {
            "size": 1234,
            "sha512": "aaaabbbbcccc"
        }
        num_optional_files_before = contents.db.execute("SELECT COUNT(*) FROM file_optional").fetchone()[0]
        contents["content.json"] = new_content
        assert contents.db.execute("SELECT COUNT(*) FROM file_optional").fetchone()[0] > num_optional_files_before

        # Remove file
        new_content = copy.deepcopy(contents["content.json"])
        del new_content["files_optional"]["testfile"]
        num_optional_files_before = contents.db.execute("SELECT COUNT(*) FROM file_optional").fetchone()[0]
        contents["content.json"] = new_content
        assert contents.db.execute("SELECT COUNT(*) FROM file_optional").fetchone()[0] < num_optional_files_before

    def testDeleteContent(self, site):
        contents = site.content_manager.contents
        num_optional_files_before = contents.db.execute("SELECT COUNT(*) FROM file_optional").fetchone()[0]
        del contents["content.json"]
        assert contents.db.execute("SELECT COUNT(*) FROM file_optional").fetchone()[0] < num_optional_files_before

    def testVerifyFiles(self, site):
        contents = site.content_manager.contents

        # Add new file
        new_content = copy.deepcopy(contents["content.json"])
        new_content["files_optional"]["testfile"] = {
            "size": 1234,
            "sha512": "aaaabbbbcccc"
        }
        contents["content.json"] = new_content
        file_row = contents.db.execute("SELECT * FROM file_optional WHERE inner_path = 'testfile'").fetchone()
        assert not file_row["is_downloaded"]

        # Write file from outside of ZeroNet
        site.storage.open("testfile", "wb").write("A" * 1234)  # For quick check hash does not matter only file size

        hashfield_len_before = len(site.content_manager.hashfield)
        site.storage.verifyFiles(quick_check=True)
        assert len(site.content_manager.hashfield) == hashfield_len_before + 1

        file_row = contents.db.execute("SELECT * FROM file_optional WHERE inner_path = 'testfile'").fetchone()
        assert file_row["is_downloaded"]

        # Delete file outside of ZeroNet
        site.storage.delete("testfile")
        site.storage.verifyFiles(quick_check=True)
        file_row = contents.db.execute("SELECT * FROM file_optional WHERE inner_path = 'testfile'").fetchone()
        assert not file_row["is_downloaded"]

    def testVerifyFilesSameHashId(self, site):
        contents = site.content_manager.contents

        new_content = copy.deepcopy(contents["content.json"])

        # Add two files with same hashid (first 4 character)
        new_content["files_optional"]["testfile1"] = {
            "size": 1234,
            "sha512": "aaaabbbbcccc"
        }
        new_content["files_optional"]["testfile2"] = {
            "size": 2345,
            "sha512": "aaaabbbbdddd"
        }
        contents["content.json"] = new_content

        assert site.content_manager.hashfield.getHashId("aaaabbbbcccc") == site.content_manager.hashfield.getHashId("aaaabbbbdddd")

        # Write files from outside of ZeroNet (For quick check hash does not matter only file size)
        site.storage.open("testfile1", "wb").write("A" * 1234)
        site.storage.open("testfile2", "wb").write("B" * 2345)

        site.storage.verifyFiles(quick_check=True)

        # Make sure that both is downloaded
        assert site.content_manager.isDownloaded("testfile1")
        assert site.content_manager.isDownloaded("testfile2")
        assert site.content_manager.hashfield.getHashId("aaaabbbbcccc") in site.content_manager.hashfield

        # Delete one of the files
        site.storage.delete("testfile1")
        site.storage.verifyFiles(quick_check=True)
        assert not site.content_manager.isDownloaded("testfile1")
        assert site.content_manager.isDownloaded("testfile2")
        assert site.content_manager.hashfield.getHashId("aaaabbbbdddd") in site.content_manager.hashfield

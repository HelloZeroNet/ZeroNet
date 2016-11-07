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

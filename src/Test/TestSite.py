import shutil
import os

import pytest
from Site import SiteManager


@pytest.mark.usefixtures("resetSettings")
class TestSite:
    def testClone(self, site):
        assert site.storage.directory == "src/Test/testdata/1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT"

        # Remove old files
        if os.path.isdir("src/Test/testdata/159EGD5srUsMP97UpcLy8AtKQbQLK2AbbL"):
            shutil.rmtree("src/Test/testdata/159EGD5srUsMP97UpcLy8AtKQbQLK2AbbL")
        assert not os.path.isfile("src/Test/testdata/159EGD5srUsMP97UpcLy8AtKQbQLK2AbbL/content.json")

        # Clone 1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT to 15E5rhcAUD69WbiYsYARh4YHJ4sLm2JEyc
        new_site = site.clone(
            "159EGD5srUsMP97UpcLy8AtKQbQLK2AbbL", "5JU2p5h3R7B1WrbaEdEDNZR7YHqRLGcjNcqwqVQzX2H4SuNe2ee", address_index=1
        )

        # Check if clone was successful
        assert new_site.address == "159EGD5srUsMP97UpcLy8AtKQbQLK2AbbL"
        assert new_site.storage.isFile("content.json")
        assert new_site.storage.isFile("index.html")
        assert new_site.storage.isFile("data/users/content.json")
        assert new_site.storage.isFile("data/zeroblog.db")
        assert new_site.storage.verifyFiles() == []  # No bad files allowed
        assert new_site.storage.query("SELECT * FROM keyvalue WHERE key = 'title'").fetchone()["value"] == "MyZeroBlog"

        # Test re-cloning (updating)

        # Changes in non-data files should be overwritten
        new_site.storage.write("index.html", "this will be overwritten")
        assert new_site.storage.read("index.html"), "this will be overwritten"

        # Changes in data file should be kept after re-cloning
        changed_contentjson = new_site.storage.loadJson("content.json")
        changed_contentjson["description"] = "Update Description Test"
        new_site.storage.writeJson("content.json", changed_contentjson)

        changed_data = new_site.storage.loadJson("data/data.json")
        changed_data["title"] = "UpdateTest"
        new_site.storage.writeJson("data/data.json", changed_data)

        # The update should be reflected to database
        assert new_site.storage.query("SELECT * FROM keyvalue WHERE key = 'title'").fetchone()["value"] == "UpdateTest"

        # Re-clone the site
        site.clone("159EGD5srUsMP97UpcLy8AtKQbQLK2AbbL")

        assert new_site.storage.loadJson("data/data.json")["title"] == "UpdateTest"
        assert new_site.storage.loadJson("content.json")["description"] == "Update Description Test"
        assert new_site.storage.read("index.html") != "this will be overwritten"

        # Delete created files
        new_site.storage.deleteFiles()
        assert not os.path.isdir("src/Test/testdata/159EGD5srUsMP97UpcLy8AtKQbQLK2AbbL")

        # Delete from site registry
        assert new_site.address in SiteManager.site_manager.sites
        SiteManager.site_manager.delete(new_site.address)
        assert new_site.address not in SiteManager.site_manager.sites

    @pytest.mark.parametrize("inner_path", ["content.json", "data/test_include/content.json", "data/users/content.json"])
    def testSign(self, site, inner_path):
        # Bad privatekey
        assert not site.content_manager.sign(inner_path, privatekey="5aaa3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMnaa", filewrite=False)

        # Good privatekey
        content = site.content_manager.sign(inner_path, privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv", filewrite=False)
        content_old = site.content_manager.contents[inner_path]  # Content before the sign
        assert not content_old == content  # Timestamp changed
        assert site.address in content["signs"]  # Used the site's private key to sign
        if inner_path == "content.json":
            assert len(content["files"]) == 24
        elif inner_path == "data/test-include/content.json":
            assert len(content["files"]) == 1
        elif inner_path == "data/users/content.json":
            assert len(content["files"]) == 0

        # Everything should be same as before except the modified timestamp and the signs
        assert (
            {key: val for key, val in content_old.items() if key not in ["modified", "signs", "sign"]}
            ==
            {key: val for key, val in content.items() if key not in ["modified", "signs", "sign"]}
        )

    def testSignOptionalFiles(self, site):
        site.content_manager.contents["content.json"]["optional"] = "((data/img/zero.*))"
        content_optional = site.content_manager.sign(privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv", filewrite=False)

        del site.content_manager.contents["content.json"]["optional"]
        content_nooptional = site.content_manager.sign(privatekey="5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv", filewrite=False)

        assert len(content_nooptional["files"]) > len(content_optional["files"])

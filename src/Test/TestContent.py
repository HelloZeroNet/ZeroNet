import json
import time
from cStringIO import StringIO

import pytest

from Crypt import CryptBitcoin


@pytest.mark.usefixtures("resetSettings")
class TestContent:
    def testInclude(self, site):
        # Rules defined in parent content.json
        rules = site.content_manager.getRules("data/test_include/content.json")

        assert rules["signers"] == ["15ik6LeBWnACWfaika1xqGapRZ1zh3JpCo"]  # Valid signer
        assert rules["user_name"] == "test"  # Extra data
        assert rules["max_size"] == 20000  # Max size of files
        assert not rules["includes_allowed"]  # Don't allow more includes
        assert rules["files_allowed"] == "data.json"  # Allowed file pattern

        # Valid signers for "data/test_include/content.json"
        valid_signers = site.content_manager.getValidSigners("data/test_include/content.json")
        assert "15ik6LeBWnACWfaika1xqGapRZ1zh3JpCo" in valid_signers  # Extra valid signer defined in parent content.json
        assert "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT" in valid_signers  # The site itself
        assert len(valid_signers) == 2  # No more

        # Valid signers for "data/users/content.json"
        valid_signers = site.content_manager.getValidSigners("data/users/content.json")
        assert "1LSxsKfC9S9TVXGGNSM3vPHjyW82jgCX5f" in valid_signers  # Extra valid signer defined in parent content.json
        assert "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT" in valid_signers  # The site itself
        assert len(valid_signers) == 2

        # Valid signers for root content.json
        assert site.content_manager.getValidSigners("content.json") == ["1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT"]

    def testInlcudeLimits(self, site):
        privatekey = "5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv"
        # Data validation
        data_dict = {
            "files": {
                "data.json": {
                    "sha512": "369d4e780cc80504285f13774ca327fe725eed2d813aad229e62356b07365906",
                    "size": 505
                }
            },
            "modified": time.time()
        }

        # Normal data
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict), privatekey)}
        data = StringIO(json.dumps(data_dict))
        assert site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        # Reset
        del data_dict["signs"]

        # Too large
        data_dict["files"]["data.json"]["size"] = 200000  # Emulate 2MB sized data.json
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict), privatekey)}
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        # Reset
        data_dict["files"]["data.json"]["size"] = 505
        del data_dict["signs"]

        # Not allowed file
        data_dict["files"]["notallowed.exe"] = data_dict["files"]["data.json"]
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict), privatekey)}
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        # Reset
        del data_dict["files"]["notallowed.exe"]
        del data_dict["signs"]

        # Should work again
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict), privatekey)}
        data = StringIO(json.dumps(data_dict))
        assert site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)

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
            assert len(content["files"]) == 17
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

        assert len(content_nooptional.get("files_optional", {})) == 0
        assert len(content_optional["files_optional"]) > 0
        assert len(content_nooptional["files"]) > len(content_optional["files"])

    def testFileInfo(self, site):
        assert "sha512" in site.content_manager.getFileInfo("index.html")
        assert not site.content_manager.getFileInfo("notexist")

        # Optional file
        file_info_optional = site.content_manager.getFileInfo("data/optional.txt")
        assert "sha512" in file_info_optional
        assert file_info_optional["optional"] is True

        # Not exists yet user content.json
        assert "cert_signers" in site.content_manager.getFileInfo("data/users/unknown/content.json")

        # Optional user file
        file_info_optional = site.content_manager.getFileInfo("data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/peanut-butter-jelly-time.gif")
        assert "sha512" in file_info_optional
        assert file_info_optional["optional"] is True

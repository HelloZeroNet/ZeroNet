import json
import time
from cStringIO import StringIO

import pytest

from Crypt import CryptBitcoin


@pytest.mark.usefixtures("resetSettings")
class TestContent:
    def testIncludes(self, site):
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

    def testLimits(self, site):
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
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict), privatekey) }
        data = StringIO(json.dumps(data_dict))
        assert site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        # Reset
        del data_dict["signs"]

        # Too large
        data_dict["files"]["data.json"]["size"] = 200000  # Emulate 2MB sized data.json
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict), privatekey) }
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        # Reset
        data_dict["files"]["data.json"]["size"] = 505
        del data_dict["signs"]

        # Not allowed file
        data_dict["files"]["notallowed.exe"] = data_dict["files"]["data.json"]
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict), privatekey) }
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        # Reset
        del data_dict["files"]["notallowed.exe"]
        del data_dict["signs"]

        # Should work again
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict), privatekey) }
        data = StringIO(json.dumps(data_dict))
        assert site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)

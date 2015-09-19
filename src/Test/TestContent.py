import json
from cStringIO import StringIO

import pytest


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

    def testSizelimit(self, site):
        # Data validation
        data_dict = {
            "files": {
                "data.json": {
                    "sha512": "369d4e780cc80504285f13774ca327fe725eed2d813aad229e62356b07365906",
                    "size": 505
                }
            },
            "modified": 1431451896.656619,
            "signs": {
                "15ik6LeBWnACWfaika1xqGapRZ1zh3JpCo":
                    "G2QC+ZIozPQQ/XiOEOMzfekOP8ipi+rKaTy/R/3MnDf98mLIhSSA8927FW6D/ZyP7HHuII2y9d0zbAk+rr8ksQM="
            }
        }
        data = StringIO(json.dumps(data_dict))

        # Normal data
        assert site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)

        # Too large
        data_dict["files"]["data.json"]["size"] = 200000  # Emulate 2MB sized data.json
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        data_dict["files"]["data.json"]["size"] = 505  # Reset

        # Not allowed file
        data_dict["files"]["notallowed.exe"] = data_dict["files"]["data.json"]
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        del data_dict["files"]["notallowed.exe"]  # Reset

        # Should work again
        data = StringIO(json.dumps(data_dict))
        assert site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)

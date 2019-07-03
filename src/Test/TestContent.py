import json
import time
import io

import pytest

from Crypt import CryptBitcoin
from Content.ContentManager import VerifyError, SignError
from util.SafeRe import UnsafePatternError


@pytest.mark.usefixtures("resetSettings")
class TestContent:
    privatekey = "5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv"

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

    def testInlcudeLimits(self, site, crypt_bitcoin_lib):
        # Data validation
        res = []
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
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)}
        data_json = json.dumps(data_dict).encode()
        data = io.BytesIO(data_json)
        assert site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)

        # Reset
        del data_dict["signs"]

        # Too large
        data_dict["files"]["data.json"]["size"] = 200000  # Emulate 2MB sized data.json
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)}
        data = io.BytesIO(json.dumps(data_dict).encode())
        with pytest.raises(VerifyError) as err:
            site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        assert "Include too large" in str(err.value)

        # Reset
        data_dict["files"]["data.json"]["size"] = 505
        del data_dict["signs"]

        # Not allowed file
        data_dict["files"]["notallowed.exe"] = data_dict["files"]["data.json"]
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)}
        data = io.BytesIO(json.dumps(data_dict).encode())
        with pytest.raises(VerifyError) as err:
            site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        assert "File not allowed" in str(err.value)

        # Reset
        del data_dict["files"]["notallowed.exe"]
        del data_dict["signs"]

        # Should work again
        data_dict["signs"] = {"1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)}
        data = io.BytesIO(json.dumps(data_dict).encode())
        assert site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)

    @pytest.mark.parametrize("inner_path", ["content.json", "data/test_include/content.json", "data/users/content.json"])
    def testSign(self, site, inner_path):
        # Bad privatekey
        with pytest.raises(SignError) as err:
            site.content_manager.sign(inner_path, privatekey="5aaa3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMnaa", filewrite=False)
        assert "Private key invalid" in str(err.value)

        # Good privatekey
        content = site.content_manager.sign(inner_path, privatekey=self.privatekey, filewrite=False)
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
            {key: val for key, val in content_old.items() if key not in ["modified", "signs", "sign", "zeronet_version"]}
            ==
            {key: val for key, val in content.items() if key not in ["modified", "signs", "sign", "zeronet_version"]}
        )

    def testSignOptionalFiles(self, site):
        for hash in list(site.content_manager.hashfield):
            site.content_manager.hashfield.remove(hash)

        assert len(site.content_manager.hashfield) == 0

        site.content_manager.contents["content.json"]["optional"] = "((data/img/zero.*))"
        content_optional = site.content_manager.sign(privatekey=self.privatekey, filewrite=False, remove_missing_optional=True)

        del site.content_manager.contents["content.json"]["optional"]
        content_nooptional = site.content_manager.sign(privatekey=self.privatekey, filewrite=False, remove_missing_optional=True)

        assert len(content_nooptional.get("files_optional", {})) == 0  # No optional files if no pattern
        assert len(content_optional["files_optional"]) > 0
        assert len(site.content_manager.hashfield) == len(content_optional["files_optional"])  # Hashed optional files should be added to hashfield
        assert len(content_nooptional["files"]) > len(content_optional["files"])

    def testFileInfo(self, site):
        assert "sha512" in site.content_manager.getFileInfo("index.html")
        assert site.content_manager.getFileInfo("data/img/domain.png")["content_inner_path"] == "content.json"
        assert site.content_manager.getFileInfo("data/users/hello.png")["content_inner_path"] == "data/users/content.json"
        assert site.content_manager.getFileInfo("data/users/content.json")["content_inner_path"] == "data/users/content.json"
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

    def testVerify(self, site, crypt_bitcoin_lib):
        inner_path = "data/test_include/content.json"
        data_dict = site.storage.loadJson(inner_path)
        data = io.BytesIO(json.dumps(data_dict).encode("utf8"))

        # Re-sign
        data_dict["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)
        }
        assert site.content_manager.verifyFile(inner_path, data, ignore_same=False)

        # Wrong address
        data_dict["address"] = "Othersite"
        del data_dict["signs"]
        data_dict["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)
        }
        data = io.BytesIO(json.dumps(data_dict).encode())
        with pytest.raises(VerifyError) as err:
            site.content_manager.verifyFile(inner_path, data, ignore_same=False)
        assert "Wrong site address" in str(err.value)

        # Wrong inner_path
        data_dict["address"] = "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT"
        data_dict["inner_path"] = "content.json"
        del data_dict["signs"]
        data_dict["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)
        }
        data = io.BytesIO(json.dumps(data_dict).encode())
        with pytest.raises(VerifyError) as err:
            site.content_manager.verifyFile(inner_path, data, ignore_same=False)
        assert "Wrong inner_path" in str(err.value)

        # Everything right again
        data_dict["address"] = "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT"
        data_dict["inner_path"] = inner_path
        del data_dict["signs"]
        data_dict["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)
        }
        data = io.BytesIO(json.dumps(data_dict).encode())
        assert site.content_manager.verifyFile(inner_path, data, ignore_same=False)

    def testVerifyInnerPath(self, site, crypt_bitcoin_lib):
        inner_path = "content.json"
        data_dict = site.storage.loadJson(inner_path)

        for good_relative_path in ["data.json", "out/data.json", "Any File [by none] (1).jpg"]:
            data_dict["files"] = {good_relative_path: {"sha512": "369d4e780cc80504285f13774ca327fe725eed2d813aad229e62356b07365906", "size": 505}}

            if "sign" in data_dict:
                del data_dict["sign"]
            del data_dict["signs"]
            data_dict["signs"] = {
                "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)
            }
            data = io.BytesIO(json.dumps(data_dict).encode())
            assert site.content_manager.verifyFile(inner_path, data, ignore_same=False)

        for bad_relative_path in ["../data.json", "data/" * 100, "invalid|file.jpg"]:
            data_dict["files"] = {bad_relative_path: {"sha512": "369d4e780cc80504285f13774ca327fe725eed2d813aad229e62356b07365906", "size": 505}}

            if "sign" in data_dict:
                del data_dict["sign"]
            del data_dict["signs"]
            data_dict["signs"] = {
                "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), self.privatekey)
            }
            data = io.BytesIO(json.dumps(data_dict).encode())
            with pytest.raises(VerifyError) as err:
                site.content_manager.verifyFile(inner_path, data, ignore_same=False)
            assert "Invalid relative path" in str(err.value)

    @pytest.mark.parametrize("key", ["ignore", "optional"])
    def testSignUnsafePattern(self, site, key):
        site.content_manager.contents["content.json"][key] = "([a-zA-Z]+)*"
        with pytest.raises(UnsafePatternError) as err:
            site.content_manager.sign("content.json", privatekey=self.privatekey, filewrite=False)
        assert "Potentially unsafe" in str(err.value)


    def testVerifyUnsafePattern(self, site, crypt_bitcoin_lib):
        site.content_manager.contents["content.json"]["includes"]["data/test_include/content.json"]["files_allowed"] = "([a-zA-Z]+)*"
        with pytest.raises(UnsafePatternError) as err:
            with site.storage.open("data/test_include/content.json") as data:
                site.content_manager.verifyFile("data/test_include/content.json", data, ignore_same=False)
        assert "Potentially unsafe" in str(err.value)

        site.content_manager.contents["data/users/content.json"]["user_contents"]["permission_rules"]["([a-zA-Z]+)*"] = {"max_size": 0}
        with pytest.raises(UnsafePatternError) as err:
            with site.storage.open("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json") as data:
                site.content_manager.verifyFile("data/users/1C5sgvWaSgfaTpV5kjBCnCiKtENNMYo69q/content.json", data, ignore_same=False)
        assert "Potentially unsafe" in str(err.value)

import json
from cStringIO import StringIO

import pytest

from Crypt import CryptBitcoin


@pytest.mark.usefixtures("resetSettings")
class TestUserContent:
    def testSigners(self, site):
        # File info for not existing user file
        file_info = site.content_manager.getFileInfo("data/users/notexist/data.json")
        assert file_info["content_inner_path"] == "data/users/notexist/content.json"
        valid_signers = site.content_manager.getValidSigners("data/users/notexist/content.json")
        assert valid_signers == ["14wgQ4VDDZNoRMFF4yCDuTrBSHmYhL3bet", "notexist", "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT"]

        # File info for exsitsing user file
        valid_signers = site.content_manager.getValidSigners("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json")
        assert '1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT' in valid_signers  # The site address
        assert '14wgQ4VDDZNoRMFF4yCDuTrBSHmYhL3bet' in valid_signers  # Admin user defined in data/users/content.json
        assert '1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C' in valid_signers  # The user itself
        assert len(valid_signers) == 3  # No more valid signers

        # Valid signer for banned user
        user_content = site.storage.loadJson("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json")
        user_content["cert_user_id"] = "bad@zeroid.bit"

        valid_signers = site.content_manager.getValidSigners("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_content)
        assert '1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT' in valid_signers  # The site address
        assert '14wgQ4VDDZNoRMFF4yCDuTrBSHmYhL3bet' in valid_signers  # Admin user defined in data/users/content.json
        assert not '1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C' in valid_signers  # The user itself


    def testRules(self, site):
        # We going to manipulate it this test rules based on data/users/content.json
        user_content = site.storage.loadJson("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json")

        # Known user
        user_content["cert_auth_type"] = "web"
        user_content["cert_user_id"] = "nofish@zeroid.bit"
        rules = site.content_manager.getRules("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_content)
        assert rules["max_size"] == 100000
        assert "1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C" in rules["signers"]

        # Unknown user
        user_content["cert_auth_type"] = "web"
        user_content["cert_user_id"] = "noone@zeroid.bit"
        rules = site.content_manager.getRules("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_content)
        assert rules["max_size"] == 10000
        assert "1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C" in rules["signers"]

        # User with more size limit based on auth type
        user_content["cert_auth_type"] = "bitmsg"
        user_content["cert_user_id"] = "noone@zeroid.bit"
        rules = site.content_manager.getRules("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_content)
        assert rules["max_size"] == 15000
        assert "1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C" in rules["signers"]

        # Banned user
        user_content["cert_auth_type"] = "web"
        user_content["cert_user_id"] = "bad@zeroid.bit"
        rules = site.content_manager.getRules("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_content)
        assert "1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C" not in rules["signers"]

    def testVerify(self, site):
        privatekey = "5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv"  # For 1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT
        user_inner_path = "data/users/1CjfbrbwtP8Y2QjPy12vpTATkUT7oSiPQ9/content.json"
        data_dict = site.storage.loadJson(user_inner_path)
        users_content = site.content_manager.contents["data/users/content.json"]

        data = StringIO(json.dumps(data_dict))
        assert site.content_manager.verifyFile(user_inner_path, data, ignore_same=False)

        # Test max size exception by setting allowed to 0
        rules = site.content_manager.getRules(user_inner_path, data_dict)
        assert rules["max_size"] == 10000
        assert users_content["user_contents"]["permission_rules"][".*"]["max_size"] == 10000

        users_content["user_contents"]["permission_rules"][".*"]["max_size"] = 0
        rules = site.content_manager.getRules(user_inner_path, data_dict)
        assert rules["max_size"] == 0
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile(user_inner_path, data, ignore_same=False)
        users_content["user_contents"]["permission_rules"][".*"]["max_size"] = 10000  # Reset

        # Test max optional size exception
        # 1 MB gif = Allowed
        data_dict["files_optional"]["peanut-butter-jelly-time.gif"]["size"] = 1024 * 1024
        del data_dict["signs"]  # Remove signs before signing
        data_dict["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), privatekey)
        }
        data = StringIO(json.dumps(data_dict))
        assert site.content_manager.verifyFile(user_inner_path, data, ignore_same=False)

        # 100 MB gif = Not allowed
        data_dict["files_optional"]["peanut-butter-jelly-time.gif"]["size"] = 100 * 1024 * 1024
        del data_dict["signs"]  # Remove signs before signing
        data_dict["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), privatekey)
        }
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile(user_inner_path, data, ignore_same=False)
        data_dict["files_optional"]["peanut-butter-jelly-time.gif"]["size"] = 1024 * 1024  # Reset

        # hello.exe = Not allowed
        data_dict["files_optional"]["hello.exe"] = data_dict["files_optional"]["peanut-butter-jelly-time.gif"]
        del data_dict["signs"]  # Remove signs before signing
        data_dict["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), privatekey)
        }
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile(user_inner_path, data, ignore_same=False)
        del data_dict["files_optional"]["hello.exe"]  # Reset

        # Includes not allowed in user content
        data_dict["includes"] = { "other.json": { } }
        del data_dict["signs"]  # Remove signs before signing
        data_dict["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(data_dict, sort_keys=True), privatekey)
        }
        data = StringIO(json.dumps(data_dict))
        assert not site.content_manager.verifyFile(user_inner_path, data, ignore_same=False)


    def testCert(self, site):
        # user_addr = "1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C"
        user_priv = "5Kk7FSA63FC2ViKmKLuBxk9gQkaQ5713hKq8LmFAf4cVeXh6K6A"
        # cert_addr = "14wgQ4VDDZNoRMFF4yCDuTrBSHmYhL3bet"
        cert_priv = "5JusJDSjHaMHwUjDT3o6eQ54pA6poo8La5fAgn1wNc3iK59jxjA"

        # Check if the user file is loaded
        assert "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json" in site.content_manager.contents
        user_content = site.content_manager.contents["data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json"]
        rules_content = site.content_manager.contents["data/users/content.json"]

        # Override valid cert signers for the test
        rules_content["user_contents"]["cert_signers"]["zeroid.bit"] = [
            "14wgQ4VDDZNoRMFF4yCDuTrBSHmYhL3bet",
            "1iD5ZQJMNXu43w1qLB8sfdHVKppVMduGz"
        ]

        # Check valid cert signers
        rules = site.content_manager.getRules("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_content)
        assert rules["cert_signers"] == {"zeroid.bit": [
            "14wgQ4VDDZNoRMFF4yCDuTrBSHmYhL3bet",
            "1iD5ZQJMNXu43w1qLB8sfdHVKppVMduGz"
        ]}

        # Sign a valid cert
        user_content["cert_sign"] = CryptBitcoin.sign("1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C#%s/%s" % (
            user_content["cert_auth_type"],
            user_content["cert_user_id"].split("@")[0]
        ), cert_priv)

        # Verify cert
        assert site.content_manager.verifyCert("data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_content)

        # Verify if the cert is valid for other address
        assert not site.content_manager.verifyCert("data/users/badaddress/content.json", user_content)

        # Sign user content
        signed_content = site.content_manager.sign(
            "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_priv, filewrite=False
        )

        # Test user cert
        assert site.content_manager.verifyFile(
            "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json",
            StringIO(json.dumps(signed_content)), ignore_same=False
        )

        # Test banned user
        cert_user_id = user_content["cert_user_id"]  # My username
        site.content_manager.contents["data/users/content.json"]["user_contents"]["permissions"][cert_user_id] = False
        assert not site.content_manager.verifyFile(
            "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json",
            StringIO(json.dumps(signed_content)), ignore_same=False
        )

        # Test invalid cert
        user_content["cert_sign"] = CryptBitcoin.sign(
            "badaddress#%s/%s" % (user_content["cert_auth_type"], user_content["cert_user_id"]), cert_priv
        )
        signed_content = site.content_manager.sign(
            "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_priv, filewrite=False
        )
        assert not site.content_manager.verifyFile(
            "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json",
            StringIO(json.dumps(signed_content)), ignore_same=False
        )

        # Test banned user, signed by the site owner
        user_content["cert_sign"] = CryptBitcoin.sign("1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C#%s/%s" % (
            user_content["cert_auth_type"],
            user_content["cert_user_id"].split("@")[0]
        ), cert_priv)
        cert_user_id = user_content["cert_user_id"]  # My username
        site.content_manager.contents["data/users/content.json"]["user_contents"]["permissions"][cert_user_id] = False

        site_privatekey = "5KUh3PvNm5HUWoCfSUfcYvfQ2g3PrRNJWr6Q9eqdBGu23mtMntv"  # For 1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT
        del user_content["signs"]  # Remove signs before signing
        user_content["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(user_content, sort_keys=True), site_privatekey)
        }
        assert site.content_manager.verifyFile(
            "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json",
            StringIO(json.dumps(user_content)), ignore_same=False
        )

    def testMissingCert(self, site):
        user_priv = "5Kk7FSA63FC2ViKmKLuBxk9gQkaQ5713hKq8LmFAf4cVeXh6K6A"
        cert_priv = "5JusJDSjHaMHwUjDT3o6eQ54pA6poo8La5fAgn1wNc3iK59jxjA"

        user_content = site.content_manager.contents["data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json"]
        rules_content = site.content_manager.contents["data/users/content.json"]

        # Override valid cert signers for the test
        rules_content["user_contents"]["cert_signers"]["zeroid.bit"] = [
            "14wgQ4VDDZNoRMFF4yCDuTrBSHmYhL3bet",
            "1iD5ZQJMNXu43w1qLB8sfdHVKppVMduGz"
        ]

        # Sign a valid cert
        user_content["cert_sign"] = CryptBitcoin.sign("1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C#%s/%s" % (
            user_content["cert_auth_type"],
            user_content["cert_user_id"].split("@")[0]
        ), cert_priv)
        signed_content = site.content_manager.sign(
            "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json", user_priv, filewrite=False
        )

        assert site.content_manager.verifyFile(
            "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json",
            StringIO(json.dumps(signed_content)), ignore_same=False
        )

        # Test removed cert
        # user_content["cert_sign"]
        del user_content["cert_auth_type"]
        del user_content["signs"]  # Remove signs before signing
        user_content["signs"] = {
            "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT": CryptBitcoin.sign(json.dumps(user_content, sort_keys=True), user_priv)
        }
        print "--- Signed content", user_content
        assert not site.content_manager.verifyFile(
            "data/users/1J6UrZMkarjVg5ax9W4qThir3BFUikbW6C/content.json",
            StringIO(json.dumps(user_content)), ignore_same=False
        )
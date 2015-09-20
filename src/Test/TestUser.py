import pytest

from Crypt import CryptBitcoin


@pytest.mark.usefixtures("resetSettings")
class TestUser:
    def testAddress(self, user):
        assert user.master_address == "15E5rhcAUD69WbiYsYARh4YHJ4sLm2JEyc"
        address_index = 1458664252141532163166741013621928587528255888800826689784628722366466547364755811L
        assert user.getAddressAuthIndex("15E5rhcAUD69WbiYsYARh4YHJ4sLm2JEyc") == address_index

    # Re-generate privatekey based on address_index
    def testNewSite(self, user):
        address, address_index, site_data = user.getNewSiteData()  # Create a new random site
        assert CryptBitcoin.hdPrivatekey(user.master_seed, address_index) == site_data["privatekey"]

        user.sites = {}  # Reset user data

        # Site address and auth address is different
        assert user.getSiteData(address)["auth_address"] != address
        # Re-generate auth_privatekey for site
        assert user.getSiteData(address)["auth_privatekey"] == site_data["auth_privatekey"]

    def testAuthAddress(self, user):
        # Auth address without Cert
        auth_address = user.getAuthAddress("1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr")
        assert auth_address == "1MyJgYQjeEkR9QD66nkfJc9zqi9uUy5Lr2"
        auth_privatekey = user.getAuthPrivatekey("1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr")
        assert CryptBitcoin.privatekeyToAddress(auth_privatekey) == auth_address

    def testCert(self, user):
        cert_auth_address = user.getAuthAddress("1iD5ZQJMNXu43w1qLB8sfdHVKppVMduGz")  # Add site to user's registry
        # Add cert
        user.addCert(cert_auth_address, "zeroid.bit", "faketype", "fakeuser", "fakesign")
        user.setCert("1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr", "zeroid.bit")

        # By using certificate the auth address should be same as the certificate provider
        assert user.getAuthAddress("1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr") == cert_auth_address
        auth_privatekey = user.getAuthPrivatekey("1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr")
        assert CryptBitcoin.privatekeyToAddress(auth_privatekey) == cert_auth_address

        # Test delete site data
        assert "1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr" in user.sites
        user.deleteSiteData("1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr")
        assert "1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr" not in user.sites

        # Re-create add site should generate normal, unique auth_address
        assert not user.getAuthAddress("1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr") == cert_auth_address
        assert user.getAuthAddress("1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr") == "1MyJgYQjeEkR9QD66nkfJc9zqi9uUy5Lr2"

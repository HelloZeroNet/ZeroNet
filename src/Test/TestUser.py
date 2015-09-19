import pytest

from Crypt import CryptBitcoin


@pytest.mark.usefixtures("resetSettings")
class TestUser:
    def testNewsite(self, user):
        user.sites = {}  # Reset user data
        assert user.master_address == "15E5rhcAUD69WbiYsYARh4YHJ4sLm2JEyc"
        address_index = 1458664252141532163166741013621928587528255888800826689784628722366466547364755811L
        assert user.getAddressAuthIndex("15E5rhcAUD69WbiYsYARh4YHJ4sLm2JEyc") == address_index

        # Re-generate privatekey based on address_index
        address, address_index, site_data = user.getNewSiteData()
        assert CryptBitcoin.hdPrivatekey(user.master_seed, address_index) == site_data["privatekey"]

        user.sites = {}  # Reset user data

        # Site address and auth address is different
        assert user.getSiteData(address)["auth_address"] != address
        # Re-generate auth_privatekey for site
        assert user.getSiteData(address)["auth_privatekey"] == site_data["auth_privatekey"]

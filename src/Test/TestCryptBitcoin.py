from Crypt import CryptBitcoin


class TestCryptBitcoin:
    def testSign(self, crypt_bitcoin_lib):
        privatekey = "5K9S6dVpufGnroRgFrT6wsKiz2mJRYsC73eWDmajaHserAp3F1C"
        privatekey_bad = "5Jbm9rrusXyApAoM8YoM4Rja337zMMoBUMRJ1uijiguU2aZRnwC"

        # Get address by privatekey
        address = crypt_bitcoin_lib.privatekeyToAddress(privatekey)
        assert address == "1MpDMxFeDUkiHohxx9tbGLeEGEuR4ZNsJz"

        address_bad = crypt_bitcoin_lib.privatekeyToAddress(privatekey_bad)
        assert address_bad != "1MpDMxFeDUkiHohxx9tbGLeEGEuR4ZNsJz"

        # Text signing
        data_len_list = list(range(0, 300, 10))
        data_len_list += [1024, 2048, 1024 * 128, 1024 * 1024, 1024 * 2048]
        for data_len in data_len_list:
            data = data_len * "!"
            sign = crypt_bitcoin_lib.sign(data, privatekey)

            assert crypt_bitcoin_lib.verify(data, address, sign)
            assert not crypt_bitcoin_lib.verify("invalid" + data, address, sign)

        # Signed by bad privatekey
        sign_bad = crypt_bitcoin_lib.sign("hello", privatekey_bad)
        assert not crypt_bitcoin_lib.verify("hello", address, sign_bad)

    def testVerify(self, crypt_bitcoin_lib):
        sign_uncompressed = b'G6YkcFTuwKMVMHI2yycGQIFGbCZVNsZEZvSlOhKpHUt/BlADY94egmDAWdlrbbFrP9wH4aKcEfbLO8sa6f63VU0='
        assert crypt_bitcoin_lib.verify("1NQUem2M4cAqWua6BVFBADtcSP55P4QobM#web/gitcenter", "19Bir5zRm1yo4pw9uuxQL8xwf9b7jqMpR", sign_uncompressed)

        sign_compressed = b'H6YkcFTuwKMVMHI2yycGQIFGbCZVNsZEZvSlOhKpHUt/BlADY94egmDAWdlrbbFrP9wH4aKcEfbLO8sa6f63VU0='
        assert crypt_bitcoin_lib.verify("1NQUem2M4cAqWua6BVFBADtcSP55P4QobM#web/gitcenter", "1KH5BdNnqxh2KRWMMT8wUXzUgz4vVQ4S8p", sign_compressed)

    def testNewPrivatekey(self):
        assert CryptBitcoin.newPrivatekey() != CryptBitcoin.newPrivatekey()
        assert CryptBitcoin.privatekeyToAddress(CryptBitcoin.newPrivatekey())

    def testNewSeed(self):
        assert CryptBitcoin.newSeed() != CryptBitcoin.newSeed()
        assert CryptBitcoin.privatekeyToAddress(
            CryptBitcoin.hdPrivatekey(CryptBitcoin.newSeed(), 0)
        )
        assert CryptBitcoin.privatekeyToAddress(
            CryptBitcoin.hdPrivatekey(CryptBitcoin.newSeed(), 2**256)
        )

from Crypt import CryptBitcoin


class TestCryptBitcoin:
    def testSignOld(self):
        privatekey = "23DKQpDz7bXM7w5KN5Wnmz7bwRNqNHcdQjb2WwrdB1QtTf5gM3pFdf"
        privatekey_bad = "23DKQpDz7bXM7w5KN5Wnmz6bwRNqNHcdQjb2WwrdB1QtTf5gM3pFdf"

        # Get address by privatekey
        address = CryptBitcoin.privatekeyToAddress(privatekey)
        assert address == "12vTsjscg4hYPewUL2onma5pgQmWPMs3ez"

        address_bad = CryptBitcoin.privatekeyToAddress(privatekey_bad)
        assert not address_bad == "12vTsjscg4hYPewUL2onma5pgQmWPMs3ez"

        # Text signing
        sign = CryptBitcoin.signOld("hello", privatekey)
        assert CryptBitcoin.verify("hello", address, sign)  # Original text
        assert not CryptBitcoin.verify("not hello", address, sign)  # Different text

        # Signed by bad privatekey
        sign_bad = CryptBitcoin.signOld("hello", privatekey_bad)
        assert not CryptBitcoin.verify("hello", address, sign_bad)

    def testSign(self):
        privatekey = "5K9S6dVpufGnroRgFrT6wsKiz2mJRYsC73eWDmajaHserAp3F1C"
        privatekey_bad = "5Jbm9rrusXyApAoM8YoM4Rja337zMMoBUMRJ1uijiguU2aZRnwC"

        # Get address by privatekey
        address = CryptBitcoin.privatekeyToAddress(privatekey)
        assert address == "1MpDMxFeDUkiHohxx9tbGLeEGEuR4ZNsJz"

        address_bad = CryptBitcoin.privatekeyToAddress(privatekey_bad)
        assert address_bad != "1MpDMxFeDUkiHohxx9tbGLeEGEuR4ZNsJz"

        # Text signing
        sign = CryptBitcoin.sign("hello", privatekey)

        assert CryptBitcoin.verify("hello", address, sign)
        assert not CryptBitcoin.verify("not hello", address, sign)

        # Signed by bad privatekey
        sign_bad = CryptBitcoin.sign("hello", privatekey_bad)
        assert not CryptBitcoin.verify("hello", address, sign_bad)

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

import pytest
import base64
from CryptMessage import CryptMessage


@pytest.mark.usefixtures("resetSettings")
class TestCrypt:
    publickey = "A3HatibU4S6eZfIQhVs2u7GLN5G9wXa9WwlkyYIfwYaj"
    privatekey = "5JBiKFYBm94EUdbxtnuLi6cvNcPzcKymCUHBDf2B6aq19vvG3rL"
    utf8_text = '\xc1rv\xedzt\xfbr\xf5t\xfck\xf6rf\xfar\xf3g\xe9'
    ecies_encrypted_text = "R5J1RFIDOzE5bnWopvccmALKACCk/CRcd/KSE9OgExJKASyMbZ57JVSUenL2TpABMmcT+wAgr2UrOqClxpOWvIUwvwwupXnMbRTzthhIJJrTRW3sCJVaYlGEMn9DAcvbflgEkQX/MVVdLV3tWKySs1Vk8sJC/y+4pGYCrZz7vwDNEEERaqU="

    @pytest.mark.parametrize("text", [b"hello", '\xc1rv\xedzt\xfbr\xf5t\xfck\xf6rf\xfar\xf3g\xe9'.encode("utf8")])
    @pytest.mark.parametrize("text_repeat", [1, 10, 128, 1024])
    def testEncryptEcies(self, text, text_repeat):
        text_repeated = text * text_repeat
        aes_key, encrypted = CryptMessage.eciesEncrypt(text_repeated, self.publickey)
        assert len(aes_key) == 32
        # assert len(encrypted) == 134 + int(len(text) / 16) * 16  # Not always true

        ecc = CryptMessage.getEcc(self.privatekey)
        assert ecc.decrypt(encrypted) == text_repeated

    def testDecryptEcies(self, user):
        encrypted = base64.b64decode(self.ecies_encrypted_text)
        ecc = CryptMessage.getEcc(self.privatekey)
        assert ecc.decrypt(encrypted) == b"hello"

    def testPublickey(self, ui_websocket):
        pub = ui_websocket.testAction("UserPublickey", 0)
        assert len(pub) == 44  # Compressed, b64 encoded publickey

        # Different pubkey for specificed index
        assert ui_websocket.testAction("UserPublickey", 1) != ui_websocket.testAction("UserPublickey", 0)

        # Same publickey for same index
        assert ui_websocket.testAction("UserPublickey", 2) == ui_websocket.testAction("UserPublickey", 2)

        # Different publickey for different cert
        site_data = ui_websocket.user.getSiteData(ui_websocket.site.address)
        site_data["cert"] = None
        pub1 = ui_websocket.testAction("UserPublickey", 0)

        site_data = ui_websocket.user.getSiteData(ui_websocket.site.address)
        site_data["cert"] = "zeroid.bit"
        pub2 = ui_websocket.testAction("UserPublickey", 0)
        assert pub1 != pub2

    def testEcies(self, ui_websocket):
        ui_websocket.actionUserPublickey(0, 0)
        pub = ui_websocket.ws.getResult()

        ui_websocket.actionEciesEncrypt(0, "hello", pub)
        encrypted = ui_websocket.ws.getResult()
        assert len(encrypted) == 180

        # Don't allow decrypt using other privatekey index
        ui_websocket.actionEciesDecrypt(0, encrypted, 123)
        decrypted = ui_websocket.ws.getResult()
        assert decrypted != "hello"

        # Decrypt using correct privatekey
        ui_websocket.actionEciesDecrypt(0, encrypted)
        decrypted = ui_websocket.ws.getResult()
        assert decrypted == "hello"

        # Decrypt batch
        ui_websocket.actionEciesDecrypt(0, [encrypted, "baad", encrypted])
        decrypted = ui_websocket.ws.getResult()
        assert decrypted == ["hello", None, "hello"]

    def testEciesUtf8(self, ui_websocket):
        # Utf8 test
        ui_websocket.actionEciesEncrypt(0, self.utf8_text)
        encrypted = ui_websocket.ws.getResult()

        ui_websocket.actionEciesDecrypt(0, encrypted)
        assert ui_websocket.ws.getResult() == self.utf8_text

    def testEciesAes(self, ui_websocket):
        ui_websocket.actionEciesEncrypt(0, "hello", return_aes_key=True)
        ecies_encrypted, aes_key = ui_websocket.ws.getResult()

        # Decrypt using Ecies
        ui_websocket.actionEciesDecrypt(0, ecies_encrypted)
        assert ui_websocket.ws.getResult() == "hello"

        # Decrypt using AES
        aes_iv, aes_encrypted = CryptMessage.split(base64.b64decode(ecies_encrypted))

        ui_websocket.actionAesDecrypt(0, base64.b64encode(aes_iv), base64.b64encode(aes_encrypted), aes_key)
        assert ui_websocket.ws.getResult() == "hello"

    def testAes(self, ui_websocket):
        ui_websocket.actionAesEncrypt(0, "hello")
        key, iv, encrypted = ui_websocket.ws.getResult()

        assert len(key) == 44
        assert len(iv) == 24
        assert len(encrypted) == 24

        # Single decrypt
        ui_websocket.actionAesDecrypt(0, iv, encrypted, key)
        assert ui_websocket.ws.getResult() == "hello"

        # Batch decrypt
        ui_websocket.actionAesEncrypt(0, "hello")
        key2, iv2, encrypted2 = ui_websocket.ws.getResult()

        assert [key, iv, encrypted] != [key2, iv2, encrypted2]

        # 2 correct key
        ui_websocket.actionAesDecrypt(0, [[iv, encrypted], [iv, encrypted], [iv, "baad"], [iv2, encrypted2]], [key])
        assert ui_websocket.ws.getResult() == ["hello", "hello", None, None]

        # 3 key
        ui_websocket.actionAesDecrypt(0, [[iv, encrypted], [iv, encrypted], [iv, "baad"], [iv2, encrypted2]], [key, key2])
        assert ui_websocket.ws.getResult() == ["hello", "hello", None, "hello"]

    def testAesUtf8(self, ui_websocket):
        ui_websocket.actionAesEncrypt(0, self.utf8_text)
        key, iv, encrypted = ui_websocket.ws.getResult()

        ui_websocket.actionAesDecrypt(0, iv, encrypted, key)
        assert ui_websocket.ws.getResult() == self.utf8_text

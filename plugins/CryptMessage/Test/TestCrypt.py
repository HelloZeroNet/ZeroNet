import pytest
from CryptMessage import CryptMessage

@pytest.mark.usefixtures("resetSettings")
class TestCrypt:
    def testPublickey(self, ui_websocket):
        pub = ui_websocket.testAction("UserPublickey", 0)
        assert len(pub) == 44  # Compressed, b64 encoded publickey

        # Different pubkey for specificed index
        assert ui_websocket.testAction("UserPublickey", 1) != ui_websocket.testAction("UserPublickey", 0)

        # Same publickey for same index
        assert ui_websocket.testAction("UserPublickey", 2) == ui_websocket.testAction("UserPublickey", 2)

        # Different publickey for different cert
        pub1 = ui_websocket.testAction("UserPublickey", 0)
        site_data = ui_websocket.user.getSiteData(ui_websocket.site.address)
        site_data["cert"] = "zeroid.bit"
        pub2 = ui_websocket.testAction("UserPublickey", 0)
        assert pub1 != pub2



    def testEcies(self, ui_websocket):
        ui_websocket.actionUserPublickey(0, 0)
        pub = ui_websocket.ws.result

        ui_websocket.actionEciesEncrypt(0, "hello", pub)
        encrypted = ui_websocket.ws.result
        assert len(encrypted) == 180

        # Don't allow decrypt using other privatekey index
        ui_websocket.actionEciesDecrypt(0, encrypted, 123)
        decrypted = ui_websocket.ws.result
        assert decrypted != "hello"

        # Decrypt using correct privatekey
        ui_websocket.actionEciesDecrypt(0, encrypted)
        decrypted = ui_websocket.ws.result
        assert decrypted == "hello"

        # Decrypt batch
        ui_websocket.actionEciesDecrypt(0, [encrypted, "baad", encrypted])
        decrypted = ui_websocket.ws.result
        assert decrypted == ["hello", None, "hello"]


    def testEciesUtf8(self, ui_websocket):
        # Utf8 test
        utf8_text = u'\xc1rv\xedzt\xfbr\xf5t\xfck\xf6rf\xfar\xf3g\xe9p'
        ui_websocket.actionEciesEncrypt(0, utf8_text)
        encrypted = ui_websocket.ws.result

        ui_websocket.actionEciesDecrypt(0, encrypted)
        assert ui_websocket.ws.result == utf8_text


    def testEciesAes(self, ui_websocket):
        ui_websocket.actionEciesEncrypt(0, "hello", return_aes_key=True)
        ecies_encrypted, aes_key = ui_websocket.ws.result

        # Decrypt using Ecies
        ui_websocket.actionEciesDecrypt(0, ecies_encrypted)
        assert ui_websocket.ws.result == "hello"

        # Decrypt using AES
        aes_iv, aes_encrypted = CryptMessage.split(ecies_encrypted.decode("base64"))

        ui_websocket.actionAesDecrypt(0, aes_iv.encode("base64"), aes_encrypted.encode("base64"), aes_key)
        assert ui_websocket.ws.result == "hello"


    def testAes(self, ui_websocket):
        ui_websocket.actionAesEncrypt(0, "hello")
        key, iv, encrypted = ui_websocket.ws.result

        assert len(key) == 44
        assert len(iv) == 24
        assert len(encrypted) == 24

        # Single decrypt
        ui_websocket.actionAesDecrypt(0, iv, encrypted, key)
        assert ui_websocket.ws.result == "hello"

        # Batch decrypt
        ui_websocket.actionAesEncrypt(0, "hello")
        key2, iv2, encrypted2 = ui_websocket.ws.result

        assert [key, iv, encrypted] != [key2, iv2, encrypted2]

        # 2 correct key
        ui_websocket.actionAesDecrypt(0, [[iv, encrypted], [iv, encrypted], [iv, "baad"], [iv2, encrypted2]], [key])
        assert ui_websocket.ws.result == ["hello", "hello", None, None]

        # 3 key
        ui_websocket.actionAesDecrypt(0, [[iv, encrypted], [iv, encrypted], [iv, "baad"], [iv2, encrypted2]], [key, key2])
        assert ui_websocket.ws.result == ["hello", "hello", None, "hello"]

    def testAesUtf8(self, ui_websocket):
        utf8_text = u'\xc1rv\xedzt\xfbr\xf5t\xfck\xf6rf\xfar\xf3g\xe9'
        ui_websocket.actionAesEncrypt(0, utf8_text)
        key, iv, encrypted = ui_websocket.ws.result

        ui_websocket.actionAesDecrypt(0, iv, encrypted, key)
        assert ui_websocket.ws.result == utf8_text

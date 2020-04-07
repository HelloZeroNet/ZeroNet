import base64
import os

import gevent

from Plugin import PluginManager
from Crypt import CryptBitcoin, CryptHash
from Config import config
import sslcrypto

from . import CryptMessage

curve = sslcrypto.ecc.get_curve("secp256k1")


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    # - Actions -

    # Returns user's public key unique to site
    # Return: Public key
    def actionUserPublickey(self, to, index=0):
        self.response(to, self.user.getEncryptPublickey(self.site.address, index))

    # Encrypt a text using the publickey or user's sites unique publickey
    # Return: Encrypted text using base64 encoding
    def actionEciesEncrypt(self, to, text, publickey=0, return_aes_key=False):
        if type(publickey) is int:  # Encrypt using user's publickey
            publickey = self.user.getEncryptPublickey(self.site.address, publickey)
        aes_key, encrypted = CryptMessage.eciesEncrypt(text.encode("utf8"), publickey)
        if return_aes_key:
            self.response(to, [base64.b64encode(encrypted).decode("utf8"), base64.b64encode(aes_key).decode("utf8")])
        else:
            self.response(to, base64.b64encode(encrypted).decode("utf8"))

    # Decrypt a text using privatekey or the user's site unique private key
    # Return: Decrypted text or list of decrypted texts
    def actionEciesDecrypt(self, to, param, privatekey=0):
        if type(privatekey) is int:  # Decrypt using user's privatekey
            privatekey = self.user.getEncryptPrivatekey(self.site.address, privatekey)

        if type(param) == list:
            encrypted_texts = param
        else:
            encrypted_texts = [param]

        texts = CryptMessage.eciesDecryptMulti(encrypted_texts, privatekey)

        if type(param) == list:
            self.response(to, texts)
        else:
            self.response(to, texts[0])

    # Encrypt a text using AES
    # Return: Iv, AES key, Encrypted text
    def actionAesEncrypt(self, to, text, key=None):
        if key:
            key = base64.b64decode(key)
        else:
            key = sslcrypto.aes.new_key()

        if text:
            encrypted, iv = sslcrypto.aes.encrypt(text.encode("utf8"), key)
        else:
            encrypted, iv = b"", b""

        res = [base64.b64encode(item).decode("utf8") for item in [key, iv, encrypted]]
        self.response(to, res)

    # Decrypt a text using AES
    # Return: Decrypted text
    def actionAesDecrypt(self, to, *args):
        if len(args) == 3:  # Single decrypt
            encrypted_texts = [(args[0], args[1])]
            keys = [args[2]]
        else:  # Batch decrypt
            encrypted_texts, keys = args

        texts = []  # Decoded texts
        for iv, encrypted_text in encrypted_texts:
            encrypted_text = base64.b64decode(encrypted_text)
            iv = base64.b64decode(iv)
            text = None
            for key in keys:
                try:
                    decrypted = sslcrypto.aes.decrypt(encrypted_text, iv, base64.b64decode(key))
                    if decrypted and decrypted.decode("utf8"):  # Valid text decoded
                        text = decrypted.decode("utf8")
                except Exception as err:
                    pass
            texts.append(text)

        if len(args) == 3:
            self.response(to, texts[0])
        else:
            self.response(to, texts)

    # Sign data using ECDSA
    # Return: Signature
    def actionEcdsaSign(self, to, data, privatekey=None):
        if privatekey is None:  # Sign using user's privatekey
            privatekey = self.user.getAuthPrivatekey(self.site.address)

        self.response(to, CryptBitcoin.sign(data, privatekey))

    # Verify data using ECDSA (address is either a address or array of addresses)
    # Return: bool
    def actionEcdsaVerify(self, to, data, address, signature):
        self.response(to, CryptBitcoin.verify(data, address, signature))

    # Gets the publickey of a given privatekey
    def actionEccPrivToPub(self, to, privatekey):
        self.response(to, curve.private_to_public(curve.wif_to_private(privatekey.encode())))

    # Gets the address of a given publickey
    def actionEccPubToAddr(self, to, publickey):
        self.response(to, curve.public_to_address(bytes.fromhex(publickey)))


@PluginManager.registerTo("User")
class UserPlugin(object):
    def getEncryptPrivatekey(self, address, param_index=0):
        if param_index < 0 or param_index > 1000:
            raise Exception("Param_index out of range")

        site_data = self.getSiteData(address)

        if site_data.get("cert"):  # Different privatekey for different cert provider
            index = param_index + self.getAddressAuthIndex(site_data["cert"])
        else:
            index = param_index

        if "encrypt_privatekey_%s" % index not in site_data:
            address_index = self.getAddressAuthIndex(address)
            crypt_index = address_index + 1000 + index
            site_data["encrypt_privatekey_%s" % index] = CryptBitcoin.hdPrivatekey(self.master_seed, crypt_index)
            self.log.debug("New encrypt privatekey generated for %s:%s" % (address, index))
        return site_data["encrypt_privatekey_%s" % index]

    def getEncryptPublickey(self, address, param_index=0):
        if param_index < 0 or param_index > 1000:
            raise Exception("Param_index out of range")

        site_data = self.getSiteData(address)

        if site_data.get("cert"):  # Different privatekey for different cert provider
            index = param_index + self.getAddressAuthIndex(site_data["cert"])
        else:
            index = param_index

        if "encrypt_publickey_%s" % index not in site_data:
            privatekey = self.getEncryptPrivatekey(address, param_index).encode()
            publickey = curve.private_to_public(curve.wif_to_private(privatekey) + b"\x01")
            site_data["encrypt_publickey_%s" % index] = base64.b64encode(publickey).decode("utf8")
        return site_data["encrypt_publickey_%s" % index]


@PluginManager.registerTo("Actions")
class ActionsPlugin:
    publickey = "A3HatibU4S6eZfIQhVs2u7GLN5G9wXa9WwlkyYIfwYaj"
    privatekey = "5JBiKFYBm94EUdbxtnuLi6cvNcPzcKymCUHBDf2B6aq19vvG3rL"
    utf8_text = '\xc1rv\xedzt\xfbr\xf5t\xfck\xf6rf\xfar\xf3g\xe9p'

    def getBenchmarkTests(self, online=False):
        if hasattr(super(), "getBenchmarkTests"):
            tests = super().getBenchmarkTests(online)
        else:
            tests = []

        aes_key, encrypted = CryptMessage.eciesEncrypt(self.utf8_text.encode("utf8"), self.publickey)  # Warm-up
        tests.extend([
            {"func": self.testCryptEciesEncrypt, "kwargs": {}, "num": 100, "time_standard": 1.2},
            {"func": self.testCryptEciesDecrypt, "kwargs": {}, "num": 500, "time_standard": 1.3},
            {"func": self.testCryptEciesDecryptMulti, "kwargs": {}, "num": 5, "time_standard": 0.68},
            {"func": self.testCryptAesEncrypt, "kwargs": {}, "num": 10000, "time_standard": 0.27},
            {"func": self.testCryptAesDecrypt, "kwargs": {}, "num": 10000, "time_standard": 0.25}
        ])
        return tests

    def testCryptEciesEncrypt(self, num_run=1):
        for i in range(num_run):
            aes_key, encrypted = CryptMessage.eciesEncrypt(self.utf8_text.encode("utf8"), self.publickey)
            assert len(aes_key) == 32
            yield "."

    def testCryptEciesDecrypt(self, num_run=1):
        aes_key, encrypted = CryptMessage.eciesEncrypt(self.utf8_text.encode("utf8"), self.publickey)
        for i in range(num_run):
            assert len(aes_key) == 32
            decrypted = CryptMessage.eciesDecrypt(base64.b64encode(encrypted), self.privatekey)
            assert decrypted == self.utf8_text.encode("utf8"), "%s != %s" % (decrypted, self.utf8_text.encode("utf8"))
            yield "."

    def testCryptEciesDecryptMulti(self, num_run=1):
        yield "x 100 (%s threads) " % config.threads_crypt
        aes_key, encrypted = CryptMessage.eciesEncrypt(self.utf8_text.encode("utf8"), self.publickey)

        threads = []
        for i in range(num_run):
            assert len(aes_key) == 32
            threads.append(gevent.spawn(
                CryptMessage.eciesDecryptMulti, [base64.b64encode(encrypted)] * 100, self.privatekey
            ))

        for thread in threads:
            res = thread.get()
            assert res[0] == self.utf8_text, "%s != %s" % (res[0], self.utf8_text)
            assert res[0] == res[-1], "%s != %s" % (res[0], res[-1])
            yield "."
        gevent.joinall(threads)

    def testCryptAesEncrypt(self, num_run=1):
        for i in range(num_run):
            key = os.urandom(32)
            encrypted = sslcrypto.aes.encrypt(self.utf8_text.encode("utf8"), key)
            yield "."

    def testCryptAesDecrypt(self, num_run=1):
        key = os.urandom(32)
        encrypted_text, iv = sslcrypto.aes.encrypt(self.utf8_text.encode("utf8"), key)

        for i in range(num_run):
            decrypted = sslcrypto.aes.decrypt(encrypted_text, iv, key).decode("utf8")
            assert decrypted == self.utf8_text
            yield "."

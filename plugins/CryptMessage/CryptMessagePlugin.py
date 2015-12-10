import base64
import os

from Plugin import PluginManager
from Crypt import CryptBitcoin
from lib.pybitcointools import bitcoin as btctools

import CryptMessage


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def encrypt(self, text, publickey):
        encrypted = CryptMessage.encrypt(text, CryptMessage.toOpensslPublickey(publickey))
        return encrypted

    def decrypt(self, encrypted, privatekey):
        back = CryptMessage.getEcc(privatekey).decrypt(encrypted)
        return back.decode("utf8")

    # - Actions -

    # Returns user's public key unique to site
    # Return: Public key
    def actionUserPublickey(self, to, index=0):
        publickey = self.user.getEncryptPublickey(self.site.address, index)
        self.response(to, publickey)

    # Encrypt a text using the publickey or user's sites unique publickey
    # Return: Encrypted text using base64 encoding
    def actionEciesEncrypt(self, to, text, publickey=0, return_aes_key=False):
        if type(publickey) is int:  # Encrypt using user's publickey
            publickey = self.user.getEncryptPublickey(self.site.address, publickey)
        aes_key, encrypted = self.encrypt(text.encode("utf8"), publickey.decode("base64"))
        if return_aes_key:
            self.response(to, [base64.b64encode(encrypted), base64.b64encode(aes_key)])
        else:
            self.response(to, base64.b64encode(encrypted))

    # Decrypt a text using privatekey or the user's site unique private key
    # Return: Decrypted text or list of decrypted texts
    def actionEciesDecrypt(self, to, param, privatekey=0):
        if type(privatekey) is int:  # Decrypt using user's privatekey
            privatekey = self.user.getEncryptPrivatekey(self.site.address, privatekey)

        if type(param) == list:
            encrypted_texts = param
        else:
            encrypted_texts = [param]

        texts = []  # Decoded texts
        for encrypted_text in encrypted_texts:
            try:
                text = self.decrypt(encrypted_text.decode("base64"), privatekey)
                texts.append(text)
            except Exception, err:
                texts.append(None)

        if type(param) == list:
            self.response(to, texts)
        else:
            self.response(to, texts[0])

    # Encrypt a text using AES
    # Return: Iv, AES key, Encrypted text
    def actionAesEncrypt(self, to, text, key=None, iv=None):
        from lib import pyelliptic

        if key:
            key = key.decode("base64")
        else:
            key = os.urandom(32)

        if iv:  # Generate new AES key if not definied
            iv = iv.decode("base64")
        else:
            iv = pyelliptic.Cipher.gen_IV('aes-256-cbc')

        if text:
            encrypted = pyelliptic.Cipher(key, iv, 1, ciphername='aes-256-cbc').ciphering(text.encode("utf8"))
        else:
            encrypted = ""

        self.response(to, [base64.b64encode(key), base64.b64encode(iv), base64.b64encode(encrypted)])

    # Decrypt a text using AES
    # Return: Decrypted text
    def actionAesDecrypt(self, to, *args):
        from lib import pyelliptic

        if len(args) == 3:  # Single decrypt
            encrypted_texts = [(args[0], args[1])]
            keys = [args[2]]
        else:  # Batch decrypt
            encrypted_texts, keys = args

        texts = []  # Decoded texts
        for iv, encrypted_text in encrypted_texts:
            encrypted_text = encrypted_text.decode("base64")
            iv = iv.decode("base64")
            text = None
            for key in keys:
                ctx = pyelliptic.Cipher(key.decode("base64"), iv, 0, ciphername='aes-256-cbc')
                try:
                    decrypted = ctx.ciphering(encrypted_text)
                    if decrypted and decrypted.decode("utf8"):  # Valid text decoded
                        text = decrypted
                except Exception, err:
                    pass
            texts.append(text)

        if len(args) == 3:
            self.response(to, texts[0])
        else:
            self.response(to, texts)


@PluginManager.registerTo("User")
class UserPlugin(object):
    def getEncryptPrivatekey(self, address, param_index=0):
        assert param_index >= 0 and param_index <= 1000
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
        assert param_index >= 0 and param_index <= 1000
        site_data = self.getSiteData(address)

        if site_data.get("cert"):  # Different privatekey for different cert provider
            index = param_index + self.getAddressAuthIndex(site_data["cert"])
        else:
            index = param_index

        if "encrypt_publickey_%s" % index not in site_data:
            privatekey = self.getEncryptPrivatekey(address, param_index)
            publickey = btctools.encode_pubkey(btctools.privtopub(privatekey), "bin_compressed")
            site_data["encrypt_publickey_%s" % index] = base64.b64encode(publickey)
        return site_data["encrypt_publickey_%s" % index]

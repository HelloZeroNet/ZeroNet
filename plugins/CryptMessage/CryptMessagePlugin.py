import base64
import os

from Plugin import PluginManager
from Crypt import CryptBitcoin, CryptHash
import lib.pybitcointools as btctools

from . import CryptMessage


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def eciesDecrypt(self, encrypted, privatekey):
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

        texts = []  # Decoded texts
        for encrypted_text in encrypted_texts:
            try:
                text = CryptMessage.eciesDecrypt(encrypted_text, privatekey).decode("utf8")
                texts.append(text)
            except Exception as err:
                texts.append(None)

        if type(param) == list:
            self.response(to, texts)
        else:
            self.response(to, texts[0])

    # Encrypt a text using AES
    # Return: Iv, AES key, Encrypted text
    def actionAesEncrypt(self, to, text, key=None, iv=None):
        import pyelliptic

        if key:
            key = base64.b64decode(key)
        else:
            key = os.urandom(32)

        if iv:  # Generate new AES key if not definied
            iv = base64.b64decode(iv)
        else:
            iv = pyelliptic.Cipher.gen_IV('aes-256-cbc')

        if text:
            encrypted = pyelliptic.Cipher(key, iv, 1, ciphername='aes-256-cbc').ciphering(text.encode("utf8"))
        else:
            encrypted = b""

        res = [base64.b64encode(item).decode("utf8") for item in [key, iv, encrypted]]
        self.response(to, res)

    # Decrypt a text using AES
    # Return: Decrypted text
    def actionAesDecrypt(self, to, *args):
        import pyelliptic

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
                ctx = pyelliptic.Cipher(base64.b64decode(key), iv, 0, ciphername='aes-256-cbc')
                try:
                    decrypted = ctx.ciphering(encrypted_text)
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
        self.response(to, btctools.privtopub(privatekey))

    # Gets the address of a given publickey
    def actionEccPubToAddr(self, to, publickey):
        address = btctools.pubtoaddr(btctools.decode_pubkey(publickey))
        self.response(to, address)


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
            privatekey = self.getEncryptPrivatekey(address, param_index)
            publickey = btctools.encode_pubkey(btctools.privtopub(privatekey), "bin_compressed")
            site_data["encrypt_publickey_%s" % index] = base64.b64encode(publickey).decode("utf8")
        return site_data["encrypt_publickey_%s" % index]

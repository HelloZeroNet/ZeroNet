from lib import pybitcointools as btctools
from hashlib import sha512
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
import base64
import os
import hmac

from . import elliptic, pack


def ecdh(privatekey, publickey):
    return elliptic.scalar_mult(privatekey, publickey)[0].to_bytes(32, byteorder="big")
def derive(privatekey, publickey):
    return sha512(ecdh(privatekey, publickey)).digest()


def eciesDecrypt(enc, privatekey):
    enc = base64.b64decode(enc)
    data = pack.parseEciesData(enc)

    privatekey = btctools.decode_privkey(privatekey, "wif_compressed")

    key = derive(privatekey, data["publickey"])
    key_e, key_m = key[:32], key[32:]

    cipher = AES.new(key_e, AES.MODE_CBC, data["iv"])

    mac = hmac.new(key_m, enc[:-32], digestmod="sha256").digest()
    assert mac == data["mac"]

    return unpad(cipher.decrypt(data["ciphertext"]), AES.block_size)



def eciesEncrypt(data, publickey):
    publickey = btctools.decode_pubkey(base64.b64decode(publickey), "bin_compressed")

    my_privatekey = int.from_bytes(os.urandom(32), byteorder="big")
    my_publickey = btctools.privtopub(my_privatekey)

    key = derive(my_privatekey, publickey)
    key_e, key_m = key[:32], key[32:]

    iv = os.urandom(16)

    cipher = AES.new(key_e, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(data, AES.block_size))

    data = {
        "iv": iv,
        "curve": 714,
        "publickey": my_publickey,
        "ciphertext": ciphertext,
        "mac": b"\x00" * 32
    }

    # Add correct MAC
    data["mac"] = hmac.new(key_m, pack.encodeEciesData(data)[:-32], digestmod="sha256").digest()

    return base64.b64encode(key_e), base64.b64encode(pack.encodeEciesData(data))
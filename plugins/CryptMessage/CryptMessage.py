import hashlib
import base64
<<<<<<< HEAD
import struct

import lib.pybitcointools as btctools
=======
import sslcrypto
>>>>>>> Use sslcrypto instead of pyelliptic and pybitcointools
from Crypt import Crypt


<<<<<<< HEAD

def eciesEncrypt(data, pubkey, ephemcurve=None, ciphername='aes-256-cbc'):
    from lib import pyelliptic
    pubkey_openssl = toOpensslPublickey(base64.b64decode(pubkey))
    curve, pubkey_x, pubkey_y, i = pyelliptic.ECC._decode_pubkey(pubkey_openssl)
    if ephemcurve is None:
        ephemcurve = curve
    ephem = pyelliptic.ECC(curve=ephemcurve)
    key = hashlib.sha512(ephem.raw_get_ecdh_key(pubkey_x, pubkey_y)).digest()
    key_e, key_m = key[:32], key[32:]
    pubkey = ephem.get_pubkey()
    iv = pyelliptic.OpenSSL.rand(pyelliptic.OpenSSL.get_cipher(ciphername).get_blocksize())
    ctx = pyelliptic.Cipher(key_e, iv, 1, ciphername)
    ciphertext = iv + pubkey + ctx.ciphering(data)
    mac = pyelliptic.hmac_sha256(key_m, ciphertext)
    return key_e, ciphertext + mac
=======
curve = sslcrypto.ecc.get_curve("secp256k1")


def eciesEncrypt(data, pubkey, ciphername="aes-256-cbc"):
    ciphertext, key_e = curve.encrypt(data, base64.b64decode(pubkey), algo=ciphername, return_aes_key=True)
    return key_e, ciphertext
>>>>>>> Use sslcrypto instead of pyelliptic and pybitcointools


@Crypt.thread_pool_crypt.wrap
def eciesDecryptMulti(encrypted_datas, privatekey):
    texts = []  # Decoded texts
    for encrypted_data in encrypted_datas:
        try:
            text = eciesDecrypt(encrypted_data, privatekey).decode("utf8")
            texts.append(text)
        except Exception:
            texts.append(None)
    return texts


<<<<<<< HEAD
def eciesDecrypt(encrypted_data, privatekey):
    ecc_key = getEcc(privatekey)
    return ecc_key.decrypt(base64.b64decode(encrypted_data))


def decodePubkey(pubkey):
    i = 0
    curve = struct.unpack('!H', pubkey[i:i + 2])[0]
    i += 2
    tmplen = struct.unpack('!H', pubkey[i:i + 2])[0]
    i += 2
    pubkey_x = pubkey[i:i + tmplen]
    i += tmplen
    tmplen = struct.unpack('!H', pubkey[i:i + 2])[0]
    i += 2
    pubkey_y = pubkey[i:i + tmplen]
    i += tmplen
    return curve, pubkey_x, pubkey_y, i


def split(encrypted):
    iv = encrypted[0:16]
    curve, pubkey_x, pubkey_y, i = decodePubkey(encrypted[16:])
    ciphertext = encrypted[16 + i:-32]

    return iv, ciphertext


def getEcc(privatekey=None):
    from lib import pyelliptic
    global ecc_cache
    if privatekey not in ecc_cache:
        if privatekey:
            publickey_bin = btctools.encode_pubkey(btctools.privtopub(privatekey), "bin")
            publickey_openssl = toOpensslPublickey(publickey_bin)
            privatekey_openssl = toOpensslPrivatekey(privatekey)
            ecc_cache[privatekey] = pyelliptic.ECC(curve='secp256k1', privkey=privatekey_openssl, pubkey=publickey_openssl)
        else:
            ecc_cache[None] = pyelliptic.ECC()
    return ecc_cache[privatekey]


def toOpensslPrivatekey(privatekey):
    privatekey_bin = btctools.encode_privkey(privatekey, "bin")
    return b'\x02\xca\x00\x20' + privatekey_bin


def toOpensslPublickey(publickey):
    publickey_bin = btctools.encode_pubkey(publickey, "bin")
    publickey_bin = publickey_bin[1:]
    publickey_openssl = b'\x02\xca\x00 ' + publickey_bin[:32] + b'\x00 ' + publickey_bin[32:]
    return publickey_openssl
=======
def eciesDecrypt(ciphertext, privatekey):
    return curve.decrypt(base64.b64decode(ciphertext), curve.wif_to_private(privatekey))
>>>>>>> Use sslcrypto instead of pyelliptic and pybitcointools

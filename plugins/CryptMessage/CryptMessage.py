from lib.pybitcointools import bitcoin as btctools
import hashlib

ecc_cache = {}


def encrypt(data, pubkey, ephemcurve=None, ciphername='aes-256-cbc'):
    from lib import pyelliptic
    curve, pubkey_x, pubkey_y, i = pyelliptic.ECC._decode_pubkey(pubkey)
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


def split(encrypted):
    iv = encrypted[0:16]
    ciphertext = encrypted[16+70:-32]

    return iv, ciphertext


def getEcc(privatekey=None):
    from lib import pyelliptic
    global eccs
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
    return '\x02\xca\x00\x20' + privatekey_bin


def toOpensslPublickey(publickey):
    publickey_bin = btctools.encode_pubkey(publickey, "bin")
    publickey_bin = publickey_bin[1:]
    publickey_openssl = '\x02\xca\x00 ' + publickey_bin[:32] + '\x00 ' + publickey_bin[32:]
    return publickey_openssl

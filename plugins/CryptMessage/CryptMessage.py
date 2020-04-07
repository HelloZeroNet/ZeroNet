import hashlib
import base64
import struct
from lib import sslcrypto
from Crypt import Crypt


curve = sslcrypto.ecc.get_curve("secp256k1")


def eciesEncrypt(data, pubkey, ciphername="aes-256-cbc"):
    ciphertext, key_e = curve.encrypt(
        data,
        base64.b64decode(pubkey),
        algo=ciphername,
        derivation="sha512",
        return_aes_key=True
    )
    return key_e, ciphertext


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


def eciesDecrypt(ciphertext, privatekey):
    return curve.decrypt(base64.b64decode(ciphertext), curve.wif_to_private(privatekey.encode()), derivation="sha512")


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

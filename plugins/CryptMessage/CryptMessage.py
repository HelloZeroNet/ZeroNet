import hashlib
import base64
import sslcrypto
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
        except:
            texts.append(None)
    return texts


def eciesDecrypt(ciphertext, privatekey):
    return curve.decrypt(
        base64.b64decode(ciphertext),
        curve.wif_to_private(privatekey),
        derivation="sha512"
    )

def split(ciphertext):
    return ciphertext[:16], ciphertext[86:-32]

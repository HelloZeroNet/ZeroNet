import hashlib
import base64

import lib.pybitcointools as btctools
from lib.ecies import eciesEncrypt, eciesDecrypt

def split(encrypted):
    iv = encrypted[0:16]
    ciphertext = encrypted[16 + 70:-32]

    return iv, ciphertext

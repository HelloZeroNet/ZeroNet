import logging
import base64
import binascii
import time
import hashlib

from util.Electrum import dbl_format
from Config import config

lib_verify_best = "sslcrypto"

from lib import sslcrypto
sslcurve_native = sslcrypto.ecc.get_curve("secp256k1")
sslcurve_fallback = sslcrypto.fallback.ecc.get_curve("secp256k1")
sslcurve = sslcurve_native

def loadLib(lib_name, silent=False):
    global sslcurve, libsecp256k1message, lib_verify_best
    if lib_name == "libsecp256k1":
        s = time.time()
        from lib import libsecp256k1message
        import coincurve
        lib_verify_best = "libsecp256k1"
        if not silent:
            logging.info(
                "Libsecpk256k1 loaded: %s in %.3fs" %
                (type(coincurve._libsecp256k1.lib).__name__, time.time() - s)
            )
    elif lib_name == "sslcrypto":
        sslcurve = sslcurve_native
    elif lib_name == "sslcrypto_fallback":
        sslcurve = sslcurve_fallback

try:
    if not config.use_libsecp256k1:
        raise Exception("Disabled by config")
    loadLib("libsecp256k1")
    lib_verify_best = "libsecp256k1"
except Exception as err:
    logging.info("Libsecp256k1 load failed: %s" % err)


def newPrivatekey():  # Return new private key
    return sslcurve.private_to_wif(sslcurve.new_private_key()).decode()


def newSeed():
    return binascii.hexlify(sslcurve.new_private_key()).decode()


def hdPrivatekey(seed, child):
    # Too large child id could cause problems
    privatekey_bin = sslcurve.derive_child(seed.encode(), child % 100000000)
    return sslcurve.private_to_wif(privatekey_bin).decode()


def privatekeyToAddress(privatekey):  # Return address from private key
    try:
        if len(privatekey) == 64:
            privatekey_bin = bytes.fromhex(privatekey)
        else:
            privatekey_bin = sslcurve.wif_to_private(privatekey.encode())
        return sslcurve.private_to_address(privatekey_bin).decode()
    except Exception:  # Invalid privatekey
        return False


def sign(data, privatekey):  # Return sign to data using private key
    if privatekey.startswith("23") and len(privatekey) > 52:
        return None  # Old style private key not supported
    return base64.b64encode(sslcurve.sign(
        data.encode(),
        sslcurve.wif_to_private(privatekey.encode()),
        recoverable=True,
        hash=dbl_format
    )).decode()


def verify(data, valid_address, sign, lib_verify=None):  # Verify data using address and sign
    if not lib_verify:
        lib_verify = lib_verify_best

    if not sign:
        return False

    if lib_verify == "libsecp256k1":
        sign_address = libsecp256k1message.recover_address(data.encode("utf8"), sign).decode("utf8")
    elif lib_verify in ("sslcrypto", "sslcrypto_fallback"):
        publickey = sslcurve.recover(base64.b64decode(sign), data.encode(), hash=dbl_format)
        sign_address = sslcurve.public_to_address(publickey).decode()
    else:
        raise Exception("No library enabled for signature verification")

    if type(valid_address) is list:  # Any address in the list
        return sign_address in valid_address
    else:  # One possible address
        return sign_address == valid_address

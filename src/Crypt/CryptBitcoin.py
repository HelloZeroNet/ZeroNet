import logging
import base64

from util import OpensslFindPatch
from lib import pybitcointools as btctools
from Config import config
from Crypt.Cryptography import WrongCryptoError

lib_verify_best = "btctools"


def loadLib(lib_name):
    global bitcoin, libsecp256k1message, lib_verify_best
    if lib_name == "libsecp256k1":
        from lib import libsecp256k1message
        lib_verify_best = "libsecp256k1"
        logging.info("Libsecpk256k1 loaded")
    elif lib_name == "openssl":
        import bitcoin.signmessage
        import bitcoin.core.key
        import bitcoin.wallet

        logging.info("OpenSSL loaded, version: %.9X" % bitcoin.core.key._ssl.SSLeay())

try:
    if not config.use_libsecp256k1:
        raise Exception("Disabled by config")
    loadLib("libsecp256k1")
    lib_verify_best = "libsecp256k1"
except Exception as err:
    logging.info("Libsecp256k1 load failed: %s, try to load OpenSSL" % err)
    try:
        if not config.use_openssl:
            raise Exception("Disabled by config")
        loadLib("openssl")
        lib_verify_best = "openssl"
    except Exception as err:
        logging.info("OpenSSL load failed: %s, falling back to slow bitcoin verify" % err)


def newPrivatekey():  # Return new private key
    privatekey = btctools.encode_privkey(btctools.random_key(), "wif")
    return privatekey


def newSeed():
    return btctools.random_key()


def hdPrivatekey(seed, child):
    if "|" in seed:
        raise WrongCryptoError()
    masterkey = btctools.bip32_master_key(bytes(seed, "ascii"))
    childkey = btctools.bip32_ckd(masterkey, child % 100000000)  # Too large child id could cause problems
    key = btctools.bip32_extract_key(childkey)
    return btctools.encode_privkey(key, "wif")


def privatekeyToAddress(privatekey):  # Return address from private key
    try:
        return btctools.privkey_to_address(privatekey)
    except Exception:  # Invalid privatekey
        raise WrongCryptoError()


def sign(data, privatekey):  # Return sign to data using private key
    if not privatekey.startswith("1"):
        raise WrongCryptoError()
    if privatekey.startswith("23") and len(privatekey) > 52:
        return None  # Old style private key not supported
    sign = btctools.ecdsa_sign(data, privatekey)
    return sign


def verify(data, valid_address, sign, lib_verify=None):  # Verify data using address and sign
    if not lib_verify:
        lib_verify = lib_verify_best

    if lib_verify == "libsecp256k1":
        try:
            sign_address = libsecp256k1message.recover_address(data.encode("utf8"), sign).decode("utf8")
        except Exception:
            raise WrongCryptoError()
    elif lib_verify == "openssl":
        sig = base64.b64decode(sign)
        message = bitcoin.signmessage.BitcoinMessage(data)
        hash = message.GetHash()

        try:
            pubkey = bitcoin.core.key.CPubKey.recover_compact(hash, sig)
        except Exception:
            raise WrongCryptoError()

        sign_address = str(bitcoin.wallet.P2PKHBitcoinAddress.from_pubkey(pubkey))
    elif lib_verify == "btctools":  # Use pure-python
        try:
            pub = btctools.ecdsa_recover(data, sign)
        except Exception:
            raise WrongCryptoError()
        sign_address = btctools.pubtoaddr(pub)
    else:
        raise Exception("No library enabled for signature verification")

    if type(valid_address) is list:  # Any address in the list
        return sign_address in valid_address
    else:  # One possible address
        return sign_address == valid_address

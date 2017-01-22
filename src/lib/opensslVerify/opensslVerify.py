# via http://pastebin.com/H1XikJFd
# -*- Mode: Python -*-

# This is a combination of http://pastebin.com/bQtdDzHx and
# https://github.com/Bitmessage/PyBitmessage/blob/master/src/pyelliptic/openssl.py
# that doesn't crash on OSX.
# Long message bug fixed by ZeroNet

import ctypes
import ctypes.util
import _ctypes
import hashlib
import base64
import time
import logging
import sys
import os

addrtype = 0


class _OpenSSL:

    """
    Wrapper for OpenSSL using ctypes
    """

    def __init__(self, library):
        self.time_opened = time.time()
        """
        Build the wrapper
        """
        try:
            self._lib = ctypes.CDLL(library)
        except:
            self._lib = ctypes.cdll.LoadLibrary(library)

        self.pointer = ctypes.pointer
        self.c_int = ctypes.c_int
        self.byref = ctypes.byref
        self.create_string_buffer = ctypes.create_string_buffer

        self.BN_new = self._lib.BN_new
        self.BN_new.restype = ctypes.c_void_p
        self.BN_new.argtypes = []

        self.BN_copy = self._lib.BN_copy
        self.BN_copy.restype = ctypes.c_void_p
        self.BN_copy.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        self.BN_mul_word = self._lib.BN_mul_word
        self.BN_mul_word.restype = ctypes.c_int
        self.BN_mul_word.argtypes = [ctypes.c_void_p, ctypes.c_int]

        self.BN_set_word = self._lib.BN_set_word
        self.BN_set_word.restype = ctypes.c_int
        self.BN_set_word.argtypes = [ctypes.c_void_p, ctypes.c_int]

        self.BN_add = self._lib.BN_add
        self.BN_add.restype = ctypes.c_void_p
        self.BN_add.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.c_void_p]

        self.BN_mod_sub = self._lib.BN_mod_sub
        self.BN_mod_sub.restype = ctypes.c_int
        self.BN_mod_sub.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_void_p,
                                    ctypes.c_void_p,
                                    ctypes.c_void_p]

        self.BN_mod_mul = self._lib.BN_mod_mul
        self.BN_mod_mul.restype = ctypes.c_int
        self.BN_mod_mul.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_void_p,
                                    ctypes.c_void_p,
                                    ctypes.c_void_p]

        self.BN_mod_inverse = self._lib.BN_mod_inverse
        self.BN_mod_inverse.restype = ctypes.c_void_p
        self.BN_mod_inverse.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_void_p,
                                        ctypes.c_void_p]

        self.BN_cmp = self._lib.BN_cmp
        self.BN_cmp.restype = ctypes.c_int
        self.BN_cmp.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        self.BN_bn2bin = self._lib.BN_bn2bin
        self.BN_bn2bin.restype = ctypes.c_int
        self.BN_bn2bin.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        self.BN_bin2bn = self._lib.BN_bin2bn
        self.BN_bin2bn.restype = ctypes.c_void_p
        self.BN_bin2bn.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                   ctypes.c_void_p]

        self.EC_KEY_new_by_curve_name = self._lib.EC_KEY_new_by_curve_name
        self.EC_KEY_new_by_curve_name.restype = ctypes.c_void_p
        self.EC_KEY_new_by_curve_name.argtypes = [ctypes.c_int]

        self.EC_KEY_get0_group = self._lib.EC_KEY_get0_group
        self.EC_KEY_get0_group.restype = ctypes.c_void_p
        self.EC_KEY_get0_group.argtypes = [ctypes.c_void_p]

        self.EC_KEY_set_private_key = self._lib.EC_KEY_set_private_key
        self.EC_KEY_set_private_key.restype = ctypes.c_int
        self.EC_KEY_set_private_key.argtypes = [ctypes.c_void_p,
                                                ctypes.c_void_p]

        self.EC_KEY_set_public_key = self._lib.EC_KEY_set_public_key
        self.EC_KEY_set_public_key.restype = ctypes.c_int
        self.EC_KEY_set_public_key.argtypes = [ctypes.c_void_p,
                                               ctypes.c_void_p]

        self.EC_POINT_set_compressed_coordinates_GFp = self._lib.EC_POINT_set_compressed_coordinates_GFp
        self.EC_POINT_set_compressed_coordinates_GFp.restype = ctypes.c_int
        self.EC_POINT_set_compressed_coordinates_GFp.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]

        self.EC_POINT_new = self._lib.EC_POINT_new
        self.EC_POINT_new.restype = ctypes.c_void_p
        self.EC_POINT_new.argtypes = [ctypes.c_void_p]

        self.EC_POINT_free = self._lib.EC_POINT_free
        self.EC_POINT_free.restype = None
        self.EC_POINT_free.argtypes = [ctypes.c_void_p]

        self.EC_GROUP_get_order = self._lib.EC_GROUP_get_order
        self.EC_GROUP_get_order.restype = ctypes.c_void_p
        self.EC_GROUP_get_order.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

        self.EC_GROUP_get_degree = self._lib.EC_GROUP_get_degree
        self.EC_GROUP_get_degree.restype = ctypes.c_void_p
        self.EC_GROUP_get_degree.argtypes = [ctypes.c_void_p]

        self.EC_GROUP_get_curve_GFp = self._lib.EC_GROUP_get_curve_GFp
        self.EC_GROUP_get_curve_GFp.restype = ctypes.c_void_p
        self.EC_GROUP_get_curve_GFp.argtypes = [ctypes.c_void_p,
                                                ctypes.c_void_p,
                                                ctypes.c_void_p,
                                                ctypes.c_void_p,
                                                ctypes.c_void_p]

        self.EC_POINT_mul = self._lib.EC_POINT_mul
        self.EC_POINT_mul.restype = ctypes.c_int
        self.EC_POINT_mul.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p, ctypes.c_void_p]

        self.EC_KEY_set_private_key = self._lib.EC_KEY_set_private_key
        self.EC_KEY_set_private_key.restype = ctypes.c_int
        self.EC_KEY_set_private_key.argtypes = [ctypes.c_void_p,
                                                ctypes.c_void_p]

        self.EC_KEY_set_conv_form = self._lib.EC_KEY_set_conv_form
        self.EC_KEY_set_conv_form.restype = None
        self.EC_KEY_set_conv_form.argtypes = [ctypes.c_void_p,
                                              ctypes.c_int]

        self.BN_CTX_new = self._lib.BN_CTX_new
        self._lib.BN_CTX_new.restype = ctypes.c_void_p
        self._lib.BN_CTX_new.argtypes = []

        self.BN_CTX_start = self._lib.BN_CTX_start
        self._lib.BN_CTX_start.restype = ctypes.c_void_p
        self._lib.BN_CTX_start.argtypes = [ctypes.c_void_p]

        self.BN_CTX_get = self._lib.BN_CTX_get
        self._lib.BN_CTX_get.restype = ctypes.c_void_p
        self._lib.BN_CTX_get.argtypes = [ctypes.c_void_p]

        self.ECDSA_sign = self._lib.ECDSA_sign
        self.ECDSA_sign.restype = ctypes.c_int
        self.ECDSA_sign.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

        self.ECDSA_verify = self._lib.ECDSA_verify
        self.ECDSA_verify.restype = ctypes.c_int
        self.ECDSA_verify.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                      ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]

        self.i2o_ECPublicKey = self._lib.i2o_ECPublicKey
        self.i2o_ECPublicKey.restype = ctypes.c_void_p
        self.i2o_ECPublicKey.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        self.BN_CTX_free = self._lib.BN_CTX_free
        self.BN_CTX_free.restype = None
        self.BN_CTX_free.argtypes = [ctypes.c_void_p]

        self.EC_POINT_free = self._lib.EC_POINT_free
        self.EC_POINT_free.restype = None
        self.EC_POINT_free.argtypes = [ctypes.c_void_p]

ssl = None

def openLibrary():
    global ssl
    try:
        if sys.platform.startswith("win"):
            dll_path = os.path.dirname(os.path.abspath(__file__)) + "/" + "libeay32.dll"
        elif sys.platform == "cygwin":
            dll_path = "/bin/cygcrypto-1.0.0.dll"
        elif os.path.isfile("../lib/libcrypto.so"): # ZeroBundle OSX
            dll_path = "../lib/libcrypto.so"
        elif os.path.isfile("/opt/lib/libcrypto.so.1.0.0"): # For optware and entware
            dll_path = "/opt/lib/libcrypto.so.1.0.0"
        else:
            dll_path = "/usr/local/ssl/lib/libcrypto.so"
        ssl = _OpenSSL(dll_path)
        assert ssl
    except Exception, err:
        ssl = _OpenSSL(ctypes.util.find_library('ssl') or ctypes.util.find_library('crypto') or ctypes.util.find_library('libcrypto') or 'libeay32')
    logging.debug("opensslVerify loaded: %s", ssl._lib)

openLibrary()
openssl_version = "%.9X" % ssl._lib.SSLeay()

NID_secp256k1 = 714


def check_result(val, func, args):
    if val == 0:
        raise ValueError
    else:
        return ctypes.c_void_p(val)

ssl.EC_KEY_new_by_curve_name.restype = ctypes.c_void_p
ssl.EC_KEY_new_by_curve_name.errcheck = check_result

POINT_CONVERSION_COMPRESSED = 2
POINT_CONVERSION_UNCOMPRESSED = 4

__b58chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
__b58base = len(__b58chars)


def b58encode(v):
    """ encode v, which is a string of bytes, to base58.
    """

    long_value = 0L
    for (i, c) in enumerate(v[::-1]):
        long_value += (256 ** i) * ord(c)

    result = ''
    while long_value >= __b58base:
        div, mod = divmod(long_value, __b58base)
        result = __b58chars[mod] + result
        long_value = div
    result = __b58chars[long_value] + result

    # Bitcoin does a little leading-zero-compression:
    # leading 0-bytes in the input become leading-1s
    nPad = 0
    for c in v:
        if c == '\0':
            nPad += 1
        else:
            break

    return (__b58chars[0] * nPad) + result


def hash_160(public_key):
    md = hashlib.new('ripemd160')
    md.update(hashlib.sha256(public_key).digest())
    return md.digest()


def hash_160_to_bc_address(h160):
    vh160 = chr(addrtype) + h160
    h = Hash(vh160)
    addr = vh160 + h[0:4]
    return b58encode(addr)


def public_key_to_bc_address(public_key):
    h160 = hash_160(public_key)
    return hash_160_to_bc_address(h160)


def encode(val, base, minlen=0):
    base, minlen = int(base), int(minlen)
    code_string = ''.join([chr(x) for x in range(256)])
    result = ""
    while val > 0:
        result = code_string[val % base] + result
        val //= base
    return code_string[0] * max(minlen - len(result), 0) + result


def num_to_var_int(x):
    x = int(x)
    if x < 253:
        return chr(x)
    elif x < 65536:
        return chr(253) + encode(x, 256, 2)[::-1]
    elif x < 4294967296:
        return chr(254) + encode(x, 256, 4)[::-1]
    else:
        return chr(255) + encode(x, 256, 8)[::-1]


def msg_magic(message):
    return "\x18Bitcoin Signed Message:\n" + num_to_var_int(len(message)) + message


def get_address(eckey):
    size = ssl.i2o_ECPublicKey(eckey, 0)
    mb = ctypes.create_string_buffer(size)
    ssl.i2o_ECPublicKey(eckey, ctypes.byref(ctypes.pointer(mb)))
    return public_key_to_bc_address(mb.raw)


def Hash(data):
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def bx(bn, size=32):
    b = ctypes.create_string_buffer(size)
    ssl.BN_bn2bin(bn, b)
    return b.raw.encode('hex')


def verify_message(address, signature, message):
    pkey = ssl.EC_KEY_new_by_curve_name(NID_secp256k1)
    eckey = SetCompactSignature(pkey, Hash(msg_magic(message)), signature)
    addr = get_address(eckey)
    return (address == addr)


def SetCompactSignature(pkey, hash, signature):
    sig = base64.b64decode(signature)
    if len(sig) != 65:
        raise BaseException("Wrong encoding")
    nV = ord(sig[0])
    if nV < 27 or nV >= 35:
        return False
    if nV >= 31:
        ssl.EC_KEY_set_conv_form(pkey, POINT_CONVERSION_COMPRESSED)
        nV -= 4
    r = ssl.BN_bin2bn(sig[1:33], 32, None)
    s = ssl.BN_bin2bn(sig[33:], 32, None)
    eckey = ECDSA_SIG_recover_key_GFp(pkey, r, s, hash, len(hash), nV - 27,
                                      False)
    return eckey


def ECDSA_SIG_recover_key_GFp(eckey, r, s, msg, msglen, recid, check):
    n = 0
    i = recid / 2
    ctx = R = O = Q = None

    try:
        group = ssl.EC_KEY_get0_group(eckey)
        ctx = ssl.BN_CTX_new()
        ssl.BN_CTX_start(ctx)
        order = ssl.BN_CTX_get(ctx)
        ssl.EC_GROUP_get_order(group, order, ctx)
        x = ssl.BN_CTX_get(ctx)
        ssl.BN_copy(x, order)
        ssl.BN_mul_word(x, i)
        ssl.BN_add(x, x, r)
        field = ssl.BN_CTX_get(ctx)
        ssl.EC_GROUP_get_curve_GFp(group, field, None, None, ctx)

        if (ssl.BN_cmp(x, field) >= 0):
            return False

        R = ssl.EC_POINT_new(group)
        ssl.EC_POINT_set_compressed_coordinates_GFp(group, R, x, recid % 2, ctx)

        if check:
            O = ssl.EC_POINT_new(group)
            ssl.EC_POINT_mul(group, O, None, R, order, ctx)
            if ssl.EC_POINT_is_at_infinity(group, O):
                return False

        Q = ssl.EC_POINT_new(group)
        n = ssl.EC_GROUP_get_degree(group)
        e = ssl.BN_CTX_get(ctx)
        ssl.BN_bin2bn(msg, msglen, e)
        if 8 * msglen > n:
            ssl.BN_rshift(e, e, 8 - (n & 7))

        zero = ssl.BN_CTX_get(ctx)
        ssl.BN_set_word(zero, 0)
        ssl.BN_mod_sub(e, zero, e, order, ctx)
        rr = ssl.BN_CTX_get(ctx)
        ssl.BN_mod_inverse(rr, r, order, ctx)
        sor = ssl.BN_CTX_get(ctx)
        ssl.BN_mod_mul(sor, s, rr, order, ctx)
        eor = ssl.BN_CTX_get(ctx)
        ssl.BN_mod_mul(eor, e, rr, order, ctx)
        ssl.EC_POINT_mul(group, Q, eor, R, sor, ctx)
        ssl.EC_KEY_set_public_key(eckey, Q)
        return eckey
    finally:
        if ctx:
            ssl.BN_CTX_free(ctx)
        if R:
            ssl.EC_POINT_free(R)
        if O:
            ssl.EC_POINT_free(O)
        if Q:
            ssl.EC_POINT_free(Q)


def closeLibrary():
    handle = ssl._lib._handle
    if "FreeLibrary" in dir(_ctypes):
        _ctypes.FreeLibrary(handle)
        _ctypes.FreeLibrary(handle)
        print "OpenSSL closed, handle:", handle
    else:
        _ctypes.dlclose(handle)
        _ctypes.dlclose(handle)
        print "OpenSSL dlclosed, handle:", handle


def getMessagePubkey(message, sig):
    pkey = ssl.EC_KEY_new_by_curve_name(NID_secp256k1)
    if type(pkey) is not int and not pkey.value:
        raise Exception(
            "OpenSSL %s (%s) EC_KEY_new_by_curve_name failed: %s, probably your OpenSSL lib does not support secp256k1 elliptic curve. Please check: https://github.com/HelloZeroNet/ZeroNet/issues/132" %
            (openssl_version, ssl._lib._name, pkey.value)
        )
    eckey = SetCompactSignature(pkey, Hash(msg_magic(message)), sig)
    size = ssl.i2o_ECPublicKey(eckey, 0)
    mb = ctypes.create_string_buffer(size)
    ssl.i2o_ECPublicKey(eckey, ctypes.byref(ctypes.pointer(mb)))
    pub = mb.raw
    """
    if time.time() - ssl.time_opened > 60 * 5:  # Reopen every 5 min
        logging.debug("Reopening OpenSSL...")
        closeLibrary()
        openLibrary()
    """
    return pub


def test():
    sign = "HGbib2kv9gm9IJjDt1FXbXFczZi35u0rZR3iPUIt5GglDDCeIQ7v8eYXVNIaLoJRI4URGZrhwmsYQ9aVtRTnTfQ="
    pubkey = "044827c756561b8ef6b28b5e53a000805adbf4938ab82e1c2b7f7ea16a0d6face9a509a0a13e794d742210b00581f3e249ebcc705240af2540ea19591091ac1d41"
    assert getMessagePubkey("hello", sign).encode("hex") == pubkey

test()  # Make sure it working right

if __name__ == "__main__":
    import time
    import os
    import sys
    sys.path.append("..")
    from pybitcointools import bitcoin as btctools
    print "OpenSSL version %s" % openssl_version
    print ssl._lib
    priv = "5JsunC55XGVqFQj5kPGK4MWgTL26jKbnPhjnmchSNPo75XXCwtk"
    address = "1N2XWu5soeppX2qUjvrf81rpdbShKJrjTr"
    sign = btctools.ecdsa_sign("hello", priv)  # HGbib2kv9gm9IJjDt1FXbXFczZi35u0rZR3iPUIt5GglDDCeIQ7v8eYXVNIaLoJRI4URGZrhwmsYQ9aVtRTnTfQ=

    s = time.time()
    for i in range(1000):
        pubkey = getMessagePubkey("hello", sign)
        verified = btctools.pubkey_to_address(pubkey) == address
    print "100x Verified", verified, time.time() - s

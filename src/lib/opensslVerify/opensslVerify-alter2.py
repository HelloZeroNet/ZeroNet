#!/usr/bin/env python
##
## @file contrib/verifymessage/python/terracoin_verifymessage.py
## @brief terracoin signed message verification sample script.
## @author unknown author ; found on pastebin
##

import ctypes
import ctypes.util
import hashlib
import base64
addrtype = 0

try:
	ssl = ctypes.CDLL("src/lib/opensslVerify/libeay32.dll")
except:
	ssl = ctypes.cdll.LoadLibrary(ctypes.util.find_library('ssl') or ctypes.util.find_library('crypto') or 'libeay32')

openssl_version = "%.9X" % ssl.SSLeay()

NID_secp256k1 = 714

def check_result (val, func, args):
	if val == 0:
		raise ValueError
	else:
		return ctypes.c_void_p (val)

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
		long_value += (256**i) * ord(c)

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
		if c == '\0': nPad += 1
		else: break

	return (__b58chars[0]*nPad) + result

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
	if x < 253: return chr(x)
	elif x < 65536: return chr(253)+encode(x, 256, 2)[::-1]
	elif x < 4294967296: return chr(254) + encode(x, 256, 4)[::-1]
	else: return chr(255) + encode(x, 256, 8)[::-1]

def msg_magic(message):
	return "\x18Bitcoin Signed Message:\n" + num_to_var_int( len(message) ) + message 

def get_address(eckey):
	size = ssl.i2o_ECPublicKey (eckey, 0)
	mb = ctypes.create_string_buffer (size)
	ssl.i2o_ECPublicKey (eckey, ctypes.byref (ctypes.pointer (mb)))
	return public_key_to_bc_address(mb.raw)

def Hash(data):
	return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def bx(bn, size=32):
	b = ctypes.create_string_buffer(size)
	ssl.BN_bn2bin(bn, b);
	return b.raw.encode('hex')

def verify_message(address, signature, message):
	pkey = ssl.EC_KEY_new_by_curve_name (NID_secp256k1)
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
	r = ssl.BN_bin2bn (sig[1:33], 32, ssl.BN_new())
	s = ssl.BN_bin2bn (sig[33:], 32, ssl.BN_new())
	eckey = ECDSA_SIG_recover_key_GFp(pkey, r, s, hash, len(hash), nV - 27, False);
	return eckey

def ECDSA_SIG_recover_key_GFp(eckey, r, s, msg, msglen, recid, check):
	n = 0
	i = recid / 2

	group = ssl.EC_KEY_get0_group(eckey)
	ctx = ssl.BN_CTX_new()
	ssl.BN_CTX_start(ctx)
	order = ssl.BN_CTX_get(ctx)
	ssl.EC_GROUP_get_order(group, order, ctx)
	x = ssl.BN_CTX_get(ctx)
	ssl.BN_copy(x, order);
	ssl.BN_mul_word(x, i);
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
	if 8 * msglen > n: ssl.BN_rshift(e, e, 8 - (n & 7))


	zero = ssl.BN_CTX_get(ctx)
	ssl.BN_set_word(zero, 0)
	ssl.BN_mod_sub(e, zero, e, order, ctx)
	rr = ssl.BN_CTX_get(ctx);
	ssl.BN_mod_inverse(rr, r, order, ctx)
	sor = ssl.BN_CTX_get(ctx)
	ssl.BN_mod_mul(sor, s, rr, order, ctx)
	eor = ssl.BN_CTX_get(ctx)
	ssl.BN_mod_mul(eor, e, rr, order, ctx)
	ssl.EC_POINT_mul(group, Q, eor, R, sor, ctx)
	ssl.EC_KEY_set_public_key(eckey, Q)
	return eckey


def getMessagePubkey(message, sig):
	pkey = ssl.EC_KEY_new_by_curve_name(NID_secp256k1)
	eckey = SetCompactSignature(pkey, Hash(msg_magic(message)), sig)
	size = ssl.i2o_ECPublicKey (eckey, 0)
	mb = ctypes.create_string_buffer (size)
	ssl.i2o_ECPublicKey (eckey, ctypes.byref (ctypes.pointer (mb)))
	return mb.raw

def test():
	sign = "HGbib2kv9gm9IJjDt1FXbXFczZi35u0rZR3iPUIt5GglDDCeIQ7v8eYXVNIaLoJRI4URGZrhwmsYQ9aVtRTnTfQ="
	pubkey = "044827c756561b8ef6b28b5e53a000805adbf4938ab82e1c2b7f7ea16a0d6face9a509a0a13e794d742210b00581f3e249ebcc705240af2540ea19591091ac1d41"
	assert getMessagePubkey("hello", sign).encode("hex") == pubkey

test() # Make sure it working right

if __name__ == "__main__":
	import time, os, sys
	sys.path.append("..")
	from pybitcointools import bitcoin as btctools
	priv = "5JsunC55XGVqFQj5kPGK4MWgTL26jKbnPhjnmchSNPo75XXCwtk"
	address = "1N2XWu5soeppX2qUjvrf81rpdbShKJrjTr"
	sign = btctools.ecdsa_sign("hello", priv) # HGbib2kv9gm9IJjDt1FXbXFczZi35u0rZR3iPUIt5GglDDCeIQ7v8eYXVNIaLoJRI4URGZrhwmsYQ9aVtRTnTfQ=

	s = time.time()
	for i in range(100):
		pubkey = getMessagePubkey("hello", sign)
		verified = btctools.pubkey_to_address(pubkey) == address
	print "100x Verified", verified, time.time()-s 

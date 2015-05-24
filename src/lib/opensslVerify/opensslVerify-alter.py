# Code is borrowed from https://github.com/blocktrail/python-bitcoinlib
# Thanks!

import base64, hashlib

import ctypes
import ctypes.util
_bchr = chr
_bord = ord
try:
	_ssl = ctypes.CDLL("src/lib/opensslVerify/libeay32.dll")
except:
	_ssl = ctypes.cdll.LoadLibrary(ctypes.util.find_library('ssl') or ctypes.util.find_library('crypto') or 'libeay32')

import sys

openssl_version = "%.9X" % _ssl.SSLeay()


# this specifies the curve used with ECDSA.
_NID_secp256k1 = 714 # from openssl/obj_mac.h

# Thx to Sam Devlin for the ctypes magic 64-bit fix.
def _check_result (val, func, args):
	if val == 0:
		raise ValueError
	else:
		return ctypes.c_void_p(val)

_ssl.EC_KEY_new_by_curve_name.restype = ctypes.c_void_p
_ssl.EC_KEY_new_by_curve_name.errcheck = _check_result

# From openssl/ecdsa.h
class ECDSA_SIG_st(ctypes.Structure):
	 _fields_ = [("r", ctypes.c_void_p),
				("s", ctypes.c_void_p)] 

class CECKey:
	"""Wrapper around OpenSSL's EC_KEY"""

	POINT_CONVERSION_COMPRESSED = 2
	POINT_CONVERSION_UNCOMPRESSED = 4

	def __init__(self):
		self.k = _ssl.EC_KEY_new_by_curve_name(_NID_secp256k1)

	def __del__(self):
		if _ssl:
			_ssl.EC_KEY_free(self.k)
		self.k = None

	def set_secretbytes(self, secret):
		priv_key = _ssl.BN_bin2bn(secret, 32, _ssl.BN_new())
		group = _ssl.EC_KEY_get0_group(self.k)
		pub_key = _ssl.EC_POINT_new(group)
		ctx = _ssl.BN_CTX_new()
		if not _ssl.EC_POINT_mul(group, pub_key, priv_key, None, None, ctx):
			raise ValueError("Could not derive public key from the supplied secret.")
		_ssl.EC_POINT_mul(group, pub_key, priv_key, None, None, ctx)
		_ssl.EC_KEY_set_private_key(self.k, priv_key)
		_ssl.EC_KEY_set_public_key(self.k, pub_key)
		_ssl.EC_POINT_free(pub_key)
		_ssl.BN_CTX_free(ctx)
		return self.k

	def set_privkey(self, key):
		self.mb = ctypes.create_string_buffer(key)
		return _ssl.d2i_ECPrivateKey(ctypes.byref(self.k), ctypes.byref(ctypes.pointer(self.mb)), len(key))

	def set_pubkey(self, key):
		self.mb = ctypes.create_string_buffer(key)
		return _ssl.o2i_ECPublicKey(ctypes.byref(self.k), ctypes.byref(ctypes.pointer(self.mb)), len(key))

	def get_privkey(self):
		size = _ssl.i2d_ECPrivateKey(self.k, 0)
		mb_pri = ctypes.create_string_buffer(size)
		_ssl.i2d_ECPrivateKey(self.k, ctypes.byref(ctypes.pointer(mb_pri)))
		return mb_pri.raw

	def get_pubkey(self):
		size = _ssl.i2o_ECPublicKey(self.k, 0)
		mb = ctypes.create_string_buffer(size)
		_ssl.i2o_ECPublicKey(self.k, ctypes.byref(ctypes.pointer(mb)))
		return mb.raw

	def get_raw_ecdh_key(self, other_pubkey):
		ecdh_keybuffer = ctypes.create_string_buffer(32)
		r = _ssl.ECDH_compute_key(ctypes.pointer(ecdh_keybuffer), 32,
								 _ssl.EC_KEY_get0_public_key(other_pubkey.k),
								 self.k, 0)
		if r != 32:
			raise Exception('CKey.get_ecdh_key(): ECDH_compute_key() failed')
		return ecdh_keybuffer.raw

	def get_ecdh_key(self, other_pubkey, kdf=lambda k: hashlib.sha256(k).digest()):
		# FIXME: be warned it's not clear what the kdf should be as a default
		r = self.get_raw_ecdh_key(other_pubkey)
		return kdf(r)

	def sign(self, hash):
		if not isinstance(hash, bytes):
			raise TypeError('Hash must be bytes instance; got %r' % hash.__class__)
		if len(hash) != 32:
			raise ValueError('Hash must be exactly 32 bytes long')

		sig_size0 = ctypes.c_uint32()
		sig_size0.value = _ssl.ECDSA_size(self.k)
		mb_sig = ctypes.create_string_buffer(sig_size0.value)
		result = _ssl.ECDSA_sign(0, hash, len(hash), mb_sig, ctypes.byref(sig_size0), self.k)
		assert 1 == result
		if bitcoin.core.script.IsLowDERSignature(mb_sig.raw[:sig_size0.value]):
			return mb_sig.raw[:sig_size0.value]
		else:
			return self.signature_to_low_s(mb_sig.raw[:sig_size0.value])

	def sign_compact(self, hash):
		if not isinstance(hash, bytes):
			raise TypeError('Hash must be bytes instance; got %r' % hash.__class__)
		if len(hash) != 32:
			raise ValueError('Hash must be exactly 32 bytes long')

		sig_size0 = ctypes.c_uint32()
		sig_size0.value = _ssl.ECDSA_size(self.k)
		mb_sig = ctypes.create_string_buffer(sig_size0.value)
		result = _ssl.ECDSA_sign(0, hash, len(hash), mb_sig, ctypes.byref(sig_size0), self.k)
		assert 1 == result

		if bitcoin.core.script.IsLowDERSignature(mb_sig.raw[:sig_size0.value]):
			sig = mb_sig.raw[:sig_size0.value]
		else:
			sig = self.signature_to_low_s(mb_sig.raw[:sig_size0.value])

		sig = bitcoin.core.DERSignature.deserialize(sig)

		r_val = sig.r
		s_val = sig.s

		# assert that the r and s are less than 32 long, excluding leading 0s
		assert len(r_val) <= 32 or r_val[0:-32] == b'\x00'
		assert len(s_val) <= 32 or s_val[0:-32] == b'\x00'

		# ensure r and s are always 32 chars long by 0padding
		r_val = ((b'\x00' * 32) + r_val)[-32:]
		s_val = ((b'\x00' * 32) + s_val)[-32:]

		# tmp pubkey of self, but always compressed
		pubkey = CECKey()
		pubkey.set_pubkey(self.get_pubkey())
		pubkey.set_compressed(True)

		# bitcoin core does <4, but I've seen other places do <2 and I've never seen a i > 1 so far
		for i in range(0, 4):
			cec_key = CECKey()
			cec_key.set_compressed(True)

			result = cec_key.recover(r_val, s_val, hash, len(hash), i, 1)
			if result == 1:
				if cec_key.get_pubkey() == pubkey.get_pubkey():
					return r_val + s_val, i

		raise ValueError

	def signature_to_low_s(self, sig):
		der_sig = ECDSA_SIG_st()
		_ssl.d2i_ECDSA_SIG(ctypes.byref(ctypes.pointer(der_sig)), ctypes.byref(ctypes.c_char_p(sig)), len(sig))
		group = _ssl.EC_KEY_get0_group(self.k)
		order = _ssl.BN_new()
		halforder = _ssl.BN_new()
		ctx = _ssl.BN_CTX_new()
		_ssl.EC_GROUP_get_order(group, order, ctx)
		_ssl.BN_rshift1(halforder, order)

		# Verify that s is over half the order of the curve before we actually subtract anything from it
		if _ssl.BN_cmp(der_sig.s, halforder) > 0:
		  _ssl.BN_sub(der_sig.s, order, der_sig.s)

		_ssl.BN_free(halforder)
		_ssl.BN_free(order)
		_ssl.BN_CTX_free(ctx)

		derlen = _ssl.i2d_ECDSA_SIG(ctypes.pointer(der_sig), 0)
		if derlen == 0:
			_ssl.ECDSA_SIG_free(der_sig)
			return None
		new_sig = ctypes.create_string_buffer(derlen)
		_ssl.i2d_ECDSA_SIG(ctypes.pointer(der_sig), ctypes.byref(ctypes.pointer(new_sig)))
		_ssl.BN_free(der_sig.r)
		_ssl.BN_free(der_sig.s)

		return new_sig.raw

	def verify(self, hash, sig):
		"""Verify a DER signature"""
		if not sig:
		  return false

		# New versions of OpenSSL will reject non-canonical DER signatures. de/re-serialize first.
		norm_sig = ctypes.c_void_p(0)
		_ssl.d2i_ECDSA_SIG(ctypes.byref(norm_sig), ctypes.byref(ctypes.c_char_p(sig)), len(sig))

		derlen = _ssl.i2d_ECDSA_SIG(norm_sig, 0)
		if derlen == 0:
			_ssl.ECDSA_SIG_free(norm_sig)
			return false

		norm_der = ctypes.create_string_buffer(derlen)
		_ssl.i2d_ECDSA_SIG(norm_sig, ctypes.byref(ctypes.pointer(norm_der)))
		_ssl.ECDSA_SIG_free(norm_sig)

		# -1 = error, 0 = bad sig, 1 = good
		return _ssl.ECDSA_verify(0, hash, len(hash), norm_der, derlen, self.k) == 1

	def set_compressed(self, compressed):
		if compressed:
			form = self.POINT_CONVERSION_COMPRESSED
		else:
			form = self.POINT_CONVERSION_UNCOMPRESSED
		_ssl.EC_KEY_set_conv_form(self.k, form)

	def recover(self, sigR, sigS, msg, msglen, recid, check):
		"""
		Perform ECDSA key recovery (see SEC1 4.1.6) for curves over (mod p)-fields
		recid selects which key is recovered
		if check is non-zero, additional checks are performed
		"""
		i = int(recid / 2)

		r = None
		s = None
		ctx = None
		R = None
		O = None
		Q = None

		assert len(sigR) == 32, len(sigR)
		assert len(sigS) == 32, len(sigS)

		try:
			r = _ssl.BN_bin2bn(bytes(sigR), len(sigR), _ssl.BN_new())
			s = _ssl.BN_bin2bn(bytes(sigS), len(sigS), _ssl.BN_new())

			group = _ssl.EC_KEY_get0_group(self.k)
			ctx = _ssl.BN_CTX_new()
			order = _ssl.BN_CTX_get(ctx)
			ctx = _ssl.BN_CTX_new()

			if not _ssl.EC_GROUP_get_order(group, order, ctx):
				return -2

			x = _ssl.BN_CTX_get(ctx)
			if not _ssl.BN_copy(x, order):
				return -1
			if not _ssl.BN_mul_word(x, i):
				return -1
			if not _ssl.BN_add(x, x, r):
				return -1

			field = _ssl.BN_CTX_get(ctx)
			if not _ssl.EC_GROUP_get_curve_GFp(group, field, None, None, ctx):
				return -2

			if _ssl.BN_cmp(x, field) >= 0:
				return 0

			R = _ssl.EC_POINT_new(group)
			if R is None:
				return -2
			if not _ssl.EC_POINT_set_compressed_coordinates_GFp(group, R, x, recid % 2, ctx):
				return 0

			if check:
				O = _ssl.EC_POINT_new(group)
				if O is None:
					return -2
				if not _ssl.EC_POINT_mul(group, O, None, R, order, ctx):
					return -2
				if not _ssl.EC_POINT_is_at_infinity(group, O):
					return 0

			Q = _ssl.EC_POINT_new(group)
			if Q is None:
				return -2

			n = _ssl.EC_GROUP_get_degree(group)
			e = _ssl.BN_CTX_get(ctx)
			if not _ssl.BN_bin2bn(msg, msglen, e):
				return -1

			if 8 * msglen > n:
				_ssl.BN_rshift(e, e, 8 - (n & 7))

			zero = _ssl.BN_CTX_get(ctx)
			# if not _ssl.BN_zero(zero):
			#     return -1
			if not _ssl.BN_mod_sub(e, zero, e, order, ctx):
				return -1
			rr = _ssl.BN_CTX_get(ctx)
			if not _ssl.BN_mod_inverse(rr, r, order, ctx):
				return -1
			sor = _ssl.BN_CTX_get(ctx)
			if not _ssl.BN_mod_mul(sor, s, rr, order, ctx):
				return -1
			eor = _ssl.BN_CTX_get(ctx)
			if not _ssl.BN_mod_mul(eor, e, rr, order, ctx):
				return -1
			if not _ssl.EC_POINT_mul(group, Q, eor, R, sor, ctx):
				return -2

			if not _ssl.EC_KEY_set_public_key(self.k, Q):
				return -2

			return 1
		finally:
			if r: _ssl.BN_free(r)
			if s: _ssl.BN_free(s)
			if ctx: _ssl.BN_CTX_free(ctx)
			if R: _ssl.EC_POINT_free(R)
			if O: _ssl.EC_POINT_free(O)
			if Q: _ssl.EC_POINT_free(Q) 


def recover_compact(hash, sig):
	"""Recover a public key from a compact signature."""
	if len(sig) != 65:
		raise ValueError("Signature should be 65 characters, not [%d]" % (len(sig), ))

	recid = (_bord(sig[0]) - 27) & 3
	compressed = (_bord(sig[0]) - 27) & 4 != 0

	cec_key = CECKey()
	cec_key.set_compressed(compressed)

	sigR = sig[1:33]
	sigS = sig[33:65]

	result = cec_key.recover(sigR, sigS, hash, len(hash), recid, 0)

	if result < 1:
		return False

	pubkey = cec_key.get_pubkey()

	return pubkey

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


def getMessagePubkey(message, sig):
	message = msg_magic(message)
	hash = hashlib.sha256(hashlib.sha256(message).digest()).digest()
	sig = base64.b64decode(sig)

	pubkey = recover_compact(hash, sig)
	return pubkey

def test():
	sign = "HGbib2kv9gm9IJjDt1FXbXFczZi35u0rZR3iPUIt5GglDDCeIQ7v8eYXVNIaLoJRI4URGZrhwmsYQ9aVtRTnTfQ="
	pubkey = "044827c756561b8ef6b28b5e53a000805adbf4938ab82e1c2b7f7ea16a0d6face9a509a0a13e794d742210b00581f3e249ebcc705240af2540ea19591091ac1d41"
	assert getMessagePubkey("hello", sign).encode("hex") == pubkey

test() # Make sure it working right

if __name__ == "__main__":
	import time, sys
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

import ctypes
import hmac
import threading
from .._ecc import ECC
from .aes import aes
from .library import lib, openssl_backend


# Initialize functions
lib.BN_new.restype = ctypes.POINTER(ctypes.c_char)
lib.BN_bin2bn.restype = ctypes.POINTER(ctypes.c_char)
lib.BN_CTX_new.restype = ctypes.POINTER(ctypes.c_char)
lib.EC_GROUP_new_curve_GFp.restype = ctypes.POINTER(ctypes.c_char)
lib.EC_KEY_new.restype = ctypes.POINTER(ctypes.c_char)
lib.EC_POINT_new.restype = ctypes.POINTER(ctypes.c_char)
lib.EC_KEY_get0_private_key.restype = ctypes.POINTER(ctypes.c_char)
lib.EVP_PKEY_new.restype = ctypes.POINTER(ctypes.c_char)
try:
    lib.EVP_PKEY_CTX_new.restype = ctypes.POINTER(ctypes.c_char)
except AttributeError:
    pass


thread_local = threading.local()


# This lock is required to keep ECC thread-safe. Old OpenSSL versions (before
# 1.1.0) use global objects so they aren't thread safe. Fortunately we can check
# the code to find out which functions are thread safe.
#
# For example, EC_GROUP_new_curve_GFp checks global error code to initialize
# the group, so if two errors happen at once or two threads read the error code,
# or the codes are read in the wrong order, the group is initialized in a wrong
# way.
#
# EC_KEY_new_by_curve_name calls EC_GROUP_new_curve_GFp so it's not thread
# safe. We can't use the lock because it would be too slow; instead, we use
# EC_KEY_new and then EC_KEY_set_group which calls EC_GROUP_copy instead which
# is thread safe.
lock = threading.Lock()


class BN:
    # BN_CTX
    class Context:
        def __init__(self):
            self.ptr = lib.BN_CTX_new()
            self.lib = lib  # For finalizer


        def __del__(self):
            self.lib.BN_CTX_free(self.ptr)


        @classmethod
        def get(cls):
            # Get thread-safe contexf
            if not hasattr(thread_local, "bn_ctx"):
                thread_local.bn_ctx = cls()
            return thread_local.bn_ctx.ptr


    def __init__(self, value=None, link_only=False):
        if link_only:
            self.bn = value
            self._free = False
        else:
            if value is None:
                self.bn = lib.BN_new()
                self._free = True
            elif isinstance(value, int) and value < 256:
                self.bn = lib.BN_new()
                lib.BN_clear(self.bn)
                lib.BN_add_word(self.bn, value)
                self._free = True
            else:
                if isinstance(value, int):
                    value = value.to_bytes(128, "big")
                self.bn = lib.BN_bin2bn(value, len(value), None)
                self._free = True


    def __del__(self):
        if self._free:
            lib.BN_free(self.bn)


    def bytes(self, length=None):
        buf = ctypes.create_string_buffer((len(self) + 7) // 8)
        lib.BN_bn2bin(self.bn, buf)
        buf = bytes(buf)
        if length is None:
            return buf
        else:
            if length < len(buf):
                raise ValueError("Too little space for BN")
            return b"\x00" * (length - len(buf)) + buf

    def __int__(self):
        value = 0
        for byte in self.bytes():
            value = value * 256 + byte
        return value

    def __len__(self):
        return lib.BN_num_bits(self.bn)


    def inverse(self, modulo):
        result = BN()
        if not lib.BN_mod_inverse(result.bn, self.bn, modulo.bn, BN.Context.get()):
            raise ValueError("Could not compute inverse")
        return result


    def __floordiv__(self, other):
        if not isinstance(other, BN):
            raise TypeError("Can only divide BN by BN, not {}".format(other))
        result = BN()
        if not lib.BN_div(result.bn, None, self.bn, other.bn, BN.Context.get()):
            raise ZeroDivisionError("Division by zero")
        return result

    def __mod__(self, other):
        if not isinstance(other, BN):
            raise TypeError("Can only divide BN by BN, not {}".format(other))
        result = BN()
        if not lib.BN_div(None, result.bn, self.bn, other.bn, BN.Context.get()):
            raise ZeroDivisionError("Division by zero")
        return result

    def __add__(self, other):
        if not isinstance(other, BN):
            raise TypeError("Can only sum BN's, not BN and {}".format(other))
        result = BN()
        if not lib.BN_add(result.bn, self.bn, other.bn):
            raise ValueError("Could not sum two BN's")
        return result

    def __sub__(self, other):
        if not isinstance(other, BN):
            raise TypeError("Can only subtract BN's, not BN and {}".format(other))
        result = BN()
        if not lib.BN_sub(result.bn, self.bn, other.bn):
            raise ValueError("Could not subtract BN from BN")
        return result

    def __mul__(self, other):
        if not isinstance(other, BN):
            raise TypeError("Can only multiply BN by BN, not {}".format(other))
        result = BN()
        if not lib.BN_mul(result.bn, self.bn, other.bn, BN.Context.get()):
            raise ValueError("Could not multiply two BN's")
        return result

    def __neg__(self):
        return BN(0) - self


    # A dirty but nice way to update current BN and free old BN at the same time
    def __imod__(self, other):
        res = self % other
        self.bn, res.bn = res.bn, self.bn
        return self
    def __iadd__(self, other):
        res = self + other
        self.bn, res.bn = res.bn, self.bn
        return self
    def __isub__(self, other):
        res = self - other
        self.bn, res.bn = res.bn, self.bn
        return self
    def __imul__(self, other):
        res = self * other
        self.bn, res.bn = res.bn, self.bn
        return self


    def cmp(self, other):
        if not isinstance(other, BN):
            raise TypeError("Can only compare BN with BN, not {}".format(other))
        return lib.BN_cmp(self.bn, other.bn)

    def __eq__(self, other):
        return self.cmp(other) == 0
    def __lt__(self, other):
        return self.cmp(other) < 0
    def __gt__(self, other):
        return self.cmp(other) > 0
    def __ne__(self, other):
        return self.cmp(other) != 0
    def __le__(self, other):
        return self.cmp(other) <= 0
    def __ge__(self, other):
        return self.cmp(other) >= 0


    def __repr__(self):
        return "<BN {}>".format(int(self))

    def __str__(self):
        return str(int(self))


class EllipticCurveBackend:
    def __init__(self, p, n, a, b, g):
        bn_ctx = BN.Context.get()

        self.lib = lib  # For finalizer

        self.p = BN(p)
        self.order = BN(n)
        self.a = BN(a)
        self.b = BN(b)
        self.h = BN((p + n // 2) // n)

        with lock:
            # Thread-safety
            self.group = lib.EC_GROUP_new_curve_GFp(self.p.bn, self.a.bn, self.b.bn, bn_ctx)
            if not self.group:
                raise ValueError("Could not create group object")
            generator = self._public_key_to_point(g)
            lib.EC_GROUP_set_generator(self.group, generator, self.order.bn, self.h.bn)
        if not self.group:
            raise ValueError("The curve is not supported by OpenSSL")

        self.public_key_length = (len(self.p) + 7) // 8

        self.is_supported_evp_pkey_ctx = hasattr(lib, "EVP_PKEY_CTX_new")


    def __del__(self):
        self.lib.EC_GROUP_free(self.group)


    def _private_key_to_ec_key(self, private_key):
        # Thread-safety
        eckey = lib.EC_KEY_new()
        lib.EC_KEY_set_group(eckey, self.group)
        if not eckey:
            raise ValueError("Failed to allocate EC_KEY")
        private_key = BN(private_key)
        if not lib.EC_KEY_set_private_key(eckey, private_key.bn):
            lib.EC_KEY_free(eckey)
            raise ValueError("Invalid private key")
        return eckey, private_key


    def _public_key_to_point(self, public_key):
        x = BN(public_key[0])
        y = BN(public_key[1])
        # EC_KEY_set_public_key_affine_coordinates is not supported by
        # OpenSSL 1.0.0 so we can't use it
        point = lib.EC_POINT_new(self.group)
        if not lib.EC_POINT_set_affine_coordinates_GFp(self.group, point, x.bn, y.bn, BN.Context.get()):
            raise ValueError("Could not set public key affine coordinates")
        return point


    def _public_key_to_ec_key(self, public_key):
        # Thread-safety
        eckey = lib.EC_KEY_new()
        lib.EC_KEY_set_group(eckey, self.group)
        if not eckey:
            raise ValueError("Failed to allocate EC_KEY")
        try:
            # EC_KEY_set_public_key_affine_coordinates is not supported by
            # OpenSSL 1.0.0 so we can't use it
            point = self._public_key_to_point(public_key)
            if not lib.EC_KEY_set_public_key(eckey, point):
                raise ValueError("Could not set point")
            lib.EC_POINT_free(point)
            return eckey
        except Exception as e:
            lib.EC_KEY_free(eckey)
            raise e from None


    def _point_to_affine(self, point):
        # Convert to affine coordinates
        x = BN()
        y = BN()
        if lib.EC_POINT_get_affine_coordinates_GFp(self.group, point, x.bn, y.bn, BN.Context.get()) != 1:
            raise ValueError("Failed to convert public key to affine coordinates")
        # Convert to binary
        if (len(x) + 7) // 8 > self.public_key_length:
            raise ValueError("Public key X coordinate is too large")
        if (len(y) + 7) // 8 > self.public_key_length:
            raise ValueError("Public key Y coordinate is too large")
        return x.bytes(self.public_key_length), y.bytes(self.public_key_length)


    def decompress_point(self, public_key):
        point = lib.EC_POINT_new(self.group)
        if not point:
            raise ValueError("Could not create point")
        try:
            if not lib.EC_POINT_oct2point(self.group, point, public_key, len(public_key), BN.Context.get()):
                raise ValueError("Invalid compressed public key")
            return self._point_to_affine(point)
        finally:
            lib.EC_POINT_free(point)


    def new_private_key(self):
        # Create random key
        # Thread-safety
        eckey = lib.EC_KEY_new()
        lib.EC_KEY_set_group(eckey, self.group)
        lib.EC_KEY_generate_key(eckey)
        # To big integer
        private_key = BN(lib.EC_KEY_get0_private_key(eckey), link_only=True)
        # To binary
        private_key_buf = private_key.bytes(self.public_key_length)
        # Cleanup
        lib.EC_KEY_free(eckey)
        return private_key_buf


    def private_to_public(self, private_key):
        eckey, private_key = self._private_key_to_ec_key(private_key)
        try:
            # Derive public key
            point = lib.EC_POINT_new(self.group)
            try:
                if not lib.EC_POINT_mul(self.group, point, private_key.bn, None, None, BN.Context.get()):
                    raise ValueError("Failed to derive public key")
                return self._point_to_affine(point)
            finally:
                lib.EC_POINT_free(point)
        finally:
            lib.EC_KEY_free(eckey)


    def ecdh(self, private_key, public_key):
        if not self.is_supported_evp_pkey_ctx:
            # Use ECDH_compute_key instead
            # Create EC_KEY from private key
            eckey, _ = self._private_key_to_ec_key(private_key)
            try:
                # Create EC_POINT from public key
                point = self._public_key_to_point(public_key)
                try:
                    key = ctypes.create_string_buffer(self.public_key_length)
                    if lib.ECDH_compute_key(key, self.public_key_length, point, eckey, None) == -1:
                        raise ValueError("Could not compute shared secret")
                    return bytes(key)
                finally:
                    lib.EC_POINT_free(point)
            finally:
                lib.EC_KEY_free(eckey)

        # Private key:
        # Create EC_KEY
        eckey, _ = self._private_key_to_ec_key(private_key)
        try:
            # Convert to EVP_PKEY
            pkey = lib.EVP_PKEY_new()
            if not pkey:
                raise ValueError("Could not create private key object")
            try:
                lib.EVP_PKEY_set1_EC_KEY(pkey, eckey)

                # Public key:
                # Create EC_KEY
                peer_eckey = self._public_key_to_ec_key(public_key)
                try:
                    # Convert to EVP_PKEY
                    peer_pkey = lib.EVP_PKEY_new()
                    if not peer_pkey:
                        raise ValueError("Could not create public key object")
                    try:
                        lib.EVP_PKEY_set1_EC_KEY(peer_pkey, peer_eckey)

                        # Create context
                        ctx = lib.EVP_PKEY_CTX_new(pkey, None)
                        if not ctx:
                            raise ValueError("Could not create EVP context")
                        try:
                            if lib.EVP_PKEY_derive_init(ctx) != 1:
                                raise ValueError("Could not initialize key derivation")
                            if not lib.EVP_PKEY_derive_set_peer(ctx, peer_pkey):
                                raise ValueError("Could not set peer")

                            # Actually derive
                            key_len = ctypes.c_int(0)
                            lib.EVP_PKEY_derive(ctx, None, ctypes.byref(key_len))
                            key = ctypes.create_string_buffer(key_len.value)
                            lib.EVP_PKEY_derive(ctx, key, ctypes.byref(key_len))

                            return bytes(key)
                        finally:
                            lib.EVP_PKEY_CTX_free(ctx)
                    finally:
                        lib.EVP_PKEY_free(peer_pkey)
                finally:
                    lib.EC_KEY_free(peer_eckey)
            finally:
                lib.EVP_PKEY_free(pkey)
        finally:
            lib.EC_KEY_free(eckey)


    def _subject_to_bn(self, subject):
        return BN(subject[:(len(self.order) + 7) // 8])


    def sign(self, subject, private_key, recoverable, is_compressed, entropy):
        z = self._subject_to_bn(subject)
        private_key = BN(private_key)
        k = BN(entropy)

        rp = lib.EC_POINT_new(self.group)
        bn_ctx = BN.Context.get()
        try:
            # Fix Minerva
            k1 = k + self.order
            k2 = k1 + self.order
            if len(k1) == len(k2):
                k = k2
            else:
                k = k1
            if not lib.EC_POINT_mul(self.group, rp, k.bn, None, None, bn_ctx):
                raise ValueError("Could not generate R")
            # Convert to affine coordinates
            rx = BN()
            ry = BN()
            if lib.EC_POINT_get_affine_coordinates_GFp(self.group, rp, rx.bn, ry.bn, bn_ctx) != 1:
                raise ValueError("Failed to convert R to affine coordinates")
            r = rx % self.order
            if r == BN(0):
                raise ValueError("Invalid k")
            # Calculate s = k^-1 * (z + r * private_key) mod n
            s = (k.inverse(self.order) * (z + r * private_key)) % self.order
            if s == BN(0):
                raise ValueError("Invalid k")

            inverted = False
            if s * BN(2) >= self.order:
                s = self.order - s
                inverted = True

            r_buf = r.bytes(self.public_key_length)
            s_buf = s.bytes(self.public_key_length)
            if recoverable:
                # Generate recid
                recid = int(ry % BN(2)) ^ inverted
                # The line below is highly unlikely to matter in case of
                # secp256k1 but might make sense for other curves
                recid += 2 * int(rx // self.order)
                if is_compressed:
                    return bytes([31 + recid]) + r_buf + s_buf
                else:
                    if recid >= 4:
                        raise ValueError("Too big recovery ID, use compressed address instead")
                    return bytes([27 + recid]) + r_buf + s_buf
            else:
                return r_buf + s_buf
        finally:
            lib.EC_POINT_free(rp)


    def recover(self, signature, subject):
        recid = signature[0] - 27 if signature[0] < 31 else signature[0] - 31
        r = BN(signature[1:self.public_key_length + 1])
        s = BN(signature[self.public_key_length + 1:])

        # Verify bounds
        if r >= self.order:
            raise ValueError("r is out of bounds")
        if s >= self.order:
            raise ValueError("s is out of bounds")

        bn_ctx = BN.Context.get()

        z = self._subject_to_bn(subject)

        rinv = r.inverse(self.order)
        u1 = (-z * rinv) % self.order
        u2 = (s * rinv) % self.order

        # Recover R
        rx = r + BN(recid // 2) * self.order
        if rx >= self.p:
            raise ValueError("Rx is out of bounds")
        rp = lib.EC_POINT_new(self.group)
        if not rp:
            raise ValueError("Could not create R")
        try:
            init_buf = b"\x02" + rx.bytes(self.public_key_length)
            if not lib.EC_POINT_oct2point(self.group, rp, init_buf, len(init_buf), bn_ctx):
                raise ValueError("Could not use Rx to initialize point")
            ry = BN()
            if lib.EC_POINT_get_affine_coordinates_GFp(self.group, rp, None, ry.bn, bn_ctx) != 1:
                raise ValueError("Failed to convert R to affine coordinates")
            if int(ry % BN(2)) != recid % 2:
                # Fix Ry sign
                ry = self.p - ry
                if lib.EC_POINT_set_affine_coordinates_GFp(self.group, rp, rx.bn, ry.bn, bn_ctx) != 1:
                    raise ValueError("Failed to update R coordinates")

            # Recover public key
            result = lib.EC_POINT_new(self.group)
            if not result:
                raise ValueError("Could not create point")
            try:
                if not lib.EC_POINT_mul(self.group, result, u1.bn, rp, u2.bn, bn_ctx):
                    raise ValueError("Could not recover public key")
                return self._point_to_affine(result)
            finally:
                lib.EC_POINT_free(result)
        finally:
            lib.EC_POINT_free(rp)


    def verify(self, signature, subject, public_key):
        r_raw = signature[:self.public_key_length]
        r = BN(r_raw)
        s = BN(signature[self.public_key_length:])
        if r >= self.order:
            raise ValueError("r is out of bounds")
        if s >= self.order:
            raise ValueError("s is out of bounds")

        bn_ctx = BN.Context.get()

        z = self._subject_to_bn(subject)

        pub_p = lib.EC_POINT_new(self.group)
        if not pub_p:
            raise ValueError("Could not create public key point")
        try:
            init_buf = b"\x04" + public_key[0] + public_key[1]
            if not lib.EC_POINT_oct2point(self.group, pub_p, init_buf, len(init_buf), bn_ctx):
                raise ValueError("Could initialize point")

            sinv = s.inverse(self.order)
            u1 = (z * sinv) % self.order
            u2 = (r * sinv) % self.order

            # Recover public key
            result = lib.EC_POINT_new(self.group)
            if not result:
                raise ValueError("Could not create point")
            try:
                if not lib.EC_POINT_mul(self.group, result, u1.bn, pub_p, u2.bn, bn_ctx):
                    raise ValueError("Could not recover public key")
                if BN(self._point_to_affine(result)[0]) % self.order != r:
                    raise ValueError("Invalid signature")
                return True
            finally:
                lib.EC_POINT_free(result)
        finally:
            lib.EC_POINT_free(pub_p)


    def derive_child(self, seed, child):
        # Round 1
        h = hmac.new(key=b"Bitcoin seed", msg=seed, digestmod="sha512").digest()
        private_key1 = h[:32]
        x, y = self.private_to_public(private_key1)
        public_key1 = bytes([0x02 + (y[-1] % 2)]) + x
        private_key1 = BN(private_key1)

        # Round 2
        child_bytes = []
        for _ in range(4):
            child_bytes.append(child & 255)
            child >>= 8
        child_bytes = bytes(child_bytes[::-1])
        msg = public_key1 + child_bytes
        h = hmac.new(key=h[32:], msg=msg, digestmod="sha512").digest()
        private_key2 = BN(h[:32])

        return ((private_key1 + private_key2) % self.order).bytes(self.public_key_length)


    @classmethod
    def get_backend(cls):
        return openssl_backend


ecc = ECC(EllipticCurveBackend, aes)

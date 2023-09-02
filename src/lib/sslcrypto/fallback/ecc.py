import hmac
import os
from ._jacobian import JacobianCurve
from .._ecc import ECC
from .aes import aes
from ._util import int_to_bytes, bytes_to_int, inverse, square_root_mod_prime


class EllipticCurveBackend:
    def __init__(self, p, n, a, b, g):
        self.p, self.n, self.a, self.b, self.g = p, n, a, b, g
        self.jacobian = JacobianCurve(p, n, a, b, g)

        self.public_key_length = (len(bin(p).replace("0b", "")) + 7) // 8
        self.order_bitlength = len(bin(n).replace("0b", ""))


    def _int_to_bytes(self, raw, len=None):
        return int_to_bytes(raw, len or self.public_key_length)


    def decompress_point(self, public_key):
        # Parse & load data
        x = bytes_to_int(public_key[1:])
        # Calculate Y
        y_square = (pow(x, 3, self.p) + self.a * x + self.b) % self.p
        try:
            y = square_root_mod_prime(y_square, self.p)
        except Exception:
            raise ValueError("Invalid public key") from None
        if y % 2 != public_key[0] - 0x02:
            y = self.p - y
        return self._int_to_bytes(x), self._int_to_bytes(y)


    def new_private_key(self):
        while True:
            private_key = os.urandom(self.public_key_length)
            if bytes_to_int(private_key) >= self.n:
                continue
            return private_key


    def private_to_public(self, private_key):
        raw = bytes_to_int(private_key)
        x, y = self.jacobian.fast_multiply(self.g, raw)
        return self._int_to_bytes(x), self._int_to_bytes(y)


    def ecdh(self, private_key, public_key):
        x, y = public_key
        x, y = bytes_to_int(x), bytes_to_int(y)
        private_key = bytes_to_int(private_key)
        x, _ = self.jacobian.fast_multiply((x, y), private_key, secret=True)
        return self._int_to_bytes(x)


    def _subject_to_int(self, subject):
        return bytes_to_int(subject[:(self.order_bitlength + 7) // 8])


    def sign(self, subject, raw_private_key, recoverable, is_compressed, entropy):
        z = self._subject_to_int(subject)
        private_key = bytes_to_int(raw_private_key)
        k = bytes_to_int(entropy)

        # Fix k length to prevent Minerva. Increasing multiplier by a
        # multiple of order doesn't break anything. This fix was ported
        # from python-ecdsa
        ks = k + self.n
        kt = ks + self.n
        ks_len = len(bin(ks).replace("0b", "")) // 8
        kt_len = len(bin(kt).replace("0b", "")) // 8
        if ks_len == kt_len:
            k = kt
        else:
            k = ks
        px, py = self.jacobian.fast_multiply(self.g, k, secret=True)

        r = px % self.n
        if r == 0:
            # Invalid k
            raise ValueError("Invalid k")

        s = (inverse(k, self.n) * (z + (private_key * r))) % self.n
        if s == 0:
            # Invalid k
            raise ValueError("Invalid k")

        inverted = False
        if s * 2 >= self.n:
            s = self.n - s
            inverted = True
        rs_buf = self._int_to_bytes(r) + self._int_to_bytes(s)

        if recoverable:
            recid = (py % 2) ^ inverted
            recid += 2 * int(px // self.n)
            if is_compressed:
                return bytes([31 + recid]) + rs_buf
            else:
                if recid >= 4:
                    raise ValueError("Too big recovery ID, use compressed address instead")
                return bytes([27 + recid]) + rs_buf
        else:
            return rs_buf


    def recover(self, signature, subject):
        z = self._subject_to_int(subject)

        recid = signature[0] - 27 if signature[0] < 31 else signature[0] - 31
        r = bytes_to_int(signature[1:self.public_key_length + 1])
        s = bytes_to_int(signature[self.public_key_length + 1:])

        # Verify bounds
        if not 0 <= recid < 2 * (self.p // self.n + 1):
            raise ValueError("Invalid recovery ID")
        if r >= self.n:
            raise ValueError("r is out of bounds")
        if s >= self.n:
            raise ValueError("s is out of bounds")

        rinv = inverse(r, self.n)
        u1 = (-z * rinv) % self.n
        u2 = (s * rinv) % self.n

        # Recover R
        rx = r + (recid // 2) * self.n
        if rx >= self.p:
            raise ValueError("Rx is out of bounds")

        # Almost copied from decompress_point
        ry_square = (pow(rx, 3, self.p) + self.a * rx + self.b) % self.p
        try:
            ry = square_root_mod_prime(ry_square, self.p)
        except Exception:
            raise ValueError("Invalid recovered public key") from None

        # Ensure the point is correct
        if ry % 2 != recid % 2:
            # Fix Ry sign
            ry = self.p - ry

        x, y = self.jacobian.fast_shamir(self.g, u1, (rx, ry), u2)
        return self._int_to_bytes(x), self._int_to_bytes(y)


    def verify(self, signature, subject, public_key):
        z = self._subject_to_int(subject)

        r = bytes_to_int(signature[:self.public_key_length])
        s = bytes_to_int(signature[self.public_key_length:])

        # Verify bounds
        if r >= self.n:
            raise ValueError("r is out of bounds")
        if s >= self.n:
            raise ValueError("s is out of bounds")

        public_key = [bytes_to_int(c) for c in public_key]

        # Ensure that the public key is correct
        if not self.jacobian.is_on_curve(public_key):
            raise ValueError("Public key is not on curve")

        sinv = inverse(s, self.n)
        u1 = (z * sinv) % self.n
        u2 = (r * sinv) % self.n

        x1, _ = self.jacobian.fast_shamir(self.g, u1, public_key, u2)
        if r != x1 % self.n:
            raise ValueError("Invalid signature")

        return True


    def derive_child(self, seed, child):
        # Round 1
        h = hmac.new(key=b"Bitcoin seed", msg=seed, digestmod="sha512").digest()
        private_key1 = h[:32]
        x, y = self.private_to_public(private_key1)
        public_key1 = bytes([0x02 + (y[-1] % 2)]) + x
        private_key1 = bytes_to_int(private_key1)

        # Round 2
        msg = public_key1 + self._int_to_bytes(child, 4)
        h = hmac.new(key=h[32:], msg=msg, digestmod="sha512").digest()
        private_key2 = bytes_to_int(h[:32])

        return self._int_to_bytes((private_key1 + private_key2) % self.n)


    @classmethod
    def get_backend(cls):
        return "fallback"


ecc = ECC(EllipticCurveBackend, aes)

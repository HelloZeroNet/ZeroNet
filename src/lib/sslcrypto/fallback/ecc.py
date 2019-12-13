import hmac
import os
from ._jacobian import JacobianCurve
from .._ecc import ECC
from .aes import aes
from ._util import int_to_bytes, bytes_to_int, inverse, square_root_mod_prime


# pylint: disable=line-too-long
CURVES = {
    # nid: (p, n, a, b, (Gx, Gy)),
    704: (
        # secp112r1
        0xDB7C2ABF62E35E668076BEAD208B,
        0xDB7C2ABF62E35E7628DFAC6561C5,
        0xDB7C2ABF62E35E668076BEAD2088,
        0x659EF8BA043916EEDE8911702B22,
        (
            0x09487239995A5EE76B55F9C2F098,
            0xA89CE5AF8724C0A23E0E0FF77500
        )
    ),
    705: (
        # secp112r2
        0xDB7C2ABF62E35E668076BEAD208B,
        0x36DF0AAFD8B8D7597CA10520D04B,
        0x6127C24C05F38A0AAAF65C0EF02C,
        0x51DEF1815DB5ED74FCC34C85D709,
        (
            0x4BA30AB5E892B4E1649DD0928643,
            0xADCD46F5882E3747DEF36E956E97
        )
    ),
    706: (
        # secp128r1
        0xFFFFFFFDFFFFFFFFFFFFFFFFFFFFFFFF,
        0xFFFFFFFE0000000075A30D1B9038A115,
        0xFFFFFFFDFFFFFFFFFFFFFFFFFFFFFFFC,
        0xE87579C11079F43DD824993C2CEE5ED3,
        (
            0x161FF7528B899B2D0C28607CA52C5B86,
            0xCF5AC8395BAFEB13C02DA292DDED7A83
        )
    ),
    707: (
        # secp128r2
        0xFFFFFFFDFFFFFFFFFFFFFFFFFFFFFFFF,
        0x3FFFFFFF7FFFFFFFBE0024720613B5A3,
        0xD6031998D1B3BBFEBF59CC9BBFF9AEE1,
        0x5EEEFCA380D02919DC2C6558BB6D8A5D,
        (
            0x7B6AA5D85E572983E6FB32A7CDEBC140,
            0x27B6916A894D3AEE7106FE805FC34B44
        )
    ),
    708: (
        # secp160k1
        0x00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFAC73,
        0x0100000000000000000001B8FA16DFAB9ACA16B6B3,
        0,
        7,
        (
            0x3B4C382CE37AA192A4019E763036F4F5DD4D7EBB,
            0x938CF935318FDCED6BC28286531733C3F03C4FEE
        )
    ),
    709: (
        # secp160r1
        0x00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7FFFFFFF,
        0x0100000000000000000001F4C8F927AED3CA752257,
        0x00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF7FFFFFFC,
        0x001C97BEFC54BD7A8B65ACF89F81D4D4ADC565FA45,
        (
            0x4A96B5688EF573284664698968C38BB913CBFC82,
            0x23A628553168947D59DCC912042351377AC5FB32
        )
    ),
    710: (
        # secp160r2
        0x00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFAC73,
        0x0100000000000000000000351EE786A818F3A1A16B,
        0x00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFAC70,
        0x00B4E134D3FB59EB8BAB57274904664D5AF50388BA,
        (
            0x52DCB034293A117E1F4FF11B30F7199D3144CE6D,
            0xFEAFFEF2E331F296E071FA0DF9982CFEA7D43F2E
        )
    ),
    711: (
        # secp192k1
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFEE37,
        0xFFFFFFFFFFFFFFFFFFFFFFFE26F2FC170F69466A74DEFD8D,
        0,
        3,
        (
            0xDB4FF10EC057E9AE26B07D0280B7F4341DA5D1B1EAE06C7D,
            0x9B2F2F6D9C5628A7844163D015BE86344082AA88D95E2F9D
        )
    ),
    409: (
        # prime192v1
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFFFF,
        0xFFFFFFFFFFFFFFFFFFFFFFFF99DEF836146BC9B1B4D22831,
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFFFC,
        0x64210519E59C80E70FA7E9AB72243049FEB8DEECC146B9B1,
        (
            0x188DA80EB03090F67CBF20EB43A18800F4FF0AFD82FF1012,
            0x07192B95FFC8DA78631011ED6B24CDD573F977A11E794811
        )
    ),
    712: (
        # secp224k1
        0x00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFE56D,
        0x010000000000000000000000000001DCE8D2EC6184CAF0A971769FB1F7,
        0,
        5,
        (
            0xA1455B334DF099DF30FC28A169A467E9E47075A90F7E650EB6B7A45C,
            0x7E089FED7FBA344282CAFBD6F7E319F7C0B0BD59E2CA4BDB556D61A5
        )
    ),
    713: (
        # secp224r1
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF000000000000000000000001,
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFF16A2E0B8F03E13DD29455C5C2A3D,
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFE,
        0xB4050A850C04B3ABF54132565044B0B7D7BFD8BA270B39432355FFB4,
        (
            0xB70E0CBD6BB4BF7F321390B94A03C1D356C21122343280D6115C1D21,
            0xBD376388B5F723FB4C22DFE6CD4375A05A07476444D5819985007E34
        )
    ),
    714: (
        # secp256k1
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F,
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141,
        0,
        7,
        (
            0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
            0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
        )
    ),
    415: (
        # prime256v1
        0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF,
        0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551,
        0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC,
        0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B,
        (
            0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
            0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5
        )
    ),
    715: (
        # secp384r1
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFF0000000000000000FFFFFFFF,
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC7634D81F4372DDF581A0DB248B0A77AECEC196ACCC52973,
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFF0000000000000000FFFFFFFC,
        0xB3312FA7E23EE7E4988E056BE3F82D19181D9C6EFE8141120314088F5013875AC656398D8A2ED19D2A85C8EDD3EC2AEF,
        (
            0xAA87CA22BE8B05378EB1C71EF320AD746E1D3B628BA79B9859F741E082542A385502F25DBF55296C3A545E3872760AB7,
            0x3617DE4A96262C6F5D9E98BF9292DC29F8F41DBD289A147CE9DA3113B5F0B8C00A60B1CE1D7E819D7A431D7C90EA0E5F
        )
    ),
    716: (
        # secp521r1
        0x01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,
        0x01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFA51868783BF2F966B7FCC0148F709A5D03BB5C9B8899C47AEBB6FB71E91386409,
        0x01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFC,
        0x0051953EB9618E1C9A1F929A21A0B68540EEA2DA725B99B315F3B8B489918EF109E156193951EC7E937B1652C0BD3BB1BF073573DF883D2C34F1EF451FD46B503F00,
        (
            0x00C6858E06B70404E9CD9E3ECB662395B4429C648139053FB521F828AF606B4D3DBAA14B5E77EFE75928FE1DC127A2FFA8DE3348B3C1856A429BF97E7E31C2E5BD66,
            0x011839296A789A3BC0045C8A5FB42C7D1BD998F54449579B446817AFBD17273E662C97EE72995EF42640C550B9013FAD0761353C7086A272C24088BE94769FD16650
        )
    )
}
# pylint: enable=line-too-long


class EllipticCurveBackend:
    def __init__(self, nid):
        self.p, self.n, self.a, self.b, self.g = CURVES[nid]
        self.jacobian = JacobianCurve(*CURVES[nid])

        self.public_key_length = (len(bin(self.p).replace("0b", "")) + 7) // 8
        self.order_bitlength = len(bin(self.n).replace("0b", ""))


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

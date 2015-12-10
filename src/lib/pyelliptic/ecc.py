#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  Copyright (C) 2011 Yann GUIBET <yannguibet@gmail.com>
#  See LICENSE for details.

from hashlib import sha512
from .openssl import OpenSSL
from .cipher import Cipher
from .hash import hmac_sha256, equals
from struct import pack, unpack


class ECC:
    """
    Asymmetric encryption with Elliptic Curve Cryptography (ECC)
    ECDH, ECDSA and ECIES

        import pyelliptic

        alice = pyelliptic.ECC() # default curve: sect283r1
        bob = pyelliptic.ECC(curve='sect571r1')

        ciphertext = alice.encrypt("Hello Bob", bob.get_pubkey())
        print bob.decrypt(ciphertext)

        signature = bob.sign("Hello Alice")
        # alice's job :
        print pyelliptic.ECC(
            pubkey=bob.get_pubkey()).verify(signature, "Hello Alice")

        # ERROR !!!
        try:
            key = alice.get_ecdh_key(bob.get_pubkey())
        except: print("For ECDH key agreement,\
                      the keys must be defined on the same curve !")

        alice = pyelliptic.ECC(curve='sect571r1')
        print alice.get_ecdh_key(bob.get_pubkey()).encode('hex')
        print bob.get_ecdh_key(alice.get_pubkey()).encode('hex')

    """
    def __init__(self, pubkey=None, privkey=None, pubkey_x=None,
                 pubkey_y=None, raw_privkey=None, curve='sect283r1'):
        """
        For a normal and High level use, specifie pubkey,
        privkey (if you need) and the curve
        """
        if type(curve) == str:
            self.curve = OpenSSL.get_curve(curve)
        else:
            self.curve = curve

        if pubkey_x is not None and pubkey_y is not None:
            self._set_keys(pubkey_x, pubkey_y, raw_privkey)
        elif pubkey is not None:
            curve, pubkey_x, pubkey_y, i = ECC._decode_pubkey(pubkey)
            if privkey is not None:
                curve2, raw_privkey, i = ECC._decode_privkey(privkey)
                if curve != curve2:
                    raise Exception("Bad ECC keys ...")
            self.curve = curve
            self._set_keys(pubkey_x, pubkey_y, raw_privkey)
        else:
            self.privkey, self.pubkey_x, self.pubkey_y = self._generate()

    def _set_keys(self, pubkey_x, pubkey_y, privkey):
        if self.raw_check_key(privkey, pubkey_x, pubkey_y) < 0:
            self.pubkey_x = None
            self.pubkey_y = None
            self.privkey = None
            raise Exception("Bad ECC keys ...")
        else:
            self.pubkey_x = pubkey_x
            self.pubkey_y = pubkey_y
            self.privkey = privkey

    @staticmethod
    def get_curves():
        """
        static method, returns the list of all the curves available
        """
        return OpenSSL.curves.keys()

    def get_curve(self):
        return OpenSSL.get_curve_by_id(self.curve)

    def get_curve_id(self):
        return self.curve

    def get_pubkey(self):
        """
        High level function which returns :
        curve(2) + len_of_pubkeyX(2) + pubkeyX + len_of_pubkeyY + pubkeyY
        """
        return b''.join((pack('!H', self.curve),
                         pack('!H', len(self.pubkey_x)),
                         self.pubkey_x,
                         pack('!H', len(self.pubkey_y)),
                         self.pubkey_y
                         ))

    def get_privkey(self):
        """
        High level function which returns
        curve(2) + len_of_privkey(2) + privkey
        """
        return b''.join((pack('!H', self.curve),
                         pack('!H', len(self.privkey)),
                         self.privkey
                         ))

    @staticmethod
    def _decode_pubkey(pubkey):
        i = 0
        curve = unpack('!H', pubkey[i:i + 2])[0]
        i += 2
        tmplen = unpack('!H', pubkey[i:i + 2])[0]
        i += 2
        pubkey_x = pubkey[i:i + tmplen]
        i += tmplen
        tmplen = unpack('!H', pubkey[i:i + 2])[0]
        i += 2
        pubkey_y = pubkey[i:i + tmplen]
        i += tmplen
        return curve, pubkey_x, pubkey_y, i

    @staticmethod
    def _decode_privkey(privkey):
        i = 0
        curve = unpack('!H', privkey[i:i + 2])[0]
        i += 2
        tmplen = unpack('!H', privkey[i:i + 2])[0]
        i += 2
        privkey = privkey[i:i + tmplen]
        i += tmplen
        return curve, privkey, i

    def _generate(self):
        try:
            pub_key_x = OpenSSL.BN_new()
            pub_key_y = OpenSSL.BN_new()

            key = OpenSSL.EC_KEY_new_by_curve_name(self.curve)
            if key == 0:
                raise Exception("[OpenSSL] EC_KEY_new_by_curve_name FAIL ...")
            if (OpenSSL.EC_KEY_generate_key(key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_generate_key FAIL ...")
            if (OpenSSL.EC_KEY_check_key(key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_check_key FAIL ...")
            priv_key = OpenSSL.EC_KEY_get0_private_key(key)

            group = OpenSSL.EC_KEY_get0_group(key)
            pub_key = OpenSSL.EC_KEY_get0_public_key(key)

            if (OpenSSL.EC_POINT_get_affine_coordinates_GFp(group, pub_key,
                                                            pub_key_x,
                                                            pub_key_y, 0
                                                            )) == 0:
                raise Exception(
                    "[OpenSSL] EC_POINT_get_affine_coordinates_GFp FAIL ...")

            privkey = OpenSSL.malloc(0, OpenSSL.BN_num_bytes(priv_key))
            pubkeyx = OpenSSL.malloc(0, OpenSSL.BN_num_bytes(pub_key_x))
            pubkeyy = OpenSSL.malloc(0, OpenSSL.BN_num_bytes(pub_key_y))
            OpenSSL.BN_bn2bin(priv_key, privkey)
            privkey = privkey.raw
            OpenSSL.BN_bn2bin(pub_key_x, pubkeyx)
            pubkeyx = pubkeyx.raw
            OpenSSL.BN_bn2bin(pub_key_y, pubkeyy)
            pubkeyy = pubkeyy.raw
            self.raw_check_key(privkey, pubkeyx, pubkeyy)

            return privkey, pubkeyx, pubkeyy

        finally:
            OpenSSL.EC_KEY_free(key)
            OpenSSL.BN_free(pub_key_x)
            OpenSSL.BN_free(pub_key_y)

    def get_ecdh_key(self, pubkey):
        """
        High level function. Compute public key with the local private key
        and returns a 512bits shared key
        """
        curve, pubkey_x, pubkey_y, i = ECC._decode_pubkey(pubkey)
        if curve != self.curve:
            raise Exception("ECC keys must be from the same curve !")
        return sha512(self.raw_get_ecdh_key(pubkey_x, pubkey_y)).digest()

    def raw_get_ecdh_key(self, pubkey_x, pubkey_y):
        try:
            ecdh_keybuffer = OpenSSL.malloc(0, 32)

            other_key = OpenSSL.EC_KEY_new_by_curve_name(self.curve)
            if other_key == 0:
                raise Exception("[OpenSSL] EC_KEY_new_by_curve_name FAIL ...")

            other_pub_key_x = OpenSSL.BN_bin2bn(pubkey_x, len(pubkey_x), 0)
            other_pub_key_y = OpenSSL.BN_bin2bn(pubkey_y, len(pubkey_y), 0)

            other_group = OpenSSL.EC_KEY_get0_group(other_key)
            other_pub_key = OpenSSL.EC_POINT_new(other_group)

            if (OpenSSL.EC_POINT_set_affine_coordinates_GFp(other_group,
                                                            other_pub_key,
                                                            other_pub_key_x,
                                                            other_pub_key_y,
                                                            0)) == 0:
                raise Exception(
                    "[OpenSSL] EC_POINT_set_affine_coordinates_GFp FAIL ...")
            if (OpenSSL.EC_KEY_set_public_key(other_key, other_pub_key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_set_public_key FAIL ...")
            if (OpenSSL.EC_KEY_check_key(other_key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_check_key FAIL ...")

            own_key = OpenSSL.EC_KEY_new_by_curve_name(self.curve)
            if own_key == 0:
                raise Exception("[OpenSSL] EC_KEY_new_by_curve_name FAIL ...")
            own_priv_key = OpenSSL.BN_bin2bn(
                self.privkey, len(self.privkey), 0)

            if (OpenSSL.EC_KEY_set_private_key(own_key, own_priv_key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_set_private_key FAIL ...")

            OpenSSL.ECDH_set_method(own_key, OpenSSL.ECDH_OpenSSL())
            ecdh_keylen = OpenSSL.ECDH_compute_key(
                ecdh_keybuffer, 32, other_pub_key, own_key, 0)

            if ecdh_keylen != 32:
                raise Exception("[OpenSSL] ECDH keylen FAIL ...")

            return ecdh_keybuffer.raw

        finally:
            OpenSSL.EC_KEY_free(other_key)
            OpenSSL.BN_free(other_pub_key_x)
            OpenSSL.BN_free(other_pub_key_y)
            OpenSSL.EC_POINT_free(other_pub_key)
            OpenSSL.EC_KEY_free(own_key)
            OpenSSL.BN_free(own_priv_key)

    def check_key(self, privkey, pubkey):
        """
        Check the public key and the private key.
        The private key is optional (replace by None)
        """
        curve, pubkey_x, pubkey_y, i = ECC._decode_pubkey(pubkey)
        if privkey is None:
            raw_privkey = None
            curve2 = curve
        else:
            curve2, raw_privkey, i = ECC._decode_privkey(privkey)
        if curve != curve2:
            raise Exception("Bad public and private key")
        return self.raw_check_key(raw_privkey, pubkey_x, pubkey_y, curve)

    def raw_check_key(self, privkey, pubkey_x, pubkey_y, curve=None):
        if curve is None:
            curve = self.curve
        elif type(curve) == str:
            curve = OpenSSL.get_curve(curve)
        else:
            curve = curve
        try:
            key = OpenSSL.EC_KEY_new_by_curve_name(curve)
            if key == 0:
                raise Exception("[OpenSSL] EC_KEY_new_by_curve_name FAIL ...")
            if privkey is not None:
                priv_key = OpenSSL.BN_bin2bn(privkey, len(privkey), 0)
            pub_key_x = OpenSSL.BN_bin2bn(pubkey_x, len(pubkey_x), 0)
            pub_key_y = OpenSSL.BN_bin2bn(pubkey_y, len(pubkey_y), 0)

            if privkey is not None:
                if (OpenSSL.EC_KEY_set_private_key(key, priv_key)) == 0:
                    raise Exception(
                        "[OpenSSL] EC_KEY_set_private_key FAIL ...")

            group = OpenSSL.EC_KEY_get0_group(key)
            pub_key = OpenSSL.EC_POINT_new(group)

            if (OpenSSL.EC_POINT_set_affine_coordinates_GFp(group, pub_key,
                                                            pub_key_x,
                                                            pub_key_y,
                                                            0)) == 0:
                raise Exception(
                    "[OpenSSL] EC_POINT_set_affine_coordinates_GFp FAIL ...")
            if (OpenSSL.EC_KEY_set_public_key(key, pub_key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_set_public_key FAIL ...")
            if (OpenSSL.EC_KEY_check_key(key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_check_key FAIL ...")
            return 0

        finally:
            OpenSSL.EC_KEY_free(key)
            OpenSSL.BN_free(pub_key_x)
            OpenSSL.BN_free(pub_key_y)
            OpenSSL.EC_POINT_free(pub_key)
            if privkey is not None:
                OpenSSL.BN_free(priv_key)

    def sign(self, inputb, digest_alg=OpenSSL.EVP_ecdsa):
        """
        Sign the input with ECDSA method and returns the signature
        """
        try:
            size = len(inputb)
            buff = OpenSSL.malloc(inputb, size)
            digest = OpenSSL.malloc(0, 64)
            md_ctx = OpenSSL.EVP_MD_CTX_create()
            dgst_len = OpenSSL.pointer(OpenSSL.c_int(0))
            siglen = OpenSSL.pointer(OpenSSL.c_int(0))
            sig = OpenSSL.malloc(0, 151)

            key = OpenSSL.EC_KEY_new_by_curve_name(self.curve)
            if key == 0:
                raise Exception("[OpenSSL] EC_KEY_new_by_curve_name FAIL ...")

            priv_key = OpenSSL.BN_bin2bn(self.privkey, len(self.privkey), 0)
            pub_key_x = OpenSSL.BN_bin2bn(self.pubkey_x, len(self.pubkey_x), 0)
            pub_key_y = OpenSSL.BN_bin2bn(self.pubkey_y, len(self.pubkey_y), 0)

            if (OpenSSL.EC_KEY_set_private_key(key, priv_key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_set_private_key FAIL ...")

            group = OpenSSL.EC_KEY_get0_group(key)
            pub_key = OpenSSL.EC_POINT_new(group)

            if (OpenSSL.EC_POINT_set_affine_coordinates_GFp(group, pub_key,
                                                            pub_key_x,
                                                            pub_key_y,
                                                            0)) == 0:
                raise Exception(
                    "[OpenSSL] EC_POINT_set_affine_coordinates_GFp FAIL ...")
            if (OpenSSL.EC_KEY_set_public_key(key, pub_key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_set_public_key FAIL ...")
            if (OpenSSL.EC_KEY_check_key(key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_check_key FAIL ...")

            OpenSSL.EVP_MD_CTX_init(md_ctx)
            OpenSSL.EVP_DigestInit_ex(md_ctx, digest_alg(), None)

            if (OpenSSL.EVP_DigestUpdate(md_ctx, buff, size)) == 0:
                raise Exception("[OpenSSL] EVP_DigestUpdate FAIL ...")
            OpenSSL.EVP_DigestFinal_ex(md_ctx, digest, dgst_len)
            OpenSSL.ECDSA_sign(0, digest, dgst_len.contents, sig, siglen, key)
            if (OpenSSL.ECDSA_verify(0, digest, dgst_len.contents, sig,
                                     siglen.contents, key)) != 1:
                raise Exception("[OpenSSL] ECDSA_verify FAIL ...")

            return sig.raw[:siglen.contents.value]

        finally:
            OpenSSL.EC_KEY_free(key)
            OpenSSL.BN_free(pub_key_x)
            OpenSSL.BN_free(pub_key_y)
            OpenSSL.BN_free(priv_key)
            OpenSSL.EC_POINT_free(pub_key)
            OpenSSL.EVP_MD_CTX_destroy(md_ctx)

    def verify(self, sig, inputb, digest_alg=OpenSSL.EVP_ecdsa):
        """
        Verify the signature with the input and the local public key.
        Returns a boolean
        """
        try:
            bsig = OpenSSL.malloc(sig, len(sig))
            binputb = OpenSSL.malloc(inputb, len(inputb))
            digest = OpenSSL.malloc(0, 64)
            dgst_len = OpenSSL.pointer(OpenSSL.c_int(0))
            md_ctx = OpenSSL.EVP_MD_CTX_create()

            key = OpenSSL.EC_KEY_new_by_curve_name(self.curve)

            if key == 0:
                raise Exception("[OpenSSL] EC_KEY_new_by_curve_name FAIL ...")

            pub_key_x = OpenSSL.BN_bin2bn(self.pubkey_x, len(self.pubkey_x), 0)
            pub_key_y = OpenSSL.BN_bin2bn(self.pubkey_y, len(self.pubkey_y), 0)
            group = OpenSSL.EC_KEY_get0_group(key)
            pub_key = OpenSSL.EC_POINT_new(group)

            if (OpenSSL.EC_POINT_set_affine_coordinates_GFp(group, pub_key,
                                                            pub_key_x,
                                                            pub_key_y,
                                                            0)) == 0:
                raise Exception(
                    "[OpenSSL] EC_POINT_set_affine_coordinates_GFp FAIL ...")
            if (OpenSSL.EC_KEY_set_public_key(key, pub_key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_set_public_key FAIL ...")
            if (OpenSSL.EC_KEY_check_key(key)) == 0:
                raise Exception("[OpenSSL] EC_KEY_check_key FAIL ...")

            OpenSSL.EVP_MD_CTX_init(md_ctx)
            OpenSSL.EVP_DigestInit_ex(md_ctx, digest_alg(), None)
            if (OpenSSL.EVP_DigestUpdate(md_ctx, binputb, len(inputb))) == 0:
                raise Exception("[OpenSSL] EVP_DigestUpdate FAIL ...")

            OpenSSL.EVP_DigestFinal_ex(md_ctx, digest, dgst_len)
            ret = OpenSSL.ECDSA_verify(
                0, digest, dgst_len.contents, bsig, len(sig), key)

            if ret == -1:
                return False  # Fail to Check
            else:
                if ret == 0:
                    return False  # Bad signature !
                else:
                    return True  # Good
            return False

        finally:
            OpenSSL.EC_KEY_free(key)
            OpenSSL.BN_free(pub_key_x)
            OpenSSL.BN_free(pub_key_y)
            OpenSSL.EC_POINT_free(pub_key)
            OpenSSL.EVP_MD_CTX_destroy(md_ctx)

    @staticmethod
    def encrypt(data, pubkey, ephemcurve=None, ciphername='aes-256-cbc'):
        """
        Encrypt data with ECIES method using the public key of the recipient.
        """
        curve, pubkey_x, pubkey_y, i = ECC._decode_pubkey(pubkey)
        return ECC.raw_encrypt(data, pubkey_x, pubkey_y, curve=curve,
                               ephemcurve=ephemcurve, ciphername=ciphername)

    @staticmethod
    def raw_encrypt(data, pubkey_x, pubkey_y, curve='sect283r1',
                    ephemcurve=None, ciphername='aes-256-cbc'):
        if ephemcurve is None:
            ephemcurve = curve
        ephem = ECC(curve=ephemcurve)
        key = sha512(ephem.raw_get_ecdh_key(pubkey_x, pubkey_y)).digest()
        key_e, key_m = key[:32], key[32:]
        pubkey = ephem.get_pubkey()
        iv = OpenSSL.rand(OpenSSL.get_cipher(ciphername).get_blocksize())
        ctx = Cipher(key_e, iv, 1, ciphername)
        ciphertext = iv + pubkey + ctx.ciphering(data)
        mac = hmac_sha256(key_m, ciphertext)
        return ciphertext + mac

    def decrypt(self, data, ciphername='aes-256-cbc'):
        """
        Decrypt data with ECIES method using the local private key
        """
        blocksize = OpenSSL.get_cipher(ciphername).get_blocksize()
        iv = data[:blocksize]
        i = blocksize
        curve, pubkey_x, pubkey_y, i2 = ECC._decode_pubkey(data[i:])
        i += i2
        ciphertext = data[i:len(data)-32]
        i += len(ciphertext)
        mac = data[i:]
        key = sha512(self.raw_get_ecdh_key(pubkey_x, pubkey_y)).digest()
        key_e, key_m = key[:32], key[32:]
        if not equals(hmac_sha256(key_m, data[:len(data) - 32]), mac):
            raise RuntimeError("Fail to verify data")
        ctx = Cipher(key_e, iv, 0, ciphername)
        return ctx.ciphering(ciphertext)

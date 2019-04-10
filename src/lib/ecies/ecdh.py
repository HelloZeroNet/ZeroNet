# Copyright (c) 2014 Yann GUIBET <yannguibet@gmail.com>.
# All rights reserved.
#
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     1. Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#
#     2. Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS''
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from .openssl import OpenSSL


def ecdh(privatekey, publickey):
    privatekey = privatekey.to_bytes(32, byteorder="big")
    publickey = tuple(map(lambda k: k.to_bytes(32, byteorder="big"), publickey))

    try:
        ecdh_keybuffer = OpenSSL.malloc(0, 32)

        other_key = OpenSSL.EC_KEY_new_by_curve_name(714)
        if other_key == 0:
            raise Exception("[OpenSSL] EC_KEY_new_by_curve_name FAIL ...")

        other_pub_key_x = OpenSSL.BN_bin2bn(publickey[0], 32, 0)
        other_pub_key_y = OpenSSL.BN_bin2bn(publickey[1], 32, 0)

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

        own_key = OpenSSL.EC_KEY_new_by_curve_name(714)
        if own_key == 0:
            raise Exception("[OpenSSL] EC_KEY_new_by_curve_name FAIL ...")
        own_priv_key = OpenSSL.BN_bin2bn(privatekey, 32, 0)

        if (OpenSSL.EC_KEY_set_private_key(own_key, own_priv_key)) == 0:
            raise Exception("[OpenSSL] EC_KEY_set_private_key FAIL ...")

        ecdh_keylen = OpenSSL.ECDH_compute_key(
            ecdh_keybuffer, 32, other_pub_key, own_key, 0
        )

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
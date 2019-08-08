#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  Copyright (C) 2011 Yann GUIBET <yannguibet@gmail.com>
#  See LICENSE for details.

from .openssl import OpenSSL


# For python3
def _equals_bytes(a, b):
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0


def _equals_str(a, b):
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def equals(a, b):
    if isinstance(a, str):
        return _equals_str(a, b)
    else:
        return _equals_bytes(a, b)


def hmac_sha256(k, m):
    """
    Compute the key and the message with HMAC SHA5256
    """
    key = OpenSSL.malloc(k, len(k))
    d = OpenSSL.malloc(m, len(m))
    md = OpenSSL.malloc(0, 32)
    i = OpenSSL.pointer(OpenSSL.c_int(0))
    OpenSSL.HMAC(OpenSSL.EVP_sha256(), key, len(k), d, len(m), md, i)
    return md.raw


def hmac_sha512(k, m):
    """
    Compute the key and the message with HMAC SHA512
    """
    key = OpenSSL.malloc(k, len(k))
    d = OpenSSL.malloc(m, len(m))
    md = OpenSSL.malloc(0, 64)
    i = OpenSSL.pointer(OpenSSL.c_int(0))
    OpenSSL.HMAC(OpenSSL.EVP_sha512(), key, len(k), d, len(m), md, i)
    return md.raw


def pbkdf2(password, salt=None, i=10000, keylen=64):
    if salt is None:
        salt = OpenSSL.rand(8)
    p_password = OpenSSL.malloc(password, len(password))
    p_salt = OpenSSL.malloc(salt, len(salt))
    output = OpenSSL.malloc(0, keylen)
    OpenSSL.PKCS5_PBKDF2_HMAC(p_password, len(password), p_salt,
                              len(p_salt), i, OpenSSL.EVP_sha256(),
                              keylen, output)
    return salt, output.raw

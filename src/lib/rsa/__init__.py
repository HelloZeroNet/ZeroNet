# -*- coding: utf-8 -*-
#
#  Copyright 2011 Sybren A. Stüvel <sybren@stuvel.eu>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""RSA module

Module for calculating large primes, and RSA encryption, decryption, signing
and verification. Includes generating public and private keys.

WARNING: this implementation does not use random padding, compression of the
cleartext input to prevent repetitions, or other common security improvements.
Use with care.

"""

from rsa.key import newkeys, PrivateKey, PublicKey
from rsa.pkcs1 import encrypt, decrypt, sign, verify, DecryptionError, \
    VerificationError

__author__ = "Sybren Stuvel, Barry Mead and Yesudeep Mangalapilly"
__date__ = "2016-03-29"
__version__ = '3.4.2'

# Do doctest if we're run directly
if __name__ == "__main__":
    import doctest

    doctest.testmod()

__all__ = ["newkeys", "encrypt", "decrypt", "sign", "verify", 'PublicKey',
           'PrivateKey', 'DecryptionError', 'VerificationError']

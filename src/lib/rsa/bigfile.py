# -*- coding: utf-8 -*-
#
#  Copyright 2011 Sybren A. Stüvel <sybren@stuvel.eu>
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

'''Large file support

    - break a file into smaller blocks, and encrypt them, and store the
      encrypted blocks in another file.

    - take such an encrypted files, decrypt its blocks, and reconstruct the
      original file.

The encrypted file format is as follows, where || denotes byte concatenation:

    FILE := VERSION || BLOCK || BLOCK ...

    BLOCK := LENGTH || DATA

    LENGTH := varint-encoded length of the subsequent data. Varint comes from
    Google Protobuf, and encodes an integer into a variable number of bytes.
    Each byte uses the 7 lowest bits to encode the value. The highest bit set
    to 1 indicates the next byte is also part of the varint. The last byte will
    have this bit set to 0.

This file format is called the VARBLOCK format, in line with the varint format
used to denote the block sizes.

'''

from rsa import key, common, pkcs1, varblock
from rsa._compat import byte

def encrypt_bigfile(infile, outfile, pub_key):
    '''Encrypts a file, writing it to 'outfile' in VARBLOCK format.
    
    :param infile: file-like object to read the cleartext from
    :param outfile: file-like object to write the crypto in VARBLOCK format to
    :param pub_key: :py:class:`rsa.PublicKey` to encrypt with

    '''

    if not isinstance(pub_key, key.PublicKey):
        raise TypeError('Public key required, but got %r' % pub_key)

    key_bytes = common.bit_size(pub_key.n) // 8
    blocksize = key_bytes - 11 # keep space for PKCS#1 padding

    # Write the version number to the VARBLOCK file
    outfile.write(byte(varblock.VARBLOCK_VERSION))

    # Encrypt and write each block
    for block in varblock.yield_fixedblocks(infile, blocksize):
        crypto = pkcs1.encrypt(block, pub_key)

        varblock.write_varint(outfile, len(crypto))
        outfile.write(crypto)

def decrypt_bigfile(infile, outfile, priv_key):
    '''Decrypts an encrypted VARBLOCK file, writing it to 'outfile'
    
    :param infile: file-like object to read the crypto in VARBLOCK format from
    :param outfile: file-like object to write the cleartext to
    :param priv_key: :py:class:`rsa.PrivateKey` to decrypt with

    '''

    if not isinstance(priv_key, key.PrivateKey):
        raise TypeError('Private key required, but got %r' % priv_key)
    
    for block in varblock.yield_varblocks(infile):
        cleartext = pkcs1.decrypt(block, priv_key)
        outfile.write(cleartext)

__all__ = ['encrypt_bigfile', 'decrypt_bigfile']


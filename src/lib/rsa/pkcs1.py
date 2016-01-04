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

'''Functions for PKCS#1 version 1.5 encryption and signing

This module implements certain functionality from PKCS#1 version 1.5. For a
very clear example, read http://www.di-mgt.com.au/rsa_alg.html#pkcs1schemes

At least 8 bytes of random padding is used when encrypting a message. This makes
these methods much more secure than the ones in the ``rsa`` module.

WARNING: this module leaks information when decryption or verification fails.
The exceptions that are raised contain the Python traceback information, which
can be used to deduce where in the process the failure occurred. DO NOT PASS
SUCH INFORMATION to your users.
'''

import hashlib
import os

from rsa._compat import b
from rsa import common, transform, core, varblock

# ASN.1 codes that describe the hash algorithm used.
HASH_ASN1 = {
    'MD5': b('\x30\x20\x30\x0c\x06\x08\x2a\x86\x48\x86\xf7\x0d\x02\x05\x05\x00\x04\x10'),
    'SHA-1': b('\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14'),
    'SHA-256': b('\x30\x31\x30\x0d\x06\x09\x60\x86\x48\x01\x65\x03\x04\x02\x01\x05\x00\x04\x20'),
    'SHA-384': b('\x30\x41\x30\x0d\x06\x09\x60\x86\x48\x01\x65\x03\x04\x02\x02\x05\x00\x04\x30'),
    'SHA-512': b('\x30\x51\x30\x0d\x06\x09\x60\x86\x48\x01\x65\x03\x04\x02\x03\x05\x00\x04\x40'),
}

HASH_METHODS = {
    'MD5': hashlib.md5,
    'SHA-1': hashlib.sha1,
    'SHA-256': hashlib.sha256,
    'SHA-384': hashlib.sha384,
    'SHA-512': hashlib.sha512,
}

class CryptoError(Exception):
    '''Base class for all exceptions in this module.'''

class DecryptionError(CryptoError):
    '''Raised when decryption fails.'''

class VerificationError(CryptoError):
    '''Raised when verification fails.'''
 
def _pad_for_encryption(message, target_length):
    r'''Pads the message for encryption, returning the padded message.
    
    :return: 00 02 RANDOM_DATA 00 MESSAGE
    
    >>> block = _pad_for_encryption('hello', 16)
    >>> len(block)
    16
    >>> block[0:2]
    '\x00\x02'
    >>> block[-6:]
    '\x00hello'

    '''

    max_msglength = target_length - 11
    msglength = len(message)
    
    if msglength > max_msglength:
        raise OverflowError('%i bytes needed for message, but there is only'
            ' space for %i' % (msglength, max_msglength))
    
    # Get random padding
    padding = b('')
    padding_length = target_length - msglength - 3
    
    # We remove 0-bytes, so we'll end up with less padding than we've asked for,
    # so keep adding data until we're at the correct length.
    while len(padding) < padding_length:
        needed_bytes = padding_length - len(padding)
        
        # Always read at least 8 bytes more than we need, and trim off the rest
        # after removing the 0-bytes. This increases the chance of getting
        # enough bytes, especially when needed_bytes is small
        new_padding = os.urandom(needed_bytes + 5)
        new_padding = new_padding.replace(b('\x00'), b(''))
        padding = padding + new_padding[:needed_bytes]
    
    assert len(padding) == padding_length
    
    return b('').join([b('\x00\x02'),
                    padding,
                    b('\x00'),
                    message])
    

def _pad_for_signing(message, target_length):
    r'''Pads the message for signing, returning the padded message.
    
    The padding is always a repetition of FF bytes.
    
    :return: 00 01 PADDING 00 MESSAGE
    
    >>> block = _pad_for_signing('hello', 16)
    >>> len(block)
    16
    >>> block[0:2]
    '\x00\x01'
    >>> block[-6:]
    '\x00hello'
    >>> block[2:-6]
    '\xff\xff\xff\xff\xff\xff\xff\xff'
    
    '''

    max_msglength = target_length - 11
    msglength = len(message)
    
    if msglength > max_msglength:
        raise OverflowError('%i bytes needed for message, but there is only'
            ' space for %i' % (msglength, max_msglength))
    
    padding_length = target_length - msglength - 3
    
    return b('').join([b('\x00\x01'),
                    padding_length * b('\xff'),
                    b('\x00'),
                    message])
    
    
def encrypt(message, pub_key):
    '''Encrypts the given message using PKCS#1 v1.5
    
    :param message: the message to encrypt. Must be a byte string no longer than
        ``k-11`` bytes, where ``k`` is the number of bytes needed to encode
        the ``n`` component of the public key.
    :param pub_key: the :py:class:`rsa.PublicKey` to encrypt with.
    :raise OverflowError: when the message is too large to fit in the padded
        block.
        
    >>> from rsa import key, common
    >>> (pub_key, priv_key) = key.newkeys(256)
    >>> message = 'hello'
    >>> crypto = encrypt(message, pub_key)
    
    The crypto text should be just as long as the public key 'n' component:

    >>> len(crypto) == common.byte_size(pub_key.n)
    True
    
    '''
    
    keylength = common.byte_size(pub_key.n)
    padded = _pad_for_encryption(message, keylength)
    
    payload = transform.bytes2int(padded)
    encrypted = core.encrypt_int(payload, pub_key.e, pub_key.n)
    block = transform.int2bytes(encrypted, keylength)
    
    return block

def decrypt(crypto, priv_key):
    r'''Decrypts the given message using PKCS#1 v1.5
    
    The decryption is considered 'failed' when the resulting cleartext doesn't
    start with the bytes 00 02, or when the 00 byte between the padding and
    the message cannot be found.
    
    :param crypto: the crypto text as returned by :py:func:`rsa.encrypt`
    :param priv_key: the :py:class:`rsa.PrivateKey` to decrypt with.
    :raise DecryptionError: when the decryption fails. No details are given as
        to why the code thinks the decryption fails, as this would leak
        information about the private key.


    >>> import rsa
    >>> (pub_key, priv_key) = rsa.newkeys(256)

    It works with strings:

    >>> crypto = encrypt('hello', pub_key)
    >>> decrypt(crypto, priv_key)
    'hello'
    
    And with binary data:

    >>> crypto = encrypt('\x00\x00\x00\x00\x01', pub_key)
    >>> decrypt(crypto, priv_key)
    '\x00\x00\x00\x00\x01'

    Altering the encrypted information will *likely* cause a
    :py:class:`rsa.pkcs1.DecryptionError`. If you want to be *sure*, use
    :py:func:`rsa.sign`.


    .. warning::

        Never display the stack trace of a
        :py:class:`rsa.pkcs1.DecryptionError` exception. It shows where in the
        code the exception occurred, and thus leaks information about the key.
        It's only a tiny bit of information, but every bit makes cracking the
        keys easier.

    >>> crypto = encrypt('hello', pub_key)
    >>> crypto = crypto[0:5] + 'X' + crypto[6:] # change a byte
    >>> decrypt(crypto, priv_key)
    Traceback (most recent call last):
    ...
    DecryptionError: Decryption failed

    '''
    
    blocksize = common.byte_size(priv_key.n)
    encrypted = transform.bytes2int(crypto)
    decrypted = core.decrypt_int(encrypted, priv_key.d, priv_key.n)
    cleartext = transform.int2bytes(decrypted, blocksize)

    # If we can't find the cleartext marker, decryption failed.
    if cleartext[0:2] != b('\x00\x02'):
        raise DecryptionError('Decryption failed')
    
    # Find the 00 separator between the padding and the message
    try:
        sep_idx = cleartext.index(b('\x00'), 2)
    except ValueError:
        raise DecryptionError('Decryption failed')
    
    return cleartext[sep_idx+1:]
    
def sign(message, priv_key, hash):
    '''Signs the message with the private key.

    Hashes the message, then signs the hash with the given key. This is known
    as a "detached signature", because the message itself isn't altered.
    
    :param message: the message to sign. Can be an 8-bit string or a file-like
        object. If ``message`` has a ``read()`` method, it is assumed to be a
        file-like object.
    :param priv_key: the :py:class:`rsa.PrivateKey` to sign with
    :param hash: the hash method used on the message. Use 'MD5', 'SHA-1',
        'SHA-256', 'SHA-384' or 'SHA-512'.
    :return: a message signature block.
    :raise OverflowError: if the private key is too small to contain the
        requested hash.

    '''

    # Get the ASN1 code for this hash method
    if hash not in HASH_ASN1:
        raise ValueError('Invalid hash method: %s' % hash)
    asn1code = HASH_ASN1[hash]
    
    # Calculate the hash
    hash = _hash(message, hash)

    # Encrypt the hash with the private key
    cleartext = asn1code + hash
    keylength = common.byte_size(priv_key.n)
    padded = _pad_for_signing(cleartext, keylength)
    
    payload = transform.bytes2int(padded)
    encrypted = core.encrypt_int(payload, priv_key.d, priv_key.n)
    block = transform.int2bytes(encrypted, keylength)
    
    return block

def verify(message, signature, pub_key):
    '''Verifies that the signature matches the message.
    
    The hash method is detected automatically from the signature.
    
    :param message: the signed message. Can be an 8-bit string or a file-like
        object. If ``message`` has a ``read()`` method, it is assumed to be a
        file-like object.
    :param signature: the signature block, as created with :py:func:`rsa.sign`.
    :param pub_key: the :py:class:`rsa.PublicKey` of the person signing the message.
    :raise VerificationError: when the signature doesn't match the message.

    .. warning::

        Never display the stack trace of a
        :py:class:`rsa.pkcs1.VerificationError` exception. It shows where in
        the code the exception occurred, and thus leaks information about the
        key. It's only a tiny bit of information, but every bit makes cracking
        the keys easier.

    '''
    
    blocksize = common.byte_size(pub_key.n)
    encrypted = transform.bytes2int(signature)
    decrypted = core.decrypt_int(encrypted, pub_key.e, pub_key.n)
    clearsig = transform.int2bytes(decrypted, blocksize)

    # If we can't find the signature  marker, verification failed.
    if clearsig[0:2] != b('\x00\x01'):
        raise VerificationError('Verification failed')
    
    # Find the 00 separator between the padding and the payload
    try:
        sep_idx = clearsig.index(b('\x00'), 2)
    except ValueError:
        raise VerificationError('Verification failed')
    
    # Get the hash and the hash method
    (method_name, signature_hash) = _find_method_hash(clearsig[sep_idx+1:])
    message_hash = _hash(message, method_name)

    # Compare the real hash to the hash in the signature
    if message_hash != signature_hash:
        raise VerificationError('Verification failed')

    return True

def _hash(message, method_name):
    '''Returns the message digest.
    
    :param message: the signed message. Can be an 8-bit string or a file-like
        object. If ``message`` has a ``read()`` method, it is assumed to be a
        file-like object.
    :param method_name: the hash method, must be a key of
        :py:const:`HASH_METHODS`.
    
    '''

    if method_name not in HASH_METHODS:
        raise ValueError('Invalid hash method: %s' % method_name)
    
    method = HASH_METHODS[method_name]
    hasher = method()

    if hasattr(message, 'read') and hasattr(message.read, '__call__'):
        # read as 1K blocks
        for block in varblock.yield_fixedblocks(message, 1024):
            hasher.update(block)
    else:
        # hash the message object itself.
        hasher.update(message)

    return hasher.digest()


def _find_method_hash(method_hash):
    '''Finds the hash method and the hash itself.
    
    :param method_hash: ASN1 code for the hash method concatenated with the
        hash itself.
    
    :return: tuple (method, hash) where ``method`` is the used hash method, and
        ``hash`` is the hash itself.
    
    :raise VerificationFailed: when the hash method cannot be found

    '''

    for (hashname, asn1code) in HASH_ASN1.items():
        if not method_hash.startswith(asn1code):
            continue
        
        return (hashname, method_hash[len(asn1code):])
    
    raise VerificationError('Verification failed')


__all__ = ['encrypt', 'decrypt', 'sign', 'verify',
           'DecryptionError', 'VerificationError', 'CryptoError']

if __name__ == '__main__':
    print('Running doctests 1000x or until failure')
    import doctest
    
    for count in range(1000):
        (failures, tests) = doctest.testmod()
        if failures:
            break
        
        if count and count % 100 == 0:
            print('%i times' % count)
    
    print('Doctests done')

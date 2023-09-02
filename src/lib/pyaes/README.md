pyaes
=====

A pure-Python implementation of the AES block cipher algorithm and the common modes of operation (CBC, CFB, CTR, ECB and OFB).


Features
--------

* Supports all AES key sizes
* Supports all AES common modes
* Pure-Python (no external dependencies)
* BlockFeeder API allows streams to easily be encrypted and decrypted
* Python 2.x and 3.x support (make sure you pass in bytes(), not strings for Python 3)


API
---

All keys may be 128 bits (16 bytes), 192 bits (24 bytes) or 256 bits (32 bytes) long.

To generate a random key use:
```python
import os

# 128 bit, 192 bit and 256 bit keys
key_128 = os.urandom(16)
key_192 = os.urandom(24)
key_256 = os.urandom(32)
```

To generate keys from simple-to-remember passwords, consider using a _password-based key-derivation function_ such as [scrypt](https://github.com/ricmoo/pyscrypt).


### Common Modes of Operation

There are many modes of operations, each with various pros and cons. In general though, the **CBC** and **CTR** modes are recommended. The **ECB is NOT recommended.**, and is included primarily for completeness.

Each of the following examples assumes the following key:
```python
import pyaes

# A 256 bit (32 byte) key
key = "This_key_for_demo_purposes_only!"

# For some modes of operation we need a random initialization vector
# of 16 bytes
iv = "InitializationVe"
```


#### Counter Mode of Operation (recommended)

```python
aes = pyaes.AESModeOfOperationCTR(key)
plaintext = "Text may be any length you wish, no padding is required"
ciphertext = aes.encrypt(plaintext)

# '''\xb6\x99\x10=\xa4\x96\x88\xd1\x89\x1co\xe6\x1d\xef;\x11\x03\xe3\xee
#    \xa9V?wY\xbfe\xcdO\xe3\xdf\x9dV\x19\xe5\x8dk\x9fh\xb87>\xdb\xa3\xd6
#    \x86\xf4\xbd\xb0\x97\xf1\t\x02\xe9 \xed'''
print repr(ciphertext)

# The counter mode of operation maintains state, so decryption requires
# a new instance be created
aes = pyaes.AESModeOfOperationCTR(key)
decrypted = aes.decrypt(ciphertext)

# True
print decrypted == plaintext

# To use a custom initial value
counter = pyaes.Counter(initial_value = 100)
aes = pyaes.AESModeOfOperationCTR(key, counter = counter)
ciphertext = aes.encrypt(plaintext)

# '''WZ\x844\x02\xbfoY\x1f\x12\xa6\xce\x03\x82Ei)\xf6\x97mX\x86\xe3\x9d
#    _1\xdd\xbd\x87\xb5\xccEM_4\x01$\xa6\x81\x0b\xd5\x04\xd7Al\x07\xe5
#    \xb2\x0e\\\x0f\x00\x13,\x07'''
print repr(ciphertext)
```


#### Cipher-Block Chaining (recommended)

```python
aes = pyaes.AESModeOfOperationCBC(key, iv = iv)
plaintext = "TextMustBe16Byte"
ciphertext = aes.encrypt(plaintext)

# '\xd6:\x18\xe6\xb1\xb3\xc3\xdc\x87\xdf\xa7|\x08{k\xb6'
print repr(ciphertext)


# The cipher-block chaining mode of operation maintains state, so
# decryption requires a new instance be created
aes = pyaes.AESModeOfOperationCBC(key, iv = iv)
decrypted = aes.decrypt(ciphertext)

# True
print decrypted == plaintext
```


#### Cipher Feedback

```python
# Each block into the mode of operation must be a multiple of the segment
# size. For this example we choose 8 bytes.
aes = pyaes.AESModeOfOperationCFB(key, iv = iv, segment_size = 8)
plaintext =  "TextMustBeAMultipleOfSegmentSize"
ciphertext = aes.encrypt(plaintext)

# '''v\xa9\xc1w"\x8aL\x93\xcb\xdf\xa0/\xf8Y\x0b\x8d\x88i\xcb\x85rmp
#    \x85\xfe\xafM\x0c)\xd5\xeb\xaf'''
print repr(ciphertext)


# The cipher-block chaining mode of operation maintains state, so
# decryption requires a new instance be created
aes = pyaes.AESModeOfOperationCFB(key, iv = iv, segment_size = 8)
decrypted = aes.decrypt(ciphertext)

# True
print decrypted == plaintext
```


#### Output Feedback Mode of Operation

```python
aes = pyaes.AESModeOfOperationOFB(key, iv = iv)
plaintext = "Text may be any length you wish, no padding is required"
ciphertext = aes.encrypt(plaintext)

# '''v\xa9\xc1wO\x92^\x9e\rR\x1e\xf7\xb1\xa2\x9d"l1\xc7\xe7\x9d\x87(\xc26s
#    \xdd8\xc8@\xb6\xd9!\xf5\x0cM\xaa\x9b\xc4\xedLD\xe4\xb9\xd8\xdf\x9e\xac
#    \xa1\xb8\xea\x0f\x8ev\xb5'''
print repr(ciphertext)

# The counter mode of operation maintains state, so decryption requires
# a new instance be created
aes = pyaes.AESModeOfOperationOFB(key, iv = iv)
decrypted = aes.decrypt(ciphertext)

# True
print decrypted == plaintext
```


#### Electronic Codebook (NOT recommended)

```python
aes = pyaes.AESModeOfOperationECB(key)
plaintext = "TextMustBe16Byte"
ciphertext = aes.encrypt(plaintext)

# 'L6\x95\x85\xe4\xd9\xf1\x8a\xfb\xe5\x94X\x80|\x19\xc3'
print repr(ciphertext)

# Since there is no state stored in this mode of operation, it
# is not necessary to create a new aes object for decryption.
#aes = pyaes.AESModeOfOperationECB(key)
decrypted = aes.decrypt(ciphertext)

# True
print decrypted == plaintext
```


### BlockFeeder

Since most of the modes of operations require data in specific block-sized or segment-sized blocks, it can be difficult when working with large arbitrary streams or strings of data.

The BlockFeeder class is meant to make life easier for you, by buffering bytes across multiple calls and returning bytes as they are available, as well as padding or stripping the output when finished, if necessary.

```python
import pyaes

# Any mode of operation can be used; for this example CBC
key = "This_key_for_demo_purposes_only!"
iv = "InitializationVe"

ciphertext = ''

# We can encrypt one line at a time, regardles of length
encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(key, iv))
for line in file('/etc/passwd'):
    ciphertext += encrypter.feed(line)

# Make a final call to flush any remaining bytes and add paddin
ciphertext += encrypter.feed()

# We can decrypt the cipher text in chunks (here we split it in half)
decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))
decrypted = decrypter.feed(ciphertext[:len(ciphertext) / 2])
decrypted += decrypter.feed(ciphertext[len(ciphertext) / 2:])

# Again, make a final call to flush any remaining bytes and strip padding
decrypted += decrypter.feed()

print file('/etc/passwd').read() == decrypted
```

### Stream Feeder

This is meant to make it even easier to encrypt and decrypt streams and large files.

```python
import pyaes

# Any mode of operation can be used; for this example CTR
key = "This_key_for_demo_purposes_only!"

# Create the mode of operation to encrypt with
mode = pyaes.AESModeOfOperationCTR(key)

# The input and output files
file_in = file('/etc/passwd')
file_out = file('/tmp/encrypted.bin', 'wb')

# Encrypt the data as a stream, the file is read in 8kb chunks, be default
pyaes.encrypt_stream(mode, file_in, file_out)

# Close the files
file_in.close()
file_out.close()
```

Decrypting is identical, except you would use `pyaes.decrypt_stream`, and the encrypted file would be the `file_in` and target for decryption the `file_out`.

### AES block cipher

Generally you should use one of the modes of operation above. This may however be useful for experimenting with a custom mode of operation or dealing with encrypted blocks.

The block cipher requires exactly one block of data to encrypt or decrypt, and each block should be an array with each element an integer representation of a byte.

```python
import pyaes

# 16 byte block of plain text
plaintext = "Hello World!!!!!"
plaintext_bytes = [ ord(c) for c in plaintext ]

# 32 byte key (256 bit)
key = "This_key_for_demo_purposes_only!"

# Our AES instance
aes = pyaes.AES(key)

# Encrypt!
ciphertext = aes.encrypt(plaintext_bytes)

# [55, 250, 182, 25, 185, 208, 186, 95, 206, 115, 50, 115, 108, 58, 174, 115]
print repr(ciphertext)

# Decrypt!
decrypted = aes.decrypt(ciphertext)

# True
print decrypted == plaintext_bytes
```

What is a key?
--------------

This seems to be a point of confusion for many people new to using encryption. You can think of the key as the *"password"*. However, these algorithms require the *"password"* to be a specific length.

With AES, there are three possible key lengths, 16-bytes, 24-bytes or 32-bytes. When you create an AES object, the key size is automatically detected, so it is important to pass in a key of the correct length.

Often, you wish to provide a password of arbitrary length, for example, something easy to remember or write down. In these cases, you must come up with a way to transform the password into a key, of a specific length. A **Password-Based Key Derivation Function** (PBKDF) is an algorithm designed for this exact purpose.

Here is an example, using the popular (possibly obsolete?) *crypt* PBKDF:

```
# See: https://www.dlitz.net/software/python-pbkdf2/
import pbkdf2

password = "HelloWorld"

# The crypt PBKDF returns a 48-byte string
key = pbkdf2.crypt(password)

# A 16-byte, 24-byte and 32-byte key, respectively
key_16 = key[:16]
key_24 = key[:24]
key_32 = key[:32]
```

The [scrypt](https://github.com/ricmoo/pyscrypt) PBKDF is intentionally slow, to make it more difficult to brute-force guess a password:

```
# See: https://github.com/ricmoo/pyscrypt
import pyscrypt

password = "HelloWorld"

# Salt is required, and prevents Rainbow Table attacks
salt = "SeaSalt"

# N, r, and p are parameters to specify how difficult it should be to
# generate a key; bigger numbers take longer and more memory
N = 1024
r = 1
p = 1

# A 16-byte, 24-byte and 32-byte key, respectively; the scrypt algorithm takes
# a 6-th parameter, indicating key length
key_16 = pyscrypt.hash(password, salt, N, r, p, 16)
key_24 = pyscrypt.hash(password, salt, N, r, p, 24)
key_32 = pyscrypt.hash(password, salt, N, r, p, 32)
```

Another possibility, is to use a hashing function, such as SHA256 to hash the password, but this method may be vulnerable to [Rainbow Attacks](http://en.wikipedia.org/wiki/Rainbow_table), unless you use a [salt](http://en.wikipedia.org/wiki/Salt_(cryptography)).

```python
import hashlib

password = "HelloWorld"

# The SHA256 hash algorithm returns a 32-byte string
hashed = hashlib.sha256(password).digest()

# A 16-byte, 24-byte and 32-byte key, respectively
key_16 = hashed[:16]
key_24 = hashed[:24]
key_32 = hashed
```




Performance
-----------

There is a test case provided in _/tests/test-aes.py_ which does some basic performance testing (its primary purpose is moreso as a regression test).

Based on that test, in **CPython**, this library is about 30x slower than [PyCrypto](https://www.dlitz.net/software/pycrypto/) for CBC, ECB and OFB; about 80x slower for CFB; and 300x slower for CTR.

Based on that same test, in **Pypy**, this library is about 4x slower than [PyCrypto](https://www.dlitz.net/software/pycrypto/) for CBC, ECB and OFB; about 12x slower for CFB; and 19x slower for CTR.

The PyCrypto documentation makes reference to the counter call being responsible for the speed problems of the counter (CTR) mode of operation, which is why they use a specially optimized counter. I will investigate this problem further in the future.


FAQ
---

#### Why do this?

The short answer, *why not?*

The longer answer, is for my [pyscrypt](https://github.com/ricmoo/pyscrypt) library. I required a pure-Python AES implementation that supported 256-bit keys with the counter (CTR) mode of operation. After searching, I found several implementations, but all were missing CTR or only supported 128 bit keys. After all the work of learning AES inside and out to implement the library, it was only a marginal amount of extra work to library-ify a more general solution. So, *why not?*

#### How do I get a question I have added?

E-mail me at pyaes@ricmoo.com with any questions, suggestions, comments, et cetera.


#### Can I give you my money?

Umm... Ok? :-)

_Bitcoin_  - `18UDs4qV1shu2CgTS2tKojhCtM69kpnWg9`

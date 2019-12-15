# PyElliptic

PyElliptic is a high level wrapper for the cryptographic library : OpenSSL.
Under the GNU General Public License

Python3 compatible. For GNU/Linux and Windows.
Require OpenSSL

## Version

The [upstream pyelliptic](https://github.com/yann2192/pyelliptic) has been
deprecated by the author at 1.5.8 and ECC API has been removed.

This version is a fork of the pyelliptic extracted from the [BitMessage source
tree](https://github.com/Bitmessage/PyBitmessage), and does contain the ECC
API. To minimize confusion but to avoid renaming the module, major version has
been bumped.

BitMessage is actively maintained, and this fork of pyelliptic will track and
incorporate any changes to pyelliptic from BitMessage. Ideally, in the future,
BitMessage would import this module as a dependency instead of maintaining a
copy of the source in its repository.

The BitMessage fork forked from v1.3 of upstream pyelliptic. The commits in
this repository are the commits extracted from the BitMessage repository and
applied to pyelliptic v1.3 upstream repository (i.e. to the base of the fork),
so history with athorship is preserved.

Some of the changes in upstream pyelliptic between 1.3 and 1.5.8 came from
BitMessage, those changes are present in this fork. Other changes do not exist
in this fork (they may be added in the future).

Also, a few minor changes exist in this fork but is not (yet) present in
BitMessage source. See:

    git log 1.3-PyBitmessage-37489cf7feff8d5047f24baa8f6d27f353a6d6ac..HEAD

## Features

### Asymmetric cryptography using Elliptic Curve Cryptography (ECC)

* Key agreement : ECDH
* Digital signatures : ECDSA
* Hybrid encryption : ECIES (like RSA)

### Symmetric cryptography

* AES-128 (CBC, OFB, CFB, CTR)
* AES-256 (CBC, OFB, CFB, CTR)
* Blowfish (CFB and CBC)
* RC4

### Other

* CSPRNG
* HMAC (using SHA512)
* PBKDF2 (SHA256 and SHA512)

## Example

```python
#!/usr/bin/python

import pyelliptic

# Symmetric encryption
iv = pyelliptic.Cipher.gen_IV('aes-256-cfb')
ctx = pyelliptic.Cipher("secretkey", iv, 1, ciphername='aes-256-cfb')

ciphertext = ctx.update('test1')
ciphertext += ctx.update('test2')
ciphertext += ctx.final()

ctx2 = pyelliptic.Cipher("secretkey", iv, 0, ciphername='aes-256-cfb')
print ctx2.ciphering(ciphertext)

# Asymmetric encryption
alice = pyelliptic.ECC() # default curve: sect283r1
bob = pyelliptic.ECC(curve='sect571r1')

ciphertext = alice.encrypt("Hello Bob", bob.get_pubkey())
print bob.decrypt(ciphertext)

signature = bob.sign("Hello Alice")
# alice's job :
print pyelliptic.ECC(pubkey=bob.get_pubkey()).verify(signature, "Hello Alice")

# ERROR !!!
try:
    key = alice.get_ecdh_key(bob.get_pubkey())
except: print("For ECDH key agreement, the keys must be defined on the same curve !")

alice = pyelliptic.ECC(curve='sect571r1')
print alice.get_ecdh_key(bob.get_pubkey()).encode('hex')
print bob.get_ecdh_key(alice.get_pubkey()).encode('hex')
```

import base64
import hashlib
import Crypt.ed25519 as ed25519
import rsa

def sign(data, privatekey):
    # !ONION v3!
    if len(privatekey) == 88:
        prv_key = base64.b64decode(privatekey)
        pub_key = ed25519.publickey_unsafe(prv_key)
        signed = ed25519.signature_unsafe(data, prv_key, pub_key)
        return signed

    # FIXME: doesn't look good
    if "BEGIN RSA PRIVATE KEY" not in privatekey:
        privatekey = "-----BEGIN RSA PRIVATE KEY-----\n%s\n-----END RSA PRIVATE KEY-----" % privatekey

    priv = rsa.PrivateKey.load_pkcs1(privatekey)
    signed = rsa.pkcs1.sign(data, priv, 'SHA-256')
    return signed

def verify(data, publickey, sign):
    # !ONION v3!
    if len(publickey) == 32:
        try:
            valid = ed25519.checkvalid(sign, data, publickey)
            valid = 'SHA-256'
        except Exception as err:
            # TODO: traceback
            print(err)
            valid = False
        return valid

    pub = rsa.PublicKey.load_pkcs1(publickey, format="DER")
    try:
        valid = rsa.pkcs1.verify(data, sign, pub)
    except rsa.pkcs1.VerificationError:
        valid = False
    return valid

def privatekeyToPublickey(privatekey):
    # !ONION v3!
    if len(privatekey) == 88:
        prv_key = base64.b64decode(privatekey)
        pub_key = ed25519.publickey_unsafe(prv_key)
        return pub_key

    if "BEGIN RSA PRIVATE KEY" not in privatekey:
        privatekey = "-----BEGIN RSA PRIVATE KEY-----\n%s\n-----END RSA PRIVATE KEY-----" % privatekey

    priv = rsa.PrivateKey.load_pkcs1(privatekey)
    pub = rsa.PublicKey(priv.n, priv.e)
    return pub.save_pkcs1("DER")

# adopted by @anonymoose & @caryoscelus from https://gitweb.torproject.org/stem.git/tree/stem/descriptor/hidden_service.py @ address_from_identity_key
def publickeyToOnionV3Address(key):
     CHECKSUM_CONSTANT = b'.onion checksum'
     version = b'\x03' # v3
     checksum = hashlib.sha3_256(CHECKSUM_CONSTANT + key + version).digest()[:2]
     onion_address = base64.b32encode(key + checksum + version)
     return onion_address.decode('utf-8', 'replace').lower()

def publickeyToOnion(publickey):
    if len(publickey) == 32:
        # !ONION v3!
        return publickeyToOnionV3Address(publickey)
    else:
        return base64.b32encode(hashlib.sha1(publickey).digest()[:10]).lower().decode("ascii")

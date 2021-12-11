import base64
import hashlib

def sign(data, privatekey):
    import rsa
    from rsa import pkcs1
    from lib import Ed25519

    ## Onion Service V3
    if len(privatekey) == 88:
        prv_key = base64.b64decode(privatekey)
        pub_key = Ed25519.publickey_unsafe(prv_key)
        sign = Ed25519.signature_unsafe(data, prv_key, pub_key)

        return sign

    ## Onion Service V2
    if "BEGIN RSA PRIVATE KEY" not in privatekey:
        privatekey = "-----BEGIN RSA PRIVATE KEY-----\n%s\n-----END RSA PRIVATE KEY-----" % privatekey

    priv = rsa.PrivateKey.load_pkcs1(privatekey)
    sign = rsa.pkcs1.sign(data, priv, 'SHA-256')
    return sign

def verify(data, publickey, sign):
    import rsa
    from rsa import pkcs1
    from lib import Ed25519

    ## Onion Service V3
    if len(publickey) == 32:
        
        try:
            valid = Ed25519.checkvalid(sign, data, publickey) 
            valid = 'SHA-256'

        except Exception as err:
            print(err)
            valid = False

        return valid

    ## Onion Service V2
    pub = rsa.PublicKey.load_pkcs1(publickey, format="DER")
    
    try:
        valid = rsa.pkcs1.verify(data, sign, pub)
    
    except pkcs1.VerificationError:
        valid = False
    
    return valid

def privatekeyToPublickey(privatekey):
    import rsa
    from rsa import pkcs1
    from lib import Ed25519

    ## Onion Service V3
    if len(privatekey) == 88:
      prv_key = base64.b64decode(privatekey)
      pub_key = Ed25519.publickey_unsafe(prv_key)

      return pub_key

    ## Onion Service V2
    if "BEGIN RSA PRIVATE KEY" not in privatekey:
        privatekey = "-----BEGIN RSA PRIVATE KEY-----\n%s\n-----END RSA PRIVATE KEY-----" % privatekey

    priv = rsa.PrivateKey.load_pkcs1(privatekey)
    pub = rsa.PublicKey(priv.n, priv.e)

    return pub.save_pkcs1("DER")

def publickeyToOnion(publickey):
    from lib import Ed25519
    
    ## Onion Service V3
    if len(publickey) == 32:
        addr = Ed25519.publickey_to_onionaddress(publickey)[:-6]
        
        return addr

    ## Onion Service V2
    return base64.b32encode(hashlib.sha1(publickey).digest()[:10]).lower().decode("ascii")

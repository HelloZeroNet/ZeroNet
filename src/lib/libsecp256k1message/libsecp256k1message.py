import hashlib
import base64
from coincurve import PrivateKey, PublicKey
from base58 import b58encode_check, b58decode_check
from hmac import compare_digest
from util.Electrum import format as zero_format

RECID_MIN = 0
RECID_MAX = 3
RECID_UNCOMPR = 27
LEN_COMPACT_SIG = 65

class SignatureError(ValueError):
    pass

def bitcoin_address():
    """Generate a public address and a secret address."""
    publickey, secretkey = key_pair()

    public_address = compute_public_address(publickey)
    secret_address = compute_secret_address(secretkey)

    return (public_address, secret_address)

def key_pair():
    """Generate a public key and a secret key."""
    secretkey = PrivateKey()
    publickey = PublicKey.from_secret(secretkey.secret)
    return (publickey, secretkey)

def compute_public_address(publickey, compressed=False):
    """Convert a public key to a public Bitcoin address."""
    public_plain = b'\x00' + public_digest(publickey, compressed=compressed)
    return b58encode_check(public_plain)

def compute_secret_address(secretkey):
    """Convert a secret key to a secret Bitcoin address."""
    secret_plain = b'\x80' + secretkey.secret
    return b58encode_check(secret_plain)

def public_digest(publickey, compressed=False):
    """Convert a public key to ripemd160(sha256()) digest."""
    publickey_hex = publickey.format(compressed=compressed)
    return hashlib.new('ripemd160', hashlib.sha256(publickey_hex).digest()).digest()

def address_public_digest(address):
    """Convert a public Bitcoin address to ripemd160(sha256()) digest."""
    public_plain = b58decode_check(address)
    if not public_plain.startswith(b'\x00') or len(public_plain) != 21:
        raise ValueError('Invalid public key digest')
    return public_plain[1:]

def _decode_bitcoin_secret(address):
    secret_plain = b58decode_check(address)
    if not secret_plain.startswith(b'\x80') or len(secret_plain) != 33:
        raise ValueError('Invalid secret key. Uncompressed keys only.')
    return secret_plain[1:]

def recover_public_key(signature, message):
    """Recover public key from signature and message.
    Recovered public key guarantees a correct signature"""
    return PublicKey.from_signature_and_message(signature, message)

def decode_secret_key(address):
    """Convert a secret Bitcoin address to a secret key."""
    return PrivateKey(_decode_bitcoin_secret(address))


def coincurve_sig(electrum_signature):
    # coincurve := r + s + recovery_id
    # where (0 <= recovery_id <= 3)
    # https://github.com/bitcoin-core/secp256k1/blob/0b7024185045a49a1a6a4c5615bf31c94f63d9c4/src/modules/recovery/main_impl.h#L35
    if len(electrum_signature) != LEN_COMPACT_SIG:
        raise ValueError('Not a 65-byte compact signature.')
    # Compute coincurve recid
    recid = (electrum_signature[0] - 27) & 3
    if not (RECID_MIN <= recid <= RECID_MAX):
        raise ValueError('Recovery ID %d is not supported.' % recid)
    recid_byte = int.to_bytes(recid, length=1, byteorder='big')
    return electrum_signature[1:] + recid_byte


def electrum_sig(coincurve_signature):
    # electrum := recovery_id + r + s
    # where (27 <= recovery_id <= 30)
    # https://github.com/scintill/bitcoin-signature-tools/blob/ed3f5be5045af74a54c92d3648de98c329d9b4f7/key.cpp#L285
    if len(coincurve_signature) != LEN_COMPACT_SIG:
        raise ValueError('Not a 65-byte compact signature.')
    # Compute Electrum recid
    recid = coincurve_signature[-1] + RECID_UNCOMPR
    if not (RECID_UNCOMPR + RECID_MIN <= recid <= RECID_UNCOMPR + RECID_MAX):
        raise ValueError('Recovery ID %d is not supported.' % recid)
    recid_byte = int.to_bytes(recid, length=1, byteorder='big')
    return recid_byte + coincurve_signature[0:-1]

def sign_data(secretkey, byte_string):
    """Sign [byte_string] with [secretkey].
    Return serialized signature compatible with Electrum (ZeroNet)."""
    # encode the message
    encoded = zero_format(byte_string)
    # sign the message and get a coincurve signature
    signature = secretkey.sign_recoverable(encoded)
    # reserialize signature and return it
    return electrum_sig(signature)

def verify_data(key_digest, electrum_signature, byte_string):
    """Verify if [electrum_signature] of [byte_string] is correctly signed and
    is signed with the secret counterpart of [key_digest].
    Raise SignatureError if the signature is forged or otherwise problematic."""
    # reserialize signature
    signature = coincurve_sig(electrum_signature)
    # encode the message
    encoded = zero_format(byte_string)
    # recover full public key from signature
    # "which guarantees a correct signature"
    publickey = recover_public_key(signature, encoded)

    # verify that the message is correctly signed by the public key
    # correct_sig = verify_sig(publickey, signature, encoded)

    # verify that the public key is what we expect
    correct_key = verify_key(publickey, key_digest)

    if not correct_key:
        raise SignatureError('Signature is forged!')

def verify_sig(publickey, signature, byte_string):
    return publickey.verify(signature, byte_string)

def verify_key(publickey, key_digest):
    return compare_digest(key_digest, public_digest(publickey))

def recover_address(data, sign):
    sign_bytes = base64.b64decode(sign)
    is_compressed = ((sign_bytes[0] - 27) & 4) != 0
    publickey = recover_public_key(coincurve_sig(sign_bytes), zero_format(data))
    return compute_public_address(publickey, compressed=is_compressed)

__all__ = [
    'SignatureError',
    'key_pair', 'compute_public_address', 'compute_secret_address',
    'public_digest', 'address_public_digest', 'recover_public_key', 'decode_secret_key',
    'sign_data', 'verify_data', "recover_address"
]

if __name__ == "__main__":
    import base64, time, multiprocessing
    s = time.time()
    privatekey = decode_secret_key(b"5JsunC55XGVqFQj5kPGK4MWgTL26jKbnPhjnmchSNPo75XXCwtk")
    threads = []
    for i in range(1000):
        data = bytes("hello", "utf8")
        address = recover_address(data, "HGbib2kv9gm9IJjDt1FXbXFczZi35u0rZR3iPUIt5GglDDCeIQ7v8eYXVNIaLoJRI4URGZrhwmsYQ9aVtRTnTfQ=")
    print("- Verify x10000: %.3fs %s" % (time.time() - s, address))

    s = time.time()
    for i in range(1000):
        privatekey = decode_secret_key(b"5JsunC55XGVqFQj5kPGK4MWgTL26jKbnPhjnmchSNPo75XXCwtk")
        sign = sign_data(privatekey, b"hello")
        sign_b64 = base64.b64encode(sign)

    print("- Sign x1000: %.3fs" % (time.time() - s))

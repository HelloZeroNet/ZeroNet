import hashlib
import struct


# Electrum, the heck?!

def bchr(i):
    return struct.pack("B", i)

def encode(val, base, minlen=0):
    base, minlen = int(base), int(minlen)
    code_string = b"".join([bchr(x) for x in range(256)])
    result = b""
    while val > 0:
        index = val % base
        result = code_string[index:index + 1] + result
        val //= base
    return code_string[0:1] * max(minlen - len(result), 0) + result

def insane_int(x):
    x = int(x)
    if x < 253:
        return bchr(x)
    elif x < 65536:
        return bchr(253) + encode(x, 256, 2)[::-1]
    elif x < 4294967296:
        return bchr(254) + encode(x, 256, 4)[::-1]
    else:
        return bchr(255) + encode(x, 256, 8)[::-1]


def magic(message):
    return b"\x18Bitcoin Signed Message:\n" + insane_int(len(message)) + message

def format(message):
    return hashlib.sha256(magic(message)).digest()

def dbl_format(message):
    return hashlib.sha256(format(message)).digest()

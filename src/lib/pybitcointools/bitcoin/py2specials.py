import sys, re
import binascii
import os
import hashlib


if sys.version_info.major == 2:
    string_types = (str, unicode)
    string_or_bytes_types = string_types
    int_types = (int, float, long)

    # Base switching
    code_strings = {
        2: '01',
        10: '0123456789',
        16: '0123456789abcdef',
        32: 'abcdefghijklmnopqrstuvwxyz234567',
        58: '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz',
        256: ''.join([chr(x) for x in range(256)])
    }

    def bin_dbl_sha256(s):
        bytes_to_hash = from_string_to_bytes(s)
        return hashlib.sha256(hashlib.sha256(bytes_to_hash).digest()).digest()

    def lpad(msg, symbol, length):
        if len(msg) >= length:
            return msg
        return symbol * (length - len(msg)) + msg

    def get_code_string(base):
        if base in code_strings:
            return code_strings[base]
        else:
            raise ValueError("Invalid base!")

    def changebase(string, frm, to, minlen=0):
        if frm == to:
            return lpad(string, get_code_string(frm)[0], minlen)
        return encode(decode(string, frm), to, minlen)

    def bin_to_b58check(inp, magicbyte=0):
        inp_fmtd = chr(int(magicbyte)) + inp
        leadingzbytes = len(re.match('^\x00*', inp_fmtd).group(0))
        checksum = bin_dbl_sha256(inp_fmtd)[:4]
        return '1' * leadingzbytes + changebase(inp_fmtd+checksum, 256, 58)

    def bytes_to_hex_string(b):
        return b.encode('hex')

    def safe_from_hex(s):
        return s.decode('hex')

    def from_int_representation_to_bytes(a):
        return str(a)

    def from_int_to_byte(a):
        return chr(a)

    def from_byte_to_int(a):
        return ord(a)

    def from_bytes_to_string(s):
        return s

    def from_string_to_bytes(a):
        return a

    def safe_hexlify(a):
        return binascii.hexlify(a)

    def encode(val, base, minlen=0):
        base, minlen = int(base), int(minlen)
        code_string = get_code_string(base)
        result = ""
        while val > 0:
            result = code_string[val % base] + result
            val //= base
        return code_string[0] * max(minlen - len(result), 0) + result

    def decode(string, base):
        base = int(base)
        code_string = get_code_string(base)
        result = 0
        if base == 16:
            string = string.lower()
        while len(string) > 0:
            result *= base
            result += code_string.find(string[0])
            string = string[1:]
        return result

    def random_string(x):
        return os.urandom(x)

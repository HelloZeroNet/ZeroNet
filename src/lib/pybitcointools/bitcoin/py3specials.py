import sys, os
import binascii
import hashlib


if sys.version_info.major == 3:
    string_types = (str)
    string_or_bytes_types = (str, bytes)
    int_types = (int, float)
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
        inp_fmtd = from_int_to_byte(int(magicbyte))+inp

        leadingzbytes = 0
        for x in inp_fmtd:
            if x != 0:
                break
            leadingzbytes += 1

        checksum = bin_dbl_sha256(inp_fmtd)[:4]
        return '1' * leadingzbytes + changebase(inp_fmtd+checksum, 256, 58)

    def bytes_to_hex_string(b):
        if isinstance(b, str):
            return b

        return ''.join('{:02x}'.format(y) for y in b)

    def safe_from_hex(s):
        return bytes.fromhex(s)

    def from_int_representation_to_bytes(a):
        return bytes(str(a), 'utf-8')

    def from_int_to_byte(a):
        return bytes([a])

    def from_byte_to_int(a):
        return a

    def from_string_to_bytes(a):
        return a if isinstance(a, bytes) else bytes(a, 'utf-8')

    def safe_hexlify(a):
        return str(binascii.hexlify(a), 'utf-8')

    def encode(val, base, minlen=0):
        base, minlen = int(base), int(minlen)
        code_string = get_code_string(base)
        result_bytes = bytes()
        while val > 0:
            curcode = code_string[val % base]
            result_bytes = bytes([ord(curcode)]) + result_bytes
            val //= base

        pad_size = minlen - len(result_bytes)

        padding_element = b'\x00' if base == 256 else b'1' \
            if base == 58 else b'0'
        if (pad_size > 0):
            result_bytes = padding_element*pad_size + result_bytes

        result_string = ''.join([chr(y) for y in result_bytes])
        result = result_bytes if base == 256 else result_string

        return result

    def decode(string, base):
        if base == 256 and isinstance(string, str):
            string = bytes(bytearray.fromhex(string))
        base = int(base)
        code_string = get_code_string(base)
        result = 0
        if base == 256:
            def extract(d, cs):
                return d
        else:
            def extract(d, cs):
                return cs.find(d if isinstance(d, str) else chr(d))

        if base == 16:
            string = string.lower()
        while len(string) > 0:
            result *= base
            result += extract(string[0], code_string)
            string = string[1:]
        return result

    def random_string(x):
        return str(os.urandom(x))

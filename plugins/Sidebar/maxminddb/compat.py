import sys

# pylint: skip-file

if sys.version_info[0] == 2:
    import ipaddr as ipaddress  # pylint:disable=F0401
    ipaddress.ip_address = ipaddress.IPAddress

    int_from_byte = ord

    FileNotFoundError = IOError

    def int_from_bytes(b):
        if b:
            return int(b.encode("hex"), 16)
        return 0

    byte_from_int = chr
else:
    import ipaddress  # pylint:disable=F0401

    int_from_byte = lambda x: x

    FileNotFoundError = FileNotFoundError

    int_from_bytes = lambda x: int.from_bytes(x, 'big')

    byte_from_int = lambda x: bytes([x])

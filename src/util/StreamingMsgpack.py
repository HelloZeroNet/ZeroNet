import os
import struct

import msgpack


def msgpackHeader(size):
    if size <= 2 ** 8 - 1:
        return b"\xc4" + struct.pack("B", size)
    elif size <= 2 ** 16 - 1:
        return b"\xc5" + struct.pack(">H", size)
    elif size <= 2 ** 32 - 1:
        return b"\xc6" + struct.pack(">I", size)
    else:
        raise Exception("huge binary string")


def stream(data, writer):
    packer = msgpack.Packer()
    writer(packer.pack_map_header(len(data)))
    for key, val in data.iteritems():
        writer(packer.pack(key))
        if issubclass(type(val), file):  # File obj
            max_size = os.fstat(val.fileno()).st_size - val.tell()
            size = min(max_size, val.read_bytes)
            bytes_left = size
            writer(msgpackHeader(size))
            buff = 1024 * 64
            while 1:
                writer(val.read(min(bytes_left, buff)))
                bytes_left = bytes_left - buff
                if bytes_left <= 0:
                    break
        else:  # Simple
            writer(packer.pack(val))
    return size


class FilePart(file):
    pass

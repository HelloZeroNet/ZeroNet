import os
import struct
import io

import msgpack
import msgpack.fallback


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
    packer = msgpack.Packer(use_bin_type=True)
    writer(packer.pack_map_header(len(data)))
    for key, val in data.items():
        writer(packer.pack(key))
        if isinstance(val, io.IOBase):  # File obj
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


class FilePart(object):
    __slots__ = ("file", "read_bytes", "__class__")

    def __init__(self, *args, **kwargs):
        self.file = open(*args, **kwargs)
        self.__enter__ == self.file.__enter__

    def __getattr__(self, attr):
        return getattr(self.file, attr)

    def __enter__(self, *args, **kwargs):
        return self.file.__enter__(*args, **kwargs)

    def __exit__(self, *args, **kwargs):
        return self.file.__exit__(*args, **kwargs)


# Don't try to decode the value of these fields as utf8
bin_value_keys = ("hashfield_raw", "peers", "peers_ipv6", "peers_onion", "body", "sites", "bin")


def objectDecoderHook(obj):
    global bin_value_keys
    back = {}
    for key, val in obj:
        if type(key) is bytes:
            key = key.decode("utf8")
        if key in bin_value_keys or type(val) is not bytes or len(key) >= 64:
            back[key] = val
        else:
            back[key] = val.decode("utf8")
    return back


def getUnpacker(fallback=False, decode=True):
    if fallback:  # Pure Python
        unpacker = msgpack.fallback.Unpacker
    else:
        unpacker = msgpack.Unpacker

    if decode:  # Workaround for backward compatibility: Try to decode bin to str
        unpacker = unpacker(raw=True, object_pairs_hook=objectDecoderHook, max_buffer_size=5 * 1024 * 1024)
    else:
        unpacker = unpacker(raw=False, max_buffer_size=5 * 1024 * 1024)

    return unpacker


def pack(data, use_bin_type=True):
    return msgpack.packb(data, use_bin_type=use_bin_type)


def unpack(data, decode=True):
    unpacker = getUnpacker(decode=decode)
    unpacker.feed(data)
    return next(unpacker)


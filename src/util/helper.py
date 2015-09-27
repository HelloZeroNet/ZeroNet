import os
import socket
import struct


def atomicWrite(dest, content, mode="w"):
    open(dest + "-new", mode).write(content)
    os.rename(dest, dest + "-old")
    os.rename(dest + "-new", dest)
    os.unlink(dest + "-old")


def shellquote(*args):
    if len(args) == 1:
        return '"%s"' % args[0].replace('"', "")
    else:
        return tuple(['"%s"' % arg.replace('"', "") for arg in args])

# ip, port to packed 6byte format
def packAddress(ip, port):
    return socket.inet_aton(ip) + struct.pack("H", port)

# From 6byte format to ip, port
def unpackAddress(packed):
    return socket.inet_ntoa(packed[0:4]), struct.unpack_from("H", packed, 4)[0]
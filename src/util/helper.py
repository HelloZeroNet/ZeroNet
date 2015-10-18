import os
import socket
import struct
import re


def atomicWrite(dest, content, mode="w"):
    with open(dest + "-new", mode) as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
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


# Get dir from file
# Return: data/site/content.json -> data/site
def getDirname(path):
    file_dir = re.sub("[^/]*?$", "", path).rstrip("/")
    if file_dir:
        file_dir += "/"  # Add / at end if its not the root
    return file_dir


# Get dir from file
# Return: data/site/content.json -> content.json
def getFilename(path):
    return re.sub("^.*/", "", path)

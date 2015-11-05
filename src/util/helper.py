import os
import socket
import struct
import re
import collections
import time


def atomicWrite(dest, content, mode="w"):
    with open(dest + "-new", mode) as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    if os.path.isfile(dest + "-old"):  # Previous incomplete write
        os.rename(dest + "-old", dest + "-old-%s" % time.time())
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


# Convert hash to hashid for hashfield
def toHashId(hash):
    return int(hash[0:4], 16)


# Merge dict values
def mergeDicts(dicts):
    back = collections.defaultdict(set)
    for d in dicts:
        for key, val in d.iteritems():
            back[key].update(val)
    return dict(back)

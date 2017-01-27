import os
import stat
import socket
import struct
import re
import collections
import time
import logging
import base64
import gevent

from Config import config


def atomicWrite(dest, content, mode="w"):
    try:
        with open(dest + "-tmpnew", mode) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if os.path.isfile(dest + "-tmpold"):  # Previous incomplete write
            os.rename(dest + "-tmpold", dest + "-tmpold-%s" % time.time())
        os.rename(dest, dest + "-tmpold")
        os.rename(dest + "-tmpnew", dest)
        os.unlink(dest + "-tmpold")
        return True
    except Exception, err:
        from Debug import Debug
        logging.error(
            "File %s write failed: %s, reverting..." %
            (dest, Debug.formatException(err))
        )
        if os.path.isfile(dest + "-tmpold") and not os.path.isfile(dest):
            os.rename(dest + "-tmpold", dest)
        return False


def openLocked(path, mode="w"):
    if os.name == "posix":
        import fcntl
        f = open(path, mode)
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    elif os.name == "nt":
        import msvcrt
        f = open(path, mode)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, -1)
    else:
        f = open(path, mode)
    return f


def getFreeSpace():
    free_space = -1
    if "statvfs" in dir(os):  # Unix
        statvfs = os.statvfs(config.data_dir.encode("utf8"))
        free_space = statvfs.f_frsize * statvfs.f_bavail
    else:  # Windows
        try:
            import ctypes
            free_space_pointer = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(config.data_dir), None, None, ctypes.pointer(free_space_pointer)
            )
            free_space = free_space_pointer.value
        except Exception, err:
            logging.error("GetFreeSpace error: %s" % err)
    return free_space


def shellquote(*args):
    if len(args) == 1:
        return '"%s"' % args[0].replace('"', "")
    else:
        return tuple(['"%s"' % arg.replace('"', "") for arg in args])


def packPeers(peers):
    packed_peers = {"ip4": [], "onion": []}
    for peer in peers:
        try:
            if peer.ip.endswith(".onion"):
                packed_peers["onion"].append(peer.packMyAddress())
            else:
                packed_peers["ip4"].append(peer.packMyAddress())
        except Exception:
            logging.error("Error packing peer address: %s" % peer)
    return packed_peers


# ip, port to packed 6byte format
def packAddress(ip, port):
    return socket.inet_aton(ip) + struct.pack("H", port)


# From 6byte format to ip, port
def unpackAddress(packed):
    assert len(packed) == 6, "Invalid length ip4 packed address: %s" % len(packed)
    return socket.inet_ntoa(packed[0:4]), struct.unpack_from("H", packed, 4)[0]


# onion, port to packed 12byte format
def packOnionAddress(onion, port):
    onion = onion.replace(".onion", "")
    return base64.b32decode(onion.upper()) + struct.pack("H", port)


# From 12byte format to ip, port
def unpackOnionAddress(packed):
    return base64.b32encode(packed[0:-2]).lower() + ".onion", struct.unpack("H", packed[-2:])[0]


# Get dir from file
# Return: data/site/content.json -> data/site
def getDirname(path):
    if "/" in path:
        return path[:path.rfind("/") + 1]
    else:
        return ""


# Get dir from file
# Return: data/site/content.json -> content.json
def getFilename(path):
    return path[path.rfind("/") + 1:]


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


# Request https url using gevent SSL error workaround
def httpRequest(url, as_file=False):
    if url.startswith("http://"):
        import urllib
        response = urllib.urlopen(url)
    else:  # Hack to avoid Python gevent ssl errors
        import socket
        import httplib
        import ssl

        host, request = re.match("https://(.*?)(/.*?)$", url).groups()

        conn = httplib.HTTPSConnection(host)
        sock = socket.create_connection((conn.host, conn.port), conn.timeout, conn.source_address)
        conn.sock = ssl.wrap_socket(sock, conn.key_file, conn.cert_file)
        conn.request("GET", request)
        response = conn.getresponse()
        if response.status in [301, 302, 303, 307, 308]:
            logging.info("Redirect to: %s" % response.getheader('Location'))
            response = httpRequest(response.getheader('Location'))

    if as_file:
        import cStringIO as StringIO
        data = StringIO.StringIO()
        while True:
            buff = response.read(1024 * 16)
            if not buff:
                break
            data.write(buff)
        return data
    else:
        return response


def timerCaller(secs, func, *args, **kwargs):
    gevent.spawn_later(secs, timerCaller, secs, func, *args, **kwargs)
    func(*args, **kwargs)


def timer(secs, func, *args, **kwargs):
    gevent.spawn_later(secs, timerCaller, secs, func, *args, **kwargs)

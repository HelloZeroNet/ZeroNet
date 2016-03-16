import os
import socket
import struct
import re
import collections
import time
import logging
import base64


def atomicWrite(dest, content, mode="w"):
    try:
        with open(dest + "-new", mode) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if os.path.isfile(dest + "-old"):  # Previous incomplete write
            os.rename(dest + "-old", dest + "-old-%s" % time.time())
        os.rename(dest, dest + "-old")
        os.rename(dest + "-new", dest)
        os.unlink(dest + "-old")
        return True
    except Exception, err:
        from Debug import Debug
        logging.error(
            "File %s write failed: %s, reverting..." %
            (dest, Debug.formatException(err))
        )
        if os.path.isfile(dest + "-old") and not os.path.isfile(dest):
            os.rename(dest + "-old", dest)
        return False


def openLocked(path, mode="w"):
    if os.name == "posix":
        import fcntl
        f = open(path, mode)
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        f = open(path, mode)
    return f


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
        except Exception, err:
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

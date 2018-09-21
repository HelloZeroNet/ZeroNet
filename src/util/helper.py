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


# ip, port to packed 6byte or 18byte format
def packAddress(ip, port):
    if ":" in ip:
        if "::" in ip:
            f_ip, b_ip = ip.split("::")
            num_f = f_ip.count(":")
            num_b = b_ip.count(":")
            num_zerobyte = 6 - num_f - num_b
            addr = range(num_f + num_b + 2)
            if num_f > 0:
                addr[0:num_f+1] = f_ip.split(":",num_f)
            else:
                addr[0]= f_ip
            if num_b > 0:
                addr[num_f+1:num_f+num_b+2] = b_ip.split(":",num_b)
            else:
                addr[num_f+1] = b_ip
            return_pack = ""
            for addr_f in addr[0:num_f+1]:
                return_pack = return_pack + struct.pack("H",int(addr_f,16))
            for addr_zerobyte in range(num_zerobyte):
                return_pack = return_pack + struct.pack("H",0)
            for addr_b in addr[num_f+1 : num_f+num_b+2]:
                return_pack = return_pack + struct.pack("H",int(addr_b,16))
            return_pack = return_pack + struct.pack("H", port)
            return return_pack
        else:
            addr1,addr2,addr3,addr4,addr5,addr6,addr7,addr8 = ip.split(":",7)
            return struct.pack("HHHHHHHH",int(addr1,16),int(addr2,16),int(addr3,16),int(addr4,16),int(addr5,16),int(addr6,16),int(addr7,16),int(addr8,16)) + struct.pack("H", port)
    else:
        return socket.inet_aton(ip) + struct.pack("H", port)


# From 6byte or 18byte format to ip, port
def unpackAddress(packed):
    if len(packed) == 18:
        addr1,addr2,addr3,addr4,addr5,addr6,addr7,addr8,port = struct.unpack("HHHHHHHHH",packed)
        ip6 = hex(addr1)[2:] + ":" + hex(addr2)[2:] + ":" + hex(addr3)[2:] + ":" + hex(addr4)[2:] + ":" + hex(addr5)[2:] + ":" + hex(addr6)[2:] + ":" + hex(addr7)[2:] + ":" + hex(addr8)[2:]
        return ip6, port
    else:
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
# Return: data/site/content.json -> data/site/
def getDirname(path):
    if "/" in path:
        return path[:path.rfind("/") + 1].lstrip("/")
    else:
        return ""


# Get dir from file
# Return: data/site/content.json -> content.json
def getFilename(path):
    return path[path.rfind("/") + 1:]

def getFilesize(path):
    try:
        s = os.stat(path)
    except:
        return None
    if stat.S_ISREG(s.st_mode):  # Test if it's file
        return s.st_size
    else:
        return None

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


def create_connection(address, timeout=None, source_address=None):
    if address in config.ip_local:
        sock = socket.create_connection_original(address, timeout, source_address)
    else:
        sock = socket.create_connection_original(address, timeout, socket.bind_addr)
    return sock

def socketBindMonkeyPatch(bind_ip, bind_port):
    import socket
    logging.info("Monkey patching socket to bind to: %s:%s" % (bind_ip, bind_port))
    socket.bind_addr = (bind_ip, int(bind_port))
    socket.create_connection_original = socket.create_connection
    socket.create_connection = create_connection


def limitedGzipFile(*args, **kwargs):
    import gzip
    class LimitedGzipFile(gzip.GzipFile):
        def read(self, size=-1):
            return super(LimitedGzipFile, self).read(1024*1024*25)
    return LimitedGzipFile(*args, **kwargs)

def avg(items):
    if len(items) > 0:
        return sum(items) / len(items)
    else:
        return 0

local_ip_pattern = re.compile(r"^(127\.)|(192\.168\.)|(10\.)|(172\.1[6-9]\.)|(172\.2[0-9]\.)|(172\.3[0-1]\.)|(::1$)|([fF][cCdD])")
def isPrivateIp(ip):
    return local_ip_pattern.match(ip)

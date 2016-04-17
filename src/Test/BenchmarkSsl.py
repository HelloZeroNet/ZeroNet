#!/usr/bin/python2
from gevent import monkey
monkey.patch_all()
import os
import time
import sys
import socket
import ssl
sys.path.append(os.path.abspath(".."))  # Imports relative to src dir

import cStringIO as StringIO
import gevent

from gevent.server import StreamServer
from gevent.pool import Pool
from Config import config
config.parse()
from util import SslPatch

# Server
socks = []
data = os.urandom(1024 * 100)
data += "\n"


def handle(sock_raw, addr):
    socks.append(sock_raw)
    sock = sock_raw
    # sock = ctx.wrap_socket(sock, server_side=True)
    # if sock_raw.recv( 1, gevent.socket.MSG_PEEK ) == "\x16":
    #   sock = gevent.ssl.wrap_socket(sock_raw, server_side=True, keyfile='key-cz.pem',
    #          certfile='cert-cz.pem', ciphers=ciphers, ssl_version=ssl.PROTOCOL_TLSv1)
    # fp = os.fdopen(sock.fileno(), 'rb', 1024*512)
    try:
        while True:
            line = sock.recv(16 * 1024)
            if not line:
                break
            if line == "bye\n":
                break
            elif line == "gotssl\n":
                sock.sendall("yes\n")
                sock = gevent.ssl.wrap_socket(
                    sock_raw, server_side=True, keyfile='../../data/key-rsa.pem', certfile='../../data/cert-rsa.pem',
                    ciphers=ciphers, ssl_version=ssl.PROTOCOL_TLSv1
                )
            else:
                sock.sendall(data)
    except Exception, err:
        print err
    try:
        sock.shutdown(gevent.socket.SHUT_WR)
        sock.close()
    except:
        pass
    socks.remove(sock_raw)

pool = Pool(1000)  # do not accept more than 10000 connections
server = StreamServer(('127.0.0.1', 1234), handle)
server.start()


# Client


total_num = 0
total_bytes = 0
clipher = None
ciphers = "ECDHE-ECDSA-AES128-GCM-SHA256:ECDH+AES128:ECDHE-RSA-AES128-GCM-SHA256:AES128-GCM-SHA256:AES128-SHA256:AES128-SHA:HIGH:" + \
    "!aNULL:!eNULL:!EXPORT:!DSS:!DES:!RC4:!3DES:!MD5:!PSK"

# ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)


def getData():
    global total_num, total_bytes, clipher
    data = None
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # sock = socket.ssl(s)
    # sock = ssl.wrap_socket(sock)
    sock.connect(("127.0.0.1", 1234))
    # sock.do_handshake()
    # clipher = sock.cipher()
    sock.send("gotssl\n")
    if sock.recv(128) == "yes\n":
        sock = ssl.wrap_socket(sock, ciphers=ciphers, ssl_version=ssl.PROTOCOL_TLSv1)
        sock.do_handshake()
        clipher = sock.cipher()

    for req in range(20):
        sock.sendall("req\n")
        buff = StringIO.StringIO()
        data = sock.recv(16 * 1024)
        buff.write(data)
        if not data:
            break
        while not data.endswith("\n"):
            data = sock.recv(16 * 1024)
            if not data:
                break
            buff.write(data)
        total_num += 1
        total_bytes += buff.tell()
        if not data:
            print "No data"

    sock.shutdown(gevent.socket.SHUT_WR)
    sock.close()

s = time.time()


def info():
    import psutil
    import os
    process = psutil.Process(os.getpid())
    if "memory_info" in dir(process):
        memory_info = process.memory_info
    else:
        memory_info = process.get_memory_info
    while 1:
        print total_num, "req", (total_bytes / 1024), "kbytes", "transfered in", time.time() - s,
        print "using", clipher, "Mem:", memory_info()[0] / float(2 ** 20)
        time.sleep(1)

gevent.spawn(info)

for test in range(1):
    clients = []
    for i in range(500):  # Thread
        clients.append(gevent.spawn(getData))
    gevent.joinall(clients)


print total_num, "req", (total_bytes / 1024), "kbytes", "transfered in", time.time() - s

# Separate client/server process:
# 10*10*100:
# Raw:      10000 req 1000009 kbytes transfered in 5.39999985695
# RSA 2048: 10000 req 1000009 kbytes transfered in 27.7890000343 using ('ECDHE-RSA-AES256-SHA', 'TLSv1/SSLv3', 256)
# ECC:      10000 req 1000009 kbytes transfered in 26.1959998608 using ('ECDHE-ECDSA-AES256-SHA', 'TLSv1/SSLv3', 256)
# ECC:      10000 req 1000009 kbytes transfered in 28.2410001755 using ('ECDHE-ECDSA-AES256-GCM-SHA384', 'TLSv1/SSLv3', 256) Mem: 13.3828125
#
# 10*100*10:
# Raw:      10000 req 1000009 kbytes transfered in 7.02700018883 Mem: 14.328125
# RSA 2048: 10000 req 1000009 kbytes transfered in 44.8860001564 using ('ECDHE-RSA-AES256-GCM-SHA384', 'TLSv1/SSLv3', 256) Mem: 20.078125
# ECC:      10000 req 1000009 kbytes transfered in 37.9430000782 using ('ECDHE-ECDSA-AES256-GCM-SHA384', 'TLSv1/SSLv3', 256) Mem: 20.0234375
#
# 1*100*100:
# Raw:      10000 req 1000009 kbytes transfered in 4.64400005341 Mem: 14.06640625
# RSA:      10000 req 1000009 kbytes transfered in 24.2300000191 using ('ECDHE-RSA-AES256-GCM-SHA384', 'TLSv1/SSLv3', 256) Mem: 19.7734375
# ECC:      10000 req 1000009 kbytes transfered in 22.8849999905 using ('ECDHE-ECDSA-AES256-GCM-SHA384', 'TLSv1/SSLv3', 256) Mem: 17.8125
# AES128:   10000 req 1000009 kbytes transfered in 21.2839999199 using ('AES128-GCM-SHA256', 'TLSv1/SSLv3', 128) Mem: 14.1328125
# ECC+128:  10000 req 1000009 kbytes transfered in 20.496999979  using ('ECDHE-ECDSA-AES128-GCM-SHA256', 'TLSv1/SSLv3', 128) Mem: 14.40234375
#
#
# Single process:
# 1*100*100
# RSA:      10000 req 1000009 kbytes transfered in 41.7899999619 using ('ECDHE-RSA-AES128-GCM-SHA256', 'TLSv1/SSLv3', 128) Mem: 26.91015625
#
# 10*10*100
# RSA:      10000 req 1000009 kbytes transfered in 40.1640000343 using ('ECDHE-RSA-AES128-GCM-SHA256', 'TLSv1/SSLv3', 128) Mem: 14.94921875

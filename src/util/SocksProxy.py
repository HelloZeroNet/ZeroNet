import socket

from lib.PySocks import socks
from Config import config

def create_connection(address, timeout=None, source_address=None):
    if address in config.ip_local:
        sock = socket.socket_noproxy(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(address)
    else:
        sock = socks.socksocket()
        sock.connect(address)
    return sock


# Dns queries using the proxy
def getaddrinfo(*args):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (args[0], args[1]))]


def monkeyPatch(proxy_ip, proxy_port):
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, proxy_ip, int(proxy_port))
    socket.socket_noproxy = socket.socket
    socket.socket = socks.socksocket
    socket.create_connection = create_connection
    socket.getaddrinfo = getaddrinfo

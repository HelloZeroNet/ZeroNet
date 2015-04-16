from lib.PySocks import socks
import socket


def create_connection(address, timeout=None, source_address=None):
	sock = socks.socksocket()
	sock.connect(address)
	return sock


# Dns queries using the proxy
def getaddrinfo(*args):
	return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (args[0], args[1]))]


def monkeyPath(proxy_ip, proxy_port):
	print proxy_ip, proxy_port
	socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, proxy_ip, int(proxy_port))
	socket.socket = socks.socksocket
	socket.create_connection = create_connection
	socket.getaddrinfo = getaddrinfo


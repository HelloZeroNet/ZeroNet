# https://journal.paul.querna.org/articles/2011/04/05/openssl-memory-use/
# Disable SSL compression to save massive memory and cpu

import logging
import os

from Config import config


def openLibrary():
    import ctypes
    import ctypes.util
    try:
        if sys.platform.startswith("win"):
            dll_path = "src/lib/opensslVerify/libeay32.dll"
        elif sys.platform == "cygwin":
            dll_path = "/bin/cygcrypto-1.0.0.dll"
        else:
            dll_path = "/usr/local/ssl/lib/libcrypto.so"
        ssl = ctypes.CDLL(dll_path, ctypes.RTLD_GLOBAL)
        assert ssl
    except:
        dll_path = ctypes.util.find_library('ssl') or ctypes.util.find_library('crypto') or ctypes.util.find_library('libcrypto')
        ssl = ctypes.CDLL(dll_path or 'libeay32', ctypes.RTLD_GLOBAL)
    return ssl


def disableSSLCompression():
    import ctypes
    import ctypes.util
    try:
        openssl = openLibrary()
        openssl.SSL_COMP_get_compression_methods.restype = ctypes.c_void_p
    except Exception, err:
        logging.debug("Disable SSL compression failed: %s (normal on Windows)" % err)
        return False

    openssl.sk_zero.argtypes = [ctypes.c_void_p]
    openssl.sk_zero(openssl.SSL_COMP_get_compression_methods())
    logging.debug("Disabled SSL compression on %s" % openssl)


if config.disable_sslcompression:
    try:
        disableSSLCompression()
    except Exception, err:
        logging.debug("Error disabling SSL compression: %s" % err)


# https://github.com/gevent/gevent/issues/477
# Re-add sslwrap to Python 2.7.9

__ssl__ = __import__('ssl')

try:
    _ssl = __ssl__._ssl
except AttributeError:
    _ssl = __ssl__._ssl2

OldSSLSocket = __ssl__.SSLSocket


class NewSSLSocket(OldSSLSocket):
    # Fix SSLSocket constructor

    def __init__(
            self, sock, keyfile=None, certfile=None, server_side=False,
            cert_reqs=__ssl__.CERT_REQUIRED, ssl_version=2, ca_certs=None,
            do_handshake_on_connect=True, suppress_ragged_eofs=True, ciphers=None,
            server_hostname=None, _context=None
    ):
        OldSSLSocket.__init__(
            self, sock, keyfile=keyfile, certfile=certfile,
            server_side=server_side, cert_reqs=cert_reqs,
            ssl_version=ssl_version, ca_certs=ca_certs,
            do_handshake_on_connect=do_handshake_on_connect,
            suppress_ragged_eofs=suppress_ragged_eofs, ciphers=ciphers
        )


def new_sslwrap(
        sock, server_side=False, keyfile=None, certfile=None,
        cert_reqs=__ssl__.CERT_NONE, ssl_version=__ssl__.PROTOCOL_SSLv23,
        ca_certs=None, ciphers=None
):
    context = __ssl__.SSLContext(ssl_version)
    context.verify_mode = cert_reqs or __ssl__.CERT_NONE
    if ca_certs:
        context.load_verify_locations(ca_certs)
    if certfile:
        context.load_cert_chain(certfile, keyfile)
    if ciphers:
        context.set_ciphers(ciphers)

    caller_self = inspect.currentframe().f_back.f_locals['self']
    return context._wrap_socket(sock, server_side=server_side, ssl_sock=caller_self)


# Re-add sslwrap to Python 2.7.9+
if not hasattr(_ssl, 'sslwrap'):
    import inspect
    _ssl.sslwrap = new_sslwrap
    __ssl__.SSLSocket = NewSSLSocket
    logging.debug("Missing SSLwrap, readded.")


# Add SSLContext to gevent.ssl (Ubuntu 15 fix)
try:
    import gevent
    if not hasattr(gevent.ssl, "SSLContext"):
        gevent.ssl.SSLContext = __ssl__.SSLContext
        logging.debug("Missing SSLContext, readded.")
except Exception, err:
    pass

# Fix PROTOCOL_SSLv3 not defined
if "PROTOCOL_SSLv3" not in dir(__ssl__):
    __ssl__.PROTOCOL_SSLv3 = __ssl__.PROTOCOL_SSLv23
    logging.debug("Redirected PROTOCOL_SSLv3 to PROTOCOL_SSLv23.")

logging.debug("Python SSL version: %s" % __ssl__.OPENSSL_VERSION)

# https://journal.paul.querna.org/articles/2011/04/05/openssl-memory-use/
# Disable SSL compression to save massive memory and cpu

import logging
import os
import sys
import ctypes
import ctypes.util

from Config import config


def getLibraryPath():
    if sys.platform.startswith("win"):
        lib_path = os.path.dirname(os.path.abspath(__file__)) + "/../lib/opensslVerify/libeay32.dll"
    elif sys.platform == "cygwin":
        lib_path = "/bin/cygcrypto-1.0.0.dll"
    elif os.path.isfile("../lib/libcrypto.so"):  # ZeroBundle OSX
        lib_path = "../lib/libcrypto.so"
    elif os.path.isfile("/opt/lib/libcrypto.so.1.0.0"):  # For optware and entware
        lib_path = "/opt/lib/libcrypto.so.1.0.0"
    else:
        lib_path = "/usr/local/ssl/lib/libcrypto.so"

    if os.path.isfile(lib_path):
        return lib_path

    if "ANDROID_APP_PATH" in os.environ:
        try:
            lib_dir = os.environ["ANDROID_APP_PATH"] + "/../../lib"
            return [lib for lib in os.listdir(lib_dir) if "crypto" in lib][0]
        except Exception, err:
            logging.debug("OpenSSL lib not found in: %s (%s)" % (lib_dir, err))

    return (
        ctypes.util.find_library('ssl.so.1.0') or ctypes.util.find_library('ssl') or
        ctypes.util.find_library('crypto') or ctypes.util.find_library('libcrypto') or 'libeay32'
    )


def openLibrary():
    lib_path = getLibraryPath() or "libeay32"
    logging.debug("Opening %s..." % lib_path)
    ssl_lib = ctypes.CDLL(lib_path, ctypes.RTLD_GLOBAL)
    return ssl_lib


def disableSSLCompression():
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
    context = __ssl__.SSLContext(__ssl__.PROTOCOL_SSLv23)
    context.options |= __ssl__.OP_NO_SSLv2
    context.options |= __ssl__.OP_NO_SSLv3
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

# Redirect insecure SSLv2 and v3
__ssl__.PROTOCOL_SSLv2 = __ssl__.PROTOCOL_SSLv3 = __ssl__.PROTOCOL_SSLv23


logging.debug("Python SSL version: %s" % __ssl__.OPENSSL_VERSION)

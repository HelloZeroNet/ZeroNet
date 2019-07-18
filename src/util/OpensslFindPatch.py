import logging
import os
import sys
import ctypes
import ctypes.util


find_library_original = ctypes.util.find_library


def getOpensslPath():
    if sys.platform.startswith("win"):
        lib_path = os.path.join(os.getcwd(), "tools/openssl/libeay32.dll")
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
        except Exception as err:
            logging.debug("OpenSSL lib not found in: %s (%s)" % (lib_dir, err))

    if "LD_LIBRARY_PATH" in os.environ:
        lib_dir_paths = os.environ["LD_LIBRARY_PATH"].split(":")
        for path in lib_dir_paths:
            try:
                return [lib for lib in os.listdir(path) if "libcrypto.so.1.0" in lib][0]
            except Exception as err:
                logging.debug("OpenSSL lib not found in: %s (%s)" % (path, err))

    lib_path = (
        find_library_original('ssl.so.1.0') or find_library_original('ssl') or
        find_library_original('crypto') or find_library_original('libcrypto') or 'libeay32'
    )

    return lib_path


def patchCtypesOpensslFindLibrary():
    def findLibraryPatched(name):
        if name in ("ssl", "crypto", "libeay32"):
            lib_path = getOpensslPath()
            return lib_path
        else:
            return find_library_original(name)

    ctypes.util.find_library = findLibraryPatched


patchCtypesOpensslFindLibrary()


def openLibrary():
    lib_path = getOpensslPath()
    logging.debug("Opening %s..." % lib_path)
    ssl_lib = ctypes.CDLL(lib_path, ctypes.RTLD_GLOBAL)
    return ssl_lib

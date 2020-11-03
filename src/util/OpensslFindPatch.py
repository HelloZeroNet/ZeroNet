import logging
import os
import sys
import ctypes.util

from Config import config

find_library_original = ctypes.util.find_library


def getOpensslPath():
    if config.openssl_lib_file:
        return config.openssl_lib_file

    if sys.platform.startswith("win"):
        lib_paths = [
            os.path.join(os.getcwd(), "tools/openssl/libeay32.dll"),  # ZeroBundle Windows
            os.path.join(os.path.dirname(sys.executable), "DLLs/libcrypto-1_1-x64.dll"),
            os.path.join(os.path.dirname(sys.executable), "DLLs/libcrypto-1_1.dll")
        ]
    elif sys.platform == "cygwin":
        lib_paths = ["/bin/cygcrypto-1.0.0.dll"]
    else:
        lib_paths = [
            "../runtime/lib/libcrypto.so.1.1",  # ZeroBundle Linux
            "../../Frameworks/libcrypto.1.1.dylib",  # ZeroBundle macOS
            "/opt/lib/libcrypto.so.1.0.0",  # For optware and entware
            "/usr/local/ssl/lib/libcrypto.so"
        ]

    for lib_path in lib_paths:
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
                return [lib for lib in os.listdir(path) if "libcrypto.so" in lib][0]
            except Exception as err:
                logging.debug("OpenSSL lib not found in: %s (%s)" % (path, err))

    lib_path = (
        ctypes.util.find_library('ssl.so') or ctypes.util.find_library('ssl') or
        ctypes.util.find_library('crypto') or ctypes.util.find_library('libcrypto') or 'libeay32'
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

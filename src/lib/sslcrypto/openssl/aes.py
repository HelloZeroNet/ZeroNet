import ctypes
import threading
from .._aes import AES
from ..fallback.aes import aes as fallback_aes
from .library import lib, openssl_backend


# Initialize functions
try:
    lib.EVP_CIPHER_CTX_new.restype = ctypes.POINTER(ctypes.c_char)
except AttributeError:
    pass
lib.EVP_get_cipherbyname.restype = ctypes.POINTER(ctypes.c_char)


thread_local = threading.local()


class Context:
    def __init__(self, ptr, do_free):
        self.lib = lib
        self.ptr = ptr
        self.do_free = do_free


    def __del__(self):
        if self.do_free:
            self.lib.EVP_CIPHER_CTX_free(self.ptr)


class AESBackend:
    ALGOS = (
        "aes-128-cbc", "aes-192-cbc", "aes-256-cbc",
        "aes-128-ctr", "aes-192-ctr", "aes-256-ctr",
        "aes-128-cfb", "aes-192-cfb", "aes-256-cfb",
        "aes-128-ofb", "aes-192-ofb", "aes-256-ofb"
    )

    def __init__(self):
        self.is_supported_ctx_new = hasattr(lib, "EVP_CIPHER_CTX_new")
        self.is_supported_ctx_reset = hasattr(lib, "EVP_CIPHER_CTX_reset")


    def _get_ctx(self):
        if not hasattr(thread_local, "ctx"):
            if self.is_supported_ctx_new:
                thread_local.ctx = Context(lib.EVP_CIPHER_CTX_new(), True)
            else:
                # 1 KiB ought to be enough for everybody. We don't know the real
                # size of the context buffer because we are unsure about padding and
                # pointer size
                thread_local.ctx = Context(ctypes.create_string_buffer(1024), False)
        return thread_local.ctx.ptr


    def get_backend(self):
        return openssl_backend


    def _get_cipher(self, algo):
        if algo not in self.ALGOS:
            raise ValueError("Unknown cipher algorithm {}".format(algo))
        cipher = lib.EVP_get_cipherbyname(algo.encode())
        if not cipher:
            raise ValueError("Unknown cipher algorithm {}".format(algo))
        return cipher


    def is_algo_supported(self, algo):
        try:
            self._get_cipher(algo)
            return True
        except ValueError:
            return False


    def random(self, length):
        entropy = ctypes.create_string_buffer(length)
        lib.RAND_bytes(entropy, length)
        return bytes(entropy)


    def encrypt(self, data, key, algo="aes-256-cbc"):
        # Initialize context
        ctx = self._get_ctx()
        if not self.is_supported_ctx_new:
            lib.EVP_CIPHER_CTX_init(ctx)
        try:
            lib.EVP_EncryptInit_ex(ctx, self._get_cipher(algo), None, None, None)

            # Generate random IV
            iv_length = 16
            iv = self.random(iv_length)

            # Set key and IV
            lib.EVP_EncryptInit_ex(ctx, None, None, key, iv)

            # Actually encrypt
            block_size = 16
            output = ctypes.create_string_buffer((len(data) // block_size + 1) * block_size)
            output_len = ctypes.c_int()

            if not lib.EVP_CipherUpdate(ctx, output, ctypes.byref(output_len), data, len(data)):
                raise ValueError("Could not feed cipher with data")

            new_output = ctypes.byref(output, output_len.value)
            output_len2 = ctypes.c_int()
            if not lib.EVP_CipherFinal_ex(ctx, new_output, ctypes.byref(output_len2)):
                raise ValueError("Could not finalize cipher")

            ciphertext = output[:output_len.value + output_len2.value]
            return ciphertext, iv
        finally:
            if self.is_supported_ctx_reset:
                lib.EVP_CIPHER_CTX_reset(ctx)
            else:
                lib.EVP_CIPHER_CTX_cleanup(ctx)


    def decrypt(self, ciphertext, iv, key, algo="aes-256-cbc"):
        # Initialize context
        ctx = self._get_ctx()
        if not self.is_supported_ctx_new:
            lib.EVP_CIPHER_CTX_init(ctx)
        try:
            lib.EVP_DecryptInit_ex(ctx, self._get_cipher(algo), None, None, None)

            # Make sure IV length is correct
            iv_length = 16
            if len(iv) != iv_length:
                raise ValueError("Expected IV to be {} bytes, got {} bytes".format(iv_length, len(iv)))

            # Set key and IV
            lib.EVP_DecryptInit_ex(ctx, None, None, key, iv)

            # Actually decrypt
            output = ctypes.create_string_buffer(len(ciphertext))
            output_len = ctypes.c_int()

            if not lib.EVP_DecryptUpdate(ctx, output, ctypes.byref(output_len), ciphertext, len(ciphertext)):
                raise ValueError("Could not feed decipher with ciphertext")

            new_output = ctypes.byref(output, output_len.value)
            output_len2 = ctypes.c_int()
            if not lib.EVP_DecryptFinal_ex(ctx, new_output, ctypes.byref(output_len2)):
                raise ValueError("Could not finalize decipher")

            return output[:output_len.value + output_len2.value]
        finally:
            if self.is_supported_ctx_reset:
                lib.EVP_CIPHER_CTX_reset(ctx)
            else:
                lib.EVP_CIPHER_CTX_cleanup(ctx)


aes = AES(AESBackend(), fallback_aes)

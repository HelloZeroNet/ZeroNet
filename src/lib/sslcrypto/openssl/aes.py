import ctypes
from .._aes import AES
from ..fallback.aes import aes as fallback_aes
from .library import lib, openssl_backend


# Initialize functions
try:
    lib.EVP_CIPHER_CTX_new.restype = ctypes.POINTER(ctypes.c_char)
except AttributeError:
    pass
lib.EVP_get_cipherbyname.restype = ctypes.POINTER(ctypes.c_char)


class AESBackend:
    ALGOS = (
        "aes-128-cbc", "aes-192-cbc", "aes-256-cbc",
        "aes-128-ctr", "aes-192-ctr", "aes-256-ctr",
        "aes-128-cfb", "aes-192-cfb", "aes-256-cfb",
        "aes-128-ofb", "aes-192-ofb", "aes-256-ofb"
    )

    def __init__(self):
        self.lib = lib  # For finalizer

        self.is_supported_ctx_new = hasattr(lib, "EVP_CIPHER_CTX_new")
        self.is_supported_ctx_reset = hasattr(lib, "EVP_CIPHER_CTX_reset")

        if self.is_supported_ctx_new:
            self.ctx = lib.EVP_CIPHER_CTX_new()
        else:
            # 1 KiB ought to be enough for everybody. We don't know the real
            # size of the context buffer because we are unsure about padding and
            # pointer size
            self.ctx = ctypes.create_string_buffer(1024)


    def get_backend(self):
        return openssl_backend


    def __del__(self):
        if self.is_supported_ctx_new:
            self.lib.EVP_CIPHER_CTX_free(self.ctx)


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
        if not self.is_supported_ctx_new:
            lib.EVP_CIPHER_CTX_init(self.ctx)
        try:
            lib.EVP_EncryptInit_ex(self.ctx, self._get_cipher(algo), None, None, None)

            # Generate random IV
            iv_length = 16
            iv = self.random(iv_length)

            # Set key and IV
            lib.EVP_EncryptInit_ex(self.ctx, None, None, key, iv)

            # Actually encrypt
            block_size = 16
            output = ctypes.create_string_buffer((len(data) // block_size + 1) * block_size)
            output_len = ctypes.c_int()

            if not lib.EVP_CipherUpdate(self.ctx, output, ctypes.byref(output_len), data, len(data)):
                raise ValueError("Could not feed cipher with data")

            new_output = ctypes.byref(output, output_len.value)
            output_len2 = ctypes.c_int()
            if not lib.EVP_CipherFinal_ex(self.ctx, new_output, ctypes.byref(output_len2)):
                raise ValueError("Could not finalize cipher")

            ciphertext = output[:output_len.value + output_len2.value]
            return ciphertext, iv
        finally:
            if self.is_supported_ctx_reset:
                lib.EVP_CIPHER_CTX_reset(self.ctx)
            else:
                lib.EVP_CIPHER_CTX_cleanup(self.ctx)


    def decrypt(self, ciphertext, iv, key, algo="aes-256-cbc"):
        # Initialize context
        if not self.is_supported_ctx_new:
            lib.EVP_CIPHER_CTX_init(self.ctx)
        try:
            lib.EVP_DecryptInit_ex(self.ctx, self._get_cipher(algo), None, None, None)

            # Make sure IV length is correct
            iv_length = 16
            if len(iv) != iv_length:
                raise ValueError("Expected IV to be {} bytes, got {} bytes".format(iv_length, len(iv)))

            # Set key and IV
            lib.EVP_DecryptInit_ex(self.ctx, None, None, key, iv)

            # Actually decrypt
            output = ctypes.create_string_buffer(len(ciphertext))
            output_len = ctypes.c_int()

            if not lib.EVP_DecryptUpdate(self.ctx, output, ctypes.byref(output_len), ciphertext, len(ciphertext)):
                raise ValueError("Could not feed decipher with ciphertext")

            new_output = ctypes.byref(output, output_len.value)
            output_len2 = ctypes.c_int()
            if not lib.EVP_DecryptFinal_ex(self.ctx, new_output, ctypes.byref(output_len2)):
                raise ValueError("Could not finalize decipher")

            return output[:output_len.value + output_len2.value]
        finally:
            if self.is_supported_ctx_reset:
                lib.EVP_CIPHER_CTX_reset(self.ctx)
            else:
                lib.EVP_CIPHER_CTX_cleanup(self.ctx)


aes = AES(AESBackend(), fallback_aes)

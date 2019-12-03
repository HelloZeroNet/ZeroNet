import os
import pyaes
from .._aes import AES


__all__ = ["aes"]

class AESBackend:
    def _get_algo_cipher_type(self, algo):
        if not algo.startswith("aes-") or algo.count("-") != 2:
            raise ValueError("Unknown cipher algorithm {}".format(algo))
        key_length, cipher_type = algo[4:].split("-")
        if key_length not in ("128", "192", "256"):
            raise ValueError("Unknown cipher algorithm {}".format(algo))
        if cipher_type not in ("cbc", "ctr", "cfb", "ofb"):
            raise ValueError("Unknown cipher algorithm {}".format(algo))
        return cipher_type


    def is_algo_supported(self, algo):
        try:
            self._get_algo_cipher_type(algo)
            return True
        except ValueError:
            return False


    def random(self, length):
        return os.urandom(length)


    def encrypt(self, data, key, algo="aes-256-cbc"):
        cipher_type = self._get_algo_cipher_type(algo)

        # Generate random IV
        iv = os.urandom(16)

        if cipher_type == "cbc":
            cipher = pyaes.AESModeOfOperationCBC(key, iv=iv)
        elif cipher_type == "ctr":
            # The IV is actually a counter, not an IV but it does almost the
            # same. Notice: pyaes always uses 1 as initial counter! Make sure
            # not to call pyaes directly.

            # We kinda do two conversions here: from byte array to int here, and
            # from int to byte array in pyaes internals. It's possible to fix that
            # but I didn't notice any performance changes so I'm keeping clean code.
            iv_int = 0
            for byte in iv:
                iv_int = (iv_int * 256) + byte
            counter = pyaes.Counter(iv_int)
            cipher = pyaes.AESModeOfOperationCTR(key, counter=counter)
        elif cipher_type == "cfb":
            # Change segment size from default 8 bytes to 16 bytes for OpenSSL
            # compatibility
            cipher = pyaes.AESModeOfOperationCFB(key, iv, segment_size=16)
        elif cipher_type == "ofb":
            cipher = pyaes.AESModeOfOperationOFB(key, iv)

        encrypter = pyaes.Encrypter(cipher)
        ciphertext = encrypter.feed(data)
        ciphertext += encrypter.feed()
        return ciphertext, iv


    def decrypt(self, ciphertext, iv, key, algo="aes-256-cbc"):
        cipher_type = self._get_algo_cipher_type(algo)

        if cipher_type == "cbc":
            cipher = pyaes.AESModeOfOperationCBC(key, iv=iv)
        elif cipher_type == "ctr":
            # The IV is actually a counter, not an IV but it does almost the
            # same. Notice: pyaes always uses 1 as initial counter! Make sure
            # not to call pyaes directly.

            # We kinda do two conversions here: from byte array to int here, and
            # from int to byte array in pyaes internals. It's possible to fix that
            # but I didn't notice any performance changes so I'm keeping clean code.
            iv_int = 0
            for byte in iv:
                iv_int = (iv_int * 256) + byte
            counter = pyaes.Counter(iv_int)
            cipher = pyaes.AESModeOfOperationCTR(key, counter=counter)
        elif cipher_type == "cfb":
            # Change segment size from default 8 bytes to 16 bytes for OpenSSL
            # compatibility
            cipher = pyaes.AESModeOfOperationCFB(key, iv, segment_size=16)
        elif cipher_type == "ofb":
            cipher = pyaes.AESModeOfOperationOFB(key, iv)

        decrypter = pyaes.Decrypter(cipher)
        data = decrypter.feed(ciphertext)
        data += decrypter.feed()
        return data


    def get_backend(self):
        return "fallback"


aes = AES(AESBackend())

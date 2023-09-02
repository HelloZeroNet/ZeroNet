# pylint: disable=too-few-public-methods

from .library import openssl_backend


class RSA:
    def get_backend(self):
        return openssl_backend


rsa = RSA()

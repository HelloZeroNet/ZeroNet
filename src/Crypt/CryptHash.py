import hashlib
import os
import base64


def sha1sum(file, blocksize=65536):
    if hasattr(file, "endswith"):  # Its a string open it
        file = open(file, "rb")
    hash = hashlib.sha1()
    for block in iter(lambda: file.read(blocksize), ""):
        hash.update(block)
    return hash.hexdigest()


def sha512sum(file, blocksize=65536, format="hexdigest"):
    if hasattr(file, "endswith"):  # Its a string open it
        file = open(file, "rb")
    hash = hashlib.sha512()
    for block in iter(lambda: file.read(blocksize), ""):
        hash.update(block)

    # Truncate to 256bits is good enough
    if format == "hexdigest":
        return hash.hexdigest()[0:64]
    else:
        return hash.digest()[0:32]



def sha256sum(file, blocksize=65536):
    if hasattr(file, "endswith"):  # Its a string open it
        file = open(file, "rb")
    hash = hashlib.sha256()
    for block in iter(lambda: file.read(blocksize), ""):
        hash.update(block)
    return hash.hexdigest()


def random(length=64, encoding="hex"):
    if encoding == "base64":  # Characters: A-Za-z0-9
        hash = hashlib.sha512(os.urandom(256)).digest()
        return base64.standard_b64encode(hash).replace("+", "").replace("/", "").replace("=", "")[0:length]
    else:  # Characters: a-f0-9 (faster)
        return hashlib.sha512(os.urandom(256)).hexdigest()[0:length]


# Sha512 truncated to 256bits
class Sha512t:
    def __init__(self, data):
        if data:
            self.sha512 = hashlib.sha512(data)
        else:
            self.sha512 = hashlib.sha512()

    def hexdigest(self):
        return self.sha512.hexdigest()[0:64]

    def digest(self):
        return self.sha512.digest()[0:32]

    def update(self, data):
        return self.sha512.update(data)


def sha512t(data=None):
    return Sha512t(data)

import hashlib
import os
import base64


def b2sum(file, blocksize=65536, format="hexdigest"):
    if type(file) is str:  # Filename specified
        file = open(file, "rb")
    hash = hashlib.blake2b()
    for block in iter(lambda: file.read(blocksize), b""):
        hash.update(block)

    # Truncate to 256bits is good enough
    if format == "hexdigest":
        return hash.hexdigest()[0:64]

def random(length=64, encoding="hex"):
    if encoding == "base64":  # Characters: A-Za-z0-9
        hash = hashlib.blake2b(os.urandom(256)).digest()
        return base64.b64encode(hash).decode("ascii").replace("+", "").replace("/", "").replace("=", "")[0:length]
    else:  # Characters: a-f0-9 (faster)
        return hashlib.blake2b(os.urandom(256)).hexdigest()[0:length]


# blake2b truncated to 256bits
class Blake2bt:
    def __init__(self, data):
        if data:
            self.blake2b = hashlib.blake2b(data)
        else:
            self.blake2b = hashlib.blake2b()

    def hexdigest(self):
        return self.blake2b.hexdigest()[0:64]

    def update(self, data):
        return self.blake2b.update(data)


def blake2bt(data=None):
    return Blake2bt(data)

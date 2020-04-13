import blake3
import os
import base64


def b3sum(file, blocksize=65536, format="hexdigest"):
    if type(file) is str:  # Filename specified
        file = open(file, "rb")
    hash = blake3.blake3()
    for block in iter(lambda: file.read(blocksize), b""):
        hash.update(block)

    # Truncate to 256bits is good enough
    if format == "hexdigest":
        return hash.hexdigest()[0:64]

def random(length=64, encoding="hex"):
    if encoding == "base64":  # Characters: A-Za-z0-9
        hash = blake3.blake3(os.urandom(256)).digest()
        return base64.b64encode(hash).decode("ascii").replace("+", "").replace("/", "").replace("=", "")[0:length]
    else:  # Characters: a-f0-9 (faster)
        return blake3.blake3(os.urandom(256)).hexdigest()[0:length]


# blake3 truncated to 256bits
class Blake3t:
    def __init__(self, data):
        if data:
            self.blake3 = blake3.blake3(data)
        else:
            self.blake3 = blake3.blake3()

    def hexdigest(self):
        return self.blake3.hexdigest()[0:64]

    def update(self, data):
        return self.blake3.update(data)


def blake3t(data=None):
    return Blake3t(data)

import array


def packPiecefield(data):
    if not isinstance(data, bytes) and not isinstance(data, bytearray):
        raise Exception("Invalid data type: %s" % type(data))

    res = []
    if not data:
        return array.array("H", b"")

    if data[0] == b"\x00":
        res.append(0)
        find = b"\x01"
    else:
        find = b"\x00"
    last_pos = 0
    pos = 0
    while 1:
        pos = data.find(find, pos)
        if find == b"\x00":
            find = b"\x01"
        else:
            find = b"\x00"
        if pos == -1:
            res.append(len(data) - last_pos)
            break
        res.append(pos - last_pos)
        last_pos = pos
    return array.array("H", res)


def unpackPiecefield(data):
    if not data:
        return b""

    res = []
    char = b"\x01"
    for times in data:
        if times > 10000:
            return b""
        res.append(char * times)
        if char == b"\x01":
            char = b"\x00"
        else:
            char = b"\x01"
    return b"".join(res)


def spliceBit(data, idx, bit):
    if bit != b"\x00" and bit != b"\x01":
        raise Exception("Invalid bit: %s" % bit)

    if len(data) < idx:
        data = data.ljust(idx + 1, b"\x00")
    return data[:idx] + bit + data[idx+ 1:]

class Piecefield(object):
    def tostring(self):
        return "".join(["1" if b else "0" for b in self.tobytes()])


class BigfilePiecefield(Piecefield):
    __slots__ = ["data"]

    def __init__(self):
        self.data = b""

    def frombytes(self, s):
        if not isinstance(s, bytes) and not isinstance(s, bytearray):
            raise Exception("Invalid type: %s" % type(s))
        self.data = s

    def tobytes(self):
        return self.data

    def pack(self):
        return packPiecefield(self.data).tobytes()

    def unpack(self, s):
        self.data = unpackPiecefield(array.array("H", s))

    def __getitem__(self, key):
        try:
            return self.data[key]
        except IndexError:
            return False

    def __setitem__(self, key, value):
        self.data = spliceBit(self.data, key, value)

class BigfilePiecefieldPacked(Piecefield):
    __slots__ = ["data"]

    def __init__(self):
        self.data = b""

    def frombytes(self, data):
        if not isinstance(data, bytes) and not isinstance(data, bytearray):
            raise Exception("Invalid type: %s" % type(data))
        self.data = packPiecefield(data).tobytes()

    def tobytes(self):
        return unpackPiecefield(array.array("H", self.data))

    def pack(self):
        return array.array("H", self.data).tobytes()

    def unpack(self, data):
        self.data = data

    def __getitem__(self, key):
        try:
            return self.tobytes()[key]
        except IndexError:
            return False

    def __setitem__(self, key, value):
        data = spliceBit(self.tobytes(), key, value)
        self.frombytes(data)


if __name__ == "__main__":
    import os
    import psutil
    import time
    testdata = b"\x01" * 100 + b"\x00" * 900 + b"\x01" * 4000 + b"\x00" * 4999 + b"\x01"
    meminfo = psutil.Process(os.getpid()).memory_info

    for storage in [BigfilePiecefieldPacked, BigfilePiecefield]:
        print("-- Testing storage: %s --" % storage)
        m = meminfo()[0]
        s = time.time()
        piecefields = {}
        for i in range(10000):
            piecefield = storage()
            piecefield.frombytes(testdata[:i] + b"\x00" + testdata[i + 1:])
            piecefields[i] = piecefield

        print("Create x10000: +%sKB in %.3fs (len: %s)" % ((meminfo()[0] - m) / 1024, time.time() - s, len(piecefields[0].data)))

        m = meminfo()[0]
        s = time.time()
        for piecefield in list(piecefields.values()):
            val = piecefield[1000]

        print("Query one x10000: +%sKB in %.3fs" % ((meminfo()[0] - m) / 1024, time.time() - s))

        m = meminfo()[0]
        s = time.time()
        for piecefield in list(piecefields.values()):
            piecefield[1000] = b"\x01"

        print("Change one x10000: +%sKB in %.3fs" % ((meminfo()[0] - m) / 1024, time.time() - s))

        m = meminfo()[0]
        s = time.time()
        for piecefield in list(piecefields.values()):
            packed = piecefield.pack()

        print("Pack x10000: +%sKB in %.3fs (len: %s)" % ((meminfo()[0] - m) / 1024, time.time() - s, len(packed)))

        m = meminfo()[0]
        s = time.time()
        for piecefield in list(piecefields.values()):
            piecefield.unpack(packed)

        print("Unpack x10000: +%sKB in %.3fs (len: %s)" % ((meminfo()[0] - m) / 1024, time.time() - s, len(piecefields[0].data)))

        piecefields = {}

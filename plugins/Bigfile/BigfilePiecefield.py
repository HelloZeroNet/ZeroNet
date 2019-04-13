import array


def packPiecefield(data):
    assert isinstance(data, bytes) or isinstance(data, bytearray)
    res = []
    if not data:
        return array.array("H", b"")

    if data[0] == b"0":
        res.append(0)
        find = b"1"
    else:
        find = b"0"
    last_pos = 0
    pos = 0
    while 1:
        pos = data.find(find, pos)
        if find == b"0":
            find = b"1"
        else:
            find = b"0"
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
    char = b"1"
    for times in data:
        if times > 10000:
            return b""
        res.append(char * times)
        if char == b"1":
            char = b"0"
        else:
            char = b"1"
    return b"".join(res)


def spliceBit(data, idx, bit):
    if len(data) < idx:
        data = data.ljust(idx + 1, b"0")
    if int(bit) == 0: # bit may be a bool or a single-element bytearray
        b = b"0"
    else:
        b = b"1"
    return data[:idx] + b + data[idx+ 1:]


class BigfilePiecefield(object):
    __slots__ = ["data"]

    def __init__(self):
        self.data = b""

    def fromstring(self, s):
        assert isinstance(s, bytes) or isinstance(s, bytearray)
        self.data = s

    def tostring(self):
        return self.data

    def pack(self):
        return packPiecefield(self.data).tobytes()

    def unpack(self, s):
        self.data = unpackPiecefield(array.array("H", s))

    def __getitem__(self, key):
        try:
            return int(chr(self.data[key]))
        except IndexError:
            return False

    def __setitem__(self, key, value):
        self.data = spliceBit(self.data, key, value)

class BigfilePiecefieldPacked(object):
    __slots__ = ["data"]

    def __init__(self):
        self.data = b""

    def fromstring(self, data):
        assert isinstance(data, bytes) or isinstance(data, bytearray)
        self.data = packPiecefield(data).tobytes()

    def tostring(self):
        return unpackPiecefield(array.array("H", self.data))

    def pack(self):
        return array.array("H", self.data).tobytes()

    def unpack(self, data):
        self.data = data

    def __getitem__(self, key):
        try:
            return int(chr(self.tostring()[key]))
        except IndexError:
            return False

    def __setitem__(self, key, value):
        data = spliceBit(self.tostring(), key, value)
        self.fromstring(data)


if __name__ == "__main__":
    import os
    import psutil
    import time
    testdata = b"1" * 100 + b"0" * 900 + b"1" * 4000 + b"0" * 4999 + b"1"
    meminfo = psutil.Process(os.getpid()).memory_info

    for storage in [BigfilePiecefieldPacked, BigfilePiecefield]:
        print("-- Testing storage: %s --" % storage)
        m = meminfo()[0]
        s = time.time()
        piecefields = {}
        for i in range(10000):
            piecefield = storage()
            piecefield.fromstring(testdata[:i] + b"0" + testdata[i + 1:])
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
            piecefield[1000] = True

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

import array


def packPiecefield(data):
    res = []
    if not data:
        return array.array("H", "")

    if data[0] == "0":
        res.append(0)
        find = "1"
    else:
        find = "0"
    last_pos = 0
    pos = 0
    while 1:
        pos = data.find(find, pos)
        if find == "0":
            find = "1"
        else:
            find = "0"
        if pos == -1:
            res.append(len(data) - last_pos)
            break
        res.append(pos - last_pos)
        last_pos = pos
    return array.array("H", res)


def unpackPiecefield(data):
    if not data:
        return ""

    res = []
    char = "1"
    for times in data:
        if times > 10000:
            return ""
        res.append(char * times)
        if char == "1":
            char = "0"
        else:
            char = "1"
    return "".join(res)


class BigfilePiecefield(object):
    __slots__ = ["data"]

    def __init__(self):
        self.data = ""

    def fromstring(self, s):
        self.data = s

    def tostring(self):
        return self.data

    def pack(self):
        return packPiecefield(self.data).tostring()

    def unpack(self, s):
        self.data = unpackPiecefield(array.array("H", s))

    def __getitem__(self, key):
        try:
            return int(self.data[key])
        except IndexError:
            return False

    def __setitem__(self, key, value):
        data = self.data
        if len(data) < key:
            data = data.ljust(key+1, "0")
        data = data[:key] + str(int(value)) + data[key + 1:]
        self.data = data


class BigfilePiecefieldPacked(object):
    __slots__ = ["data"]

    def __init__(self):
        self.data = ""

    def fromstring(self, data):
        self.data = packPiecefield(data).tostring()

    def tostring(self):
        return unpackPiecefield(array.array("H", self.data))

    def pack(self):
        return array.array("H", self.data).tostring()

    def unpack(self, data):
        self.data = data

    def __getitem__(self, key):
        try:
            return int(self.tostring()[key])
        except IndexError:
            return False

    def __setitem__(self, key, value):
        data = self.tostring()
        if len(data) < key:
            data = data.ljust(key+1, "0")
        data = data[:key] + str(int(value)) + data[key + 1:]
        self.fromstring(data)


if __name__ == "__main__":
    import os
    import psutil
    import time
    testdata = "1" * 100 + "0" * 900 + "1" * 4000 + "0" * 4999 + "1"
    meminfo = psutil.Process(os.getpid()).memory_info

    for storage in [BigfilePiecefieldPacked, BigfilePiecefield]:
        print "-- Testing storage: %s --" % storage
        m = meminfo()[0]
        s = time.time()
        piecefields = {}
        for i in range(10000):
            piecefield = storage()
            piecefield.fromstring(testdata[:i] + "0" + testdata[i + 1:])
            piecefields[i] = piecefield

        print "Create x10000: +%sKB in %.3fs (len: %s)" % ((meminfo()[0] - m) / 1024, time.time() - s, len(piecefields[0].data))

        m = meminfo()[0]
        s = time.time()
        for piecefield in piecefields.values():
            val = piecefield[1000]

        print "Query one x10000: +%sKB in %.3fs" % ((meminfo()[0] - m) / 1024, time.time() - s)

        m = meminfo()[0]
        s = time.time()
        for piecefield in piecefields.values():
            piecefield[1000] = True

        print "Change one x10000: +%sKB in %.3fs" % ((meminfo()[0] - m) / 1024, time.time() - s)

        m = meminfo()[0]
        s = time.time()
        for piecefield in piecefields.values():
            packed = piecefield.pack()

        print "Pack x10000: +%sKB in %.3fs (len: %s)" % ((meminfo()[0] - m) / 1024, time.time() - s, len(packed))

        m = meminfo()[0]
        s = time.time()
        for piecefield in piecefields.values():
            piecefield.unpack(packed)

        print "Unpack x10000: +%sKB in %.3fs (len: %s)" % ((meminfo()[0] - m) / 1024, time.time() - s, len(piecefields[0].data))

        piecefields = {}

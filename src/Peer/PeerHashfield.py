import array
import time


class PeerHashfield(object):
    __slots__ = ("storage", "time_changed", "append", "remove", "tostring", "fromstring", "__len__", "__iter__")
    def __init__(self):
        self.storage = self.createStorage()
        self.time_changed = time.time()

    def createStorage(self):
        storage = array.array("H")
        self.append = storage.append
        self.remove = storage.remove
        self.tostring = storage.tostring
        self.fromstring = storage.fromstring
        self.__len__ = storage.__len__
        self.__iter__ = storage.__iter__
        return storage

    def appendHash(self, hash):
        hash_id = int(hash[0:4], 16)
        if hash_id not in self.storage:
            self.storage.append(hash_id)
            self.time_changed = time.time()
            return True
        else:
            return False

    def appendHashId(self, hash_id):
        if hash_id not in self.storage:
            self.storage.append(hash_id)
            self.time_changed = time.time()
            return True
        else:
            return False

    def removeHash(self, hash):
        hash_id = int(hash[0:4], 16)
        if hash_id in self.storage:
            self.storage.remove(hash_id)
            self.time_changed = time.time()
            return True
        else:
            return False

    def removeHashId(self, hash_id):
        if hash_id in self.storage:
            self.storage.remove(hash_id)
            self.time_changed = time.time()
            return True
        else:
            return False

    def getHashId(self, hash):
        return int(hash[0:4], 16)

    def hasHash(self, hash):
        return int(hash[0:4], 16) in self.storage

    def replaceFromString(self, hashfield_raw):
        self.storage = self.createStorage()
        self.storage.fromstring(hashfield_raw)
        self.time_changed = time.time()

if __name__ == "__main__":
    field = PeerHashfield()
    s = time.time()
    for i in range(10000):
        field.appendHashId(i)
    print time.time()-s
    s = time.time()
    for i in range(10000):
        field.hasHash("AABB")
    print time.time()-s
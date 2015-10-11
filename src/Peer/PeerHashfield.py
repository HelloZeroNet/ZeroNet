import array


class PeerHashfield():
    def __init__(self):
        self.storage = self.createStoreage()

    def createStoreage(self):
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
        if hash_id not in self:
            self.append(hash_id)
            return True
        else:
            return False

    def removeHash(self, hash):
        hash_id = int(hash[0:4], 16)
        if hash_id in self:
            self.remove(hash_id)
            return True
        else:
            return False

    def getHashId(self, hash):
        return int(hash[0:4], 16)

    def hasHash(self, hash):
        return int(hash[0:4], 16) in self

    def replaceFromString(self, hashfield_raw):
        self.storage = self.createStoreage()
        self.fromstring(hashfield_raw)
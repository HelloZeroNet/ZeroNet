import random

class CircularIterator:
    def __init__(self):
        self.successive_count = 0
        self.last_size = 0
        self.index = -1

    def next(self, items):
        self.last_size = len(items)

        if self.last_size == 0:
            return None

        if self.index < 0:
            self.index = random.randint(0, self.last_size)
        else:
            self.index += 1

        self.index = self.index % self.last_size

        self.successive_count += 1

        return items[self.index]

    def resetSuccessiveCount(self):
        self.successive_count = 0

    def getSuccessiveCount(self):
        return self.successive_count

    def isWrapped(self):
        return self.successive_count >= self.last_size


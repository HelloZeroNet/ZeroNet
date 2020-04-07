import bisect
from collections.abc import MutableSequence


class CustomSortedList(MutableSequence):
    def __init__(self):
        super().__init__()
        self.items = []  # (priority, added index, actual value)
        self.logging = False

    def __repr__(self):
        return "<{0} {1}>".format(self.__class__.__name__, self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        if type(index) is int:
            return self.items[index][2]
        else:
            return [item[2] for item in self.items[index]]

    def __delitem__(self, index):
        del self.items[index]

    def __setitem__(self, index, value):
        self.items[index] = self.valueToItem(value)

    def __str__(self):
        return str(self[:])

    def insert(self, index, value):
        self.append(value)

    def append(self, value):
        bisect.insort(self.items, self.valueToItem(value))

    def updateItem(self, value, update_key=None, update_value=None):
        self.remove(value)
        if update_key is not None:
            value[update_key] = update_value
        self.append(value)

    def sort(self, *args, **kwargs):
        raise Exception("Sorted list can't be sorted")

    def valueToItem(self, value):
        return (self.getPriority(value), self.getId(value), value)

    def getPriority(self, value):
        return value

    def getId(self, value):
        return id(value)

    def indexSlow(self, value):
        for pos, item in enumerate(self.items):
            if item[2] == value:
                return pos
        return None

    def index(self, value):
        item = (self.getPriority(value), self.getId(value), value)
        bisect_pos = bisect.bisect(self.items, item) - 1
        if bisect_pos >= 0 and self.items[bisect_pos][2] == value:
            return bisect_pos

        # Item probably changed since added, switch to slow iteration
        pos = self.indexSlow(value)

        if self.logging:
            print("Slow index for %s in pos %s bisect: %s" % (item[2], pos, bisect_pos))

        if pos is None:
            raise ValueError("%r not in list" % value)
        else:
            return pos

    def __contains__(self, value):
        try:
            self.index(value)
            return True
        except ValueError:
            return False


class WorkerTaskManager(CustomSortedList):
    def __init__(self):
        super().__init__()
        self.inner_paths = {}

    def getPriority(self, value):
        return 0 - (value["priority"] - value["workers_num"] * 10)

    def getId(self, value):
        return value["id"]

    def __contains__(self, value):
        return value["inner_path"] in self.inner_paths

    def __delitem__(self, index):
        # Remove from inner path cache
        del self.inner_paths[self.items[index][2]["inner_path"]]
        super().__delitem__(index)

    # Fast task search by inner_path

    def append(self, task):
        if task["inner_path"] in self.inner_paths:
            raise ValueError("File %s already has a task" % task["inner_path"])
        super().append(task)
        # Create inner path cache for faster lookup by filename
        self.inner_paths[task["inner_path"]] = task

    def remove(self, task):
        if task not in self:
            raise ValueError("%r not in list" % task)
        else:
            super().remove(task)

    def findTask(self, inner_path):
        return self.inner_paths.get(inner_path, None)

import pytest

from Worker import WorkerTaskManager
from . import Spy


class TestUiWebsocket:
    def checkSort(self, tasks):  # Check if it has the same order as a list sorted separately
        tasks_list = list(tasks)
        tasks_list.sort(key=lambda task: task["id"])
        assert tasks_list != list(tasks)
        tasks_list.sort(key=lambda task: (0 - (task["priority"] - task["workers_num"] * 10), task["id"]))
        assert tasks_list == list(tasks)

    def testAppendSimple(self):
        tasks = WorkerTaskManager.WorkerTaskManager()
        tasks.append({"id": 1, "priority": 15, "workers_num": 1, "inner_path": "file1.json"})
        tasks.append({"id": 2, "priority": 1, "workers_num": 0, "inner_path": "file2.json"})
        tasks.append({"id": 3, "priority": 8, "workers_num": 0, "inner_path": "file3.json"})
        assert [task["inner_path"] for task in tasks] == ["file3.json", "file1.json", "file2.json"]

        self.checkSort(tasks)

    def testAppendMany(self):
        tasks = WorkerTaskManager.WorkerTaskManager()
        for i in range(1000):
            tasks.append({"id": i, "priority": i % 20, "workers_num": i % 3, "inner_path": "file%s.json" % i})
        assert tasks[0]["inner_path"] == "file39.json"
        assert tasks[-1]["inner_path"] == "file980.json"

        self.checkSort(tasks)

    def testRemove(self):
        tasks = WorkerTaskManager.WorkerTaskManager()
        for i in range(1000):
            tasks.append({"id": i, "priority": i % 20, "workers_num": i % 3, "inner_path": "file%s.json" % i})

        i = 333
        task = {"id": i, "priority": i % 20, "workers_num": i % 3, "inner_path": "file%s.json" % i}
        assert task in tasks

        with Spy.Spy(tasks, "indexSlow") as calls:
            tasks.remove(task)
            assert len(calls) == 0

        assert task not in tasks

        # Remove non existent item
        with Spy.Spy(tasks, "indexSlow") as calls:
            with pytest.raises(ValueError):
                tasks.remove(task)
            assert len(calls) == 0

        self.checkSort(tasks)

    def testRemoveAll(self):
        tasks = WorkerTaskManager.WorkerTaskManager()
        tasks_list = []
        for i in range(1000):
            task = {"id": i, "priority": i % 20, "workers_num": i % 3, "inner_path": "file%s.json" % i}
            tasks.append(task)
            tasks_list.append(task)

        for task in tasks_list:
            tasks.remove(task)

        assert len(tasks.inner_paths) == 0
        assert len(tasks) == 0

    def testModify(self):
        tasks = WorkerTaskManager.WorkerTaskManager()
        for i in range(1000):
            tasks.append({"id": i, "priority": i % 20, "workers_num": i % 3, "inner_path": "file%s.json" % i})

        task = tasks[333]
        task["priority"] += 10

        with pytest.raises(AssertionError):
            self.checkSort(tasks)

        with Spy.Spy(tasks, "indexSlow") as calls:
            tasks.updateItem(task)
            assert len(calls) == 1

        assert task in tasks

        self.checkSort(tasks)

        # Check reorder optimization
        with Spy.Spy(tasks, "indexSlow") as calls:
            tasks.updateItem(task, "priority", task["priority"] + 10)
            assert len(calls) == 0

        with Spy.Spy(tasks, "indexSlow") as calls:
            tasks.updateItem(task, "priority", task["workers_num"] - 1)
            assert len(calls) == 0

        self.checkSort(tasks)

    def testModifySamePriority(self):
        tasks = WorkerTaskManager.WorkerTaskManager()
        for i in range(1000):
            tasks.append({"id": i, "priority": 10, "workers_num": 5, "inner_path": "file%s.json" % i})

        task = tasks[333]

        # Check reorder optimization
        with Spy.Spy(tasks, "indexSlow") as calls:
            tasks.updateItem(task, "priority", task["workers_num"] - 1)
            assert len(calls) == 0

    def testIn(self):
        tasks = WorkerTaskManager.WorkerTaskManager()

        i = 1
        task = {"id": i, "priority": i % 20, "workers_num": i % 3, "inner_path": "file%s.json" % i}

        assert task not in tasks

    def testFindTask(self):
        tasks = WorkerTaskManager.WorkerTaskManager()
        for i in range(1000):
            tasks.append({"id": i, "priority": i % 20, "workers_num": i % 3, "inner_path": "file%s.json" % i})

        assert tasks.findTask("file999.json")
        assert not tasks.findTask("file-unknown.json")
        tasks.remove(tasks.findTask("file999.json"))
        assert not tasks.findTask("file999.json")

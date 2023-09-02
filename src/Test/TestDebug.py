from Debug import Debug
import gevent
import os
import re

import pytest


class TestDebug:
    @pytest.mark.parametrize("items,expected", [
        (["@/src/A/B/C.py:17"], ["A/B/C.py line 17"]),  # basic test
        (["@/src/Db/Db.py:17"], ["Db.py line 17"]),  # path compression
        (["%s:1" % __file__], ["TestDebug.py line 1"]),
        (["@/plugins/Chart/ChartDb.py:100"], ["ChartDb.py line 100"]),  # plugins
        (["@/main.py:17"], ["main.py line 17"]),  # root
        (["@\\src\\Db\\__init__.py:17"], ["Db/__init__.py line 17"]),  # Windows paths
        (["<frozen importlib._bootstrap>:1"], []),  # importlib builtins
        (["<frozen importlib._bootstrap_external>:1"], []),  # importlib builtins
        (["/home/ivanq/ZeroNet/src/main.py:13"], ["?/src/main.py line 13"]),  # best-effort anonymization
        (["C:\\ZeroNet\\core\\src\\main.py:13"], ["?/src/main.py line 13"]),
        (["/root/main.py:17"], ["/root/main.py line 17"]),
        (["{gevent}:13"], ["<gevent>/__init__.py line 13"]),  # modules
        (["{os}:13"], ["<os> line 13"]),  # python builtin modules
        (["src/gevent/event.py:17"], ["<gevent>/event.py line 17"]),  # gevent-overriden __file__
        (["@/src/Db/Db.py:17", "@/src/Db/DbQuery.py:1"], ["Db.py line 17", "DbQuery.py line 1"]),  # mutliple args
        (["@/src/Db/Db.py:17", "@/src/Db/Db.py:1"], ["Db.py line 17", "1"]),  # same file
        (["{os}:1", "@/src/Db/Db.py:17"], ["<os> line 1", "Db.py line 17"]),  # builtins
        (["{gevent}:1"] + ["{os}:3"] * 4 + ["@/src/Db/Db.py:17"], ["<gevent>/__init__.py line 1", "...", "Db.py line 17"])
    ])
    def testFormatTraceback(self, items, expected):
        q_items = []
        for item in items:
            file, line = item.rsplit(":", 1)
            if file.startswith("@"):
                file = Debug.root_dir + file[1:]
            file = file.replace("{os}", os.__file__)
            file = file.replace("{gevent}", gevent.__file__)
            q_items.append((file, int(line)))
        assert Debug.formatTraceback(q_items) == expected

    def testFormatException(self):
        try:
            raise ValueError("Test exception")
        except Exception:
            assert re.match(r"ValueError: Test exception in TestDebug.py line [0-9]+", Debug.formatException())
        try:
            os.path.abspath(1)
        except Exception:
            assert re.search(r"in TestDebug.py line [0-9]+ > <(posixpath|ntpath)> line ", Debug.formatException())

    def testFormatStack(self):
        assert re.match(r"TestDebug.py line [0-9]+ > <_pytest>/python.py line [0-9]+", Debug.formatStack())

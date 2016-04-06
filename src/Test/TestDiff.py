import cStringIO as StringIO

from util import Diff


class TestDiff:
    def testDiff(self):
        assert Diff.diff(
            [],
            ["one", "two", "three"]
        ) == [("+", ["one", "two","three"])]

        assert Diff.diff(
            ["one", "two", "three"],
            ["one", "two", "three", "four", "five"]
        ) == [("=", 11), ("+", ["four", "five"])]

        assert Diff.diff(
            ["one", "two", "three", "six"],
            ["one", "two", "three", "four", "five", "six"]
        ) == [("=", 11), ("+", ["four", "five"]), ("=", 3)]

        assert Diff.diff(
            ["one", "two", "three", "hmm", "six"],
            ["one", "two", "three", "four", "five", "six"]
        ) == [("=", 11), ("-", 3), ("+", ["four", "five"]), ("=", 3)]

        assert Diff.diff(
            ["one", "two", "three"],
            []
        ) == [("-", 11)]

    def testDiffLimit(self):
        old_f = StringIO.StringIO("one\ntwo\nthree\nhmm\nsix")
        new_f = StringIO.StringIO("one\ntwo\nthree\nfour\nfive\nsix")
        actions = Diff.diff(list(old_f), list(new_f), limit=1024)
        assert actions

        old_f = StringIO.StringIO("one\ntwo\nthree\nhmm\nsix")
        new_f = StringIO.StringIO("one\ntwo\nthree\nfour\nfive\nsix"*1024)
        actions = Diff.diff(list(old_f), list(new_f), limit=1024)
        assert actions is False

    def testPatch(self):
        old_f = StringIO.StringIO("one\ntwo\nthree\nhmm\nsix")
        new_f = StringIO.StringIO("one\ntwo\nthree\nfour\nfive\nsix")
        actions = Diff.diff(
            list(old_f),
            list(new_f)
        )
        old_f.seek(0)
        assert Diff.patch(old_f, actions).getvalue() == new_f.getvalue()

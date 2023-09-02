from util import SafeRe

import pytest


class TestSafeRe:
    def testSafeMatch(self):
        assert SafeRe.match(
            "((js|css)/(?!all.(js|css))|data/users/.*db|data/users/.*/.*|data/archived|.*.py)",
            "js/ZeroTalk.coffee"
        )
        assert SafeRe.match(".+/data.json", "data/users/1J3rJ8ecnwH2EPYa6MrgZttBNc61ACFiCj/data.json")

    @pytest.mark.parametrize("pattern", ["([a-zA-Z]+)*", "(a|aa)+*", "(a|a?)+", "(.*a){10}", "((?!json).)*$", r"(\w+\d+)+C"])
    def testUnsafeMatch(self, pattern):
        with pytest.raises(SafeRe.UnsafePatternError) as err:
            SafeRe.match(pattern, "aaaaaaaaaaaaaaaaaaaaaaaa!")
        assert "Potentially unsafe" in str(err.value)

    @pytest.mark.parametrize("pattern", ["^(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)(.*a)$"])
    def testUnsafeRepetition(self, pattern):
        with pytest.raises(SafeRe.UnsafePatternError) as err:
            SafeRe.match(pattern, "aaaaaaaaaaaaaaaaaaaaaaaa!")
        assert "More than" in str(err.value)

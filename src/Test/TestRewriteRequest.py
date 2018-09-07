import pytest
import json
from Ui.RewriteRequest import rewrite_request

class TestRewriteRequest:
    def testRewrite_1(self):
        rewrite_rules = json.loads(
            """
            [
              { "match": "index.html", "terminate": true },
              { "match": "files/.*", "terminate": true },
              { "match": "post/([0-9]+)/([0-9]+)/([0-9]+)(/.*)?", "replace": "post.html", "replace_query_string": "year=$1&month=$2&day=$3", "terminate": true },
              { "match": "(.*)", "replace": "index.html", "replace_query_string": "url=$1", "terminate": true }
            ]
            """
        )

        assert rewrite_request(rewrite_rules, "index.html", "example=true&a=3") == ("index.html", "example=true&a=3")
        assert rewrite_request(rewrite_rules, "files/somefile", "") == ("files/somefile", "")
        assert rewrite_request(rewrite_rules, "otherfile.txt", "a=3") == ("index.html", "url=otherfile.txt")
        assert rewrite_request(rewrite_rules, "post/2018/09/07/post-title", "a=3") == ("post.html", "year=2018&month=09&day=07")


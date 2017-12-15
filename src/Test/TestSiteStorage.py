import pytest


@pytest.mark.usefixtures("resetSettings")
class TestSiteStorage:
    def testWalk(self, site):
        # Rootdir
        walk_root = list(site.storage.walk(""))
        assert "content.json" in walk_root
        assert "css/all.css" in walk_root

        # Subdir
        assert list(site.storage.walk("data-default")) == ["data.json", "users/content-default.json"]

    def testList(self, site):
        # Rootdir
        list_root = list(site.storage.list(""))
        assert "content.json" in list_root
        assert "css/all.css" not in list_root

        # Subdir
        assert set(site.storage.list("data-default")) == set(["data.json", "users"])

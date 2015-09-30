import pytest


@pytest.mark.usefixtures("resetSettings")
class TestSiteStorage:
    def testList(self, site):
        # Rootdir
        list_root = list(site.storage.list(""))
        assert "content.json" in list_root
        assert "css/all.css" in list_root

        # Subdir
        assert list(site.storage.list("data-default")) == ["data.json", "users/content-default.json"]

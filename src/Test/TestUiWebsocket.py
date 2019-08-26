import sys
import pytest

@pytest.mark.usefixtures("resetSettings")
class TestUiWebsocket:
    def testPermission(self, ui_websocket):
        res = ui_websocket.testAction("ping")
        assert res == "pong"

        res = ui_websocket.testAction("certList")
        assert "You don't have permission" in res["error"]

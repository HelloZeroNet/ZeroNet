import pytest

from binascii import unhexlify

@pytest.mark.usefixtures("resetSettings")
class TestMessage:
    def testSend(self, ui_websocket):
        ui_websocket.actionSendBitmessage('BM-2cVuNdpRNKaPmPCroMxrzS14RXbXZhxPrx', "TestMessage", 0)
        result = ui_websocket.ws.result

        assert len(unhexlify(result)) == 32  # random 32 bytes hexencoded

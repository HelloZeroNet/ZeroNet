import cStringIO as StringIO

import pytest

from Connection import ConnectionServer


@pytest.mark.usefixtures("resetSettings")
class TestFileRequest:
    def testGetFile(self, file_server, site):
        file_server.ip_incoming = {}  # Reset flood protection
        client = ConnectionServer("127.0.0.1", 1545)

        connection = client.getConnection("127.0.0.1", 1544)
        file_server.sites[site.address] = site

        response = connection.request("getFile", {"site": site.address, "inner_path": "content.json", "location": 0})
        assert "sign" in response["body"]

        connection.close()
        client.stop()

    def testStreamFile(self, file_server, site):
        file_server.ip_incoming = {}  # Reset flood protection
        client = ConnectionServer("127.0.0.1", 1545)
        connection = client.getConnection("127.0.0.1", 1544)
        file_server.sites[site.address] = site

        buff = StringIO.StringIO()
        response = connection.request("streamFile", {"site": site.address, "inner_path": "content.json", "location": 0}, buff)
        assert "stream_bytes" in response
        assert "sign" in buff.getvalue()

        connection.close()
        client.stop()

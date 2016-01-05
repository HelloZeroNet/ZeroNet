import time
import gevent

import pytest

from Crypt import CryptConnection
from Connection import ConnectionServer


@pytest.mark.usefixtures("resetSettings")
class TestConnection:
    def testSslConnection(self, file_server):
        file_server.ip_incoming = {}  # Reset flood protection
        client = ConnectionServer("127.0.0.1", 1545)
        assert file_server != client

        # Connect to myself
        connection = client.getConnection("127.0.0.1", 1544)
        assert len(file_server.connections) == 1
        assert len(file_server.ips) == 1
        assert connection.handshake
        assert connection.crypt

        # Close connection
        connection.close()
        client.stop()
        time.sleep(0.01)
        assert len(file_server.connections) == 0
        assert len(file_server.ips) == 0

    def testRawConnection(self, file_server):
        file_server.ip_incoming = {}  # Reset flood protection
        client = ConnectionServer("127.0.0.1", 1545)
        assert file_server != client

        # Remove all supported crypto
        crypt_supported_bk = CryptConnection.manager.crypt_supported
        CryptConnection.manager.crypt_supported = []

        connection = client.getConnection("127.0.0.1", 1544)
        assert len(file_server.connections) == 1
        assert not connection.crypt

        # Close connection
        connection.close()
        client.stop()
        time.sleep(0.01)
        assert len(file_server.connections) == 0

        # Reset supported crypts
        CryptConnection.manager.crypt_supported = crypt_supported_bk

    def testPing(self, file_server, site):
        file_server.ip_incoming = {}  # Reset flood protection
        client = ConnectionServer("127.0.0.1", 1545)
        connection = client.getConnection("127.0.0.1", 1544)

        assert connection.ping()

        connection.close()
        client.stop()

    def testGetConnection(self, file_server):
        file_server.ip_incoming = {}  # Reset flood protection
        client = ConnectionServer("127.0.0.1", 1545)
        connection = client.getConnection("127.0.0.1", 1544)

        # Get connection by ip/port
        connection2 = client.getConnection("127.0.0.1", 1544)
        assert connection == connection2

        # Get connection by peerid
        assert not client.getConnection("127.0.0.1", 1544, peer_id="notexists", create=False)
        connection2 = client.getConnection("127.0.0.1", 1544, peer_id=connection.handshake["peer_id"], create=False)
        assert connection2 == connection

        connection.close()
        client.stop()

    def testFloodProtection(self, file_server):
        file_server.ip_incoming = {}  # Reset flood protection
        whitelist = file_server.whitelist  # Save for reset
        file_server.whitelist = []  # Disable 127.0.0.1 whitelist
        client = ConnectionServer("127.0.0.1", 1545)

        # Only allow 6 connection in 1 minute
        for reconnect in range(6):
            connection = client.getConnection("127.0.0.1", 1544)
            assert connection.handshake
            connection.close()

        # The 7. one will timeout
        with pytest.raises(gevent.Timeout):
            with gevent.Timeout(0.1):
                connection = client.getConnection("127.0.0.1", 1544)

        # Reset whitelist
        file_server.whitelist = whitelist

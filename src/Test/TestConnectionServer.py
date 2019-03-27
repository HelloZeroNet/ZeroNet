import time
import socket
import gevent

import pytest
import mock

from Crypt import CryptConnection
from Connection import ConnectionServer
from Config import config


@pytest.mark.usefixtures("resetSettings")
class TestConnection:
    def testIpv6(self, file_server6):
        assert ":" in file_server6.ip

        client = ConnectionServer(file_server6.ip, 1545)
        connection = client.getConnection(file_server6.ip, 1544)

        assert connection.ping()

        # Close connection
        connection.close()
        client.stop()
        time.sleep(0.01)
        assert len(file_server6.connections) == 0

        # Should not able to reach on ipv4 ip
        with pytest.raises(socket.error) as err:
            client = ConnectionServer("127.0.0.1", 1545)
            connection = client.getConnection("127.0.0.1", 1544)

    def testSslConnection(self, file_server):
        client = ConnectionServer(file_server.ip, 1545)
        assert file_server != client

        # Connect to myself
        with mock.patch('Config.config.ip_local', return_value=[]):  # SSL not used for local ips
            connection = client.getConnection(file_server.ip, 1544)

        assert len(file_server.connections) == 1
        assert connection.handshake
        assert connection.crypt


        # Close connection
        connection.close("Test ended")
        client.stop()
        time.sleep(0.01)
        assert len(file_server.connections) == 0
        assert file_server.num_incoming == 2  # One for file_server fixture, one for the test

    def testRawConnection(self, file_server):
        client = ConnectionServer(file_server.ip, 1545)
        assert file_server != client

        # Remove all supported crypto
        crypt_supported_bk = CryptConnection.manager.crypt_supported
        CryptConnection.manager.crypt_supported = []

        with mock.patch('Config.config.ip_local', return_value=[]):  # SSL not used for local ips
            connection = client.getConnection(file_server.ip, 1544)
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
        client = ConnectionServer(file_server.ip, 1545)
        connection = client.getConnection(file_server.ip, 1544)

        assert connection.ping()

        connection.close()
        client.stop()

    def testGetConnection(self, file_server):
        client = ConnectionServer(file_server.ip, 1545)
        connection = client.getConnection(file_server.ip, 1544)

        # Get connection by ip/port
        connection2 = client.getConnection(file_server.ip, 1544)
        assert connection == connection2

        # Get connection by peerid
        assert not client.getConnection(file_server.ip, 1544, peer_id="notexists", create=False)
        connection2 = client.getConnection(file_server.ip, 1544, peer_id=connection.handshake["peer_id"], create=False)
        assert connection2 == connection

        connection.close()
        client.stop()

    def testFloodProtection(self, file_server):
        whitelist = file_server.whitelist  # Save for reset
        file_server.whitelist = []  # Disable 127.0.0.1 whitelist
        client = ConnectionServer(file_server.ip, 1545)

        # Only allow 6 connection in 1 minute
        for reconnect in range(6):
            connection = client.getConnection(file_server.ip, 1544)
            assert connection.handshake
            connection.close()

        # The 7. one will timeout
        with pytest.raises(gevent.Timeout):
            with gevent.Timeout(0.1):
                connection = client.getConnection(file_server.ip, 1544)

        # Reset whitelist
        file_server.whitelist = whitelist

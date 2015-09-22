import time

from Crypt import CryptConnection

class TestConnection:
    def testSslConnection(self, connection_server):
        server = connection_server
        assert server.running

        # Connect to myself
        connection = server.getConnection("127.0.0.1", 1544)
        assert connection.handshake
        assert connection.crypt

        # Close connection
        connection.close()
        time.sleep(0.01)
        assert len(server.connections) == 0

    def testRawConnection(self, connection_server):
        server = connection_server
        crypt_supported_bk = CryptConnection.manager.crypt_supported
        CryptConnection.manager.crypt_supported = []

        connection = server.getConnection("127.0.0.1", 1544)
        assert not connection.crypt

        # Close connection
        connection.close()
        time.sleep(0.01)
        assert len(server.connections) == 0

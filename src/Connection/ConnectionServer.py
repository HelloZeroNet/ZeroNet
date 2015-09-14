import logging
import random
import string
import time
import sys

import gevent
import msgpack
from gevent.server import StreamServer
from gevent.pool import Pool

from Debug import Debug
from Connection import Connection
from Config import config
from Crypt import CryptConnection
from Crypt import CryptHash


class ConnectionServer:
    def __init__(self, ip=None, port=None, request_handler=None):
        self.ip = ip
        self.port = port
        self.last_connection_id = 1  # Connection id incrementer
        self.log = logging.getLogger("ConnServer")
        self.port_opened = None

        self.connections = []  # Connections
        self.ip_incoming = {}  # Incoming connections from ip in the last minute to avoid connection flood
        self.broken_ssl_peer_ids = {}  # Peerids of broken ssl connections
        self.ips = {}  # Connection by ip
        self.peer_ids = {}  # Connections by peer_ids

        self.running = True
        self.thread_checker = gevent.spawn(self.checkConnections)

        self.bytes_recv = 0
        self.bytes_sent = 0

        # Bittorrent style peerid
        self.peer_id = "-ZN0%s-%s" % (config.version.replace(".", ""), CryptHash.random(12, "base64"))

        # Check msgpack version
        if msgpack.version[0] == 0 and msgpack.version[1] < 4:
            self.log.error(
                "Error: Unsupported msgpack version: %s (<0.4.0), please run `sudo pip install msgpack-python --upgrade`" %
                str(msgpack.version)
            )
            sys.exit(0)

        if port:  # Listen server on a port
            self.pool = Pool(1000)  # do not accept more than 1000 connections
            self.stream_server = StreamServer(
                (ip.replace("*", ""), port), self.handleIncomingConnection, spawn=self.pool, backlog=100
            )
            if request_handler:
                self.handleRequest = request_handler

        CryptConnection.manager.loadCerts()

    def start(self):
        self.running = True
        self.log.debug("Binding to: %s:%s, (msgpack: %s), supported crypt: %s" % (
            self.ip, self.port,
            ".".join(map(str, msgpack.version)), CryptConnection.manager.crypt_supported)
        )
        try:
            self.stream_server.serve_forever()  # Start normal connection server
        except Exception, err:
            self.log.info("StreamServer bind error, must be running already: %s" % err)

    def stop(self):
        self.running = False
        self.stream_server.stop()

    def handleIncomingConnection(self, sock, addr):
        ip, port = addr

        # Connection flood protection
        if ip in self.ip_incoming:
            self.ip_incoming[ip] += 1
            if self.ip_incoming[ip] > 3:  # Allow 3 in 1 minute from same ip
                self.log.debug("Connection flood detected from %s" % ip)
                time.sleep(30)
                sock.close()
                return False
        else:
            self.ip_incoming[ip] = 0

        connection = Connection(self, ip, port, sock)
        self.connections.append(connection)
        self.ips[ip] = connection
        connection.handleIncomingConnection(sock)

    def getConnection(self, ip=None, port=None, peer_id=None, create=True):
        if peer_id and peer_id in self.peer_ids:  # Find connection by peer id
            connection = self.peer_ids.get(peer_id)
            if not connection.connected and create:
                succ = connection.event_connected.get()  # Wait for connection
                if not succ:
                    raise Exception("Connection event return error")
            return connection
        # Find connection by ip
        if ip in self.ips:
            connection = self.ips[ip]
            if not connection.connected and create:
                succ = connection.event_connected.get()  # Wait for connection
                if not succ:
                    raise Exception("Connection event return error")
            return connection
        # Recover from connection pool
        for connection in self.connections:
            if connection.ip == ip:
                if not connection.connected and create:
                    succ = connection.event_connected.get()  # Wait for connection
                    if not succ:
                        raise Exception("Connection event return error")
                return connection

        # No connection found
        if create:  # Allow to create new connection if not found
            if port == 0:
                raise Exception("This peer is not connectable")
            try:
                connection = Connection(self, ip, port)
                self.ips[ip] = connection
                self.connections.append(connection)
                succ = connection.connect()
                if not succ:
                    connection.close()
                    raise Exception("Connection event return error")

            except Exception, err:
                self.log.debug("%s Connect error: %s" % (ip, Debug.formatException(err)))
                connection.close()
                raise err
            return connection
        else:
            return None

    def removeConnection(self, connection):
        self.log.debug("Removing %s..." % connection)
        if self.ips.get(connection.ip) == connection:  # Delete if same as in registry
            del self.ips[connection.ip]
        if connection.peer_id and self.peer_ids.get(connection.peer_id) == connection:  # Delete if same as in registry
            del self.peer_ids[connection.peer_id]
        if connection in self.connections:
            self.connections.remove(connection)

    def checkConnections(self):
        while self.running:
            time.sleep(60)  # Sleep 1 min
            self.ip_incoming = {}  # Reset connected ips counter
            self.broken_ssl_peer_ids = {}  # Reset broken ssl peerids count
            for connection in self.connections[:]:  # Make a copy
                idle = time.time() - max(connection.last_recv_time, connection.start_time, connection.last_message_time)

                if connection.unpacker and idle > 30:
                    # Delete the unpacker if not needed
                    del connection.unpacker
                    connection.unpacker = None
                    connection.log("Unpacker deleted")

                if idle > 60 * 60:
                    # Wake up after 1h
                    connection.log("[Cleanup] After wakeup, idle: %s" % idle)
                    connection.close()

                elif idle > 20 * 60 and connection.last_send_time < time.time() - 10:
                    # Idle more than 20 min and we not send request in last 10 sec
                    if not connection.ping():  # send ping request
                        connection.close()

                elif idle > 10 and connection.incomplete_buff_recv > 0:
                    # Incompelte data with more than 10 sec idle
                    connection.log("[Cleanup] Connection buff stalled")
                    connection.close()

                elif idle > 10 and connection.waiting_requests and time.time() - connection.last_send_time > 10:
                    # Sent command and no response in 10 sec
                    connection.log(
                        "[Cleanup] Command %s timeout: %s" % (connection.last_cmd, time.time() - connection.last_send_time)
                    )
                    connection.close()

                elif idle > 60 and connection.protocol == "?":  # No connection after 1 min
                    connection.log("[Cleanup] Connect timeout: %s" % idle)
                    connection.close()

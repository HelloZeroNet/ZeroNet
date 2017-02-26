import logging
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
from Tor import TorManager


class ConnectionServer:
    def __init__(self, ip=None, port=None, request_handler=None):
        self.ip = ip
        self.port = port
        self.last_connection_id = 1  # Connection id incrementer
        self.log = logging.getLogger("ConnServer")
        self.port_opened = None

        if config.tor != "disabled":
            self.tor_manager = TorManager(self.ip, self.port)
        else:
            self.tor_manager = None

        self.connections = []  # Connections
        self.whitelist = config.ip_local  # No flood protection on this ips
        self.ip_incoming = {}  # Incoming connections from ip in the last minute to avoid connection flood
        self.broken_ssl_peer_ids = {}  # Peerids of broken ssl connections
        self.ips = {}  # Connection by ip
        self.has_internet = True  # Internet outage detection

        self.running = True
        self.thread_checker = gevent.spawn(self.checkConnections)

        self.bytes_recv = 0
        self.bytes_sent = 0

        # Bittorrent style peerid
        self.peer_id = "-ZN0%s-%s" % (config.version.replace(".", ""), CryptHash.random(12, "base64"))

        # Check msgpack version
        if msgpack.version[0] == 0 and msgpack.version[1] < 4:
            self.log.error(
                "Error: Unsupported msgpack version: %s (<0.4.0), please run `sudo apt-get install python-pip; sudo pip install msgpack-python --upgrade`" %
                str(msgpack.version)
            )
            sys.exit(0)

        if port:  # Listen server on a port
            self.pool = Pool(1000)  # do not accept more than 1000 connections
            self.stream_server = StreamServer(
                (ip.replace("*", "0.0.0.0"), port), self.handleIncomingConnection, spawn=self.pool, backlog=500
            )
            if request_handler:
                self.handleRequest = request_handler

    def start(self):
        self.running = True
        CryptConnection.manager.loadCerts()
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
        if ip in self.ip_incoming and ip not in self.whitelist:
            self.ip_incoming[ip] += 1
            if self.ip_incoming[ip] > 6:  # Allow 6 in 1 minute from same ip
                self.log.debug("Connection flood detected from %s" % ip)
                time.sleep(30)
                sock.close()
                return False
        else:
            self.ip_incoming[ip] = 1

        connection = Connection(self, ip, port, sock)
        self.connections.append(connection)
        self.ips[ip] = connection
        connection.handleIncomingConnection(sock)

    def getConnection(self, ip=None, port=None, peer_id=None, create=True, site=None):
        if ip.endswith(".onion") and self.tor_manager.start_onions and site:  # Site-unique connection for Tor
            key = ip + site.address
        else:
            key = ip

        # Find connection by ip
        if key in self.ips:
            connection = self.ips[key]
            if not peer_id or connection.handshake.get("peer_id") == peer_id:  # Filter by peer_id
                if not connection.connected and create:
                    succ = connection.event_connected.get()  # Wait for connection
                    if not succ:
                        raise Exception("Connection event return error")
                return connection

            # Recover from connection pool
            for connection in self.connections:
                if connection.ip == ip:
                    if peer_id and connection.handshake.get("peer_id") != peer_id:  # Does not match
                        continue
                    if ip.endswith(".onion") and self.tor_manager.start_onions and connection.site_lock != site.address:
                        # For different site
                        continue
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
                if ip.endswith(".onion") and self.tor_manager.start_onions and site:  # Lock connection to site
                    connection = Connection(self, ip, port, site_lock=site.address)
                else:
                    connection = Connection(self, ip, port)
                self.ips[key] = connection
                self.connections.append(connection)
                succ = connection.connect()
                if not succ:
                    connection.close("Connection event return error")
                    raise Exception("Connection event return error")

            except Exception, err:
                connection.close("%s Connect error: %s" % (ip, Debug.formatException(err)))
                raise err
            return connection
        else:
            return None

    def removeConnection(self, connection):
        # Delete if same as in registry
        if self.ips.get(connection.ip) == connection:
            del self.ips[connection.ip]
        # Site locked connection
        if connection.site_lock and self.ips.get(connection.ip + connection.site_lock) == connection:
            del self.ips[connection.ip + connection.site_lock]
        # Cert pinned connection
        if connection.cert_pin and self.ips.get(connection.ip + "#" + connection.cert_pin) == connection:
            del self.ips[connection.ip + "#" + connection.cert_pin]

        if connection in self.connections:
            self.connections.remove(connection)

    def checkConnections(self):
        run_i = 0
        while self.running:
            run_i += 1
            time.sleep(60)  # Check every minute
            self.ip_incoming = {}  # Reset connected ips counter
            self.broken_ssl_peer_ids = {}  # Reset broken ssl peerids count
            last_message_time = 0
            for connection in self.connections[:]:  # Make a copy
                idle = time.time() - max(connection.last_recv_time, connection.start_time, connection.last_message_time)
                last_message_time = max(last_message_time, connection.last_message_time)

                if connection.unpacker and idle > 30:
                    # Delete the unpacker if not needed
                    del connection.unpacker
                    connection.unpacker = None

                elif connection.last_cmd == "announce" and idle > 20:  # Bootstrapper connection close after 20 sec
                    connection.close("[Cleanup] Tracker connection: %s" % idle)

                if idle > 60 * 60:
                    # Wake up after 1h
                    connection.close("[Cleanup] After wakeup, idle: %s" % idle)

                elif idle > 20 * 60 and connection.last_send_time < time.time() - 10:
                    # Idle more than 20 min and we have not sent request in last 10 sec
                    if not connection.ping():
                        connection.close("[Cleanup] Ping timeout")

                elif idle > 10 and connection.incomplete_buff_recv > 0:
                    # Incomplete data with more than 10 sec idle
                    connection.close("[Cleanup] Connection buff stalled")

                elif idle > 10 and connection.waiting_requests and time.time() - connection.last_send_time > 20:
                    # Sent command and no response in 10 sec
                    connection.close(
                        "[Cleanup] Command %s timeout: %.3fs" % (connection.last_cmd, time.time() - connection.last_send_time)
                    )

                elif idle > 30 and connection.protocol == "?":  # No connection after 30 sec
                    connection.close(
                        "[Cleanup] Connect timeout: %.3fs" % idle
                    )

                elif idle < 60 and connection.bad_actions > 40:
                    connection.close(
                        "[Cleanup] Too many bad actions: %s" % connection.bad_actions
                    )

                elif idle > 5*60 and connection.sites == 0:
                    connection.close(
                        "[Cleanup] No site for connection"
                    )

                elif run_i % 30 == 0:
                    # Reset bad action counter every 30 min
                    connection.bad_actions = 0

            # Internet outage detection
            if time.time() - last_message_time > max(60, 60*10/max(1,float(len(self.connections))/50)):
                # Offline: Last message more than 60-600sec depending on connection number
                if self.has_internet:
                    self.has_internet = False
                    self.onInternetOffline()
            else:
                # Online
                if not self.has_internet:
                    self.has_internet = True
                    self.onInternetOnline()

    def onInternetOnline(self):
        self.log.info("Internet online")

    def onInternetOffline(self):
        self.log.info("Internet offline")

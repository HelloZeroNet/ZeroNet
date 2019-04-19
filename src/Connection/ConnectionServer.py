import logging
import time
import sys
import socket
from collections import defaultdict

import gevent
import msgpack
from gevent.server import StreamServer
from gevent.pool import Pool

import util
from util import helper
from Debug import Debug
from .Connection import Connection
from Config import config
from Crypt import CryptConnection
from Crypt import CryptHash
from Tor import TorManager
from Site import SiteManager


class ConnectionServer(object):
    def __init__(self, ip=None, port=None, request_handler=None):
        if not ip:
            if config.fileserver_ip_type == "ipv6":
                ip = "::1"
            else:
                ip = "127.0.0.1"
            port = 15441
        self.ip = ip
        self.port = port
        self.last_connection_id = 1  # Connection id incrementer
        self.log = logging.getLogger("ConnServer")
        self.port_opened = {}
        self.peer_blacklist = SiteManager.peer_blacklist

        self.tor_manager = TorManager(self.ip, self.port)
        self.connections = []  # Connections
        self.whitelist = config.ip_local  # No flood protection on this ips
        self.ip_incoming = {}  # Incoming connections from ip in the last minute to avoid connection flood
        self.broken_ssl_ips = {}  # Peerids of broken ssl connections
        self.ips = {}  # Connection by ip
        self.has_internet = True  # Internet outage detection

        self.stream_server = None
        self.stream_server_proxy = None
        self.running = False

        self.stat_recv = defaultdict(lambda: defaultdict(int))
        self.stat_sent = defaultdict(lambda: defaultdict(int))
        self.bytes_recv = 0
        self.bytes_sent = 0
        self.num_recv = 0
        self.num_sent = 0

        self.num_incoming = 0
        self.num_outgoing = 0
        self.had_external_incoming = False

        self.timecorrection = 0.0
        self.pool = Pool(500)  # do not accept more than 500 connections

        # Bittorrent style peerid
        self.peer_id = "-UT3530-%s" % CryptHash.random(12, "base64")

        # Check msgpack version
        if msgpack.version[0] == 0 and msgpack.version[1] < 4:
            self.log.error(
                "Error: Unsupported msgpack version: %s (<0.4.0), please run `sudo apt-get install python-pip; sudo pip install msgpack --upgrade`" %
                str(msgpack.version)
            )
            sys.exit(0)

        if request_handler:
            self.handleRequest = request_handler

    def start(self, check_connections=True):
        self.running = True
        if check_connections:
            self.thread_checker = gevent.spawn(self.checkConnections)
        CryptConnection.manager.loadCerts()
        if config.tor != "disable":
            self.tor_manager.start()
        if not self.port:
            self.log.info("No port found, not binding")
            return False

        self.log.debug("Binding to: %s:%s, (msgpack: %s), supported crypt: %s" % (
            self.ip, self.port, ".".join(map(str, msgpack.version)),
            CryptConnection.manager.crypt_supported
        ))
        try:
            self.stream_server = StreamServer(
                (self.ip, self.port), self.handleIncomingConnection, spawn=self.pool, backlog=100
            )
        except Exception as err:
            self.log.info("StreamServer create error: %s" % Debug.formatException(err))

    def listen(self):
        if not self.running:
            return False
        if self.stream_server_proxy:
            gevent.spawn(self.listenProxy)
        try:
            self.stream_server.serve_forever()
        except Exception as err:
            self.log.info("StreamServer listen error: %s" % err)

    def stop(self):
        self.log.debug("Stopping")
        self.running = False
        if self.stream_server:
            self.stream_server.stop()

    def closeConnections(self):
        self.log.debug("Closing all connection: %s" % len(self.connections))
        for connection in self.connections[:]:
            connection.close("Close all connections")

    def handleIncomingConnection(self, sock, addr):
        if config.offline:
            sock.close()
            return False

        ip, port = addr[0:2]
        ip = ip.lower()
        if ip.startswith("::ffff:"):  # IPv6 to IPv4 mapping
            ip = ip.replace("::ffff:", "", 1)
        self.num_incoming += 1

        if not self.had_external_incoming and not helper.isPrivateIp(ip):
            self.had_external_incoming = True

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
        if ip not in config.ip_local:
            self.ips[ip] = connection
        connection.handleIncomingConnection(sock)

    def handleMessage(self, *args, **kwargs):
        pass

    def getConnection(self, ip=None, port=None, peer_id=None, create=True, site=None, is_tracker_connection=False):
        ip_type = helper.getIpType(ip)
        has_per_site_onion = (ip.endswith(".onion") or self.port_opened.get(ip_type, None) == False) and self.tor_manager.start_onions and site
        if has_per_site_onion:  # Site-unique connection for Tor
            if ip.endswith(".onion"):
                site_onion = self.tor_manager.getOnion(site.address)
            else:
                site_onion = self.tor_manager.getOnion("global")
            key = ip + site_onion
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
                    if ip.endswith(".onion") and self.tor_manager.start_onions and ip.replace(".onion", "") != connection.target_onion:
                        # For different site
                        continue
                    if not connection.connected and create:
                        succ = connection.event_connected.get()  # Wait for connection
                        if not succ:
                            raise Exception("Connection event return error")
                    return connection

        # No connection found
        if create and not config.offline:  # Allow to create new connection if not found
            if port == 0:
                raise Exception("This peer is not connectable")

            if (ip, port) in self.peer_blacklist and not is_tracker_connection:
                raise Exception("This peer is blacklisted")

            try:
                if has_per_site_onion:  # Lock connection to site
                    connection = Connection(self, ip, port, target_onion=site_onion, is_tracker_connection=is_tracker_connection)
                else:
                    connection = Connection(self, ip, port, is_tracker_connection=is_tracker_connection)
                self.num_outgoing += 1
                self.ips[key] = connection
                self.connections.append(connection)
                connection.log("Connecting... (site: %s)" % site)
                succ = connection.connect()
                if not succ:
                    connection.close("Connection event return error")
                    raise Exception("Connection event return error")

            except Exception as err:
                connection.close("%s Connect error: %s" % (ip, Debug.formatException(err)))
                raise err

            if len(self.connections) > config.global_connected_limit:
                gevent.spawn(self.checkMaxConnections)

            return connection
        else:
            return None

    def removeConnection(self, connection):
        # Delete if same as in registry
        if self.ips.get(connection.ip) == connection:
            del self.ips[connection.ip]
        # Site locked connection
        if connection.target_onion:
            if self.ips.get(connection.ip + connection.target_onion) == connection:
                del self.ips[connection.ip + connection.target_onion]
        # Cert pinned connection
        if connection.cert_pin and self.ips.get(connection.ip + "#" + connection.cert_pin) == connection:
            del self.ips[connection.ip + "#" + connection.cert_pin]

        if connection in self.connections:
            self.connections.remove(connection)

    def checkConnections(self):
        run_i = 0
        while self.running:
            run_i += 1
            time.sleep(15)  # Check every minute
            self.ip_incoming = {}  # Reset connected ips counter
            last_message_time = 0
            s = time.time()
            for connection in self.connections[:]:  # Make a copy
                if connection.ip.endswith(".onion") or config.tor == "always":
                    timeout_multipler = 2
                else:
                    timeout_multipler = 1

                idle = time.time() - max(connection.last_recv_time, connection.start_time, connection.last_message_time)
                if connection.last_message_time > last_message_time and not connection.is_private_ip:
                    # Message from local IPs does not means internet connection
                    last_message_time = connection.last_message_time

                if connection.unpacker and idle > 30:
                    # Delete the unpacker if not needed
                    del connection.unpacker
                    connection.unpacker = None

                elif connection.last_cmd_sent == "announce" and idle > 20:  # Bootstrapper connection close after 20 sec
                    connection.close("[Cleanup] Tracker connection, idle: %.3fs" % idle)

                if idle > 60 * 60:
                    # Wake up after 1h
                    connection.close("[Cleanup] After wakeup, idle: %.3fs" % idle)

                elif idle > 20 * 60 and connection.last_send_time < time.time() - 10:
                    # Idle more than 20 min and we have not sent request in last 10 sec
                    if not connection.ping():
                        connection.close("[Cleanup] Ping timeout")

                elif idle > 10 * timeout_multipler and connection.incomplete_buff_recv > 0:
                    # Incomplete data with more than 10 sec idle
                    connection.close("[Cleanup] Connection buff stalled")

                elif idle > 10 * timeout_multipler and connection.protocol == "?":  # No connection after 10 sec
                    connection.close(
                        "[Cleanup] Connect timeout: %.3fs" % idle
                    )

                elif idle > 10 * timeout_multipler and connection.waiting_requests and time.time() - connection.last_send_time > 10 * timeout_multipler:
                    # Sent command and no response in 10 sec
                    connection.close(
                        "[Cleanup] Command %s timeout: %.3fs" % (connection.last_cmd_sent, time.time() - connection.last_send_time)
                    )

                elif idle < 60 and connection.bad_actions > 40:
                    connection.close(
                        "[Cleanup] Too many bad actions: %s" % connection.bad_actions
                    )

                elif idle > 5 * 60 and connection.sites == 0:
                    connection.close(
                        "[Cleanup] No site for connection"
                    )

                elif run_i % 90 == 0:
                    # Reset bad action counter every 30 min
                    connection.bad_actions = 0

            # Internet outage detection
            if time.time() - last_message_time > max(60, 60 * 10 / max(1, float(len(self.connections)) / 50)):
                # Offline: Last message more than 60-600sec depending on connection number
                if self.has_internet and last_message_time:
                    self.has_internet = False
                    self.onInternetOffline()
            else:
                # Online
                if not self.has_internet:
                    self.has_internet = True
                    self.onInternetOnline()

            self.timecorrection = self.getTimecorrection()

            if time.time() - s > 0.01:
                self.log.debug("Connection cleanup in %.3fs" % (time.time() - s))
        self.log.debug("Checkconnections ended")

    @util.Noparallel(blocking=False)
    def checkMaxConnections(self):
        if len(self.connections) < config.global_connected_limit:
            return 0

        s = time.time()
        num_connected_before = len(self.connections)
        self.connections.sort(key=lambda connection: connection.sites)
        num_closed = 0
        for connection in self.connections:
            idle = time.time() - max(connection.last_recv_time, connection.start_time, connection.last_message_time)
            if idle > 60:
                connection.close("Connection limit reached")
                num_closed += 1
            if num_closed > config.global_connected_limit * 0.1:
                break

        self.log.debug("Closed %s connections of %s after reached limit %s in %.3fs" % (
            num_closed, num_connected_before, config.global_connected_limit, time.time() - s
        ))
        return num_closed

    def onInternetOnline(self):
        self.log.info("Internet online")

    def onInternetOffline(self):
        self.had_external_incoming = False
        self.log.info("Internet offline")

    def getTimecorrection(self):
        corrections = sorted([
            connection.handshake.get("time") - connection.handshake_time + connection.last_ping_delay
            for connection in self.connections
            if connection.handshake.get("time") and connection.last_ping_delay
        ])
        if len(corrections) < 6:
            return 0.0
        mid = int(len(corrections) / 2 - 1)
        median = (corrections[mid - 1] + corrections[mid] + corrections[mid + 1]) / 3
        return median

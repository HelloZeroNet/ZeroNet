import logging
import re
import time
import sys
import socket
from collections import defaultdict

import gevent
import msgpack
from gevent.server import StreamServer
from gevent.pool import Pool
import gevent.event

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

        self.managed_pools = {}

        self.tor_manager = TorManager(self.ip, self.port)
        self.connections = []  # Connections
        self.whitelist = config.ip_local  # No flood protection on this ips
        self.ip_incoming = {}  # Incoming connections from ip in the last minute to avoid connection flood
        self.broken_ssl_ips = {}  # Peerids of broken ssl connections
        self.ips = {}  # Connection by ip

        self.has_internet = True  # Internet outage detection
        self.internet_online_since = 0
        self.internet_offline_since = 0
        self.last_outgoing_internet_activity_time = 0 # Last time the application tried to send any data
        self.last_successful_internet_activity_time = 0 # Last time the application successfully sent or received any data
        self.internet_outage_threshold = 60 * 2

        self.stream_server = None
        self.stream_server_proxy = None
        self.running = False
        self.stopping = False
        self.stopping_event = gevent.event.Event()
        self.thread_checker = None

        self.thread_pool = Pool(None)
        self.managed_pools["thread"] = self.thread_pool

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
        self.managed_pools["incoming"] = self.pool

        self.outgoing_pool = Pool(None)
        self.managed_pools["outgoing"] = self.outgoing_pool

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
        if self.stopping:
            return False
        self.running = True
        if check_connections:
            self.thread_checker = self.spawn(self.checkConnections)
        CryptConnection.manager.loadCerts()
        if config.tor != "disable":
            self.tor_manager.start()
            self.tor_manager.startOnions()
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
            return None

        if self.stream_server_proxy:
            self.spawn(self.listenProxy)
        try:
            self.stream_server.serve_forever()
        except Exception as err:
            self.log.info("StreamServer listen error: %s" % err)
            return False
        self.log.debug("Stopped.")

    def stop(self, ui_websocket=None):
        self.log.debug("Stopping %s" % self.stream_server)
        self.stopping = True
        self.running = False
        self.stopping_event.set()
        self.onStop(ui_websocket=ui_websocket)

    def onStop(self, ui_websocket=None):
        timeout = 30
        start_time = time.time()
        join_quantum = 0.1
        prev_msg = None
        while True:
            if time.time() >= start_time + timeout:
                break

            total_size = 0
            sizes = {}
            timestep = 0
            for name, pool in list(self.managed_pools.items()):
                timestep += join_quantum
                pool.join(timeout=join_quantum)
                size = len(pool)
                if size:
                    sizes[name] = size
                    total_size += size

            if len(sizes) == 0:
                break

            if timestep < 1:
                time.sleep(1 - timestep)

            # format message
            s = ""
            for name, size in sizes.items():
                s += "%s pool: %s, " % (name, size)
            msg = "Waiting for tasks in managed pools to stop: %s" % s
            # Prevent flooding to log
            if msg != prev_msg:
                prev_msg = msg
                self.log.info("%s", msg)

            percent = 100 * (time.time() - start_time) / timeout
            msg = "File Server: waiting for %s tasks to stop" % total_size
            self.sendShutdownProgress(ui_websocket, msg, percent)

        for name, pool in list(self.managed_pools.items()):
            size = len(pool)
            if size:
                self.log.info("Killing %s tasks in %s pool", size, name)
                pool.kill()

        self.sendShutdownProgress(ui_websocket, "File Server stopped. Now to exit.", 100)

        if self.thread_checker:
            gevent.kill(self.thread_checker)
            self.thread_checker = None
        if self.stream_server:
            self.stream_server.stop()

    def sendShutdownProgress(self, ui_websocket, message, progress):
        if not ui_websocket:
            return
        ui_websocket.cmd("progress", ["shutdown", message, progress])
        time.sleep(0.01)

    # Sleeps the specified amount of time or until ConnectionServer is stopped
    def sleep(self, t):
        if t:
            self.stopping_event.wait(timeout=t)
        else:
            time.sleep(t)

    # Spawns a thread that will be waited for on server being stopped (and killed after a timeout)
    def spawn(self, *args, **kwargs):
        thread = self.thread_pool.spawn(*args, **kwargs)
        return thread

    def closeConnections(self):
        self.log.debug("Closing all connection: %s" % len(self.connections))
        for connection in self.connections[:]:
            connection.close("Close all connections")

    def handleIncomingConnection(self, sock, addr):
        if not self.allowsAcceptingConnections():
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
                self.sleep(30)
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
        ip_type = self.getIpType(ip)
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
        if create and self.allowsCreatingConnections():
            if port == 0:
                raise Exception("This peer is not connectable")

            if (ip, port) in self.peer_blacklist and not is_tracker_connection:
                raise Exception("This peer is blacklisted")

            try:
                #self.log.info("Connection to: %s:%s", ip, port)
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
                #self.log.info("Connection error (%s, %s): %s", ip, port, Debug.formatException(err))
                connection.close("%s Connect error: %s" % (ip, Debug.formatException(err)))
                raise err

            if len(self.connections) > config.global_connected_limit:
                self.spawn(self.checkMaxConnections)

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
        self.sleep(15)
        while self.running:
            run_i += 1
            self.ip_incoming = {}  # Reset connected ips counter
            s = time.time()
            self.updateOnlineStatus(None)
            for connection in self.connections[:]:  # Make a copy
                if connection.ip.endswith(".onion") or config.tor == "always":
                    timeout_multipler = 2
                else:
                    timeout_multipler = 1

                idle = time.time() - max(connection.last_recv_time, connection.start_time, connection.last_message_time)

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

            self.timecorrection = self.getTimecorrection()

            if time.time() - s > 0.01:
                self.log.debug("Connection cleanup in %.3fs" % (time.time() - s))

            self.sleep(15)
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

    # Returns True if we should slow down opening new connections as at the moment
    # there are too many connections being established and not connected completely
    # (not entered the message loop yet).
    def shouldThrottleNewConnections(self):
        threshold = config.simultaneous_connection_throttle_threshold
        if len(self.connections) <= threshold:
            return False
        nr_connections_being_established = 0
        for connection in self.connections[:]:  # Make a copy
            if connection.connecting and not connection.connected and connection.type == "out":
                nr_connections_being_established += 1
                if nr_connections_being_established > threshold:
                    return True
        return False

    # Internet outage detection
    def updateOnlineStatus(self, connection, outgoing_activity=False, successful_activity=False):

        now = time.time()

        if connection and not connection.is_private_ip:
            if outgoing_activity:
                self.last_outgoing_internet_activity_time = now
            if successful_activity:
                self.last_successful_internet_activity_time = now
                self.setInternetStatus(True)
            return

        if not self.last_outgoing_internet_activity_time:
            return

        if (
            (self.last_successful_internet_activity_time < now - self.internet_outage_threshold)
            and
            (self.last_successful_internet_activity_time < self.last_outgoing_internet_activity_time)
        ):
            self.setInternetStatus(False)
            return

        # This is the old algorithm just in case we missed something
        idle = now - self.last_successful_internet_activity_time
        if idle > max(60, 60 * 10 / max(1, float(len(self.connections)) / 50)):
            # Offline: Last successful activity more than 60-600sec depending on connection number
            self.setInternetStatus(False)
            return

    def setInternetStatus(self, status):
        if self.has_internet == status:
            return

        self.has_internet = status

        if self.has_internet:
            self.internet_online_since = time.time()
            self.spawn(self.onInternetOnline)
        else:
            self.internet_offline_since = time.time()
            self.spawn(self.onInternetOffline)

    def isInternetOnline(self):
        return self.has_internet

    def onInternetOnline(self):
        self.log.info("Internet online")

    def onInternetOffline(self):
        self.had_external_incoming = False
        self.log.info("Internet offline")

    def setOfflineMode(self, offline_mode):
        if config.offline == offline_mode:
            return
        config.offline = offline_mode # Yep, awkward
        if offline_mode:
            self.log.info("offline mode is ON")
        else:
            self.log.info("offline mode is OFF")

    def isOfflineMode(self):
        return config.offline

    def allowsCreatingConnections(self):
        if self.isOfflineMode():
            return False
        if self.stopping:
            return False
        return True

    def allowsAcceptingConnections(self):
        if self.isOfflineMode():
            return False
        if self.stopping:
            return False
        return True

    def getTimecorrection(self):
        corrections = sorted([
            connection.handshake.get("time") - connection.handshake_time + connection.last_ping_delay
            for connection in self.connections
            if connection.handshake.get("time") and connection.last_ping_delay
        ])
        if len(corrections) < 9:
            return 0.0
        mid = int(len(corrections) / 2 - 1)
        median = (corrections[mid - 1] + corrections[mid] + corrections[mid + 1]) / 3
        return median


    ############################################################################

    # Methods for handling network address types
    # (ipv4, ipv6, onion etc... more to be implemented by plugins)
    #
    # All the functions handling network address types have "Ip" in the name.
    # So it was in the initial codebase, and I keep the naming, since I couldn't
    # think of a better option.
    # "IP" is short and quite clear and lets you understand that a variable
    # contains a peer address or other transport-level address and not
    # an address of ZeroNet site.
    #

    # Returns type of the given network address.
    # Since: 0.8.0
    # Replaces helper.getIpType() in order to be extensible by plugins.
    def getIpType(self, ip):
        if ip.endswith(".onion"):
            return "onion"
        elif ":" in ip:
            return "ipv6"
        elif re.match(r"[0-9\.]+$", ip):
            return "ipv4"
        else:
            return "unknown"

    # Checks if a network address can be reachable in the current configuration
    # and returs a string describing why it cannot.
    # If the network address can be reachable, returns False.
    # Since: 0.8.0
    def getIpUnreachability(self, ip):
        ip_type = self.getIpType(ip)
        if ip_type == 'onion' and not self.tor_manager.enabled:
            return "Can't connect to onion addresses, no Tor controller present"
        if config.tor == "always" and helper.isPrivateIp(ip) and ip not in config.ip_local:
            return "Can't connect to local IPs in Tor: always mode"
        return False

    # Returns True if ConnctionServer has means for establishing outgoing
    # connections to the given address.
    # Since: 0.8.0
    def isIpReachable(self, ip):
        return self.getIpUnreachability(ip) == False

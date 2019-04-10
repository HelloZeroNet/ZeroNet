import socket
import time

import gevent
try:
    from gevent.coros import RLock
except:
    from gevent.lock import RLock

from Config import config
from Debug import Debug
from util import Msgpack
from Crypt import CryptConnection
from util import helper


class Connection(object):
    __slots__ = (
        "sock", "sock_wrapped", "ip", "port", "cert_pin", "target_onion", "id", "protocol", "type", "server", "unpacker", "unpacker_bytes", "req_id", "ip_type",
        "handshake", "crypt", "connected", "event_connected", "closed", "start_time", "handshake_time", "last_recv_time", "is_private_ip", "is_tracker_connection",
        "last_message_time", "last_send_time", "last_sent_time", "incomplete_buff_recv", "bytes_recv", "bytes_sent", "cpu_time", "send_lock",
        "last_ping_delay", "last_req_time", "last_cmd_sent", "last_cmd_recv", "bad_actions", "sites", "name", "waiting_requests", "waiting_streams"
    )

    def __init__(self, server, ip, port, sock=None, target_onion=None, is_tracker_connection=False):
        self.sock = sock
        self.cert_pin = None
        if "#" in ip:
            ip, self.cert_pin = ip.split("#")
        self.target_onion = target_onion  # Requested onion adress
        self.id = server.last_connection_id
        server.last_connection_id += 1
        self.protocol = "?"
        self.type = "?"
        self.ip_type = "?"
        self.port = int(port)
        self.setIp(ip)

        if helper.isPrivateIp(self.ip) and self.ip not in config.ip_local:
            self.is_private_ip = True
        else:
            self.is_private_ip = False
        self.is_tracker_connection = is_tracker_connection

        self.server = server
        self.unpacker = None  # Stream incoming socket messages here
        self.unpacker_bytes = 0  # How many bytes the unpacker received
        self.req_id = 0  # Last request id
        self.handshake = {}  # Handshake info got from peer
        self.crypt = None  # Connection encryption method
        self.sock_wrapped = False  # Socket wrapped to encryption

        self.connected = False
        self.event_connected = gevent.event.AsyncResult()  # Solves on handshake received
        self.closed = False

        # Stats
        self.start_time = time.time()
        self.handshake_time = 0
        self.last_recv_time = 0
        self.last_message_time = 0
        self.last_send_time = 0
        self.last_sent_time = 0
        self.incomplete_buff_recv = 0
        self.bytes_recv = 0
        self.bytes_sent = 0
        self.last_ping_delay = None
        self.last_req_time = 0
        self.last_cmd_sent = None
        self.last_cmd_recv = None
        self.bad_actions = 0
        self.sites = 0
        self.cpu_time = 0.0
        self.send_lock = RLock()

        self.name = None
        self.updateName()

        self.waiting_requests = {}  # Waiting sent requests
        self.waiting_streams = {}  # Waiting response file streams

    def setIp(self, ip):
        self.ip = ip
        self.ip_type = helper.getIpType(ip)
        self.updateName()

    def createSocket(self):
        if helper.getIpType(self.ip) == "ipv6" and not hasattr(socket, "socket_noproxy"):
            # Create IPv6 connection as IPv4 when using proxy
            return socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            return socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def updateName(self):
        self.name = "Conn#%2s %-12s [%s]" % (self.id, self.ip, self.protocol)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<%s>" % self.__str__()

    def log(self, text):
        self.server.log.debug("%s > %s" % (self.name, text))

    def getValidSites(self):
        return [key for key, val in self.server.tor_manager.site_onions.items() if val == self.target_onion]

    def badAction(self, weight=1):
        self.bad_actions += weight
        if self.bad_actions > 40:
            self.close("Too many bad actions")
        elif self.bad_actions > 20:
            time.sleep(5)

    def goodAction(self):
        self.bad_actions = 0

    # Open connection to peer and wait for handshake
    def connect(self):
        self.type = "out"
        if self.ip_type == "onion":
            if not self.server.tor_manager or not self.server.tor_manager.enabled:
                raise Exception("Can't connect to onion addresses, no Tor controller present")
            self.sock = self.server.tor_manager.createSocket(self.ip, self.port)
        elif config.tor == "always" and helper.isPrivateIp(self.ip) and self.ip not in config.ip_local:
            raise Exception("Can't connect to local IPs in Tor: always mode")
        elif config.trackers_proxy != "disable" and self.is_tracker_connection:
            if config.trackers_proxy == "tor":
                self.sock = self.server.tor_manager.createSocket(self.ip, self.port)
            else:
                from lib.PySocks import socks
                self.sock = socks.socksocket()
                proxy_ip, proxy_port = config.trackers_proxy.split(":")
                self.sock.set_proxy(socks.PROXY_TYPE_SOCKS5, proxy_ip, int(proxy_port))
        else:
            self.sock = self.createSocket()

        if "TCP_NODELAY" in dir(socket):
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        timeout_before = self.sock.gettimeout()
        self.sock.settimeout(30)
        if self.ip_type == "ipv6" and not hasattr(self.sock, "proxy"):
            sock_address = (self.ip, self.port, 1, 1)
        else:
            sock_address = (self.ip, self.port)

        self.sock.connect(sock_address)

        # Implicit SSL
        should_encrypt = not self.ip_type == "onion" and self.ip not in self.server.broken_ssl_ips and self.ip not in config.ip_local
        if self.cert_pin:
            self.sock = CryptConnection.manager.wrapSocket(self.sock, "tls-rsa", cert_pin=self.cert_pin)
            self.sock.do_handshake()
            self.crypt = "tls-rsa"
            self.sock_wrapped = True
        elif should_encrypt and "tls-rsa" in CryptConnection.manager.crypt_supported:
            try:
                self.sock = CryptConnection.manager.wrapSocket(self.sock, "tls-rsa")
                self.sock.do_handshake()
                self.crypt = "tls-rsa"
                self.sock_wrapped = True
            except Exception as err:
                if not config.force_encryption:
                    self.log("Crypt connection error, adding %s:%s as broken ssl. %s" % (self.ip, self.port, Debug.formatException(err)))
                    self.server.broken_ssl_ips[self.ip] = True
                self.sock.close()
                self.crypt = None
                self.sock = self.createSocket()
                self.sock.settimeout(30)
                self.sock.connect(sock_address)

        # Detect protocol
        self.send({"cmd": "handshake", "req_id": 0, "params": self.getHandshakeInfo()})
        event_connected = self.event_connected
        gevent.spawn(self.messageLoop)
        connect_res = event_connected.get()  # Wait for handshake
        self.sock.settimeout(timeout_before)
        return connect_res

    # Handle incoming connection
    def handleIncomingConnection(self, sock):
        self.log("Incoming connection...")

        if "TCP_NODELAY" in dir(socket):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        self.type = "in"
        if self.ip not in config.ip_local:   # Clearnet: Check implicit SSL
            try:
                first_byte = sock.recv(1, gevent.socket.MSG_PEEK)
                if first_byte == b"\x16":
                    self.log("Crypt in connection using implicit SSL")
                    self.sock = CryptConnection.manager.wrapSocket(self.sock, "tls-rsa", True)
                    self.sock_wrapped = True
                    self.crypt = "tls-rsa"
            except Exception as err:
                self.log("Socket peek error: %s" % Debug.formatException(err))
        self.messageLoop()

    def getMsgpackUnpacker(self):
        if self.handshake and self.handshake.get("use_bin_type"):
            return Msgpack.getUnpacker(fallback=True, decode=False)
        else:  # Backward compatibility for <0.7.0
            return Msgpack.getUnpacker(fallback=True, decode=True)

    # Message loop for connection
    def messageLoop(self):
        if not self.sock:
            self.log("Socket error: No socket found")
            return False
        self.protocol = "v2"
        self.updateName()
        self.connected = True
        buff_len = 0
        req_len = 0
        self.unpacker_bytes = 0

        try:
            while not self.closed:
                buff = self.sock.recv(64 * 1024)
                if not buff:
                    break  # Connection closed
                buff_len = len(buff)

                # Statistics
                self.last_recv_time = time.time()
                self.incomplete_buff_recv += 1
                self.bytes_recv += buff_len
                self.server.bytes_recv += buff_len
                req_len += buff_len

                if not self.unpacker:
                    self.unpacker = self.getMsgpackUnpacker()
                    self.unpacker_bytes = 0

                self.unpacker.feed(buff)
                self.unpacker_bytes += buff_len

                while True:
                    try:
                        message = next(self.unpacker)
                    except StopIteration:
                        break
                    if not type(message) is dict:
                        if config.debug_socket:
                            self.log("Invalid message type: %s, content: %r, buffer: %r" % (type(message), message, buff[0:16]))
                        raise Exception("Invalid message type: %s" % type(message))

                    # Stats
                    self.incomplete_buff_recv = 0
                    stat_key = message.get("cmd", "unknown")
                    if stat_key == "response" and "to" in message:
                        cmd_sent = self.waiting_requests.get(message["to"], {"cmd": "unknown"})["cmd"]
                        stat_key = "response: %s" % cmd_sent
                    if stat_key == "update":
                        stat_key = "update: %s" % message["params"]["site"]
                    self.server.stat_recv[stat_key]["bytes"] += req_len
                    self.server.stat_recv[stat_key]["num"] += 1
                    if "stream_bytes" in message:
                        self.server.stat_recv[stat_key]["bytes"] += message["stream_bytes"]
                    req_len = 0

                    # Handle message
                    if "stream_bytes" in message:
                        buff_left = self.handleStream(message, buff)
                        self.unpacker = self.getMsgpackUnpacker()
                        self.unpacker.feed(buff_left)
                        self.unpacker_bytes = len(buff_left)
                        if config.debug_socket:
                            self.log("Start new unpacker with buff_left: %r" % buff_left)
                    else:
                        self.handleMessage(message)

                message = None
        except Exception as err:
            if not self.closed:
                self.log("Socket error: %s" % Debug.formatException(err))
                self.server.stat_recv["error: %s" % err]["bytes"] += req_len
                self.server.stat_recv["error: %s" % err]["num"] += 1
        self.close("MessageLoop ended (closed: %s)" % self.closed)  # MessageLoop ended, close connection

    def getUnpackerUnprocessedBytesNum(self):
        if "tell" in dir(self.unpacker):
            bytes_num = self.unpacker_bytes - self.unpacker.tell()
        else:
            bytes_num = self.unpacker._fb_buf_n - self.unpacker._fb_buf_o
        return bytes_num

    # Stream socket directly to a file
    def handleStream(self, message, buff):
        stream_bytes_left = message["stream_bytes"]
        file = self.waiting_streams[message["to"]]

        unprocessed_bytes_num = self.getUnpackerUnprocessedBytesNum()

        if unprocessed_bytes_num:  # Found stream bytes in unpacker
            unpacker_stream_bytes = min(unprocessed_bytes_num, stream_bytes_left)
            buff_stream_start = len(buff) - unprocessed_bytes_num
            file.write(buff[buff_stream_start:buff_stream_start + unpacker_stream_bytes])
            stream_bytes_left -= unpacker_stream_bytes
        else:
            unpacker_stream_bytes = 0

        if config.debug_socket:
            self.log(
                "Starting stream %s: %s bytes (%s from unpacker, buff size: %s, unprocessed: %s)" %
                (message["to"], message["stream_bytes"], unpacker_stream_bytes, len(buff), unprocessed_bytes_num)
            )

        try:
            while 1:
                if stream_bytes_left <= 0:
                    break
                stream_buff = self.sock.recv(min(64 * 1024, stream_bytes_left))
                if not stream_buff:
                    break
                buff_len = len(stream_buff)
                stream_bytes_left -= buff_len
                file.write(stream_buff)

                # Statistics
                self.last_recv_time = time.time()
                self.incomplete_buff_recv += 1
                self.bytes_recv += buff_len
                self.server.bytes_recv += buff_len
        except Exception as err:
            self.log("Stream read error: %s" % Debug.formatException(err))

        if config.debug_socket:
            self.log("End stream %s, file pos: %s" % (message["to"], file.tell()))

        self.incomplete_buff_recv = 0
        self.waiting_requests[message["to"]]["evt"].set(message)  # Set the response to event
        del self.waiting_streams[message["to"]]
        del self.waiting_requests[message["to"]]

        if unpacker_stream_bytes:
            return buff[buff_stream_start + unpacker_stream_bytes:]
        else:
            return b""

    # My handshake info
    def getHandshakeInfo(self):
        # No TLS for onion connections
        if self.ip_type == "onion":
            crypt_supported = []
        elif self.ip in self.server.broken_ssl_ips:
            crypt_supported = []
        else:
            crypt_supported = CryptConnection.manager.crypt_supported
        # No peer id for onion connections
        if self.ip_type == "onion" or self.ip in config.ip_local:
            peer_id = ""
        else:
            peer_id = self.server.peer_id
        # Setup peer lock from requested onion address
        if self.handshake and self.handshake.get("target_ip", "").endswith(".onion") and self.server.tor_manager.start_onions:
            self.target_onion = self.handshake.get("target_ip").replace(".onion", "")  # My onion address
            if not self.server.tor_manager.site_onions.values():
                self.server.log.warning("Unknown target onion address: %s" % self.target_onion)

        handshake = {
            "version": config.version,
            "protocol": "v2",
            "use_bin_type": True,
            "peer_id": peer_id,
            "fileserver_port": self.server.port,
            "port_opened": self.server.port_opened.get(self.ip_type, None),
            "target_ip": self.ip,
            "rev": config.rev,
            "crypt_supported": crypt_supported,
            "crypt": self.crypt,
            "time": int(time.time())
        }
        if self.target_onion:
            handshake["onion"] = self.target_onion
        elif self.ip_type == "onion":
            handshake["onion"] = self.server.tor_manager.getOnion("global")

        if self.is_tracker_connection:
            handshake["tracker_connection"] = True

        if config.debug_socket:
            self.log("My Handshake: %s" % handshake)

        return handshake

    def setHandshake(self, handshake):
        if config.debug_socket:
            self.log("Remote Handshake: %s" % handshake)

        if handshake.get("peer_id") == self.server.peer_id and not handshake.get("tracker_connection") and not self.is_tracker_connection:
            self.close("Same peer id, can't connect to myself")
            self.server.peer_blacklist.append((handshake["target_ip"], handshake["fileserver_port"]))
            return False

        self.handshake = handshake
        if handshake.get("port_opened", None) is False and "onion" not in handshake and not self.is_private_ip:  # Not connectable
            self.port = 0
        else:
            self.port = int(handshake["fileserver_port"])  # Set peer fileserver port

        if handshake.get("use_bin_type") and self.unpacker:
            unprocessed_bytes_num = self.getUnpackerUnprocessedBytesNum()
            self.log("Changing unpacker to bin type (unprocessed bytes: %s)" % unprocessed_bytes_num)
            unprocessed_bytes = self.unpacker.read_bytes(unprocessed_bytes_num)
            self.unpacker = self.getMsgpackUnpacker()  # Create new unpacker for different msgpack type
            self.unpacker_bytes = 0
            if unprocessed_bytes:
                self.unpacker.feed(unprocessed_bytes)

        # Check if we can encrypt the connection
        if handshake.get("crypt_supported") and self.ip not in self.server.broken_ssl_ips:
            if type(handshake["crypt_supported"][0]) is bytes:
                handshake["crypt_supported"] = [item.decode() for item in handshake["crypt_supported"]]  # Backward compatibility

            if self.ip_type == "onion" or self.ip in config.ip_local:
                crypt = None
            elif handshake.get("crypt"):  # Recommended crypt by server
                crypt = handshake["crypt"]
            else:  # Select the best supported on both sides
                crypt = CryptConnection.manager.selectCrypt(handshake["crypt_supported"])

            if crypt:
                self.crypt = crypt

        if self.type == "in" and handshake.get("onion") and not self.ip_type == "onion":  # Set incoming connection's onion address
            if self.server.ips.get(self.ip) == self:
                del self.server.ips[self.ip]
            self.setIp(handshake["onion"] + ".onion")
            self.log("Changing ip to %s" % self.ip)
            self.server.ips[self.ip] = self
            self.updateName()

        self.event_connected.set(True)  # Mark handshake as done
        self.event_connected = None
        self.handshake_time = time.time()

    # Handle incoming message
    def handleMessage(self, message):
        cmd = message["cmd"]

        self.last_message_time = time.time()
        self.last_cmd_recv = cmd
        if cmd == "response":  # New style response
            if message["to"] in self.waiting_requests:
                if self.last_send_time and len(self.waiting_requests) == 1:
                    ping = time.time() - self.last_send_time
                    self.last_ping_delay = ping
                self.waiting_requests[message["to"]]["evt"].set(message)  # Set the response to event
                del self.waiting_requests[message["to"]]
            elif message["to"] == 0:  # Other peers handshake
                ping = time.time() - self.start_time
                if config.debug_socket:
                    self.log("Handshake response: %s, ping: %s" % (message, ping))
                self.last_ping_delay = ping
                # Server switched to crypt, lets do it also if not crypted already
                if message.get("crypt") and not self.sock_wrapped:
                    self.crypt = message["crypt"]
                    server = (self.type == "in")
                    self.log("Crypt out connection using: %s (server side: %s, ping: %.3fs)..." % (self.crypt, server, ping))
                    self.sock = CryptConnection.manager.wrapSocket(self.sock, self.crypt, server, cert_pin=self.cert_pin)
                    self.sock.do_handshake()
                    self.sock_wrapped = True

                if not self.sock_wrapped and self.cert_pin:
                    self.close("Crypt connection error: Socket not encrypted, but certificate pin present")
                    return

                self.setHandshake(message)
            else:
                self.log("Unknown response: %s" % message)
        elif cmd:
            self.server.num_recv += 1
            if cmd == "handshake":
                self.handleHandshake(message)
            else:
                self.server.handleRequest(self, message)

    # Incoming handshake set request
    def handleHandshake(self, message):
        self.setHandshake(message["params"])
        data = self.getHandshakeInfo()
        data["cmd"] = "response"
        data["to"] = message["req_id"]
        self.send(data)  # Send response to handshake
        # Sent crypt request to client
        if self.crypt and not self.sock_wrapped:
            server = (self.type == "in")
            self.log("Crypt in connection using: %s (server side: %s)..." % (self.crypt, server))
            try:
                self.sock = CryptConnection.manager.wrapSocket(self.sock, self.crypt, server, cert_pin=self.cert_pin)
                self.sock_wrapped = True
            except Exception as err:
                if not config.force_encryption:
                    self.log("Crypt connection error, adding %s:%s as broken ssl. %s" % (self.ip, self.port, Debug.formatException(err)))
                    self.server.broken_ssl_ips[self.ip] = True
                self.close("Broken ssl")

        if not self.sock_wrapped and self.cert_pin:
            self.close("Crypt connection error: Socket not encrypted, but certificate pin present")

    # Send data to connection
    def send(self, message, streaming=False):
        self.last_send_time = time.time()
        if config.debug_socket:
            self.log("Send: %s, to: %s, streaming: %s, site: %s, inner_path: %s, req_id: %s" % (
                message.get("cmd"), message.get("to"), streaming,
                message.get("params", {}).get("site"), message.get("params", {}).get("inner_path"),
                message.get("req_id"))
            )

        if not self.sock:
            self.log("Send error: missing socket")
            return False

        if not self.connected and message.get("cmd") != "handshake":
            self.log("Wait for handshake before send request")
            self.event_connected.get()

        try:
            stat_key = message.get("cmd", "unknown")
            if stat_key == "response":
                stat_key = "response: %s" % self.last_cmd_recv
            else:
                self.server.num_sent += 1

            self.server.stat_sent[stat_key]["num"] += 1
            if streaming:
                with self.send_lock:
                    bytes_sent = Msgpack.stream(message, self.sock.sendall)
                self.bytes_sent += bytes_sent
                self.server.bytes_sent += bytes_sent
                self.server.stat_sent[stat_key]["bytes"] += bytes_sent
                message = None
            else:
                data = Msgpack.pack(message)
                self.bytes_sent += len(data)
                self.server.bytes_sent += len(data)
                self.server.stat_sent[stat_key]["bytes"] += len(data)
                message = None
                with self.send_lock:
                    self.sock.sendall(data)
        except Exception as err:
            self.close("Send error: %s (cmd: %s)" % (err, stat_key))
            return False
        self.last_sent_time = time.time()
        return True

    # Stream file to connection without msgpacking
    def sendRawfile(self, file, read_bytes):
        buff = 64 * 1024
        bytes_left = read_bytes
        bytes_sent = 0
        while True:
            self.last_send_time = time.time()
            data = file.read(min(bytes_left, buff))
            bytes_sent += len(data)
            with self.send_lock:
                self.sock.sendall(data)
            bytes_left -= buff
            if bytes_left <= 0:
                break
        self.bytes_sent += bytes_sent
        self.server.bytes_sent += bytes_sent
        self.server.stat_sent["raw_file"]["num"] += 1
        self.server.stat_sent["raw_file"]["bytes"] += bytes_sent
        return True

    # Create and send a request to peer
    def request(self, cmd, params={}, stream_to=None):
        # Last command sent more than 10 sec ago, timeout
        if self.waiting_requests and self.protocol == "v2" and time.time() - max(self.last_req_time, self.last_recv_time) > 10:
            self.close("Request %s timeout: %.3fs" % (self.last_cmd_sent, time.time() - self.last_send_time))
            return False

        self.last_req_time = time.time()
        self.last_cmd_sent = cmd
        self.req_id += 1
        data = {"cmd": cmd, "req_id": self.req_id, "params": params}
        event = gevent.event.AsyncResult()  # Create new event for response
        self.waiting_requests[self.req_id] = {"evt": event, "cmd": cmd}
        if stream_to:
            self.waiting_streams[self.req_id] = stream_to
        self.send(data)  # Send request
        res = event.get()  # Wait until event solves
        return res

    def ping(self):
        s = time.time()
        response = None
        with gevent.Timeout(10.0, False):
            try:
                response = self.request("ping")
            except Exception as err:
                self.log("Ping error: %s" % Debug.formatException(err))
        if response and "body" in response and response["body"] == b"Pong!":
            self.last_ping_delay = time.time() - s
            return True
        else:
            return False

    # Close connection
    def close(self, reason="Unknown"):
        if self.closed:
            return False  # Already closed
        self.closed = True
        self.connected = False
        if self.event_connected:
            self.event_connected.set(False)

        self.log(
            "Closing connection: %s, waiting_requests: %s, sites: %s, buff: %s..." %
            (reason, len(self.waiting_requests), self.sites, self.incomplete_buff_recv)
        )
        for request in self.waiting_requests.values():  # Mark pending requests failed
            request["evt"].set(False)
        self.waiting_requests = {}
        self.waiting_streams = {}
        self.sites = 0
        self.server.removeConnection(self)  # Remove connection from server registry
        try:
            if self.sock:
                self.sock.shutdown(gevent.socket.SHUT_WR)
                self.sock.close()
        except Exception as err:
            if config.debug_socket:
                self.log("Close error: %s" % err)

        # Little cleanup
        self.sock = None
        self.unpacker = None
        self.event_connected = None

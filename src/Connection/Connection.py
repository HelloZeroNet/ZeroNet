import socket
import time

import gevent
import msgpack

from Config import config
from Debug import Debug
from util import StreamingMsgpack
from Crypt import CryptConnection


class Connection(object):
    __slots__ = (
        "sock", "sock_wrapped", "ip", "port", "peer_id", "id", "protocol", "type", "server", "unpacker", "req_id",
        "handshake", "crypt", "connected", "event_connected", "closed", "start_time", "last_recv_time",
        "last_message_time", "last_send_time", "last_sent_time", "incomplete_buff_recv", "bytes_recv", "bytes_sent",
        "last_ping_delay", "last_req_time", "last_cmd", "name", "updateName", "waiting_requests", "waiting_streams"
    )

    def __init__(self, server, ip, port, sock=None):
        self.sock = sock
        self.ip = ip
        self.port = port
        self.peer_id = None  # Bittorrent style peer id (not used yet)
        self.id = server.last_connection_id
        server.last_connection_id += 1
        self.protocol = "?"
        self.type = "?"

        self.server = server
        self.unpacker = None  # Stream incoming socket messages here
        self.req_id = 0  # Last request id
        self.handshake = {}  # Handshake info got from peer
        self.crypt = None  # Connection encryption method
        self.sock_wrapped = False  # Socket wrapped to encryption

        self.connected = False
        self.event_connected = gevent.event.AsyncResult()  # Solves on handshake received
        self.closed = False

        # Stats
        self.start_time = time.time()
        self.last_recv_time = 0
        self.last_message_time = 0
        self.last_send_time = 0
        self.last_sent_time = 0
        self.incomplete_buff_recv = 0
        self.bytes_recv = 0
        self.bytes_sent = 0
        self.last_ping_delay = None
        self.last_req_time = 0
        self.last_cmd = None

        self.name = None
        self.updateName()

        self.waiting_requests = {}  # Waiting sent requests
        self.waiting_streams = {}  # Waiting response file streams

    def updateName(self):
        self.name = "Conn#%2s %-12s [%s]" % (self.id, self.ip, self.protocol)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<%s>" % self.__str__()

    def log(self, text):
        self.server.log.debug("%s > %s" % (self.name, text))

    # Open connection to peer and wait for handshake
    def connect(self):
        self.log("Connecting...")
        self.type = "out"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.ip, int(self.port)))

        # Implicit SSL in the future
        # self.sock = CryptConnection.manager.wrapSocket(self.sock, "tls-rsa")
        # self.sock.do_handshake()
        # self.crypt = "tls-rsa"
        # self.sock_wrapped = True

        # Detect protocol
        self.send({"cmd": "handshake", "req_id": 0, "params": self.handshakeInfo()})
        event_connected = self.event_connected
        gevent.spawn(self.messageLoop)
        return event_connected.get()  # Wait for handshake

    # Handle incoming connection
    def handleIncomingConnection(self, sock):
        self.log("Incoming connection...")
        self.type = "in"
        try:
            if sock.recv(1, gevent.socket.MSG_PEEK) == "\x16":
                self.log("Crypt in connection using implicit SSL")
                self.sock = CryptConnection.manager.wrapSocket(self.sock, "tls-rsa", True)
                self.sock_wrapped = True
                self.crypt = "tls-rsa"
        except Exception, err:
            self.log("Socket peek error: %s" % Debug.formatException(err))
        self.messageLoop()

    # Message loop for connection
    def messageLoop(self):
        if not self.sock:
            self.log("Socket error: No socket found")
            return False
        self.protocol = "v2"
        self.updateName()
        self.connected = True

        self.unpacker = msgpack.Unpacker()
        try:
            while True:
                buff = self.sock.recv(16 * 1024)
                if not buff:
                    break  # Connection closed

                # Statistics
                self.last_recv_time = time.time()
                self.incomplete_buff_recv += 1
                self.bytes_recv += len(buff)
                self.server.bytes_recv += len(buff)

                if not self.unpacker:
                    self.unpacker = msgpack.Unpacker()
                self.unpacker.feed(buff)
                buff = None
                for message in self.unpacker:
                    self.incomplete_buff_recv = 0
                    if "stream_bytes" in message:
                        self.handleStream(message)
                    else:
                        self.handleMessage(message)

                message = None
        except Exception, err:
            if not self.closed:
                self.log("Socket error: %s" % Debug.formatException(err))
        self.close()  # MessageLoop ended, close connection

    # My handshake info
    def handshakeInfo(self):
        return {
            "version": config.version,
            "protocol": "v2",
            "peer_id": self.server.peer_id,
            "fileserver_port": self.server.port,
            "port_opened": self.server.port_opened,
            "rev": config.rev,
            "crypt_supported": CryptConnection.manager.crypt_supported,
            "crypt": self.crypt
        }

    def setHandshake(self, handshake):
        self.handshake = handshake
        if handshake.get("port_opened", None) is False:  # Not connectable
            self.port = 0
        else:
            self.port = handshake["fileserver_port"]  # Set peer fileserver port
        # Check if we can encrypt the connection
        if handshake.get("crypt_supported") and handshake["peer_id"] not in self.server.broken_ssl_peer_ids:
            if handshake.get("crypt"):  # Recommended crypt by server
                crypt = handshake["crypt"]
            else:  # Select the best supported on both sides
                crypt = CryptConnection.manager.selectCrypt(handshake["crypt_supported"])

            if crypt:
                self.crypt = crypt
        self.event_connected.set(True)  # Mark handshake as done
        self.event_connected = None

    # Handle incoming message
    def handleMessage(self, message):
        self.last_message_time = time.time()
        if message.get("cmd") == "response":  # New style response
            if message["to"] in self.waiting_requests:
                if self.last_send_time:
                    ping = time.time() - self.last_send_time
                    self.last_ping_delay = ping
                self.waiting_requests[message["to"]].set(message)  # Set the response to event
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
                    self.log("Crypt out connection using: %s (server side: %s)..." % (self.crypt, server))
                    self.sock = CryptConnection.manager.wrapSocket(self.sock, self.crypt, server)
                    self.sock.do_handshake()
                self.setHandshake(message)
            else:
                self.log("Unknown response: %s" % message)
        elif message.get("cmd"):  # Handhsake request
            if message["cmd"] == "handshake":
                if config.debug_socket:
                    self.log("Handshake request: %s" % message)
                self.setHandshake(message["params"])
                data = self.handshakeInfo()
                data["cmd"] = "response"
                data["to"] = message["req_id"]
                self.send(data)  # Send response to handshake
                # Sent crypt request to client
                if self.crypt and not self.sock_wrapped:
                    server = (self.type == "in")
                    self.log("Crypt in connection using: %s (server side: %s)..." % (self.crypt, server))
                    try:
                        self.sock = CryptConnection.manager.wrapSocket(self.sock, self.crypt, server)
                        self.sock_wrapped = True
                    except Exception, err:
                        self.log("Crypt connection error: %s, adding peerid %s as broken ssl." % (err, message["params"]["peer_id"]))
                        self.server.broken_ssl_peer_ids[message["params"]["peer_id"]] = True
            else:
                self.server.handleRequest(self, message)
        else:  # Old style response, no req_id definied
            if config.debug_socket:
                self.log("Old style response, waiting: %s" % self.waiting_requests.keys())
            last_req_id = min(self.waiting_requests.keys())  # Get the oldest waiting request and set it true
            self.waiting_requests[last_req_id].set(message)
            del self.waiting_requests[last_req_id]  # Remove from waiting request

    # Stream socket directly to a file
    def handleStream(self, message):
        if config.debug_socket:
            self.log("Starting stream %s: %s bytes" % (message["to"], message["stream_bytes"]))

        read_bytes = message["stream_bytes"]  # Bytes left we have to read from socket
        try:
            buff = self.unpacker.read_bytes(min(16 * 1024, read_bytes))  # Check if the unpacker has something left in buffer
        except Exception, err:
            buff = ""
        file = self.waiting_streams[message["to"]]
        if buff:
            read_bytes -= len(buff)
            file.write(buff)

        try:
            while 1:
                if read_bytes <= 0:
                    break
                buff = self.sock.recv(16 * 1024)
                if not buff:
                    break
                buff_len = len(buff)
                read_bytes -= buff_len
                file.write(buff)

                # Statistics
                self.last_recv_time = time.time()
                self.incomplete_buff_recv += 1
                self.bytes_recv += buff_len
                self.server.bytes_recv += buff_len
        except Exception, err:
            self.log("Stream read error: %s" % Debug.formatException(err))

        if config.debug_socket:
            self.log("End stream %s" % message["to"])

        self.incomplete_buff_recv = 0
        self.waiting_requests[message["to"]].set(message)  # Set the response to event
        del self.waiting_streams[message["to"]]
        del self.waiting_requests[message["to"]]

    # Send data to connection
    def send(self, message, streaming=False):
        if config.debug_socket:
            self.log("Send: %s, to: %s, streaming: %s, site: %s, inner_path: %s, req_id: %s" % (
                message.get("cmd"), message.get("to"), streaming,
                message.get("params", {}).get("site"), message.get("params", {}).get("inner_path"),
                message.get("req_id"))
            )
        self.last_send_time = time.time()
        try:
            if streaming:
                bytes_sent = StreamingMsgpack.stream(message, self.sock.sendall)
                message = None
                self.bytes_sent += bytes_sent
                self.server.bytes_sent += bytes_sent
            else:
                data = msgpack.packb(message)
                message = None
                self.bytes_sent += len(data)
                self.server.bytes_sent += len(data)
                self.sock.sendall(data)
        except Exception, err:
            self.log("Send errror: %s" % Debug.formatException(err))
            self.close()
            return False
        self.last_sent_time = time.time()
        return True

    # Stream raw file to connection
    def sendRawfile(self, file, read_bytes):
        buff = 64 * 1024
        bytes_left = read_bytes
        while True:
            self.last_send_time = time.time()
            self.sock.sendall(
                file.read(min(bytes_left, buff))
            )
            bytes_left -= buff
            if bytes_left <= 0:
                break
        self.bytes_sent += read_bytes
        self.server.bytes_sent += read_bytes
        return True

    # Create and send a request to peer
    def request(self, cmd, params={}, stream_to=None):
        # Last command sent more than 10 sec ago, timeout
        if self.waiting_requests and self.protocol == "v2" and time.time() - max(self.last_req_time, self.last_recv_time) > 10:
            self.log("Request %s timeout: %s" % (self.last_cmd, time.time() - self.last_send_time))
            self.close()
            return False

        self.last_req_time = time.time()
        self.last_cmd = cmd
        self.req_id += 1
        data = {"cmd": cmd, "req_id": self.req_id, "params": params}
        event = gevent.event.AsyncResult()  # Create new event for response
        self.waiting_requests[self.req_id] = event
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
            except Exception, err:
                self.log("Ping error: %s" % Debug.formatException(err))
        if response and "body" in response and response["body"] == "Pong!":
            self.last_ping_delay = time.time() - s
            return True
        else:
            return False

    # Close connection
    def close(self):
        if self.closed:
            return False  # Already closed
        self.closed = True
        self.connected = False
        if self.event_connected:
            self.event_connected.set(False)

        if config.debug_socket:
            self.log(
                "Closing connection, waiting_requests: %s, buff: %s..." %
                (len(self.waiting_requests), self.incomplete_buff_recv)
            )
        for request in self.waiting_requests.values():  # Mark pending requests failed
            request.set(False)
        self.waiting_requests = {}
        self.waiting_streams = {}
        self.server.removeConnection(self)  # Remove connection from server registry
        try:
            if self.sock:
                self.sock.shutdown(gevent.socket.SHUT_WR)
                self.sock.close()
        except Exception, err:
            if config.debug_socket:
                self.log("Close error: %s" % err)

        # Little cleanup
        self.sock = None
        self.unpacker = None
        self.event_connected = None

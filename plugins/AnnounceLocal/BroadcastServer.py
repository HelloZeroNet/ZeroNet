import socket
import logging
import time
from contextlib import closing

from Debug import Debug
from util import UpnpPunch
from util import Msgpack


class BroadcastServer(object):
    def __init__(self, service_name, listen_port=1544, listen_ip=''):
        self.log = logging.getLogger("BroadcastServer")
        self.listen_port = listen_port
        self.listen_ip = listen_ip

        self.running = False
        self.sock = None
        self.sender_info = {"service": service_name}

    def createBroadcastSocket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, 'SO_REUSEPORT'):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception as err:
                self.log.warning("Error setting SO_REUSEPORT: %s" % err)

        binded = False
        for retry in range(3):
            try:
                sock.bind((self.listen_ip, self.listen_port))
                binded = True
                break
            except Exception as err:
                self.log.error(
                    "Socket bind to %s:%s error: %s, retry #%s" %
                    (self.listen_ip, self.listen_port, Debug.formatException(err), retry)
                )
                time.sleep(retry)

        if binded:
            return sock
        else:
            return False

    def start(self):  # Listens for discover requests
        self.sock = self.createBroadcastSocket()
        if not self.sock:
            self.log.error("Unable to listen on port %s" % self.listen_port)
            return

        self.log.debug("Started on port %s" % self.listen_port)

        self.running = True

        while self.running:
            try:
                data, addr = self.sock.recvfrom(8192)
            except Exception as err:
                if self.running:
                    self.log.error("Listener receive error: %s" % err)
                continue

            if not self.running:
                break

            try:
                message = Msgpack.unpack(data)
                response_addr, message = self.handleMessage(addr, message)
                if message:
                    self.send(response_addr, message)
            except Exception as err:
                self.log.error("Handlemessage error: %s" % Debug.formatException(err))
        self.log.debug("Stopped listening on port %s" % self.listen_port)

    def stop(self):
        self.log.debug("Stopping, socket: %s" % self.sock)
        self.running = False
        if self.sock:
            self.sock.close()

    def send(self, addr, message):
        if type(message) is not list:
            message = [message]

        for message_part in message:
            message_part["sender"] = self.sender_info

            self.log.debug("Send to %s: %s" % (addr, message_part["cmd"]))
            with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as sock:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(Msgpack.pack(message_part), addr)

    def getMyIps(self):
        return UpnpPunch._get_local_ips()

    def broadcast(self, message, port=None):
        if not port:
            port = self.listen_port

        my_ips = self.getMyIps()
        addr = ("255.255.255.255", port)

        message["sender"] = self.sender_info
        self.log.debug("Broadcast using ips %s on port %s: %s" % (my_ips, port, message["cmd"]))

        for my_ip in my_ips:
            try:
                with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as sock:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.bind((my_ip, 0))
                    sock.sendto(Msgpack.pack(message), addr)
            except Exception as err:
                self.log.warning("Error sending broadcast using ip %s: %s" % (my_ip, err))

    def handleMessage(self, addr, message):
        self.log.debug("Got from %s: %s" % (addr, message["cmd"]))
        cmd = message["cmd"]
        params = message.get("params", {})
        sender = message["sender"]
        sender["ip"] = addr[0]

        func_name = "action" + cmd[0].upper() + cmd[1:]
        func = getattr(self, func_name, None)

        if sender["service"] != "zeronet" or sender["peer_id"] == self.sender_info["peer_id"]:
            # Skip messages not for us or sent by us
            message = None
        elif func:
            message = func(sender, params)
        else:
            self.log.debug("Unknown cmd: %s" % cmd)
            message = None

        return (sender["ip"], sender["broadcast_port"]), message

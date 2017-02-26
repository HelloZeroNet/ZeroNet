import logging
import time
import sys

import gevent

from cStringIO import StringIO
from Debug import Debug
from Config import config
from util import helper
from PeerHashfield import PeerHashfield

if config.use_tempfiles:
    import tempfile


# Communicate remote peers
class Peer(object):
    __slots__ = (
        "ip", "port", "site", "key", "connection", "connection_server", "time_found", "time_response", "time_hashfield", "time_added", "has_hashfield",
        "time_my_hashfield_sent", "last_ping", "reputation", "last_content_json_update", "hashfield", "connection_error", "hash_failed", "download_bytes", "download_time"
    )

    def __init__(self, ip, port, site=None, connection_server=None):
        self.ip = ip
        self.port = port
        self.site = site
        self.key = "%s:%s" % (ip, port)

        self.connection = None
        self.connection_server = connection_server
        self.has_hashfield = False  # Lazy hashfield object not created yet
        self.time_hashfield = None  # Last time peer's hashfiled downloaded
        self.time_my_hashfield_sent = None  # Last time my hashfield sent to peer
        self.time_found = time.time()  # Time of last found in the torrent tracker
        self.time_response = None  # Time of last successful response from peer
        self.time_added = time.time()
        self.last_ping = None  # Last response time for ping
        self.reputation = 0  # More likely to connect if larger
        self.last_content_json_update = 0.0  # Modify date of last received content.json

        self.connection_error = 0  # Series of connection error
        self.hash_failed = 0  # Number of bad files from peer
        self.download_bytes = 0  # Bytes downloaded
        self.download_time = 0  # Time spent to download

    def __getattr__(self, key):
        if key == "hashfield":
            self.has_hashfield = True
            self.hashfield = PeerHashfield()
            return self.hashfield
        else:
            return getattr(self, key)

    def log(self, text):
        if not config.verbose:
            return  # Only log if we are in debug mode
        if self.site:
            self.site.log.debug("%s:%s %s" % (self.ip, self.port, text))
        else:
            logging.debug("%s:%s %s" % (self.ip, self.port, text))

    # Connect to host
    def connect(self, connection=None):
        if self.connection:
            self.log("Getting connection (Closing %s)..." % self.connection)
            self.connection.close("Connection change")
        else:
            self.log("Getting connection...")

        if connection:  # Connection specified
            self.connection = connection
            self.connection.sites += 1
        else:  # Try to find from connection pool or create new connection
            self.connection = None

            try:
                if self.connection_server:
                    self.connection = self.connection_server.getConnection(self.ip, self.port, site=self.site)
                elif self.site:
                    self.connection = self.site.connection_server.getConnection(self.ip, self.port, site=self.site)
                else:
                    self.connection = sys.modules["main"].file_server.getConnection(self.ip, self.port, site=self.site)
                self.connection.sites += 1

            except Exception, err:
                self.onConnectionError("Getting connection error")
                self.log("Getting connection error: %s (connection_error: %s, hash_failed: %s)" %
                         (Debug.formatException(err), self.connection_error, self.hash_failed))
                self.connection = None

    # Check if we have connection to peer
    def findConnection(self):
        if self.connection and self.connection.connected:  # We have connection to peer
            return self.connection
        else:  # Try to find from other sites connections
            self.connection = self.site.connection_server.getConnection(self.ip, self.port, create=False, site=self.site)
            if self.connection:
                self.connection.sites += 1
        return self.connection

    def __str__(self):
        return "Peer:%-12s" % self.ip

    def __repr__(self):
        return "<%s>" % self.__str__()

    def packMyAddress(self):
        if self.ip.endswith(".onion"):
            return helper.packOnionAddress(self.ip, self.port)
        else:
            return helper.packAddress(self.ip, self.port)

    # Found a peer on tracker
    def found(self):
        self.time_found = time.time()

    # Send a command to peer and return response value
    def request(self, cmd, params={}, stream_to=None):
        if not self.connection or self.connection.closed:
            self.connect()
            if not self.connection:
                self.onConnectionError("Reconnect error")
                return None  # Connection failed

        self.log("Send request: %s %s" % (params.get("site", ""), cmd))

        for retry in range(1, 4):  # Retry 3 times
            try:
                res = self.connection.request(cmd, params, stream_to)
                if not res:
                    raise Exception("Send error")
                if "error" in res:
                    self.log("%s error: %s" % (cmd, res["error"]))
                    self.onConnectionError("Response error")
                    break
                else:  # Successful request, reset connection error num
                    self.connection_error = 0
                self.time_response = time.time()
                return res
            except Exception, err:
                if type(err).__name__ == "Notify":  # Greenlet killed by worker
                    self.log("Peer worker got killed: %s, aborting cmd: %s" % (err.message, cmd))
                    break
                else:
                    self.onConnectionError("Request error")
                    self.log(
                        "%s (connection_error: %s, hash_failed: %s, retry: %s)" %
                        (Debug.formatException(err), self.connection_error, self.hash_failed, retry)
                    )
                    time.sleep(1 * retry)
                    self.connect()
        return None  # Failed after 4 retry

    # Get a file content from peer
    def getFile(self, site, inner_path):
        # Use streamFile if client supports it
        if config.stream_downloads and self.connection and self.connection.handshake and self.connection.handshake["rev"] > 310:
            return self.streamFile(site, inner_path)

        location = 0
        if config.use_tempfiles:
            buff = tempfile.SpooledTemporaryFile(max_size=16 * 1024, mode='w+b')
        else:
            buff = StringIO()

        s = time.time()
        while True:  # Read in 512k parts
            res = self.request("getFile", {"site": site, "inner_path": inner_path, "location": location})

            if not res or "body" not in res:  # Error
                return False

            buff.write(res["body"])
            res["body"] = None  # Save memory
            if res["location"] == res["size"]:  # End of file
                break
            else:
                location = res["location"]

        self.download_bytes += res["location"]
        self.download_time += (time.time() - s)
        if self.site:
            self.site.settings["bytes_recv"] = self.site.settings.get("bytes_recv", 0) + res["location"]
        buff.seek(0)
        return buff

    # Download file out of msgpack context to save memory and cpu
    def streamFile(self, site, inner_path):
        location = 0
        if config.use_tempfiles:
            buff = tempfile.SpooledTemporaryFile(max_size=16 * 1024, mode='w+b')
        else:
            buff = StringIO()

        s = time.time()
        while True:  # Read in 512k parts
            res = self.request("streamFile", {"site": site, "inner_path": inner_path, "location": location}, stream_to=buff)

            if not res or "location" not in res:  # Error
                self.log("Invalid response: %s" % res)
                return False

            if res["location"] == res["size"]:  # End of file
                break
            else:
                location = res["location"]

        self.download_bytes += res["location"]
        self.download_time += (time.time() - s)
        self.site.settings["bytes_recv"] = self.site.settings.get("bytes_recv", 0) + res["location"]
        buff.seek(0)
        return buff

    # Send a ping request
    def ping(self):
        response_time = None
        for retry in range(1, 3):  # Retry 3 times
            s = time.time()
            with gevent.Timeout(10.0, False):  # 10 sec timeout, don't raise exception
                res = self.request("ping")

                if res and "body" in res and res["body"] == "Pong!":
                    response_time = time.time() - s
                    break  # All fine, exit from for loop
            # Timeout reached or bad response
            self.onConnectionError("Ping timeout")
            self.connect()
            time.sleep(1)

        if response_time:
            self.log("Ping: %.3f" % response_time)
        else:
            self.log("Ping failed")
        self.last_ping = response_time
        return response_time

    # Request peer exchange from peer
    def pex(self, site=None, need_num=5):
        if not site:
            site = self.site  # If no site defined request peers for this site

        # give back 5 connectible peers
        packed_peers = helper.packPeers(self.site.getConnectablePeers(5))
        request = {"site": site.address, "peers": packed_peers["ip4"], "need": need_num}
        if packed_peers["onion"]:
            request["peers_onion"] = packed_peers["onion"]
        res = self.request("pex", request)
        if not res or "error" in res:
            return False
        added = 0
        # Ip4
        for peer in res.get("peers", []):
            address = helper.unpackAddress(peer)
            if site.addPeer(*address):
                added += 1
        # Onion
        for peer in res.get("peers_onion", []):
            address = helper.unpackOnionAddress(peer)
            if site.addPeer(*address):
                added += 1

        if added:
            self.log("Added peers using pex: %s" % added)

        return added

    # List modified files since the date
    # Return: {inner_path: modification date,...}
    def listModified(self, since):
        return self.request("listModified", {"since": since, "site": self.site.address})

    def updateHashfield(self, force=False):
        # Don't update hashfield again in 15 min
        if self.time_hashfield and time.time() - self.time_hashfield > 60 * 15 and not force:
            return False

        self.time_hashfield = time.time()
        res = self.request("getHashfield", {"site": self.site.address})
        if not res or "error" in res:
            return False
        self.hashfield.replaceFromString(res["hashfield_raw"])

        return self.hashfield

    # Find peers for hashids
    # Return: {hash1: ["ip:port", "ip:port",...],...}
    def findHashIds(self, hash_ids):
        res = self.request("findHashIds", {"site": self.site.address, "hash_ids": hash_ids})
        if not res or "error" in res:
            return False
        # Unpack IP4
        back = {key: map(helper.unpackAddress, val) for key, val in res["peers"].items()[0:30]}
        # Unpack onion
        for hash, onion_peers in res.get("peers_onion", {}).items()[0:30]:
            if hash not in back:
                back[hash] = []
            back[hash] += map(helper.unpackOnionAddress, onion_peers)

        return back

    # Send my hashfield to peer
    # Return: True if sent
    def sendMyHashfield(self):
        if self.connection and self.connection.handshake.get("rev", 0) < 510:
            return False  # Not supported
        if self.time_my_hashfield_sent and self.site.content_manager.hashfield.time_changed <= self.time_my_hashfield_sent:
            return False  # Peer already has the latest hashfield

        res = self.request("setHashfield", {"site": self.site.address, "hashfield_raw": self.site.content_manager.hashfield.tostring()})
        if not res or "error" in res:
            return False
        else:
            self.time_my_hashfield_sent = time.time()
            return True

    # Stop and remove from site
    def remove(self, reason="Removing"):
        self.log("Removing peer...Connection error: %s, Hash failed: %s" % (self.connection_error, self.hash_failed))
        if self.site and self.key in self.site.peers:
            del(self.site.peers[self.key])
        if self.connection:
            self.connection.close(reason)

    # - EVENTS -

    # On connection error
    def onConnectionError(self, reason="Unknown"):
        self.connection_error += 1
        if self.connection_error >= 6:  # Dead peer
            self.remove("Peer connection: %s" % reason)

    # Done working with peer
    def onWorkerDone(self):
        pass

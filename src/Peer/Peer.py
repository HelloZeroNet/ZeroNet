import logging
import time
import sys
import itertools
import collections

import gevent

import io
from Debug import Debug
from Config import config
from util import helper
from .PeerHashfield import PeerHashfield
from Plugin import PluginManager

if config.use_tempfiles:
    import tempfile


# Communicate remote peers
@PluginManager.acceptPlugins
class Peer(object):
    def __init__(self, ip, port, site=None, connection_server=None):
        self.ip = ip
        self.port = port
        self.site = site
        self.key = "%s:%s" % (ip, port)

        self.ip_type = None

        self.removed = False

        self.log_level = logging.DEBUG
        self.connection_error_log_level = logging.DEBUG

        self.connection = None
        self.connection_server = connection_server
        self.has_hashfield = False  # Lazy hashfield object not created yet
        self.time_hashfield = None  # Last time peer's hashfiled downloaded
        self.time_my_hashfield_sent = None  # Last time my hashfield sent to peer
        self.time_found = time.time()  # Time of last found in the torrent tracker
        self.time_response = 0 # Time of last successful response from peer
        self.time_added = time.time()
        self.last_ping = None  # Last response time for ping
        self.last_pex = 0  # Last query/response time for pex
        self.is_tracker_connection = False  # Tracker connection instead of normal peer
        self.reputation = 0  # More likely to connect if larger
        self.last_content_json_update = 0.0  # Modify date of last received content.json
        self.protected = 0
        self.reachable = None

        self.connection_error = 0  # Series of connection error
        self.hash_failed = 0  # Number of bad files from peer
        self.download_bytes = 0  # Bytes downloaded
        self.download_time = 0  # Time spent to download

        self.protectedRequests = ["getFile", "streamFile", "update", "listModified"]

    def __getattr__(self, key):
        if key == "hashfield":
            self.has_hashfield = True
            self.hashfield = PeerHashfield()
            return self.hashfield
        else:
            # Raise appropriately formatted attribute error
            return object.__getattribute__(self, key)

    def log(self, text, log_level = None):
        if log_level is None:
            log_level = self.log_level
        if log_level <= logging.DEBUG:
            if not config.verbose:
                return  # Only log if we are in debug mode

        logger = None

        if self.site:
            logger = self.site.log
        else:
            logger = logging.getLogger()

        logger.log(log_level, "%s:%s %s" % (self.ip, self.port, text))

    # Protect connection from being closed by site.cleanupPeers()
    def markProtected(self, interval=60*2):
        self.protected = max(self.protected, time.time() + interval)

    def isProtected(self):
        if self.protected > 0:
            if self.protected < time.time():
                self.protected = 0
        return self.protected > 0

    def isTtlExpired(self, ttl):
        last_activity = max(self.time_found, self.time_response)
        return (time.time() - last_activity) > ttl

    # Since 0.8.0
    def isConnected(self):
        if self.connection and not self.connection.connected:
            self.connection = None
        return self.connection and self.connection.connected

    # Peer proved to to be connectable recently
    # Since 0.8.0
    def isConnectable(self):
        if self.connection_error >= 1:  # The last connection attempt failed
            return False
        if time.time() - self.time_response > 60 * 60 * 2:  # Last successful response more than 2 hours ago
            return False
        return self.isReachable()

    # Since 0.8.0
    def isReachable(self):
        if self.reachable is None:
            self.updateCachedState()
        return self.reachable

    # Since 0.8.0
    def getIpType(self):
        if not self.ip_type:
            self.updateCachedState()
        return self.ip_type

    # We cache some ConnectionServer-related state for better performance.
    # This kind of state currently doesn't change during a program session,
    # and it's safe to read and cache it just once. But future versions
    # may bring more pieces of dynamic configuration. So we update the state
    # on each peer.found().
    def updateCachedState(self):
        connection_server = self.getConnectionServer()
        if not self.port or self.port == 1: # Port 1 considered as "no open port"
            self.reachable = False
        else:
            self.reachable = connection_server.isIpReachable(self.ip)
        self.ip_type = connection_server.getIpType(self.ip)


    # FIXME:
    # This should probably be changed.
    # When creating a peer object, the caller must provide either `connection_server`,
    # or `site`, so Peer object is able to use `site.connection_server`.
    def getConnectionServer(self):
        if self.connection_server:
            connection_server = self.connection_server
        elif self.site:
            connection_server = self.site.connection_server
        else:
            import main
            connection_server = main.file_server
        return connection_server

    # Connect to host
    def connect(self, connection=None):
        if self.reputation < -10:
            self.reputation = -10
        if self.reputation > 10:
            self.reputation = 10

        if self.connection:
            self.log("Getting connection (Closing %s)..." % self.connection)
            self.connection.close("Connection change")
        else:
            self.log("Getting connection (reputation: %s)..." % self.reputation)

        if connection:  # Connection specified
            self.log("Assigning connection %s" % connection)
            self.connection = connection
            self.connection.sites += 1
        else:  # Try to find from connection pool or create new connection
            self.connection = None

            try:
                connection_server = self.getConnectionServer()
                self.connection = connection_server.getConnection(self.ip, self.port, site=self.site, is_tracker_connection=self.is_tracker_connection)
                if self.connection and self.connection.connected:
                    self.reputation += 1
                    self.connection.sites += 1
            except Exception as err:
                self.onConnectionError("Getting connection error")
                self.log("Getting connection error: %s (connection_error: %s, hash_failed: %s)" %
                         (Debug.formatException(err), self.connection_error, self.hash_failed),
                         log_level=self.connection_error_log_level)
                self.connection = None
        return self.connection

    def disconnect(self, reason="Unknown"):
        if self.connection:
            self.connection.close(reason)
            self.connection = None

    # Check if we have connection to peer
    def findConnection(self):
        if self.connection and self.connection.connected:  # We have connection to peer
            return self.connection
        else:  # Try to find from other sites connections
            self.connection = self.getConnectionServer().getConnection(self.ip, self.port, create=False, site=self.site)
            if self.connection:
                self.connection.sites += 1
        return self.connection

    def __str__(self):
        if self.site:
            return "Peer:%-12s of %s" % (self.ip, self.site.address_short)
        else:
            return "Peer:%-12s" % self.ip

    def __repr__(self):
        return "<%s>" % self.__str__()

    def packMyAddress(self):
        if self.ip.endswith(".onion"):
            return helper.packOnionAddress(self.ip, self.port)
        else:
            return helper.packAddress(self.ip, self.port)

    # Found a peer from a source
    def found(self, source="other"):
        if self.reputation < 5:
            if source == "tracker":
                if self.ip.endswith(".onion"):
                    self.reputation += 1
                else:
                    self.reputation += 2
            elif source == "local":
                self.reputation += 20

        if source in ("tracker", "local"):
            self.site.peers_recent.appendleft(self)
        self.time_found = time.time()
        self.updateCachedState()

    # Send a command to peer and return response value
    def request(self, cmd, params={}, stream_to=None):
        if self.removed:
            return False

        if not self.connection or self.connection.closed:
            self.connect()
            if not self.connection:
                self.onConnectionError("Reconnect error")
                return None  # Connection failed

        self.log("Send request: %s %s %s %s" % (params.get("site", ""), cmd, params.get("inner_path", ""), params.get("location", "")))

        for retry in range(1, 4):  # Retry 3 times
            try:
                if cmd in self.protectedRequests:
                    self.markProtected()
                if not self.connection:
                    raise Exception("No connection found")
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
                if res:
                    return res
                else:
                    raise Exception("Invalid response: %s" % res)
            except Exception as err:
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
    def getFile(self, site, inner_path, file_size=None, pos_from=0, pos_to=None, streaming=False):
        if self.removed:
            return False

        if file_size and file_size > 5 * 1024 * 1024:
            max_read_size = 1024 * 1024
        else:
            max_read_size = 512 * 1024

        if pos_to:
            read_bytes = min(max_read_size, pos_to - pos_from)
        else:
            read_bytes = max_read_size

        location = pos_from

        if config.use_tempfiles:
            buff = tempfile.SpooledTemporaryFile(max_size=16 * 1024, mode='w+b')
        else:
            buff = io.BytesIO()

        s = time.time()
        while True:  # Read in smaller parts
            if config.stream_downloads or read_bytes > 256 * 1024 or streaming:
                res = self.request("streamFile", {"site": site, "inner_path": inner_path, "location": location, "read_bytes": read_bytes, "file_size": file_size}, stream_to=buff)
                if not res or "location" not in res:  # Error
                    return False
            else:
                self.log("Send: %s" % inner_path)
                res = self.request("getFile", {"site": site, "inner_path": inner_path, "location": location, "read_bytes": read_bytes, "file_size": file_size})
                if not res or "location" not in res:  # Error
                    return False
                self.log("Recv: %s" % inner_path)
                buff.write(res["body"])
                res["body"] = None  # Save memory

            if res["location"] == res["size"] or res["location"] == pos_to:  # End of file
                break
            else:
                location = res["location"]
                if pos_to:
                    read_bytes = min(max_read_size, pos_to - location)

        if pos_to:
            recv = pos_to - pos_from
        else:
            recv = res["location"]

        self.download_bytes += recv
        self.download_time += (time.time() - s)
        if self.site:
            self.site.settings["bytes_recv"] = self.site.settings.get("bytes_recv", 0) + recv
        self.log("Downloaded: %s, pos: %s, read_bytes: %s" % (inner_path, buff.tell(), read_bytes))
        buff.seek(0)
        return buff

    # Send a ping request
    def ping(self, timeout=10.0, tryes=3):
        if self.removed:
            return False

        response_time = None
        for retry in range(1, tryes):  # Retry 3 times
            s = time.time()
            with gevent.Timeout(timeout, False):
                res = self.request("ping")

                if res and "body" in res and res["body"] == b"Pong!":
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
    def pex(self, site=None, need_num=5, request_interval=60*2):
        if self.removed:
            return False

        if not site:
            site = self.site  # If no site defined request peers for this site

        if self.last_pex + request_interval >= time.time():
            return False

        self.last_pex = time.time()

        # give back 5 connectible peers
        packed_peers = helper.packPeers(self.site.getConnectablePeers(5, allow_private=False))
        request = {"site": site.address, "peers": packed_peers["ipv4"], "need": need_num}
        if packed_peers["onion"]:
            request["peers_onion"] = packed_peers["onion"]
        if packed_peers["ipv6"]:
            request["peers_ipv6"] = packed_peers["ipv6"]
        res = self.request("pex", request)
        self.last_pex = time.time()
        if not res or "error" in res:
            return False
        added = 0

        # Remove unsupported peer types
        if "peers_ipv6" in res and self.connection and "ipv6" not in self.connection.server.supported_ip_types:
            del res["peers_ipv6"]

        if "peers_onion" in res and self.connection and "onion" not in self.connection.server.supported_ip_types:
            del res["peers_onion"]

        # Add IPv4 + IPv6
        for peer in itertools.chain(res.get("peers", []), res.get("peers_ipv6", [])):
            address = helper.unpackAddress(peer)
            if site.addPeer(*address, source="pex"):
                added += 1

        # Add Onion
        for peer in res.get("peers_onion", []):
            address = helper.unpackOnionAddress(peer)
            if site.addPeer(*address, source="pex"):
                added += 1

        if added:
            self.log("Added peers using pex: %s" % added)

        return added

    # List modified files since the date
    # Return: {inner_path: modification date,...}
    def listModified(self, since):
        if self.removed:
            return False
        return self.request("listModified", {"since": since, "site": self.site.address})

    def updateHashfield(self, force=False):
        if self.removed:
            return False

        # Don't update hashfield again in 5 min
        if self.time_hashfield and time.time() - self.time_hashfield < 5 * 60 and not force:
            return False

        self.time_hashfield = time.time()
        res = self.request("getHashfield", {"site": self.site.address})
        if not res or "error" in res or "hashfield_raw" not in res:
            return False
        self.hashfield.replaceFromBytes(res["hashfield_raw"])

        return self.hashfield

    # Find peers for hashids
    # Return: {hash1: ["ip:port", "ip:port",...],...}
    def findHashIds(self, hash_ids):
        if self.removed:
            return False

        res = self.request("findHashIds", {"site": self.site.address, "hash_ids": hash_ids})
        if not res or "error" in res or type(res) is not dict:
            return False

        back = collections.defaultdict(list)

        for ip_type in ["ipv4", "ipv6", "onion"]:
            if ip_type == "ipv4":
                key = "peers"
            else:
                key = "peers_%s" % ip_type
            for hash, peers in list(res.get(key, {}).items())[0:30]:
                if ip_type == "onion":
                    unpacker_func = helper.unpackOnionAddress
                else:
                    unpacker_func = helper.unpackAddress

                back[hash] += list(map(unpacker_func, peers))

        for hash in res.get("my", []):
            if self.connection:
                back[hash].append((self.connection.ip, self.connection.port))
            else:
                back[hash].append((self.ip, self.port))

        return back

    # Send my hashfield to peer
    # Return: True if sent
    def sendMyHashfield(self):
        if self.connection and self.connection.handshake.get("rev", 0) < 510:
            return False  # Not supported
        if self.time_my_hashfield_sent and self.site.content_manager.hashfield.time_changed <= self.time_my_hashfield_sent:
            return False  # Peer already has the latest hashfield

        res = self.request("setHashfield", {"site": self.site.address, "hashfield_raw": self.site.content_manager.hashfield.tobytes()})
        if not res or "error" in res:
            return False
        else:
            self.time_my_hashfield_sent = time.time()
            return True

    def publish(self, address, inner_path, body, modified, diffs=[]):
        if self.removed:
            return False

        if len(body) > 10 * 1024 and self.connection and self.connection.handshake.get("rev", 0) >= 4095:
            # To save bw we don't push big content.json to peers
            body = b""

        return self.request("update", {
            "site": address,
            "inner_path": inner_path,
            "body": body,
            "modified": modified,
            "diffs": diffs
        })

    # Stop and remove from site
    def remove(self, reason="Removing"):
        self.removed = True
        self.log("Removing peer with reason: <%s>. Connection error: %s, Hash failed: %s" % (reason, self.connection_error, self.hash_failed))
        if self.site:
            self.site.deregisterPeer(self)
            # No way: self.site = None
            # We don't assign None to self.site here because it leads to random exceptions in various threads,
            # that hold references to the peer and still believe it belongs to the site.

        self.disconnect(reason)

    # - EVENTS -

    # On connection error
    def onConnectionError(self, reason="Unknown"):
        if not self.getConnectionServer().isInternetOnline():
            return
        self.connection_error += 1
        if self.site and len(self.site.peers) > 200:
            limit = 3
        else:
            limit = 6
        self.reputation -= 1
        if self.connection_error >= limit:  # Dead peer
            self.remove("Connection error limit reached: %s. Provided message: %s" % (limit, reason))

    # Done working with peer
    def onWorkerDone(self):
        pass

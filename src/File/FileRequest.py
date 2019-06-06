# Included modules
import os
import time
import json
import collections
import itertools

# Third party modules
import gevent

from Debug import Debug
from Config import config
from util import RateLimit
from util import Msgpack
from util import helper
from Plugin import PluginManager
from contextlib import closing

FILE_BUFF = 1024 * 512


class RequestError(Exception):
    pass


# Incoming requests
@PluginManager.acceptPlugins
class FileRequest(object):
    __slots__ = ("server", "connection", "req_id", "sites", "log", "responded")

    def __init__(self, server, connection):
        self.server = server
        self.connection = connection

        self.req_id = None
        self.sites = self.server.sites
        self.log = server.log
        self.responded = False  # Responded to the request

    def send(self, msg, streaming=False):
        if not self.connection.closed:
            self.connection.send(msg, streaming)

    def sendRawfile(self, file, read_bytes):
        if not self.connection.closed:
            self.connection.sendRawfile(file, read_bytes)

    def response(self, msg, streaming=False):
        if self.responded:
            if config.verbose:
                self.log.debug("Req id %s already responded" % self.req_id)
            return
        if not isinstance(msg, dict):  # If msg not a dict create a {"body": msg}
            msg = {"body": msg}
        msg["cmd"] = "response"
        msg["to"] = self.req_id
        self.responded = True
        self.send(msg, streaming=streaming)

    # Route file requests
    def route(self, cmd, req_id, params):
        self.req_id = req_id
        # Don't allow other sites than locked
        if "site" in params and self.connection.target_onion:
            valid_sites = self.connection.getValidSites()
            if params["site"] not in valid_sites and valid_sites != ["global"]:
                self.response({"error": "Invalid site"})
                self.connection.log(
                    "Site lock violation: %s not in %s, target onion: %s" %
                    (params["site"], valid_sites, self.connection.target_onion)
                )
                self.connection.badAction(5)
                return False

        if cmd == "update":
            event = "%s update %s %s" % (self.connection.id, params["site"], params["inner_path"])
            # If called more than once within 15 sec only keep the last update
            RateLimit.callAsync(event, max(self.connection.bad_actions, 15), self.actionUpdate, params)
        else:
            func_name = "action" + cmd[0].upper() + cmd[1:]
            func = getattr(self, func_name, None)
            if cmd not in ["getFile", "streamFile"]:  # Skip IO bound functions
                if self.connection.cpu_time > 0.5:
                    self.log.debug(
                        "Delay %s %s, cpu_time used by connection: %.3fs" %
                        (self.connection.ip, cmd, self.connection.cpu_time)
                    )
                    time.sleep(self.connection.cpu_time)
                    if self.connection.cpu_time > 5:
                        self.connection.close("Cpu time: %.3fs" % self.connection.cpu_time)
                s = time.time()
            if func:
                func(params)
            else:
                self.actionUnknown(cmd, params)

            if cmd not in ["getFile", "streamFile"]:
                taken = time.time() - s
                taken_sent = self.connection.last_sent_time - self.connection.last_send_time
                self.connection.cpu_time += taken - taken_sent

    # Update a site file request
    def actionUpdate(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.isServing():  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(1)
            self.connection.badAction(5)
            return False

        inner_path = params.get("inner_path", "")
        current_content_modified = site.content_manager.contents.get(inner_path, {}).get("modified", 0)
        body = params["body"]

        if not inner_path.endswith("content.json"):
            self.response({"error": "Only content.json update allowed"})
            self.connection.badAction(5)
            return

        should_validate_content = True
        if "modified" in params and params["modified"] <= current_content_modified:
            should_validate_content = False
            valid = None  # Same or earlier content as we have
        elif not body:  # No body sent, we have to download it first
            self.log.debug("Missing body from update, downloading...")
            peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True, source="update")  # Add or get peer
            try:
                body = peer.getFile(site.address, inner_path).read()
            except Exception as err:
                self.log.debug("Can't download updated file %s: %s" % (inner_path, err))
                self.response({"error": "File invalid update: Can't download updaed file"})
                self.connection.badAction(5)
                return

        if should_validate_content:
            try:
                content = json.loads(body.decode())
            except Exception as err:
                self.log.debug("Update for %s is invalid JSON: %s" % (inner_path, err))
                self.response({"error": "File invalid JSON"})
                self.connection.badAction(5)
                return

            file_uri = "%s/%s:%s" % (site.address, inner_path, content["modified"])

            if self.server.files_parsing.get(file_uri):  # Check if we already working on it
                valid = None  # Same file
            else:
                try:
                    valid = site.content_manager.verifyFile(inner_path, content)
                except Exception as err:
                    self.log.debug("Update for %s is invalid: %s" % (inner_path, err))
                    error = err
                    valid = False

        if valid is True:  # Valid and changed
            site.log.info("Update for %s looks valid, saving..." % inner_path)
            self.server.files_parsing[file_uri] = True
            site.storage.write(inner_path, body)
            del params["body"]

            site.onFileDone(inner_path)  # Trigger filedone

            if inner_path.endswith("content.json"):  # Download every changed file from peer
                peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True, source="update")  # Add or get peer
                # On complete publish to other peers
                diffs = params.get("diffs", {})
                site.onComplete.once(lambda: site.publish(inner_path=inner_path, diffs=diffs, limit=3), "publish_%s" % inner_path)

                # Load new content file and download changed files in new thread
                def downloader():
                    site.downloadContent(inner_path, peer=peer, diffs=params.get("diffs", {}))
                    del self.server.files_parsing[file_uri]

                gevent.spawn(downloader)
            else:
                del self.server.files_parsing[file_uri]

            self.response({"ok": "Thanks, file %s updated!" % inner_path})
            self.connection.goodAction()

        elif valid is None:  # Not changed
            peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True, source="update old")  # Add or get peer
            if peer:
                if not peer.connection:
                    peer.connect(self.connection)  # Assign current connection to peer
                if inner_path in site.content_manager.contents:
                    peer.last_content_json_update = site.content_manager.contents[inner_path]["modified"]
                if config.verbose:
                    self.log.debug(
                        "Same version, adding new peer for locked files: %s, tasks: %s" %
                        (peer.key, len(site.worker_manager.tasks))
                    )
                for task in site.worker_manager.tasks:  # New peer add to every ongoing task
                    if task["peers"] and not task["optional_hash_id"]:
                        # Download file from this peer too if its peer locked
                        site.needFile(task["inner_path"], peer=peer, update=True, blocking=False)

            self.response({"ok": "File not changed"})
            self.connection.badAction()

        else:  # Invalid sign or sha hash
            self.response({"error": "File %s invalid: %s" % (inner_path, error)})
            self.connection.badAction(5)

    def isReadable(self, site, inner_path, file, pos):
        return True

    # Send file content request
    def handleGetFile(self, params, streaming=False):
        site = self.sites.get(params["site"])
        if not site or not site.isServing():  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(5)
            return False
        try:
            file_path = site.storage.getPath(params["inner_path"])
            if streaming:
                file_obj = site.storage.open(params["inner_path"])
            else:
                file_obj = Msgpack.FilePart(file_path, "rb")

            with file_obj as file:
                file.seek(params["location"])
                read_bytes = params.get("read_bytes", FILE_BUFF)
                file_size = os.fstat(file.fileno()).st_size

                if file_size > read_bytes:  # Check if file is readable at current position (for big files)
                    if not self.isReadable(site, params["inner_path"], file, params["location"]):
                        raise RequestError("File not readable at position: %s" % params["location"])
                else:
                    if params.get("file_size") and params["file_size"] != file_size:
                        self.connection.badAction(2)
                        raise RequestError("File size does not match: %sB != %sB" % (params["file_size"], file_size))

                if not streaming:
                    file.read_bytes = read_bytes

                if params["location"] > file_size:
                    self.connection.badAction(5)
                    raise RequestError("Bad file location")

                if streaming:
                    back = {
                        "size": file_size,
                        "location": min(file.tell() + read_bytes, file_size),
                        "stream_bytes": min(read_bytes, file_size - params["location"])
                    }
                    self.response(back)
                    self.sendRawfile(file, read_bytes=read_bytes)
                else:
                    back = {
                        "body": file,
                        "size": file_size,
                        "location": min(file.tell() + file.read_bytes, file_size)
                    }
                    self.response(back, streaming=True)

                bytes_sent = min(read_bytes, file_size - params["location"])  # Number of bytes we going to send
                site.settings["bytes_sent"] = site.settings.get("bytes_sent", 0) + bytes_sent
            if config.debug_socket:
                self.log.debug("File %s at position %s sent %s bytes" % (file_path, params["location"], bytes_sent))

            # Add peer to site if not added before
            connected_peer = site.addPeer(self.connection.ip, self.connection.port, source="request")
            if connected_peer:  # Just added
                connected_peer.connect(self.connection)  # Assign current connection to peer

            return {"bytes_sent": bytes_sent, "file_size": file_size, "location": params["location"]}

        except RequestError as err:
            self.log.debug("GetFile %s %s request error: %s" % (self.connection, params["inner_path"], Debug.formatException(err)))
            self.response({"error": "File read error: %s" % err})
        except OSError as err:
            if config.verbose:
                self.log.debug("GetFile read error: %s" % Debug.formatException(err))
            self.response({"error": "File read error"})
            return False
        except Exception as err:
            self.log.error("GetFile exception: %s" % Debug.formatException(err))
            self.response({"error": "File read exception"})
            return False

    def actionGetFile(self, params):
        return self.handleGetFile(params)

    def actionStreamFile(self, params):
        return self.handleGetFile(params, streaming=True)

    # Peer exchange request
    def actionPex(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.isServing():  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(5)
            return False

        got_peer_keys = []
        added = 0

        # Add requester peer to site
        connected_peer = site.addPeer(self.connection.ip, self.connection.port, source="request")

        if connected_peer:  # It was not registered before
            added += 1
            connected_peer.connect(self.connection)  # Assign current connection to peer

        # Add sent peers to site
        for packed_address in itertools.chain(params.get("peers", []), params.get("peers_ipv6", [])):
            address = helper.unpackAddress(packed_address)
            got_peer_keys.append("%s:%s" % address)
            if site.addPeer(*address, source="pex"):
                added += 1

        # Add sent onion peers to site
        for packed_address in params.get("peers_onion", []):
            address = helper.unpackOnionAddress(packed_address)
            got_peer_keys.append("%s:%s" % address)
            if site.addPeer(*address, source="pex"):
                added += 1

        # Send back peers that is not in the sent list and connectable (not port 0)
        packed_peers = helper.packPeers(site.getConnectablePeers(params["need"], ignore=got_peer_keys, allow_private=False))

        if added:
            site.worker_manager.onPeers()
            if config.verbose:
                self.log.debug(
                    "Added %s peers to %s using pex, sending back %s" %
                    (added, site, {key: len(val) for key, val in packed_peers.items()})
                )

        back = {
            "peers": packed_peers["ipv4"],
            "peers_ipv6": packed_peers["ipv6"],
            "peers_onion": packed_peers["onion"]
        }

        self.response(back)

    # Get modified content.json files since
    def actionListModified(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.isServing():  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(5)
            return False
        modified_files = site.content_manager.listModified(params["since"])

        # Add peer to site if not added before
        connected_peer = site.addPeer(self.connection.ip, self.connection.port, source="request")
        if connected_peer:  # Just added
            connected_peer.connect(self.connection)  # Assign current connection to peer

        self.response({"modified_files": modified_files})

    def actionGetHashfield(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.isServing():  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(5)
            return False

        # Add peer to site if not added before
        peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True, source="request")
        if not peer.connection:  # Just added
            peer.connect(self.connection)  # Assign current connection to peer

        peer.time_my_hashfield_sent = time.time()  # Don't send again if not changed

        self.response({"hashfield_raw": site.content_manager.hashfield.tobytes()})

    def findHashIds(self, site, hash_ids, limit=100):
        back = collections.defaultdict(lambda: collections.defaultdict(list))
        found = site.worker_manager.findOptionalHashIds(hash_ids, limit=limit)

        for hash_id, peers in found.items():
            for peer in peers:
                ip_type = helper.getIpType(peer.ip)
                if len(back[ip_type][hash_id]) < 20:
                    back[ip_type][hash_id].append(peer.packMyAddress())
        return back

    def actionFindHashIds(self, params):
        site = self.sites.get(params["site"])
        s = time.time()
        if not site or not site.isServing():  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(5)
            return False

        event_key = "%s_findHashIds_%s_%s" % (self.connection.ip, params["site"], len(params["hash_ids"]))
        if self.connection.cpu_time > 0.5 or not RateLimit.isAllowed(event_key, 60 * 5):
            time.sleep(0.1)
            back = self.findHashIds(site, params["hash_ids"], limit=10)
        else:
            back = self.findHashIds(site, params["hash_ids"])
        RateLimit.called(event_key)

        my_hashes = []
        my_hashfield_set = set(site.content_manager.hashfield)
        for hash_id in params["hash_ids"]:
            if hash_id in my_hashfield_set:
                my_hashes.append(hash_id)

        if config.verbose:
            self.log.debug(
                "Found: %s for %s hashids in %.3fs" %
                ({key: len(val) for key, val in back.items()}, len(params["hash_ids"]), time.time() - s)
            )
        self.response({"peers": back["ipv4"], "peers_onion": back["onion"], "peers_ipv6": back["ipv6"], "my": my_hashes})

    def actionSetHashfield(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.isServing():  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(5)
            return False

        # Add or get peer
        peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True, connection=self.connection, source="request")
        if not peer.connection:
            peer.connect(self.connection)
        peer.hashfield.replaceFromBytes(params["hashfield_raw"])
        self.response({"ok": "Updated"})

    # Send a simple Pong! answer
    def actionPing(self, params):
        self.response(b"Pong!")

    # Check requested port of the other peer
    def actionCheckport(self, params):
        if helper.getIpType(self.connection.ip) == "ipv6":
            sock_address = (self.connection.ip, params["port"], 0, 0)
        else:
            sock_address = (self.connection.ip, params["port"])

        with closing(helper.createSocket(self.connection.ip)) as sock:
            sock.settimeout(5)
            if sock.connect_ex(sock_address) == 0:
                self.response({"status": "open", "ip_external": self.connection.ip})
            else:
                self.response({"status": "closed", "ip_external": self.connection.ip})

    # Unknown command
    def actionUnknown(self, cmd, params):
        self.response({"error": "Unknown command: %s" % cmd})
        self.connection.badAction(5)

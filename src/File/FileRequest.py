# Included modules
import os
import time
from cStringIO import StringIO

# Third party modules
import gevent

from Debug import Debug
from Config import config
from util import RateLimit
from util import StreamingMsgpack
from util import helper
from Plugin import PluginManager

FILE_BUFF = 1024 * 512


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
        if "site" in params and self.connection.site_lock and self.connection.site_lock not in (params["site"], "global"):
            self.response({"error": "Invalid site"})
            self.log.error("Site lock violation: %s != %s" % (self.connection.site_lock != params["site"]))
            self.connection.badAction(5)
            return False

        if cmd == "update":
            event = "%s update %s %s" % (self.connection.id, params["site"], params["inner_path"])
            if not RateLimit.isAllowed(event):  # There was already an update for this file in the last 10 second
                time.sleep(5)
                self.response({"ok": "File update queued"})
            # If called more than once within 20 sec only keep the last update
            RateLimit.callAsync(event, max(self.connection.bad_actions, 20), self.actionUpdate, params)
        else:
            func_name = "action" + cmd[0].upper() + cmd[1:]
            func = getattr(self, func_name, None)
            if func:
                func(params)
            else:
                self.actionUnknown(cmd, params)

    # Update a site file request
    def actionUpdate(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.settings["serving"]:  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            return False
        if site.settings["own"] and params["inner_path"].endswith("content.json"):
            self.log.debug(
                "%s pushing a file to own site %s, reloading local %s first" %
                (self.connection.ip, site.address, params["inner_path"])
            )
            changed, deleted = site.content_manager.loadContent(params["inner_path"], add_bad_files=False)
            if changed or deleted:  # Content.json changed locally
                site.settings["size"] = site.content_manager.getTotalSize()  # Update site size
        buff = StringIO(params["body"])
        valid = site.content_manager.verifyFile(params["inner_path"], buff)
        if valid is True:  # Valid and changed
            self.log.info("Update for %s looks valid, saving..." % params["inner_path"])
            buff.seek(0)
            site.storage.write(params["inner_path"], buff)

            site.onFileDone(params["inner_path"])  # Trigger filedone

            if params["inner_path"].endswith("content.json"):  # Download every changed file from peer
                peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True)  # Add or get peer
                # On complete publish to other peers
                site.onComplete.once(lambda: site.publish(inner_path=params["inner_path"]), "publish_%s" % params["inner_path"])

                # Load new content file and download changed files in new thread
                gevent.spawn(
                    lambda: site.downloadContent(params["inner_path"], peer=peer)
                )

            self.response({"ok": "Thanks, file %s updated!" % params["inner_path"]})
            self.connection.goodAction()

        elif valid is None:  # Not changed
            if params.get("peer"):
                peer = site.addPeer(*params["peer"], return_peer=True)  # Add or get peer
            else:
                peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True)  # Add or get peer
            if peer:
                peer.last_content_json_update = site.content_manager.contents[params["inner_path"]]["modified"]
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
            self.log.debug("Update for %s is invalid" % params["inner_path"])
            self.response({"error": "File invalid"})
            self.connection.badAction(5)

    # Send file content request
    def actionGetFile(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.settings["serving"]:  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            return False
        try:
            file_path = site.storage.getPath(params["inner_path"])
            if config.debug_socket:
                self.log.debug("Opening file: %s" % file_path)
            with StreamingMsgpack.FilePart(file_path, "rb") as file:
                file.seek(params["location"])
                file.read_bytes = FILE_BUFF
                file_size = os.fstat(file.fileno()).st_size
                assert params["location"] <= file_size, "Bad file location"

                back = {
                    "body": file,
                    "size": file_size,
                    "location": min(file.tell() + FILE_BUFF, file_size)
                }
                if config.debug_socket:
                    self.log.debug(
                        "Sending file %s from position %s to %s" %
                        (file_path, params["location"], back["location"])
                    )
                self.response(back, streaming=True)

                bytes_sent = min(FILE_BUFF, file_size - params["location"])  # Number of bytes we going to send
                site.settings["bytes_sent"] = site.settings.get("bytes_sent", 0) + bytes_sent
            if config.debug_socket:
                self.log.debug("File %s at position %s sent %s bytes" % (file_path, params["location"], bytes_sent))

            # Add peer to site if not added before
            connected_peer = site.addPeer(self.connection.ip, self.connection.port)
            if connected_peer:  # Just added
                connected_peer.connect(self.connection)  # Assign current connection to peer

        except Exception, err:
            self.log.debug("GetFile read error: %s" % Debug.formatException(err))
            self.response({"error": "File read error: %s" % Debug.formatException(err)})
            return False

    # New-style file streaming out of Msgpack context
    def actionStreamFile(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.settings["serving"]:  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            return False
        try:
            if config.debug_socket:
                self.log.debug("Opening file: %s" % params["inner_path"])
            with site.storage.open(params["inner_path"]) as file:
                file.seek(params["location"])
                file_size = os.fstat(file.fileno()).st_size
                stream_bytes = min(FILE_BUFF, file_size - params["location"])
                assert stream_bytes >= 0, "Stream bytes out of range"

                back = {
                    "size": file_size,
                    "location": min(file.tell() + FILE_BUFF, file_size),
                    "stream_bytes": stream_bytes
                }
                if config.debug_socket:
                    self.log.debug(
                        "Sending file %s from position %s to %s" %
                        (params["inner_path"], params["location"], back["location"])
                    )
                self.response(back)
                self.sendRawfile(file, read_bytes=FILE_BUFF)

                site.settings["bytes_sent"] = site.settings.get("bytes_sent", 0) + stream_bytes
            if config.debug_socket:
                self.log.debug("File %s at position %s sent %s bytes" % (params["inner_path"], params["location"], stream_bytes))

            # Add peer to site if not added before
            connected_peer = site.addPeer(self.connection.ip, self.connection.port)
            if connected_peer:  # Just added
                connected_peer.connect(self.connection)  # Assign current connection to peer

        except Exception, err:
            self.log.debug("GetFile read error: %s" % Debug.formatException(err))
            self.response({"error": "File read error: %s" % Debug.formatException(err)})
            return False

    # Peer exchange request
    def actionPex(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.settings["serving"]:  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            return False

        got_peer_keys = []
        added = 0

        # Add requester peer to site
        connected_peer = site.addPeer(self.connection.ip, self.connection.port)
        if connected_peer:  # It was not registered before
            added += 1
            connected_peer.connect(self.connection)  # Assign current connection to peer

        # Add sent peers to site
        for packed_address in params.get("peers", []):
            address = helper.unpackAddress(packed_address)
            got_peer_keys.append("%s:%s" % address)
            if site.addPeer(*address):
                added += 1

        # Add sent peers to site
        for packed_address in params.get("peers_onion", []):
            address = helper.unpackOnionAddress(packed_address)
            got_peer_keys.append("%s:%s" % address)
            if site.addPeer(*address):
                added += 1

        # Send back peers that is not in the sent list and connectable (not port 0)
        packed_peers = helper.packPeers(site.getConnectablePeers(params["need"], got_peer_keys))

        if added:
            site.worker_manager.onPeers()
            if config.verbose:
                self.log.debug(
                    "Added %s peers to %s using pex, sending back %s" %
                    (added, site, len(packed_peers["ip4"]) + len(packed_peers["onion"]))
                )

        back = {}
        if packed_peers["ip4"]:
            back["peers"] = packed_peers["ip4"]
        if packed_peers["onion"]:
            back["peers_onion"] = packed_peers["onion"]

        self.response(back)

    # Get modified content.json files since
    def actionListModified(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.settings["serving"]:  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            return False
        modified_files = {
            inner_path: content["modified"]
            for inner_path, content in site.content_manager.contents.iteritems()
            if content["modified"] > params["since"]
        }

        # Add peer to site if not added before
        connected_peer = site.addPeer(self.connection.ip, self.connection.port)
        if connected_peer:  # Just added
            connected_peer.connect(self.connection)  # Assign current connection to peer

        self.response({"modified_files": modified_files})

    def actionGetHashfield(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.settings["serving"]:  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            return False

        # Add peer to site if not added before
        peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True)
        if not peer.connection:  # Just added
            peer.connect(self.connection)  # Assign current connection to peer

        peer.time_my_hashfield_sent = time.time()  # Don't send again if not changed

        self.response({"hashfield_raw": site.content_manager.hashfield.tostring()})

    def actionFindHashIds(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.settings["serving"]:  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(5)
            return False

        found = site.worker_manager.findOptionalHashIds(params["hash_ids"])

        back_ip4 = {}
        back_onion = {}
        for hash_id, peers in found.iteritems():
            back_onion[hash_id] = [helper.packOnionAddress(peer.ip, peer.port) for peer in peers if peer.ip.endswith("onion")]
            back_ip4[hash_id] = [helper.packAddress(peer.ip, peer.port) for peer in peers if not peer.ip.endswith("onion")]

        # Check my hashfield
        if self.server.tor_manager and self.server.tor_manager.site_onions.get(site.address):  # Running onion
            my_ip = helper.packOnionAddress(self.server.tor_manager.site_onions[site.address], self.server.port)
            my_back = back_onion
        elif config.ip_external:  # External ip defined
            my_ip = helper.packAddress(config.ip_external, self.server.port)
            my_back = back_ip4
        else:  # No external ip defined
            my_ip = my_ip = helper.packAddress(self.server.ip, self.server.port)
            my_back = back_ip4

        for hash_id in params["hash_ids"]:
            if hash_id in site.content_manager.hashfield:
                if hash_id not in my_back:
                    my_back[hash_id] = []
                my_back[hash_id].append(my_ip)  # Add myself

        if config.verbose:
            self.log.debug(
                "Found: IP4: %s, Onion: %s for %s hashids" %
                (len(back_ip4), len(back_onion), len(params["hash_ids"]))
            )
        self.response({"peers": back_ip4, "peers_onion": back_onion})

    def actionSetHashfield(self, params):
        site = self.sites.get(params["site"])
        if not site or not site.settings["serving"]:  # Site unknown or not serving
            self.response({"error": "Unknown site"})
            self.connection.badAction(5)
            return False

        peer = site.addPeer(self.connection.ip, self.connection.port, return_peer=True, connection=self.connection)  # Add or get peer
        if not peer.connection:
            peer.connect(self.connection)
        peer.hashfield.replaceFromString(params["hashfield_raw"])
        self.response({"ok": "Updated"})

    def actionSiteReload(self, params):
        if self.connection.ip != "127.0.0.1" and self.connection.ip != config.ip_external:
            self.response({"error": "Only local host allowed"})

        site = self.sites.get(params["site"])
        site.content_manager.loadContent(params["inner_path"], add_bad_files=False)
        site.storage.verifyFiles(quick_check=True)
        site.updateWebsocket()

        self.response({"ok": "Reloaded"})

    def actionSitePublish(self, params):
        if self.connection.ip != "127.0.0.1" and self.connection.ip != config.ip_external:
            self.response({"error": "Only local host allowed"})

        site = self.sites.get(params["site"])
        num = site.publish(limit=8, inner_path=params.get("inner_path", "content.json"))

        self.response({"ok": "Successfuly published to %s peers" % num})

    # Send a simple Pong! answer
    def actionPing(self, params):
        self.response("Pong!")

    # Unknown command
    def actionUnknown(self, cmd, params):
        self.response({"error": "Unknown command: %s" % cmd})
        self.connection.badAction(5)

import os, msgpack, shutil, gevent, socket, struct, random
from cStringIO import StringIO
from Debug import Debug
from Config import config
from util import RateLimit, StreamingMsgpack

FILE_BUFF = 1024*512

# Request from me
class FileRequest(object):
	__slots__ = ("server", "connection", "req_id", "sites", "log", "responded")

	def __init__(self, server, connection):
		self.server = server
		self.connection = connection

		self.req_id = None
		self.sites = self.server.sites
		self.log = server.log
		self.responded = False # Responded to the request


	def unpackAddress(self, packed):
		return (socket.inet_ntoa(packed[0:4]), struct.unpack_from("H", packed, 4)[0])


	def send(self, msg, streaming=False):
		if not self.connection.closed:
			self.connection.send(msg, streaming)


	def response(self, msg, streaming=False):
		if self.responded:
			self.log.debug("Req id %s already responded" % self.req_id)
			return
		if not isinstance(msg, dict): # If msg not a dict create a {"body": msg}
			msg = {"body": msg}
		msg["cmd"] = "response"
		msg["to"] = self.req_id
		self.responded = True
		self.send(msg, streaming=streaming)


	# Route file requests
	def route(self, cmd, req_id, params):
		self.req_id = req_id

		if cmd == "getFile":
			self.actionGetFile(params)
		elif cmd == "update":
			event = "%s update %s %s" % (self.connection.id, params["site"], params["inner_path"])
			if not RateLimit.isAllowed(event): # There was already an updat for this file in the last 10 second
				self.response({"ok": "File update queued"})
			RateLimit.callAsync(event, 10, self.actionUpdate, params) # If called more than once within 10 sec only keep the last update

		elif cmd == "pex":
			self.actionPex(params)
		elif cmd == "listModified":
			self.actionListModified(params)
		elif cmd == "ping":
			self.actionPing()
		else:
			self.actionUnknown(cmd, params)


	# Update a site file request
	def actionUpdate(self, params):
		site = self.sites.get(params["site"])
		if not site or not site.settings["serving"]: # Site unknown or not serving
			self.response({"error": "Unknown site"})
			return False
		if site.settings["own"] and params["inner_path"].endswith("content.json"):
			self.log.debug("Someone trying to push a file to own site %s, reload local %s first" % (site.address, params["inner_path"]))
			changed = site.content_manager.loadContent(params["inner_path"], add_bad_files=False)
			if changed: # Content.json changed locally
				site.settings["size"] = site.content_manager.getTotalSize() # Update site size
		buff = StringIO(params["body"])
		valid = site.content_manager.verifyFile(params["inner_path"], buff)
		if valid == True: # Valid and changed
			self.log.info("Update for %s looks valid, saving..." % params["inner_path"])
			buff.seek(0)
			site.storage.write(params["inner_path"], buff)

			site.onFileDone(params["inner_path"]) # Trigger filedone

			if params["inner_path"].endswith("content.json"): # Download every changed file from peer
				peer = site.addPeer(self.connection.ip, self.connection.port, return_peer = True) # Add or get peer
				site.onComplete.once(lambda: site.publish(inner_path=params["inner_path"]), "publish_%s" % params["inner_path"]) # On complete publish to other peers
				gevent.spawn(
					lambda: site.downloadContent(params["inner_path"], peer=peer)
				) # Load new content file and download changed files in new thread

			self.response({"ok": "Thanks, file %s updated!" % params["inner_path"]})

		elif valid == None: # Not changed
			peer = site.addPeer(*params["peer"], return_peer = True) # Add or get peer
			if peer:
				self.log.debug("Same version, adding new peer for locked files: %s, tasks: %s" % (peer.key, len(site.worker_manager.tasks)) )
				for task in site.worker_manager.tasks: # New peer add to every ongoing task
					if task["peers"]: site.needFile(task["inner_path"], peer=peer, update=True, blocking=False) # Download file from this peer too if its peer locked

			self.response({"ok": "File not changed"})

		else: # Invalid sign or sha1 hash
			self.log.debug("Update for %s is invalid" % params["inner_path"])
			self.response({"error": "File invalid"})


	# Send file content request
	def actionGetFile(self, params):
		site = self.sites.get(params["site"])
		if not site or not site.settings["serving"]: # Site unknown or not serving
			self.response({"error": "Unknown site"})
			return False
		try:
			file_path = site.storage.getPath(params["inner_path"])
			if config.debug_socket: self.log.debug("Opening file: %s" % file_path)
			with StreamingMsgpack.FilePart(file_path, "rb") as file:
				file.seek(params["location"])
				file.read_bytes = FILE_BUFF
				back = {}
				back["body"] = file
				back["size"] = os.fstat(file.fileno()).st_size
				back["location"] = min(file.tell()+FILE_BUFF, back["size"])
				if config.debug_socket: self.log.debug("Sending file %s from position %s to %s" % (file_path, params["location"], back["location"]))
				self.response(back, streaming=True)
			if config.debug_socket: self.log.debug("File %s sent" % file_path)

			# Add peer to site if not added before
			connected_peer = site.addPeer(self.connection.ip, self.connection.port)
			if connected_peer: # Just added
				connected_peer.connect(self.connection) # Assign current connection to peer

		except Exception, err:
			self.log.debug("GetFile read error: %s" % Debug.formatException(err))
			self.response({"error": "File read error: %s" % Debug.formatException(err)})
			return False


	# Peer exchange request
	def actionPex(self, params):
		site = self.sites.get(params["site"])
		if not site or not site.settings["serving"]: # Site unknown or not serving
			self.response({"error": "Unknown site"})
			return False

		got_peer_keys = []
		added = 0
		connected_peer = site.addPeer(self.connection.ip, self.connection.port) # Add requester peer to site
		if connected_peer: # Just added
			added +=1
			connected_peer.connect(self.connection) # Assign current connection to peer

		for peer in params["peers"]: # Add sent peers to site
			address = self.unpackAddress(peer)
			got_peer_keys.append("%s:%s" % address)
			if site.addPeer(*address): added += 1
		# Send back peers that is not in the sent list and connectable (not port 0)
		packed_peers = [peer.packAddress() for peer in site.getConnectablePeers(params["need"], got_peer_keys)]
		if added:
			site.worker_manager.onPeers()
			self.log.debug("Added %s peers to %s using pex, sending back %s" % (added, site, len(packed_peers)))
		self.response({"peers": packed_peers})


	# Get modified content.json files since
	def actionListModified(self, params):
		site = self.sites.get(params["site"])
		if not site or not site.settings["serving"]: # Site unknown or not serving
			self.response({"error": "Unknown site"})
			return False
		modified_files = {inner_path: content["modified"] for inner_path, content in site.content_manager.contents.iteritems() if content["modified"] > params["since"]}

		# Add peer to site if not added before
		connected_peer = site.addPeer(self.connection.ip, self.connection.port)
		if connected_peer: # Just added
			connected_peer.connect(self.connection) # Assign current connection to peer

		self.response({"modified_files": modified_files})



	# Send a simple Pong! answer
	def actionPing(self):
		self.response("Pong!")


	# Unknown command
	def actionUnknown(self, cmd, params):
		self.response({"error": "Unknown command: %s" % cmd})

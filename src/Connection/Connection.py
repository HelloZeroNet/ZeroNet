import logging, socket, time
from cStringIO import StringIO
import gevent, msgpack
from Config import config
from Debug import Debug
from util import StreamingMsgpack

class Connection(object):
	__slots__ = ("sock", "ip", "port", "peer_id", "id", "protocol", "type", "server", "unpacker", "req_id", "handshake", "connected", "event_connected", "closed", "start_time", "last_recv_time", "last_message_time", "last_send_time", "last_sent_time", "incomplete_buff_recv", "bytes_recv", "bytes_sent", "last_ping_delay", "last_req_time", "last_cmd", "name", "updateName", "waiting_requests")

	def __init__(self, server, ip, port, sock=None):
		self.sock = sock
		self.ip = ip
		self.port = port
		self.peer_id = None # Bittorrent style peer id (not used yet)
		self.id = server.last_connection_id
		server.last_connection_id += 1
		self.protocol = "?"
		self.type = "?"

		self.server = server
		self.unpacker = None # Stream incoming socket messages here
		self.req_id = 0 # Last request id
		self.handshake = {} # Handshake info got from peer
		self.connected = False
		self.event_connected = gevent.event.AsyncResult() # Solves on handshake received
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

		self.waiting_requests = {} # Waiting sent requests


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
		# Detect protocol
		self.send({"cmd": "handshake", "req_id": 0, "params": self.handshakeInfo()})
		gevent.spawn(self.messageLoop)
		return self.event_connected.get() # Wait for handshake



	# Handle incoming connection
	def handleIncomingConnection(self, sock):
		self.type = "in"
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
		sock = self.sock
		try:
			while True:
				buff = sock.recv(16*1024)
				if not buff: break # Connection closed
				self.last_recv_time = time.time()
				self.incomplete_buff_recv += 1
				self.bytes_recv += len(buff)
				self.server.bytes_recv += len(buff)
				if not self.unpacker: 
					self.unpacker = msgpack.Unpacker()
				self.unpacker.feed(buff)
				for message in self.unpacker:
					self.incomplete_buff_recv = 0
					self.handleMessage(message)
				message = None
				buff = None
		except Exception, err:
			if not self.closed: self.log("Socket error: %s" % Debug.formatException(err))
		self.close() # MessageLoop ended, close connection


	# My handshake info
	def handshakeInfo(self):
		return {
			"version": config.version, 
			"protocol": "v2", 
			"peer_id": self.server.peer_id,
			"fileserver_port": config.fileserver_port,
			"port_opened": self.server.port_opened,
			"rev": config.rev
		}


	# Handle incoming message
	def handleMessage(self, message):
		self.last_message_time = time.time()
		if message.get("cmd") == "response": # New style response
			if message["to"] in self.waiting_requests:
				self.waiting_requests[message["to"]].set(message) # Set the response to event
				del self.waiting_requests[message["to"]]
			elif message["to"] == 0: # Other peers handshake
				ping = time.time()-self.start_time
				if config.debug_socket: self.log("Got handshake response: %s, ping: %s" % (message, ping))
				self.last_ping_delay = ping
				self.handshake = message
				if self.handshake.get("port_opened", None) == False: # Not connectable
					self.port = 0
				else:
					self.port = message["fileserver_port"] # Set peer fileserver port
				self.event_connected.set(True) # Mark handshake as done
			else:
				self.log("Unknown response: %s" % message)
		elif message.get("cmd"): # Handhsake request
			if message["cmd"] == "handshake":
				self.handshake = message["params"]
				if self.handshake.get("port_opened", None) == False: # Not connectable
					self.port = 0
				else:
					self.port = self.handshake["fileserver_port"] # Set peer fileserver port
				self.event_connected.set(True) # Mark handshake as done
				if config.debug_socket: self.log("Handshake request: %s" % message)
				data = self.handshakeInfo()
				data["cmd"] = "response"
				data["to"] = message["req_id"]
				self.send(data)
			else:
				self.server.handleRequest(self, message)
		else: # Old style response, no req_id definied
			if config.debug_socket: self.log("Old style response, waiting: %s" % self.waiting_requests.keys())
			last_req_id = min(self.waiting_requests.keys()) # Get the oldest waiting request and set it true
			self.waiting_requests[last_req_id].set(message)
			del self.waiting_requests[last_req_id] # Remove from waiting request



	# Send data to connection
	def send(self, message, streaming=False):
		if config.debug_socket: self.log("Send: %s, to: %s, streaming: %s, site: %s, inner_path: %s, req_id: %s" % (message.get("cmd"), message.get("to"), streaming, message.get("params", {}).get("site"), message.get("params", {}).get("inner_path"), message.get("req_id")))
		self.last_send_time = time.time()
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
		self.last_sent_time = time.time()
		return True


	# Create and send a request to peer
	def request(self, cmd, params={}):
		if self.waiting_requests and self.protocol == "v2" and time.time() - max(self.last_req_time, self.last_recv_time) > 10: # Last command sent more than 10 sec ago, timeout
			self.log("Request %s timeout: %s" % (self.last_cmd, time.time() - self.last_send_time))
			self.close()
			return False

		self.last_req_time = time.time()
		self.last_cmd = cmd
		self.req_id += 1
		data = {"cmd": cmd, "req_id": self.req_id, "params": params}
		event = gevent.event.AsyncResult() # Create new event for response
		self.waiting_requests[self.req_id] = event
		self.send(data) # Send request
		res = event.get() # Wait until event solves
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
			self.last_ping_delay = time.time()-s
			return True
		else:
			return False
		

	# Close connection
	def close(self):
		if self.closed: return False # Already closed
		self.closed = True
		self.connected = False
		self.event_connected.set(False)
		
		if config.debug_socket: self.log("Closing connection, waiting_requests: %s, buff: %s..." % (len(self.waiting_requests), self.incomplete_buff_recv))
		for request in self.waiting_requests.values(): # Mark pending requests failed
			request.set(False)
		self.waiting_requests = {}
		self.server.removeConnection(self) # Remove connection from server registry
		try:
			if self.sock:
				self.sock.shutdown(gevent.socket.SHUT_WR)
				self.sock.close()
		except Exception, err:
			if config.debug_socket: self.log("Close error: %s" % err)

		# Little cleanup
		self.sock = None
		self.unpacker = None

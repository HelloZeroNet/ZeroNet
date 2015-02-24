import logging, socket, time
from cStringIO import StringIO
import gevent, msgpack
from Config import config
from Debug import Debug
try:
	import zmq.green as zmq
except:
	zmq = None

class Connection:
	def __init__(self, server, ip, port, sock=None):
		self.sock = sock
		self.ip = ip
		self.port = port
		self.peer_id = None # Bittorrent style peer id (not used yet)
		self.id = server.last_connection_id
		self.protocol = "?"
		server.last_connection_id += 1

		self.server = server
		self.log = logging.getLogger(str(self))
		self.unpacker = msgpack.Unpacker() # Stream incoming socket messages here
		self.req_id = 0 # Last request id
		self.handshake = None # Handshake info got from peer
		self.event_handshake = gevent.event.AsyncResult() # Solves on handshake received
		self.closed = False

		self.zmq_sock = None # Zeromq sock if outgoing connection
		self.zmq_queue = [] # Messages queued to send
		self.zmq_working = False # Zmq currently working, just add to queue
		self.forward_thread = None # Zmq forwarder thread

		self.waiting_requests = {} # Waiting sent requests
		if not sock: self.connect() # Not an incoming connection, connect to peer


	def __str__(self):
		return "Conn#%2s %-12s [%s]" % (self.id, self.ip, self.protocol)

	def __repr__(self):
		return "<%s>" % self.__str__()


	# Open connection to peer and wait for handshake
	def connect(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
		self.sock.connect((self.ip, self.port)) 
		# Detect protocol
		self.send({"cmd": "handshake", "req_id": 0, "params": self.handshakeInfo()})
		gevent.spawn(self.messageLoop)
		return self.event_handshake.get() # Wait for handshake



	# Handle incoming connection
	def handleIncomingConnection(self, sock):
		firstchar = sock.recv(1) # Find out if pure socket or zeromq
		if firstchar == "\xff": # Backward compatiblity: forward data to zmq
			if config.debug_socket: self.log.debug("Fallback incoming connection to ZeroMQ")

			self.protocol = "zeromq"
			self.log.name = str(self)
			self.event_handshake.set(self.protocol)

			if self.server.zmq_running: 
				zmq_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
				zmq_sock.connect(("127.0.0.1", self.server.zmq_port)) 
				zmq_sock.send(firstchar)
				
				self.forward_thread = gevent.spawn(self.server.forward, self, zmq_sock, sock)
				self.server.forward(self, sock, zmq_sock)
				self.close() # Forward ended close connection
			else:
				self.config.debug("ZeroMQ Server not running, exiting!")
		else: # Normal socket
			self.messageLoop(firstchar)


	# Message loop for connection
	def messageLoop(self, firstchar=None):
		sock = self.sock
		if not firstchar: firstchar = sock.recv(1)
		if firstchar == "\xff": # Backward compatibility to zmq
			self.sock.close() # Close normal socket
			if zmq:
				if config.debug_socket: self.log.debug("Connecting as ZeroMQ")
				self.protocol = "zeromq"
				self.log.name = str(self)
				self.event_handshake.set(self.protocol) # Mark handshake as done

				try:
					context = zmq.Context()
					zmq_sock = context.socket(zmq.REQ) 
					zmq_sock.hwm = 1
					zmq_sock.setsockopt(zmq.RCVTIMEO, 50000) # Wait for data arrive
					zmq_sock.setsockopt(zmq.SNDTIMEO, 5000) # Wait for data send
					zmq_sock.setsockopt(zmq.LINGER, 500) # Wait for zmq_sock close
					zmq_sock.connect('tcp://%s:%s' % (self.ip, self.port))
					self.zmq_sock = zmq_sock
				except Exception, err:
					self.log.debug("Socket error: %s" % Debug.formatException(err))
			else:
				return False # No zeromq connection supported
		else: # Normal socket
			self.protocol = "v2"
			self.log.name = str(self)
			self.event_handshake.set(self.protocol) # Mark handshake as done

			unpacker = self.unpacker
			unpacker.feed(firstchar) # Feed the first char we already requested
			try:
				while True:
					buff = sock.recv(16*1024)
					if not buff: break # Connection closed
					unpacker.feed(buff)
					for message in unpacker:
						self.handleMessage(message)
			except Exception, err:
				self.log.debug("Socket error: %s" % Debug.formatException(err))
			self.close() # MessageLoop ended, close connection


	# Read one line (not used)
	def recvLine(self):
		sock = self.sock
		data = sock.recv(16*1024)
		if not data: return
		if not data.endswith("\n"): # Multipart, read until \n
			buff = StringIO()
			buff.write(data)
			while not data.endswith("\n"):
				data = sock.recv(16*1024)
				if not data: break
				buff.write(data)
			return buff.getvalue().strip("\n")

		return data.strip("\n")


	# My handshake info
	def handshakeInfo(self):
		return {
			"version": config.version, 
			"protocol": "v2", 
			"peer_id": self.server.peer_id,
			"fileserver_port": config.fileserver_port
		}


	# Handle incoming message
	def handleMessage(self, message):
		if message.get("cmd") == "response": # New style response
			if message["to"] in self.waiting_requests:
				self.waiting_requests[message["to"]].set(message) # Set the response to event
				del self.waiting_requests[message["to"]]
			elif message["to"] == 0: # Other peers handshake
				if config.debug_socket: self.log.debug("Got handshake response: %s" % message)
				self.handshake = message
				self.port = message["fileserver_port"] # Set peer fileserver port
			else:
				self.log.debug("Unknown response: %s" % message)
		elif message.get("cmd"): # Handhsake request
			if message["cmd"] == "handshake":
				self.handshake = message["params"]
				self.port = self.handshake["fileserver_port"] # Set peer fileserver port
				if config.debug_socket: self.log.debug("Handshake request: %s" % message)
				data = self.handshakeInfo()
				data["cmd"] = "response"
				data["to"] = message["req_id"]
				self.send(data)
			else:
				self.server.handleRequest(self, message)
		else: # Old style response, no req_id definied
			if config.debug_socket: self.log.debug("Old style response, waiting: %s" % self.waiting_requests.keys())
			last_req_id = min(self.waiting_requests.keys()) # Get the oldest waiting request and set it true
			self.waiting_requests[last_req_id].set(message)
			del self.waiting_requests[last_req_id] # Remove from waiting request



	# Send data to connection
	def send(self, data):
		if config.debug_socket: self.log.debug("Send: %s" % data.get("cmd"))
		if self.protocol == "zeromq":
			if self.zmq_sock: # Outgoing connection
				self.zmq_queue.append(data)
				if self.zmq_working: 
					self.log.debug("ZeroMQ already working...")
					return
				while self.zmq_queue:
					self.zmq_working = True
					data = self.zmq_queue.pop(0)
					self.zmq_sock.send(msgpack.packb(data))
					self.handleMessage(msgpack.unpackb(self.zmq_sock.recv()))
					self.zmq_working = False

			else: # Incoming request
				self.server.zmq_sock.send(msgpack.packb(data))
		else: # Normal connection
			self.sock.sendall(msgpack.packb(data))


	# Create and send a request to peer
	def request(self, cmd, params={}):
		self.req_id += 1
		data = {"cmd": cmd, "req_id": self.req_id, "params": params}
		event = gevent.event.AsyncResult() # Create new event for response
		self.waiting_requests[self.req_id] = event
		self.send(data) # Send request
		res = event.get() # Wait until event solves

		return res
		

	# Close connection
	def close(self):
		if self.closed: return False # Already closed
		self.closed = True
		if config.debug_socket: self.log.debug("Closing connection, waiting_requests: %s..." % len(self.waiting_requests))
		for request in self.waiting_requests.values(): # Mark pending requests failed
			request.set(False)
		self.waiting_requests = {}
		self.server.removeConnection(self) # Remove connection from server registry
		try:
			if self.forward_thread:
				self.forward_thread.kill(exception=Debug.Notify("Closing connection"))
			if self.zmq_sock:
				self.zmq_sock.close()
			if self.sock:
				self.sock.shutdown(gevent.socket.SHUT_WR)
				self.sock.close()
		except Exception, err:
			if config.debug_socket: self.log.debug("Close error: %s" % Debug.formatException(err))

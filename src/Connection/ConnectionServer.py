from gevent.server import StreamServer
from gevent.pool import Pool
import socket, os, logging, random, string
import gevent, msgpack
import cStringIO as StringIO
from Debug import Debug
from Connection import Connection
from Config import config


class ConnectionServer:
	def __init__(self, ip=None, port=None, request_handler=None):
		self.ip = ip
		self.port = port
		self.last_connection_id = 1 # Connection id incrementer
		self.log = logging.getLogger(__name__)
		
		self.connections = [] # Connections
		self.ips = {} # Connection by ip
		self.peer_ids = {} # Connections by peer_ids

		self.running = True
		self.zmq_running = False
		self.zmq_last_connection = None # Last incoming message client

		self.peer_id = "-ZN0"+config.version.replace(".", "")+"-"+''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(12)) # Bittorrent style peerid
		
		if port: # Listen server on a port
			self.zmq_port = port-1
			self.pool = Pool(1000) # do not accept more than 1000 connections
			self.stream_server = StreamServer((ip.replace("*", ""), port), self.handleIncomingConnection, spawn=self.pool, backlog=100)
			if request_handler: self.handleRequest = request_handler
			gevent.spawn(self.zmqServer) # Start ZeroMQ server for backward compatibility



	def start(self):
		self.running = True
		try:
			self.log.debug("Binding to: %s:%s" % (self.ip, self.port))
			self.stream_server.serve_forever() # Start normal connection server
		except Exception, err:
			self.log.info("StreamServer bind error, must be running already: %s" % err)


	def stop(self):
		self.running = False
		self.stream_server.stop() 


	def handleIncomingConnection(self, sock, addr):
		ip, port = addr
		connection = Connection(self, ip, port, sock)
		self.connections.append(connection)
		self.ips[ip] = connection
		connection.handleIncomingConnection(sock)



	def connect(self, ip=None, port=None, peer_id=None):
		if peer_id and peer_id in self.peer_ids: # Find connection by peer id
			return self.peer_ids.get(peer_id)
		if ip in self.ips: # Find connection by ip
			return self.ips[ip]
		# No connection found yet
		try:
			connection = Connection(self, ip, port)
			self.ips[ip] = connection
			self.connections.append(connection)
		except Exception, err:
			self.log.debug("%s Connect error: %s" % (ip, Debug.formatException(err)))
			raise err
		return connection



	def removeConnection(self, connection):
		if self.ips.get(connection.ip) == connection: # Delete if same as in registry
			del self.ips[connection.ip]
		if connection in self.connections:
			self.connections.remove(connection)
		if connection.peer_id and self.peer_ids.get(connection.peer_id) == connection: # Delete if same as in registry
			del self.peer_ids[connection.peer_id]


	def zmqServer(self):
		self.log.debug("Starting ZeroMQ on: tcp://127.0.0.1:%s..." % self.zmq_port)
		try:
			import zmq.green as zmq
			context = zmq.Context()
			self.zmq_sock = context.socket(zmq.REP)
			self.zmq_sock.bind("tcp://127.0.0.1:%s" % self.zmq_port)
			self.zmq_sock.hwm = 1
			self.zmq_sock.setsockopt(zmq.RCVTIMEO, 5000) # Wait for data receive
			self.zmq_sock.setsockopt(zmq.SNDTIMEO, 50000) # Wait for data send
			self.zmq_running = True
		except Exception, err:
			self.log.debug("ZeroMQ start error: %s" % Debug.formatException(err))
			return False

		while True:
			try:
				data = self.zmq_sock.recv()
				if not data: break
				message = msgpack.unpackb(data)
				self.zmq_last_connection.handleMessage(message)
			except Exception, err:
				self.log.debug("ZMQ Server error: %s" % Debug.formatException(err))
				self.zmq_sock.send(msgpack.packb({"error": "%s" % err}, use_bin_type=True))


	# Forward incoming data to other socket
	def forward(self, connection, source, dest):
		data = True
		try:
			while data:
				data = source.recv(16*1024)
				self.zmq_last_connection = connection
				if data:
					dest.sendall(data)
				else:
					source.shutdown(socket.SHUT_RD)
					dest.shutdown(socket.SHUT_WR)
		except Exception, err:
			self.log.debug("%s ZMQ forward error: %s" % (connection.ip, Debug.formatException(err)))
		connection.close()


# -- TESTING --

def testCreateServer():
	global server
	server = ConnectionServer("127.0.0.1", 1234, testRequestHandler)
	server.start()


def testRequestHandler(connection, req):
	print req
	if req["cmd"] == "Bigdata":
		connection.send({"res": "HelloWorld"*1024})
	else:
		connection.send({"res": "pong"})


def testClient(num):
	time.sleep(1)
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
	s.connect(("localhost", 1234)) 
	for i in range(10):
		print "[C%s] send..." % num
		s.sendall(msgpack.packb({"cmd": "[C] Ping"}))
		print "[C%s] recv..." % num
		print "[C%s] %s" % (num, repr(s.recv(1024)))
		time.sleep(1)


def testSlowClient(num):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
	s.connect(("localhost", 1234)) 
	for i in range(1):
		print "[C%s] send..." % num
		s.sendall(msgpack.packb({"cmd": "Bigdata"}))
		print "[C%s] recv..." % num
		gevent.spawn_later(1, lambda s: s.send(msgpack.packb({"cmd": "[Z] Ping"})), s)
		while 1:
			data = s.recv(1000)
			if not data: break
			print "[C%s] %s" % (num, data)
			time.sleep(1)
			#s.sendall(msgpack.packb({"cmd": "[C] Ping"}))


def testZmqClient(num):
	import zmq.green as zmq
	c = zmq.Context(1)
	for i in range(10):
		s = c.socket(zmq.REQ)
		s.connect('tcp://127.0.0.1:1234')
		print "[Z%s] send..." % num
	 	s.send(msgpack.packb({"cmd": "[Z] Ping %s" % i}))
	 	print "[Z%s] recv..." % num
		print "[Z%s] %s" % (num, s.recv(1024))
		s.close()
		time.sleep(1)


def testZmqSlowClient(num):
	import zmq.green as zmq
	c = zmq.Context(1)
	s = c.socket(zmq.REQ)
	for i in range(1):
		s.connect('tcp://127.0.0.1:1234')
		print "[Z%s] send..." % num
	 	s.send(msgpack.packb({"cmd": "Bigdata"}))
	 	print "[Z%s] recv..." % num
	 	#gevent.spawn_later(1, lambda s: s.send(msgpack.packb({"cmd": "[Z] Ping"})), s)
		while 1:
			data = s.recv(1024*1024)
			if not data: break
			print "[Z%s] %s" % (num, data)
			time.sleep(1)
			s.send(msgpack.packb({"cmd": "[Z] Ping"}))


def testConnection():
	global server
	connection = server.connect("127.0.0.1", 1234)
	connection.send({"res": "Sending: Hello!"})
	print connection


def greenletsNum():
	from greenlet import greenlet
	import gc
	while 1:
		print len([ob for ob in gc.get_objects() if isinstance(ob, greenlet)])
		time.sleep(1)

if __name__ == "__main__":
	from gevent import monkey; monkey.patch_all(thread=False)
	import sys, time
	logging.getLogger().setLevel(logging.DEBUG)

	gevent.spawn(testZmqClient, 1)
	gevent.spawn(greenletsNum)
	#gevent.spawn(testClient, 1)
	#gevent.spawn_later(1, testConnection)
	print "Running server..."
	server = None
	testCreateServer()


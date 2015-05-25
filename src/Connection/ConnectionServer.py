from gevent.server import StreamServer
from gevent.pool import Pool
import socket, os, logging, random, string, time
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
		self.log = logging.getLogger("ConnServer")
		self.port_opened = None
		
		self.connections = [] # Connections
		self.ips = {} # Connection by ip
		self.peer_ids = {} # Connections by peer_ids

		self.running = True
		self.thread_checker = gevent.spawn(self.checkConnections)

		self.bytes_recv = 0
		self.bytes_sent = 0

		self.peer_id = "-ZN0"+config.version.replace(".", "")+"-"+''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(12)) # Bittorrent style peerid

		# Check msgpack version
		if msgpack.version[0] == 0 and msgpack.version[1] < 4:
			self.log.error("Error: Too old msgpack version: %s (>0.4.0 required), please update using `sudo pip install msgpack-python --upgrade`" % str(msgpack.version))
			import sys
			sys.exit(0)

		if port: # Listen server on a port
			self.pool = Pool(1000) # do not accept more than 1000 connections
			self.stream_server = StreamServer((ip.replace("*", ""), port), self.handleIncomingConnection, spawn=self.pool, backlog=100)
			if request_handler: self.handleRequest = request_handler



	def start(self):
		self.running = True
		try:
			self.log.debug("Binding to: %s:%s (msgpack: %s)" % (self.ip, self.port, ".".join(map(str, msgpack.version))))
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



	def getConnection(self, ip=None, port=None, peer_id=None, create=True):
		if peer_id and peer_id in self.peer_ids: # Find connection by peer id
			connection = self.peer_ids.get(peer_id)
			if not connection.connected and create: 
				succ = connection.event_connected.get() # Wait for connection
				if not succ: raise Exception("Connection event return error")
			return connection
		# Find connection by ip
		if ip in self.ips: 
			connection = self.ips[ip]
			if not connection.connected and create: 
				succ = connection.event_connected.get() # Wait for connection
				if not succ: raise Exception("Connection event return error")
			return connection
		# Recover from connection pool
		for connection in self.connections:
			if connection.ip == ip: 
				if not connection.connected and create: 
					succ = connection.event_connected.get() # Wait for connection
					if not succ: raise Exception("Connection event return error")
				return connection

		# No connection found
		if create: # Allow to create new connection if not found
			if port == 0:
				raise Exception("This peer is not connectable")
			try:
				connection = Connection(self, ip, port)
				self.ips[ip] = connection
				self.connections.append(connection)
				succ = connection.connect()
				if not succ:
					connection.close()
					raise Exception("Connection event return error")

			except Exception, err:
				self.log.debug("%s Connect error: %s" % (ip, Debug.formatException(err)))
				connection.close()
				raise err
			return connection
		else:
			return None



	def removeConnection(self, connection):
		self.log.debug("Removing %s..." % connection)
		if self.ips.get(connection.ip) == connection: # Delete if same as in registry
			del self.ips[connection.ip]
		if connection.peer_id and self.peer_ids.get(connection.peer_id) == connection: # Delete if same as in registry
			del self.peer_ids[connection.peer_id]
		if connection in self.connections:
			self.connections.remove(connection)



	def checkConnections(self):
		while self.running:
			time.sleep(60) # Sleep 1 min
			for connection in self.connections[:]: # Make a copy
				idle = time.time() - max(connection.last_recv_time, connection.start_time, connection.last_message_time)

				if connection.unpacker and idle > 30: # Delete the unpacker if not needed
					del connection.unpacker
					connection.unpacker = None
					connection.log("Unpacker deleted")

				if idle > 60*60: # Wake up after 1h
					connection.log("[Cleanup] After wakeup, idle: %s" % idle)
					connection.close()

				elif idle > 20*60 and connection.last_send_time < time.time()-10: # Idle more than 20 min and we not send request in last 10 sec
					if not connection.ping(): # send ping request
						connection.close()

				elif idle > 10 and connection.incomplete_buff_recv > 0: # Incompelte data with more than 10 sec idle
					connection.log("[Cleanup] Connection buff stalled")
					connection.close()

				elif idle > 10 and connection.waiting_requests and time.time() - connection.last_send_time > 10: # Sent command and no response in 10 sec
					connection.log("[Cleanup] Command %s timeout: %s" % (connection.last_cmd, time.time() - connection.last_send_time))
					connection.close()

				elif idle > 60 and connection.protocol == "?": # No connection after 1 min
					connection.log("[Cleanup] Connect timeout: %s" % idle)
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
	connection = server.getConnection("127.0.0.1", 1234)
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


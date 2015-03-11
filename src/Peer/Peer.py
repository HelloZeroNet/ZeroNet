import os, logging, gevent, time, msgpack, sys
import zmq.green as zmq
from cStringIO import StringIO
from Config import config
from Debug import Debug

# Communicate remote peers
class Peer:
	def __init__(self, ip, port, site=None):
		self.ip = ip
		self.port = port
		self.site = site
		self.key = "%s:%s" % (ip, port)
		self.log = None
		self.connection_server = sys.modules["src.main"].file_server

		self.connection = None
		self.last_found = None # Time of last found in the torrent tracker
		self.last_response = None # Time of last successfull response from peer
		self.last_ping = None # Last response time for ping
		self.added = time.time()

		self.connection_error = 0 # Series of connection error
		self.hash_failed = 0 # Number of bad files from peer
		self.download_bytes = 0 # Bytes downloaded
		self.download_time = 0 # Time spent to download


	# Connect to host
	def connect(self):
		if not self.log: self.log = logging.getLogger("Peer:%s:%s %s" % (self.ip, self.port, self.site.address_short))
		if self.connection: 
			self.log.debug("Getting connection (Closing %s)..." % self.connection)
			self.connection.close()
		else:
			self.log.debug("Getting connection...")
			
		self.connection = None

		try:
			self.connection = self.connection_server.getConnection(self.ip, self.port)
		except Exception, err:
			self.log.debug("Getting connection error: %s (connection_error: %s, hash_failed: %s)" % (Debug.formatException(err), self.connection_error, self.hash_failed))
			
	def __str__(self):
		return "Peer %-12s" % self.ip

	def __repr__(self):
		return "<%s>" % self.__str__() 

	# Found a peer on tracker
	def found(self):
		self.last_found = time.time()


	# Send a command to peer
	def request(self, cmd, params = {}):
		if not self.connection or self.connection.closed: 
			self.connect()
			if not self.connection: 
				self.onConnectionError()
				return None # Connection failed

		#if cmd != "ping" and self.last_response and time.time() - self.last_response > 20*60: # If last response if older than 20 minute, ping first to see if still alive
		#	if not self.ping(): return None

		for retry in range(1,3): # Retry 3 times
			#if config.debug_socket: self.log.debug("sendCmd: %s %s" % (cmd, params.get("inner_path")))
			try:
				response = self.connection.request(cmd, params)
				if not response: raise Exception("Send error")
				#if config.debug_socket: self.log.debug("Got response to: %s" % cmd)
				if "error" in response:
					self.log.debug("%s error: %s" % (cmd, response["error"]))
					self.onConnectionError()
				else: # Successful request, reset connection error num
					self.connection_error = 0
				self.last_response = time.time()
				return response
			except Exception, err:
				if type(err).__name__ == "Notify": # Greenlet kill by worker
					self.log.debug("Peer worker got killed: %s, aborting cmd: %s" % (err.message, cmd))
					break
				else:
					self.onConnectionError()
					self.log.debug("%s (connection_error: %s, hash_failed: %s, retry: %s)" % (Debug.formatException(err), self.connection_error, self.hash_failed, retry))
					time.sleep(1*retry)
					self.connect()
		return None # Failed after 4 retry


	# Get a file content from peer
	def getFile(self, site, inner_path):
		location = 0
		buff = StringIO()
		s = time.time()
		while 1: # Read in 512k parts
			back = self.request("getFile", {"site": site, "inner_path": inner_path, "location": location}) # Get file content from last location
			if not back or "body" not in back: # Error
				return False

			buff.write(back["body"])
			if back["location"] == back["size"]: # End of file
				break
			else:
				location = back["location"]
		self.download_bytes += back["location"]
		self.download_time += (time.time() - s)
		buff.seek(0)
		return buff


	# Send a ping request
	def ping(self):
		response_time = None
		for retry in range(1,3): # Retry 3 times
			s = time.time()
			with gevent.Timeout(10.0, False): # 10 sec timeout, dont raise exception
				response = self.request("ping")

				if response and "body" in response and response["body"] == "Pong!":
					response_time = time.time()-s
					break # All fine, exit from for loop
			# Timeout reached or bad response
			self.onConnectionError()
			self.connect()
			time.sleep(1)

		if response_time:
			self.log.debug("Ping: %.3f" % response_time)
		else:
			self.log.debug("Ping failed")
		self.last_ping = response_time
		return response_time


	# Stop and remove from site
	def remove(self):
		self.log.debug("Removing peer...Connection error: %s, Hash failed: %s" % (self.connection_error, self.hash_failed))
		if self.key in self.site.peers: del(self.site.peers[self.key])
		if self.connection:
			self.connection.close()


	# - EVENTS -

	# On connection error
	def onConnectionError(self):
		self.connection_error += 1
		if self.connection_error >= 3: # Dead peer
			self.remove()


	# Done working with peer
	def onWorkerDone(self):
		pass

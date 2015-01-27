import os, logging, gevent, time, msgpack
import zmq.green as zmq
from cStringIO import StringIO
from Config import config
from Debug import Debug

context = zmq.Context()

# Communicate remote peers
class Peer:
	def __init__(self, ip, port, site):
		self.ip = ip
		self.port = port
		self.site = site
		self.key = "%s:%s" % (ip, port)
		self.log = None

		self.socket = None
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
		if not self.log: self.log = logging.getLogger("Peer:%s:%s" % (self.ip, self.port))
		if self.socket: self.socket.close()

		self.socket = context.socket(zmq.REQ)
		self.socket.setsockopt(zmq.SNDTIMEO, 5000) # Wait for data send
		self.socket.setsockopt(zmq.LINGER, 500) # Wait for socket close
		#self.socket.setsockopt(zmq.TCP_KEEPALIVE, 1) # Enable keepalive
		#self.socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 4*60) # Send after 4 minute idle
		#self.socket.setsockopt(zmq.TCP_KEEPALIVE_INTVL, 15) # Wait 15 sec to response
		#self.socket.setsockopt(zmq.TCP_KEEPALIVE_CNT, 4) # 4 Probes
		self.socket.connect('tcp://%s:%s' % (self.ip, self.port))


	# Found a peer on tracker
	def found(self):
		self.last_found = time.time()


	# Send a command to peer
	def sendCmd(self, cmd, params = {}):
		if not self.socket: self.connect()
		if cmd != "ping" and self.last_response and time.time() - self.last_response > 20*60: # If last response if older than 20 minute, ping first to see if still alive
			if not self.ping(): return None

		for retry in range(1,3): # Retry 3 times
			if config.debug_socket: self.log.debug("sendCmd: %s" % cmd)
			try:
				self.socket.send(msgpack.packb({"cmd": cmd, "params": params}, use_bin_type=True))
				if config.debug_socket: self.log.debug("Sent command: %s" % cmd)
				response = msgpack.unpackb(self.socket.recv())
				if config.debug_socket: self.log.debug("Got response to: %s" % cmd)
				if "error" in response:
					self.log.debug("%s error: %s" % (cmd, response["error"]))
					self.onConnectionError()
				else: # Successful request, reset connection error num
					self.connection_error = 0
				self.last_response = time.time()
				return response
			except Exception, err:
				self.onConnectionError()
				self.log.debug("%s (connection_error: %s, hash_failed: %s, retry: %s)" % (Debug.formatException(err), self.connection_error, self.hash_failed, retry))
				time.sleep(1*retry)
				self.connect()
				if type(err).__name__ == "Notify" and err.message == "Worker stopped": # Greenlet kill by worker
					self.log.debug("Peer worker got killed, aborting cmd: %s" % cmd)
					break
		return None # Failed after 4 retry


	# Get a file content from peer
	def getFile(self, site, inner_path):
		location = 0
		buff = StringIO()
		s = time.time()
		while 1: # Read in 512k parts
			back = self.sendCmd("getFile", {"site": site, "inner_path": inner_path, "location": location}) # Get file content from last location
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
				response = self.sendCmd("ping")
				if response and "body" in response and response["body"] == "Pong!":
					response_time = time.time()-s
					break # All fine, exit from for loop
			# Timeout reached or bad response
			self.onConnectionError()
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
		self.socket.close()


	# - EVENTS -

	# On connection error
	def onConnectionError(self):
		self.connection_error += 1
		if self.connection_error >= 5: # Dead peer
			self.remove()


	# Done working with peer
	def onWorkerDone(self):
		pass

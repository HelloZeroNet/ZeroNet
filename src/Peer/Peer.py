import os, logging, gevent, time, msgpack
import zmq.green as zmq
from cStringIO import StringIO
from Config import config

context = zmq.Context()

# Communicate remote peers
class Peer:
	def __init__(self, ip, port, site):
		self.ip = ip
		self.port = port
		self.site = site
		self.socket = None
		self.last_found = None
		self.added = time.time()

		self.connection_error = 0
		self.hash_failed = 0
		self.download_bytes = 0
		self.download_time = 0


	# Connect to host
	def connect(self):
		self.log = logging.getLogger("Peer:%s:%s" % (self.ip, self.port))
		self.socket = context.socket(zmq.REQ)
		self.socket.setsockopt(zmq.SNDTIMEO, 5000) # Wait for data send
		self.socket.setsockopt(zmq.LINGER, 500) # Wait for socket close
		self.socket.connect('tcp://%s:%s' % (self.ip, self.port))


	# Found a peer on tracker
	def found(self):
		self.last_found = time.time()


	# Send a command to peer
	def sendCmd(self, cmd, params = {}):
		if not self.socket: self.connect()
		try:
			self.socket.send(msgpack.packb({"cmd": cmd, "params": params}, use_bin_type=True))
			response = msgpack.unpackb(self.socket.recv())
			if "error" in response:
				self.log.debug("%s %s error: %s" % (cmd, params, response["error"]))
			else: # Successful request, reset connection error num
				self.connection_error = 0
			return response
		except Exception, err:
			self.onConnectionError()
			self.log.error("%s" % err)
			if config.debug:
				import traceback
				traceback.print_exc()
			self.socket.close()
			time.sleep(1)
			self.connect()
			return None


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
		return self.sendCmd("ping")


	# Stop and remove from site
	def remove(self):
		self.log.debug("Removing peer...Connection error: %s, Hash failed: %s" % (self.connection_error, self.hash_failed))
		del(self.site.peers[self.key])
		self.socket.close()


	# - EVENTS -

	# On connection error
	def onConnectionError(self):
		self.connection_error += 1
		if self.connection_error > 5: # Dead peer
			self.remove()


	# Done working with peer
	def onWorkerDone(self):
		pass

import os, logging, gevent, time, msgpack
import zmq.green as zmq
from cStringIO import StringIO
from Config import config

context = zmq.Context()

# Communicate remote peers
class Peer:
	def __init__(self, ip, port):
		self.ip = ip
		self.port = port
		self.socket = None
		self.last_found = None
		self.added = time.time()

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


	# Done working with peer
	def disconnect(self):
		pass


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
				self.log.error("%s %s error: %s" % (cmd, params, response["error"]))
			return response
		except Exception, err:
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
			if "body" not in back: # Error
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

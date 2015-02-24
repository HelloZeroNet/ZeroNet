import time, socket, msgpack
from cStringIO import StringIO

print "Connecting..."
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
sock.connect(("localhost", 1234)) 


print "1 Threaded: Send, receive 10000 ping request...",
s = time.time()
for i in range(10000):
	sock.sendall(msgpack.packb({"cmd": "Ping"}))
	req = sock.recv(16*1024)
print time.time()-s, repr(req), time.time()-s


print "1 Threaded: Send, receive, decode 10000 ping request...",
s = time.time()
unpacker = msgpack.Unpacker()
reqs = 0
for i in range(10000):
	sock.sendall(msgpack.packb({"cmd": "Ping"}))
	unpacker.feed(sock.recv(16*1024))
	for req in unpacker:
		reqs += 1
print "Found:", req, "x", reqs, time.time()-s


print "1 Threaded: Send, receive, decode, reconnect 1000 ping request...",
s = time.time()
unpacker = msgpack.Unpacker()
reqs = 0
for i in range(1000):
	sock.sendall(msgpack.packb({"cmd": "Ping"}))
	unpacker.feed(sock.recv(16*1024))
	for req in unpacker:
		reqs += 1
	sock.close()
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
	sock.connect(("localhost", 1234)) 
print "Found:", req, "x", reqs, time.time()-s


print "1 Threaded: Request, receive, decode 10000 x 10k data request...",
s = time.time()
unpacker = msgpack.Unpacker()
reqs = 0
for i in range(10000):
	sock.sendall(msgpack.packb({"cmd": "Bigdata"}))

	"""buff = StringIO() 
	data = sock.recv(16*1024) 
	buff.write(data) 
	if not data: 
		break
	while not data.endswith("\n"): 
		data = sock.recv(16*1024) 
		if not data: break 
		buff.write(data) 
	req = msgpack.unpackb(buff.getvalue().strip("\n"))
	reqs += 1"""

	req_found = False
	while not req_found:
		buff = sock.recv(16*1024)
		unpacker.feed(buff)
		for req in unpacker:
			reqs += 1
			req_found = True
			break # Only process one request
print "Found:", len(req["res"]), "x", reqs, time.time()-s


print "10 Threaded: Request, receive, decode 10000 x 10k data request...",
import gevent
s = time.time()
reqs = 0
req = None
def requester():
	global reqs, req
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
	sock.connect(("localhost", 1234)) 
	unpacker = msgpack.Unpacker()
	for i in range(1000):
		sock.sendall(msgpack.packb({"cmd": "Bigdata"}))

		req_found = False
		while not req_found:
			buff = sock.recv(16*1024)
			unpacker.feed(buff)
			for req in unpacker:
				reqs += 1
				req_found = True
				break # Only process one request

threads = []
for i in range(10):
	threads.append(gevent.spawn(requester))
gevent.joinall(threads)
print "Found:", len(req["res"]), "x", reqs, time.time()-s


print "1 Threaded: ZeroMQ Send, receive 1000 ping request...",
s = time.time()
import zmq.green as zmq
c = zmq.Context()
zmq_sock = c.socket(zmq.REQ)
zmq_sock.connect('tcp://127.0.0.1:1234')
for i in range(1000):
	zmq_sock.send(msgpack.packb({"cmd": "Ping"}))
	req = zmq_sock.recv(16*1024)
print "Found:", req, time.time()-s


print "1 Threaded: ZeroMQ Send, receive 1000 x 10k data request...",
s = time.time()
import zmq.green as zmq
c = zmq.Context()
zmq_sock = c.socket(zmq.REQ)
zmq_sock.connect('tcp://127.0.0.1:1234')
for i in range(1000):
	zmq_sock.send(msgpack.packb({"cmd": "Bigdata"}))
	req = msgpack.unpackb(zmq_sock.recv(1024*1024))
print "Found:", len(req["res"]), time.time()-s


print "1 Threaded: direct ZeroMQ Send, receive 1000 x 10k data request...",
s = time.time()
import zmq.green as zmq
c = zmq.Context()
zmq_sock = c.socket(zmq.REQ)
zmq_sock.connect('tcp://127.0.0.1:1233')
for i in range(1000):
	zmq_sock.send(msgpack.packb({"cmd": "Bigdata"}))
	req = msgpack.unpackb(zmq_sock.recv(1024*1024))
print "Found:", len(req["res"]), time.time()-s
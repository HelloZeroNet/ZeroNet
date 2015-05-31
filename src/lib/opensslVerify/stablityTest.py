import opensslVerify, gevent, time
from gevent import monkey
monkey.patch_all(thread=False, ssl=False)

def test():
	data = "A"*1024
	sign = "G2Jo8dDa+jqvJipft9E3kfrAxjESWLBpVtuGIiEBCD/UUyHmRMYNqnlWeOiaHHpja5LOP+U5CanRALfOjCSYIa8="
	for i in range(2*1000):
		if i%1000 == 0:
			print i, len(data)
			#data += data+"A"
			time.sleep(0)
		pub = opensslVerify.getMessagePubkey(data, sign)

	print repr(pub), len(data)

while 1:
	s = time.time()
	gevent.joinall([gevent.spawn(test), gevent.spawn(test)])
	try:
		import psutil, os
		process = psutil.Process(os.getpid())
		print "Mem:", process.get_memory_info()[0] / float(2 ** 20)
	except:
		pass
	raw_input("finished, in %.2fs, check memory usage" % (time.time()-s))
	opensslVerify.close()
	opensslVerify.open()
	try:
		import psutil, os
		process = psutil.Process(os.getpid())
		print "Mem:", process.get_memory_info()[0] / float(2 ** 20)
	except:
		pass
	raw_input("closed and openssl, check memory again, press enter to start again")

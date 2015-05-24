import opensslVerify, gevent, time
from gevent import monkey; monkey.patch_all(thread=False, ssl=False)

def test():
	data = "A"*1024
	sign = "G2Jo8dDa+jqvJipft9E3kfrAxjESWLBpVtuGIiEBCD/UUyHmRMYNqnlWeOiaHHpja5LOP+U5CanRALfOjCSYIa8="
	for i in range(5*1000):
		if i%1000 == 0:
			print i, len(data)
			data += data+"A"
			time.sleep(0)
		pub = opensslVerify.getMessagePubkey(data, sign)

	print repr(pub), len(data)

gevent.joinall([gevent.spawn(test), gevent.spawn(test)])
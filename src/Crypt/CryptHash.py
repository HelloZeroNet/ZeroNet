import hashlib

def sha1sum(file, blocksize=65536):
	if hasattr(file, "endswith"): # Its a string open it
		file = open(file, "rb")
	hash = hashlib.sha1()
	for block in iter(lambda: file.read(blocksize), ""):
		hash.update(block)
	return hash.hexdigest()


def sha512sum(file, blocksize=65536):
	if hasattr(file, "endswith"): # Its a string open it
		file = open(file, "rb")
	hash = hashlib.sha512()
	for block in iter(lambda: file.read(blocksize), ""):
		hash.update(block)
	return hash.hexdigest()[0:64] # Truncate to 256bits is good enough


if __name__ == "__main__":
	import cStringIO as StringIO
	a = StringIO.StringIO()
	a.write("hello!")
	a.seek(0)
	print hashlib.sha1("hello!").hexdigest()
	print sha1sum(a)

	import time
	s = time.time()
	print sha1sum(open("F:\\Temp\\bigfile")),
	print time.time()-s

	s = time.time()
	print sha512sum(open("F:\\Temp\\bigfile")),
	print time.time()-s
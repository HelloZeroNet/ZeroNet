import hashlib

def sha1sum(file, blocksize=65536):
	if hasattr(file, "endswith"): # Its a string open it
		file = open(file, "rb")
	hash = hashlib.sha1()
	for block in iter(lambda: file.read(blocksize), ""):
		hash.update(block)
	return hash.hexdigest()


if __name__ == "__main__":
	import cStringIO as StringIO
	a = StringIO.StringIO()
	a.write("hello!")
	a.seek(0)
	print hashlib.sha1("hello!").hexdigest()
	print sha1sum(a)
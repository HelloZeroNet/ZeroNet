from gevent import monkey; monkey.patch_all()
import urllib, zipfile, os, ssl, httplib, socket
import cStringIO as StringIO

def update():
	# Gevent https bug workaround (https://github.com/gevent/gevent/issues/477)
	reload(socket)
	reload(httplib)
	reload(ssl)

	print "Downloading.",
	file = urllib.urlopen("https://github.com/HelloZeroNet/ZeroNet/archive/master.zip")
	data = StringIO.StringIO()
	while True:
		buff = file.read(1024*16)
		if not buff: break
		data.write(buff)
		print ".",

	print "Extracting...",
	zip = zipfile.ZipFile(data)
	for inner_path in zip.namelist():
		print ".",
		dest_path = inner_path.replace("ZeroNet-master/", "")
		if not dest_path: continue

		dest_dir = os.path.dirname(dest_path)
		if dest_dir and not os.path.isdir(dest_dir):
			os.makedirs(dest_dir)

		if dest_dir != dest_path.strip("/"):
			data = zip.read(inner_path)
			open(dest_path, 'wb').write(data)

	print "Done."


if __name__ == "__main__":
	update()
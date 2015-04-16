import urllib2, logging
import GeventSslPatch
from Config import config

def get(url):
	logging.debug("Get %s" % url)
	req = urllib2.Request(url)
	req.add_header('User-Agent', "ZeroNet %s (https://github.com/HelloZeroNet/ZeroNet)" % config.version)
	req.add_header('Accept', 'application/json')
	return urllib2.urlopen(req)


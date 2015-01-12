import json, logging, time, re, os
import gevent

TRACKERS = [
	("udp", "sugoi.pomf.se", 2710),
	("udp", "open.demonii.com", 1337), # Retry 3 times
	("udp", "open.demonii.com", 1337),
	("udp", "open.demonii.com", 1337),
	("udp", "bigfoot1942.sektori.org", 6969),
	("udp", "tracker.coppersurfer.tk", 80),
	("udp", "tracker.leechers-paradise.org", 6969),
	("udp", "tracker.blazing.de", 80),
]

# Load all sites from data/sites.json
def load():
	from Site import Site
	global sites
	if not sites: sites = {}
	address_found = []
	added = 0
	# Load new adresses
	for address in json.load(open("data/sites.json")):
		if address not in sites and os.path.isfile("data/%s/content.json" % address):
			sites[address] = Site(address)
			added += 1
		address_found.append(address)

	# Remove deleted adresses
	for address in sites.keys():
		if address not in address_found: 
			del(sites[address])
			logging.debug("Removed site: %s" % address)

	if added: logging.debug("SiteManager added %s sites" % added)


# Checks if its a valid address
def isAddress(address):
	return re.match("^[A-Za-z0-9]{34}$", address)


# Return site and start download site files
def need(address, all_file=True):
	from Site import Site
	if address not in sites: # Site not exits yet
		if not isAddress(address): raise Exception("Not address: %s" % address)
		sites[address] = Site(address)
	site = sites[address]
	if all_file: site.download()
	return site


# Lazy load sites
def list():
	if sites == None: # Not loaded yet
		load()
	return sites


sites = None
peer_blacklist = [] # Dont download from this peers
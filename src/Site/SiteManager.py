import json, logging, time, re, os
import gevent

TRACKERS = [
	("udp", "open.demonii.com", 1337),
	("udp", "sugoi.pomf.se", 2710),
	("udp", "tracker.coppersurfer.tk", 80),
	("udp", "tracker.leechers-paradise.org", 6969),
	("udp", "9.rarbg.com", 2710),
	#("udp", "www.eddie4.nl", 6969), Backup trackers
	#("udp", "trackr.sytes.net", 80),
	#("udp", "tracker4.piratux.com", 6969)
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
	return re.match("^[A-Za-z0-9]{26,35}$", address)


# Return site and start download site files
def need(address, all_file=True):
	from Site import Site
	new = False
	if address not in sites: # Site not exits yet
		if not isAddress(address): return False # Not address: %s % address
		logging.debug("Added new site: %s" % address)
		sites[address] = Site(address)
		if not sites[address].settings["serving"]: # Maybe it was deleted before
			sites[address].settings["serving"] = True
			sites[address].saveSettings()
		new = True
			
	site = sites[address]
	if all_file: site.download()
	return site


def delete(address):
	global sites
	logging.debug("SiteManager deleted site: %s" % address)
	del(sites[address])


# Lazy load sites
def list():
	if sites == None: # Not loaded yet
		load()
	return sites


sites = None
peer_blacklist = [] # Dont download from this peers
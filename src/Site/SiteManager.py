import json, logging, time, re, os
import gevent
from Plugin import PluginManager
from Config import config

TRACKERS = [
	("udp", "open.demonii.com", 1337),
	#("udp", "sugoi.pomf.se", 2710),
	#("udp", "tracker.coppersurfer.tk", 80),
	("udp", "tracker.leechers-paradise.org", 6969),
	("udp", "9.rarbg.com", 2710),
	#("udp", "www.eddie4.nl", 6969), 
	#("udp", "trackr.sytes.net", 80),
	#("udp", "tracker4.piratux.com", 6969)
	("http", "exodus.desync.com:80/announce", None), 
	("http", "tracker.aletorrenty.pl:2710/announce", None),
	#("http", "torrent.gresille.org/announce", None), # Slow
	#("http", "announce.torrentsmd.com:6969/announce", None), # Off
	#("http", "i.bandito.org/announce", None), # Off
	("http", "retracker.telecom.kz/announce", None)

]


@PluginManager.acceptPlugins
class SiteManager(object):
	def __init__(self):
		self.sites = None

	# Load all sites from data/sites.json
	def load(self):
		from Site import Site
		if not self.sites: self.sites = {}
		address_found = []
		added = 0
		# Load new adresses
		for address in json.load(open("%s/sites.json" % config.data_dir)):
			if address not in self.sites and os.path.isfile("%s/%s/content.json" % (config.data_dir, address)):
				self.sites[address] = Site(address)
				added += 1
			address_found.append(address)

		# Remove deleted adresses
		for address in self.sites.keys():
			if address not in address_found: 
				del(self.sites[address])
				logging.debug("Removed site: %s" % address)

		if added: logging.debug("SiteManager added %s sites" % added)


	# Checks if its a valid address
	def isAddress(self, address):
		return re.match("^[A-Za-z0-9]{26,35}$", address)


	# Return: Site object or None if not found
	def get(self, address):
		if self.sites == None: # Not loaded yet
			self.load()
		return self.sites.get(address)


	# Return or create site and start download site files
	def need(self, address, all_file=True):
		from Site import Site
		new = False
		site = self.get(address)
		if not site: # Site not exits yet
			if not self.isAddress(address): return False # Not address: %s % address
			logging.debug("Added new site: %s" % address)
			site = Site(address)
			self.sites[address] = site
			if not site.settings["serving"]: # Maybe it was deleted before
				site.settings["serving"] = True
				site.saveSettings()
			new = True

		if all_file: site.download()
		return site


	def delete(self, address):
		logging.debug("SiteManager deleted site: %s" % address)
		del(self.sites[address])


	# Lazy load sites
	def list(self):
		if self.sites == None: # Not loaded yet
			self.load()
		return self.sites



site_manager = SiteManager() # Singletone

peer_blacklist = [] # Dont download from this peers
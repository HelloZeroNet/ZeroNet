import logging, json, os, re, sys, time
import gevent
from Plugin import PluginManager
from Config import config
from Debug import Debug

allow_reload = False # No reload supported

log = logging.getLogger("ZeronamePlugin")


@PluginManager.registerTo("SiteManager")
class SiteManagerPlugin(object):
	zeroname_address = "1Name2NXVi1RDPDgf5617UoW7xA6YrhM9F"
	site_zeroname = None
	def load(self):
		super(SiteManagerPlugin, self).load()
		if not self.get(self.zeroname_address): self.need(self.zeroname_address) # Need ZeroName site

	# Checks if its a valid address
	def isAddress(self, address):
		if self.isDomain(address): 
			return True
		else:
			return super(SiteManagerPlugin, self).isAddress(address)


	# Return: True if the address is domain
	def isDomain(self, address):
		return re.match("(.*?)([A-Za-z0-9_-]+\.[A-Za-z0-9]+)$", address)


	# Resolve domain
	# Return: The address or None
	def resolveDomain(self, domain):
		domain = domain.lower()
		if not self.site_zeroname:
			self.site_zeroname = self.need(self.zeroname_address)
		self.site_zeroname.needFile("data/names.json", priority=10)
		db = self.site_zeroname.storage.loadJson("data/names.json")
		return db.get(domain)


	# Return or create site and start download site files
	# Return: Site or None if dns resolve failed
	def need(self, address, all_file=True):
		if self.isDomain(address): # Its looks like a domain
			address_resolved = self.resolveDomain(address)
			if address_resolved:
				address = address_resolved
			else:
				return None
		
		return super(SiteManagerPlugin, self).need(address, all_file)


	# Return: Site object or None if not found
	def get(self, address):
		if self.sites == None: # Not loaded yet
			self.load()
		if self.isDomain(address): # Its looks like a domain
			address_resolved = self.resolveDomain(address)
			if address_resolved: # Domain found
				site = self.sites.get(address_resolved)
				if site:
					site_domain = site.settings.get("domain")
					if site_domain != address:
						site.settings["domain"] = address
			else: # Domain not found
				site = self.sites.get(address)

		else: # Access by site address
			site = self.sites.get(address)
		return site


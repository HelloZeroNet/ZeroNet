import logging, json, os, re, sys, time
import gevent
from Plugin import PluginManager
from Config import config
from util import Http
from Debug import Debug

allow_reload = False # No reload supported

log = logging.getLogger("DnschainPlugin")

@PluginManager.registerTo("SiteManager")
class SiteManagerPlugin(object):
	dns_cache_path = "%s/dns_cache.json" % config.data_dir
	dns_cache = None

	# Checks if its a valid address
	def isAddress(self, address):
		if self.isDomain(address): 
			return True
		else:
			return super(SiteManagerPlugin, self).isAddress(address)


	# Return: True if the address is domain
	def isDomain(self, address):
		return re.match("(.*?)([A-Za-z0-9_-]+\.[A-Za-z0-9]+)$", address)


	# Load dns entries from data/dns_cache.json
	def loadDnsCache(self):
		if os.path.isfile(self.dns_cache_path):
			self.dns_cache = json.load(open(self.dns_cache_path))
		else:
			self.dns_cache = {}
		log.debug("Loaded dns cache, entries: %s" % len(self.dns_cache))


	# Save dns entries to data/dns_cache.json
	def saveDnsCache(self):
		json.dump(self.dns_cache, open(self.dns_cache_path, "wb"), indent=2)


	# Resolve domain using dnschain.net
	# Return: The address or None
	def resolveDomainDnschainNet(self, domain):
		try:
			match = self.isDomain(domain)
			sub_domain = match.group(1).strip(".")
			top_domain = match.group(2)
			if not sub_domain: sub_domain = "@"
			address = None
			with gevent.Timeout(5, Exception("Timeout: 5s")):
				res = Http.get("https://api.dnschain.net/v1/namecoin/key/%s" % top_domain).read()
				data = json.loads(res)["data"]["value"]
				if "zeronet" in data:
					for key, val in data["zeronet"].iteritems():
						self.dns_cache[key+"."+top_domain] = [val, time.time()+60*60*5] # Cache for 5 hours
					self.saveDnsCache()
					return data["zeronet"].get(sub_domain)
			# Not found
			return address
		except Exception, err:
			log.debug("Dnschain.net %s resolve error: %s" % (domain, Debug.formatException(err)))


	# Resolve domain using dnschain.info
	# Return: The address or None
	def resolveDomainDnschainInfo(self, domain):
		try:
			match = self.isDomain(domain)
			sub_domain = match.group(1).strip(".")
			top_domain = match.group(2)
			if not sub_domain: sub_domain = "@"
			address = None
			with gevent.Timeout(5, Exception("Timeout: 5s")):
				res = Http.get("https://dnschain.info/bit/d/%s" % re.sub("\.bit$", "", top_domain)).read()
				data = json.loads(res)["value"]
				for key, val in data["zeronet"].iteritems():
					self.dns_cache[key+"."+top_domain] = [val, time.time()+60*60*5] # Cache for 5 hours
				self.saveDnsCache()
				return data["zeronet"].get(sub_domain)
			# Not found
			return address
		except Exception, err:
			log.debug("Dnschain.info %s resolve error: %s" % (domain, Debug.formatException(err)))


	# Resolve domain
	# Return: The address or None
	def resolveDomain(self, domain):
		domain = domain.lower()
		if self.dns_cache == None:
			self.loadDnsCache()
		if domain.count(".") < 2: # Its a topleved request, prepend @. to it
			domain = "@."+domain

		domain_details = self.dns_cache.get(domain)
		if domain_details and time.time() < domain_details[1]: # Found in cache and its not expired
			return domain_details[0]
		else:
			# Resovle dns using dnschain
			thread_dnschain_info = gevent.spawn(self.resolveDomainDnschainInfo, domain)
			thread_dnschain_net = gevent.spawn(self.resolveDomainDnschainNet, domain)
			gevent.joinall([thread_dnschain_net, thread_dnschain_info]) # Wait for finish

			if thread_dnschain_info.value and thread_dnschain_net.value: # Booth successfull
				if thread_dnschain_info.value == thread_dnschain_net.value: # Same returned value
					return thread_dnschain_info.value 
				else:
					log.error("Dns %s missmatch: %s != %s" % (domain, thread_dnschain_info.value, thread_dnschain_net.value))

			# Problem during resolve
			if domain_details: # Resolve failed, but we have it in the cache
				domain_details[1] = time.time()+60*60 # Dont try again for 1 hour
				return domain_details[0]
			else: # Not found in cache
				self.dns_cache[domain] = [None, time.time()+60] # Don't check again for 1 min
				return None


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


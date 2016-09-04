import re
from Plugin import PluginManager

@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
	def __init__(self, server = None):
		from Site import SiteManager
		self.site_manager = SiteManager.site_manager
		super(UiRequestPlugin, self).__init__(server)


	# Media request
	def actionSiteMedia(self, path):
		match = re.match("/media/(?P<address>[A-Za-z0-9-]+\.[A-Za-z0-9\.-]+)(?P<inner_path>/.*|$)", path)
		if match: # Its a valid domain, resolve first
			domain = match.group("address")
			address = self.site_manager.resolveDomain(domain)
			if address:
				path = "/media/"+address+match.group("inner_path")
		return super(UiRequestPlugin, self).actionSiteMedia(path) # Get the wrapper frame output


	# Is mediarequest allowed from that referer
	def isMediaRequestAllowed(self, site_address, referer):
		referer_path = re.sub("http[s]{0,1}://.*?/", "/", referer).replace("/media", "") # Remove site address
		referer_site_address = re.match("/(?P<address>[A-Za-z0-9\.-]+)(?P<inner_path>/.*|$)", referer_path).group("address")

		if referer_site_address == site_address: # Referer site address as simple address
			return True
		elif self.site_manager.resolveDomain(referer_site_address) == site_address: # Referer site address as dns
			return True
		else: # Invalid referer
			return False


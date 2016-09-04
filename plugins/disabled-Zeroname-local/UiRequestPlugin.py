import re
from Plugin import PluginManager

@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def __init__(self, *args, **kwargs):
        from Site import SiteManager
        self.site_manager = SiteManager.site_manager
        super(UiRequestPlugin, self).__init__(*args, **kwargs)


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
        referer_path = re.sub("\?.*", "", referer_path) # Remove http params

        if self.isProxyRequest(): # Match to site domain
            referer = re.sub("^http://zero[/]+", "http://", referer) # Allow /zero access
            referer_site_address = re.match("http[s]{0,1}://(.*?)(/|$)", referer).group(1)
        else: # Match to request path
            referer_site_address = re.match("/(?P<address>[A-Za-z0-9\.-]+)(?P<inner_path>/.*|$)", referer_path).group("address")

        if referer_site_address == site_address: # Referer site address as simple address
            return True
        elif self.site_manager.resolveDomain(referer_site_address) == site_address: # Referer site address as dns
            return True
        else: # Invalid referer
            return False


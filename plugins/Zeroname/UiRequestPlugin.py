import re

from Plugin import PluginManager


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):

    def __init__(self, *args, **kwargs):
        from Site import SiteManager
        self.site_manager = SiteManager.site_manager
        super(UiRequestPlugin, self).__init__(*args, **kwargs)

    # Media request
    def actionSiteMedia(self, path, header_length=True):
        match = re.match("/media/(?P<address>[A-Za-z0-9-]+\.[A-Za-z0-9\.-]+)(?P<inner_path>/.*|$)", path)
        if match:  # Its a valid domain, resolve first
            domain = match.group("address")
            address = self.site_manager.resolveDomain(domain)
            if address:
                path = "/media/" + address + match.group("inner_path")
        return super(UiRequestPlugin, self).actionSiteMedia(path, header_length=header_length)  # Get the wrapper frame output

    # Is mediarequest allowed from that referer
    def isMediaRequestAllowed(self, site_address, referer):
        referer_path = re.sub("http[s]{0,1}://.*?/", "/", referer).replace("/media", "")  # Remove site address
        referer_path = re.sub("\?.*", "", referer_path)  # Remove http params

        if not re.sub("^http[s]{0,1}://", "", referer).startswith(self.env["HTTP_HOST"]):  # Different origin
            return False

        if self.isProxyRequest():  # Match to site domain
            referer = re.sub("^http://zero[/]+", "http://", referer)  # Allow /zero access
            match = re.match("http[s]{0,1}://(.*?)(/|$)", referer)
            if match:
                referer_site_address = match.group(1)
            else:
                referer_site_address = None
        else:  # Match to request path
            match = re.match("/(?P<address>[A-Za-z0-9\.-]+)(?P<inner_path>/.*|$)", referer_path)
            if match:
                referer_site_address = match.group("address")
            else:
                referer_site_address = None

        if not referer_site_address:
            return False
        elif referer_site_address == site_address:  # Referer site address as simple address
            return True
        elif self.site_manager.resolveDomain(referer_site_address) == site_address:  # Referer site address as dns
            return True
        else:  # Invalid referer
            return False

@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("Zeroname plugin")
        group.add_argument('--bit_resolver', help='ZeroNet site to resolve .bit domains', default="1Name2NXVi1RDPDgf5617UoW7xA6YrhM9F", metavar="address")

        return super(ConfigPlugin, self).createArguments()

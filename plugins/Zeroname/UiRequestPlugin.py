import re

from Plugin import PluginManager


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):

    def __init__(self, *args, **kwargs):
        from Site import SiteManager
        self.site_manager = SiteManager.site_manager
        super(UiRequestPlugin, self).__init__(*args, **kwargs)

    # Media request
    def actionSiteMedia(self, path, **kwargs):
        match = re.match(r"/media/(?P<address>[A-Za-z0-9-]+\.[A-Za-z0-9\.-]+)(?P<inner_path>/.*|$)", path)
        if match:  # Its a valid domain, resolve first
            domain = match.group("address")
            address = self.site_manager.resolveDomain(domain)
            if address:
                path = "/media/" + address + match.group("inner_path")
        return super(UiRequestPlugin, self).actionSiteMedia(path, **kwargs)  # Get the wrapper frame output

@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("Zeroname plugin")
        group.add_argument('--bit_resolver', help='ZeroNet site to resolve .bit domains', default="1Name2NXVi1RDPDgf5617UoW7xA6YrhM9F", metavar="address")

        return super(ConfigPlugin, self).createArguments()

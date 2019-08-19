from Plugin import PluginManager

import re

@PluginManager.registerTo('UiRequest')
class UiRequestPlugin:
    def __init__(self, *args, **kwargs):
        from Site import SiteManager
        self.site_manager = SiteManager.site_manager

        super(UiRequestPlugin, self).__init__(*args, **kwargs)

    def actionSiteMedia(self, path, **kwargs):
        match = re.match(r'/media/(?P<address>[A-Za-z0-9-]+\.[A-Za-z0-9\.-]+)(?P<inner_path>/.*|$)', path)

        if match:
            domain = match.group('address')
            address = self.site_manager.ens_resolver.resolveDomain(domain)

            if address:
                path = '/media/' + address + match.group('inner_path')

        return super(UiRequestPlugin, self).actionSiteMedia(path, **kwargs)

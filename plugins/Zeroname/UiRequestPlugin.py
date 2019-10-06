import re

from Plugin import PluginManager


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):

    def __init__(self, *args, **kwargs):
        from Site import SiteManager
        self.site_manager = SiteManager.site_manager
        super(UiRequestPlugin, self).__init__(*args, **kwargs)

@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("Zeroname plugin")
        group.add_argument('--bit_resolver', help='ZeroNet site to resolve .bit domains', default="1Name2NXVi1RDPDgf5617UoW7xA6YrhM9F", metavar="address")

        return super(ConfigPlugin, self).createArguments()

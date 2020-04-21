from Plugin import PluginManager

@PluginManager.registerTo('ConfigPlugin')
class ConfigPlugin:
    def createArguments(self):
        nameservers = [
            'https://doh.libredns.gr/dns-query',

            'https://doh-de.blahdns.com/dns-query',
            'https://doh-jp.blahdns.com/dns-query',
            'https://doh-ch.blahdns.com/dns-query'
        ]

        group = self.parser.add_argument_group('DNS plugin')

        group.add_argument('--dns_nameservers', help='Nameservers for DNS plugin', default=nameservers, metavar='address', nargs='*')
        group.add_argument('--dns_configure', help='Configure resolver with system config for DNS plugin', action='store_true', default=False)

        return super(ConfigPlugin, self).createArguments()

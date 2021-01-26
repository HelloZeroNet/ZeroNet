from Config import config
from Plugin import PluginManager

from .DNSResolver import DNSResolver

allow_reload = False

@PluginManager.registerTo('SiteManager')
class SiteManagerPlugin:
    _dns_resolver = None

    @property
    def dns_resolver(self):
        if not self._dns_resolver:
            nameservers = config.dns_nameservers
            configure = config.dns_configure

            self._dns_resolver = DNSResolver(
                site_manager=self,
                nameservers=nameservers,
                configure=configure
            )

        return self._dns_resolver

    def load(self, *args, **kwargs):
        super(SiteManagerPlugin, self).load(*args, **kwargs)
        self.dns_resolver.load()

    def isDomain(self, address):
        return self.dns_resolver.isDomain(address) or super(SiteManagerPlugin, self).isDomain(address)

    def resolveDomain(self, domain):
        return self.dns_resolver.resolveDomain(domain) or super(SiteManagerPlugin, self).resolveDomain(domain)

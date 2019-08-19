from Config import config
from Plugin import PluginManager

from .ENSResolver import ENSResolver

allow_reload = False

@PluginManager.registerTo('SiteManager')
class SiteManagerPlugin:
    _ens_resolver = None

    @property
    def ens_resolver(self):
        if not self._ens_resolver:
            local = {
                'name': 'local',
                'providers': config.ens_local_providers,
                'enabled': config.ens_use_local,
                'instance': None,
            }

            mainnet = {
                'name': 'mainnet',
                'providers': config.ens_mainnet_providers,
                'enabled': config.ens_use_mainnet,
                'instance': None,
            }

            ropsten = {
                'name': 'ropsten',
                'providers': config.ens_ropsten_providers,
                'enabled': config.ens_use_ropsten,
                'instance': None,
            }

            rinkeby = {
                'name': 'rinkeby',
                'providers': config.ens_rinkeby_providers,
                'enabled': config.ens_use_rinkeby,
                'instance': None,
            }

            goerli = {
                'name': 'goerli',
                'providers': config.ens_goerli_providers,
                'enabled': config.ens_use_goerli,
                'instance': None,
            }

            networks = [
                local,
                mainnet,
                ropsten,
                rinkeby,
                goerli,
            ]

            self._ens_resolver = ENSResolver(
                site_manager=self,
                networks=networks,
            )

        return self._ens_resolver

    def load(self, *args, **kwargs):
        super(SiteManagerPlugin, self).load(*args, **kwargs)
        self.ens_resolver.load()

    def isDomain(self, address):
        return self.ens_resolver.isDomain(address) or super(SiteManagerPlugin, self).isDomain(address)

    def resolveDomain(self, domain):
        return self.ens_resolver.resolveDomain(domain) or super(SiteManagerPlugin, self).resolveDomain(domain)

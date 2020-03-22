from Plugin import PluginManager

@PluginManager.registerTo('ConfigPlugin')
class ConfigPlugin:
    def createArguments(self):
        localProviders = ['web3py://default-ipc-providers', 'ws://127.0.0.1:8546', 'http://127.0.0.1:8545']
        mainnetProviders = ['https://cloudflare-eth.com', 'wss://mainnet.infura.io/ws', 'https://mainnet.infura.io']
        ropstenProviders = ['wss://ropsten.infura.io/ws', 'https://ropsten.infura.io']
        rinkebyProviders = ['wss://rinkeby.infura.io/ws', 'https://rinkeby.infura.io']
        goerliProviders = ['wss://goerli.infura.io/ws', 'https://goerli.infura.io']

        group = self.parser.add_argument_group('ENS plugin')

        group.add_argument('--ens_local_providers', help='Ethereum local providers for ENS plugin', default=localProviders, metavar='protocol://address', nargs='*')
        group.add_argument('--ens_mainnet_providers', help='Ethereum mainnet providers for ENS plugin', default=mainnetProviders, metavar='protocol://address', nargs='*')
        group.add_argument('--ens_ropsten_providers', help='Ethereum ropsten providers for ENS plugin', default=ropstenProviders, metavar='protocol://address', nargs='*')
        group.add_argument('--ens_rinkeby_providers', help='Ethereum rinkeby providers for ENS plugin', default=rinkebyProviders, metavar='protocol://address', nargs='*')
        group.add_argument('--ens_goerli_providers', help='Ethereum goerli providers for ENS plugin', default=goerliProviders, metavar='protocol://address', nargs='*')

        group.add_argument('--ens_use_local', help='Use local providers for ENS plugin', action='store_true', default=True)
        group.add_argument('--ens_use_mainnet', help='Use mainnet providers for ENS plugin', action='store_true', default=True)
        group.add_argument('--ens_use_ropsten', help='Use ropsten providers for ENS plugin', action='store_true', default=True)
        group.add_argument('--ens_use_rinkeby', help='Use rinkeby providers for ENS plugin', action='store_true', default=True)
        group.add_argument('--ens_use_goerli', help='Use goerli providers for ENS plugin', action='store_true', default=True)

        return super(ConfigPlugin, self).createArguments()

from Config import config

from web3 import HTTPProvider, WebsocketProvider, IPCProvider
from ens import ENS
import gevent

from urllib.parse import urlparse
import logging
import time
import json
import re
import os

FILE_SCHEMES = {'file'}
HTTP_SCHEMES = {'http', 'https'}
WS_SCHEMES = {'ws', 'wss'}

log = logging.getLogger('ENSPlugin')

class ENSResolver:
    loaded = False
    cache = {}

    def __init__(self, site_manager, networks):
        self.site_manager = site_manager
        self.networks = networks

    def load(self):
        if not self.loaded:
            self.loadCache()

            greenlets = []
            for network in self.networks:
                greenlets.append(gevent.spawn(self.loadNetwork, network))
            gevent.joinall(greenlets)

            self.loaded = True

    def loadNetwork(self, network):
        if not network['enabled']:
            return

        for provider_uri in network['providers']:
            provider_scheme = urlparse(provider_uri).scheme
            provider_path = urlparse(provider_uri).path

            if provider_uri == 'web3py://default-ipc-providers':
                provider = IPCProvider()

            elif provider_scheme in FILE_SCHEMES:
                provider = IPCProvider(provider_path)

            elif provider_scheme in HTTP_SCHEMES:
                provider = HTTPProvider(provider_uri)

            elif provider_scheme in WS_SCHEMES:
                provider = WebsocketProvider(provider_uri)

            try:
                if provider.isConnected():
                    network['instance'] = ENS(provider)
                    return
            except:
                pass

        network['enabled'] = False

    def loadCache(self, path=os.path.join(config.data_dir, 'ens_cache.json')):
        if os.path.isfile(path):
            try: self.cache = json.load(open(path))
            except json.decoder.JSONDecodeError: pass

    def saveCache(self, path=os.path.join(config.data_dir, 'ens_cache.json')):
        json.dump(self.cache, open(path, 'w'), indent=2)

    def isDomain(self, address):
        return re.match(r'(.*?)([A-Za-z0-9_-]+\.eth)$', address)

    def resolveDomain(self, domain):
        if not self.loaded:
            self.load()

        domain = domain.lower()

        cache_entry = self.lookupCache(domain)
        if cache_entry and time.time() < cache_entry['timeout']:
            log.info('cache: %s -> %s', domain, cache_entry['address'])
            return cache_entry['address']

        provider_entry = None
        provider_error = None

        try:
            provider_entry = self.lookupProviders(domain)
        except Exception as err:
            provider_error = err

        if provider_entry and not provider_error:
            log.info('provider: %s -> %s', domain, provider_entry['address'])
            self.saveInCache(provider_entry)
            return provider_entry['address']

        if cache_entry and provider_error:
            log.info('fallback: %s -> %s', domain, cache_entry['address'])
            self.extendInCache(cache_entry)
            return cache_entry['address']

    def lookupCache(self, domain):
        entry = self.cache.get(domain)

        if not entry:
            return None

        for network in self.networks:
            if entry['network'] == network['name'] and not network['enabled']:
                return None

        return entry

    def lookupProviders(self, domain):
        error = None

        greenlets = []
        for network in self.networks:
            greenlets.append(gevent.spawn(self.lookupProvider, domain, network))
        gevent.joinall(greenlets)

        for greenlet in greenlets:
            try:
                entry = greenlet.get()
            except Exception as err:
                error = err

            if entry and entry['address']:
                return entry

        if error:
            raise error

    def lookupProvider(self, domain, network):
        if not network['enabled']:
            return None

        name = network['name']
        instance = network['instance']

        content = instance.content(domain)

        if content and content['type'] == 'zeronet':
            return {'network': name, 'domain': domain, 'address': content['hash']}

    def saveInCache(self, entry):
        entry['timeout'] = time.time() + 60 * 60
        self.cache[entry['domain']] = entry

        self.saveCache()

    def extendInCache(self, entry):
        self.cache[entry['domain']]['timeout'] = time.time() + 60 * 15

        self.saveCache()

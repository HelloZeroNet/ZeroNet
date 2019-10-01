from Config import config

import logging
import time
import json
import re
import os

log = logging.getLogger('DNSPlugin')

class DNSResolver:
    loaded = False
    cache = {}

    def __init__(self, site_manager, nameservers, configure):
        self.site_manager = site_manager
        self.nameservers = nameservers
        self.configure = configure

    def load(self):
        if not self.loaded:
            self.loadModule()
            self.loadCache()

            self.resolver = dns.resolver.Resolver(configure=self.configure)

            if not self.configure:
                self.resolver.nameservers = self.nameservers

            self.loaded = True

    def loadModule(self):
        global dns, dnslink
        import dns.resolver
        import dnslink

        if config.tor == 'always':
            class Response:
                flags = dns.flags.TC

            query = lambda *x, **y: Response()
            dns.query.udp = query

    def loadCache(self, path=os.path.join(config.data_dir, 'dns_cache.json')):
        if os.path.isfile(path):
            try:
                self.cache = json.load(open(path))
            except json.decoder.JSONDecodeError:
                pass

    def saveCache(self, path=os.path.join(config.data_dir, 'dns_cache.json')):
        with open(path, 'w') as file:
            json.dump(self.cache, file, indent=2)

    def isDomain(self, address):
        return re.match(r'(.*?)([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$', address)

    def resolveDomain(self, domain):
        if not self.loaded:
            self.load()

        domain = domain.lower()

        cache_entry = self.cache.get(domain)
        if cache_entry and time.time() < cache_entry['timeout']:
            log.info('cache: %s -> %s', domain, cache_entry['address'])
            return cache_entry['address']

        try:
            resolver_record = dnslink.resolve(domain, protocol='zeronet', resolver=self.resolver)[0]
            resolver_entry = {'domain': domain, 'address': resolver_record.split('/', 2)[2]}
        except IndexError:
            resolver_entry = None

        resolver_error = None
        try:
            self.resolver.query(domain, 'TXT')
        except dns.resolver.NXDOMAIN:
            pass
        except dns.resolver.NoAnswer:
            pass
        except dns.exception.DNSException as err:
            resolver_error = err

        if resolver_entry and not resolver_error:
            log.info('resolver: %s -> %s', domain, resolver_entry['address'])
            self.saveInCache(resolver_entry)
            return resolver_entry['address']

        if cache_entry and resolver_error:
            log.info('fallback: %s -> %s', domain, cache_entry['address'])
            self.extendInCache(cache_entry)
            return cache_entry['address']

    def saveInCache(self, entry):
        entry['timeout'] = time.time() + 60 * 60
        self.cache[entry['domain']] = entry

        self.saveCache()

    def extendInCache(self, entry):
        self.cache[entry['domain']]['timeout'] = time.time() + 60 * 15

        self.saveCache()

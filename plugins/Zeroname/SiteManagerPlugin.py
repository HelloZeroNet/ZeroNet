import logging
import re
import time

from Config import config
from Plugin import PluginManager

allow_reload = False  # No reload supported

log = logging.getLogger("ZeronamePlugin")


@PluginManager.registerTo("SiteManager")
class SiteManagerPlugin(object):
    site_zeroname = None
    db_domains = None
    db_domains_modified = None

    def load(self, *args, **kwargs):
        super(SiteManagerPlugin, self).load(*args, **kwargs)
        if not self.get(config.bit_resolver):
            self.need(config.bit_resolver)  # Need ZeroName site

    # Checks if its a valid address
    def isAddress(self, address):
        if self.isDomain(address):
            return True
        else:
            return super(SiteManagerPlugin, self).isAddress(address)

    # Return: True if the address is domain
    def isDomain(self, address):
        return re.match("(.*?)([A-Za-z0-9_-]+\.[A-Za-z0-9]+)$", address)

    # Resolve domain
    # Return: The address or None
    def resolveDomain(self, domain):
        domain = domain.lower()
        if not self.site_zeroname:
            self.site_zeroname = self.need(config.bit_resolver)

        site_zeroname_modified = self.site_zeroname.content_manager.contents.get("content.json", {}).get("modified", 0)
        if not self.db_domains or self.db_domains_modified != site_zeroname_modified:
            self.site_zeroname.needFile("data/names.json", priority=10)
            s = time.time()
            self.db_domains = self.site_zeroname.storage.loadJson("data/names.json")
            log.debug(
                "Domain db with %s entries loaded in %.3fs (modification: %s -> %s)" %
                (len(self.db_domains), time.time() - s, self.db_domains_modified, site_zeroname_modified)
            )
            self.db_domains_modified = site_zeroname_modified
        return self.db_domains.get(domain)

    # Return or create site and start download site files
    # Return: Site or None if dns resolve failed
    def need(self, address, all_file=True):
        if self.isDomain(address):  # Its looks like a domain
            address_resolved = self.resolveDomain(address)
            if address_resolved:
                address = address_resolved
            else:
                return None

        return super(SiteManagerPlugin, self).need(address, all_file)

    # Return: Site object or None if not found
    def get(self, address):
        if self.sites is None:  # Not loaded yet
            self.load()
        if self.isDomain(address):  # Its looks like a domain
            address_resolved = self.resolveDomain(address)
            if address_resolved:  # Domain found
                site = self.sites.get(address_resolved)
                if site:
                    site_domain = site.settings.get("domain")
                    if site_domain != address:
                        site.settings["domain"] = address
            else:  # Domain not found
                site = self.sites.get(address)

        else:  # Access by site address
            site = self.sites.get(address)
        return site

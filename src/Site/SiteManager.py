import json
import logging
import re
import os
import time

from Plugin import PluginManager
from Config import config
from util import helper

@PluginManager.acceptPlugins
class SiteManager(object):

    def __init__(self):
        self.sites = None

    # Load all sites from data/sites.json
    def load(self):
        from Site import Site
        if not self.sites:
            self.sites = {}
        address_found = []
        added = 0
        # Load new adresses
        for address in json.load(open("%s/sites.json" % config.data_dir)):
            if address not in self.sites and os.path.isfile("%s/%s/content.json" % (config.data_dir, address)):
                s = time.time()
                self.sites[address] = Site(address)
                logging.debug("Loaded site %s in %.3fs" % (address, time.time()-s))
                added += 1
            address_found.append(address)

        # Remove deleted adresses
        for address in self.sites.keys():
            if address not in address_found:
                del(self.sites[address])
                logging.debug("Removed site: %s" % address)

        if added:
            logging.debug("SiteManager added %s sites" % added)

    # Checks if its a valid address
    def isAddress(self, address):
        return re.match("^[A-Za-z0-9]{26,35}$", address)

    # Return: Site object or None if not found
    def get(self, address):
        if self.sites is None:  # Not loaded yet
            self.load()
        return self.sites.get(address)

    # Return or create site and start download site files
    def need(self, address, all_file=True):
        from Site import Site
        site = self.get(address)
        if not site:  # Site not exist yet
            # Try to find site with differect case
            for recover_address, recover_site in self.sites.items():
                if recover_address.lower() == address.lower():
                    return recover_site

            if not self.isAddress(address):
                return False  # Not address: %s % address
            logging.debug("Added new site: %s" % address)
            site = Site(address)
            self.sites[address] = site
            if not site.settings["serving"]:  # Maybe it was deleted before
                site.settings["serving"] = True
                site.saveSettings()
            if all_file:  # Also download user files on first sync
                site.download(blind_includes=True)
        else:
            if all_file:
                site.download()

        return site

    def delete(self, address):
        logging.debug("SiteManager deleted site: %s" % address)
        del(self.sites[address])
        # Delete from sites.json
        sites_settings = json.load(open("%s/sites.json" % config.data_dir))
        del(sites_settings[address])
        helper.atomicWrite("%s/sites.json" % config.data_dir, json.dumps(sites_settings, indent=2, sort_keys=True))

    # Lazy load sites
    def list(self):
        if self.sites is None:  # Not loaded yet
            logging.debug("Loading sites...")
            self.load()
        return self.sites


site_manager = SiteManager()  # Singletone

peer_blacklist = [("127.0.0.1", config.fileserver_port)]  # Dont add this peers

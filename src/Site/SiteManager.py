import json
import logging
import re
import os
import time
import sys

import gevent

from Plugin import PluginManager
from Config import config
from util import helper


@PluginManager.acceptPlugins
class SiteManager(object):
    def __init__(self):
        self.sites = None
        gevent.spawn(self.saveTimer)

    # Load all sites from data/sites.json
    def load(self):
        from Site import Site
        if not self.sites:
            self.sites = {}
        address_found = []
        added = 0
        serving = 0
        # Load new adresses
        for address in json.load(open("%s/sites.json" % config.data_dir)):
            if address not in self.sites and os.path.isfile("%s/%s/content.json" % (config.data_dir, address)):
                s = time.time()
                self.sites[address] = Site(address)
                logging.debug("Loaded site %s in %.3fs" % (address, time.time() - s))
                added += 1
                if self.sites[address].settings["serving"]:
                    serving += 1
            address_found.append(address)

        # check if there are enough onions available
        if sys.modules.get("main") and sys.modules["main"].file_server:
            tor_manager = sys.modules["main"].file_server.tor_manager
            if tor_manager and tor_manager.numOnions() < serving+1:
                sys.exit("Insufficient number of onions: supplied %u, need at least %u, recommended to have %u+ onions" % (tor_manager.numOnions(), serving+1, serving*3))

        # Remove deleted adresses
        for address in self.sites.keys():
            if address not in address_found:
                del(self.sites[address])
                logging.debug("Removed site: %s" % address)

        if added:
            logging.debug("SiteManager added %s sites" % added)

    def save(self):
        if not self.sites:
            logging.error("Save error: No sites found")
        s = time.time()
        data = json.load(open("%s/sites.json" % config.data_dir))
        for address, site in self.list().iteritems():
            data[address] = site.settings
        helper.atomicWrite("%s/sites.json" % config.data_dir, json.dumps(data, indent=2, sort_keys=True))
        logging.debug("Saved sites in %.2fs" % (time.time() - s))

    def saveTimer(self):
        while 1:
            time.sleep(60 * 10)
            self.save()

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

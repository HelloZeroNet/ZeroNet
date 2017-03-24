import json
import logging
import re
import os
import time
import atexit

import gevent

from Plugin import PluginManager
from Content import ContentDb
from Config import config
from util import helper


@PluginManager.acceptPlugins
class SiteManager(object):
    def __init__(self):
        self.log = logging.getLogger("SiteManager")
        self.log.debug("SiteManager created.")
        self.sites = None
        self.loaded = False
        gevent.spawn(self.saveTimer)
        atexit.register(self.save)

    # Load all sites from data/sites.json
    def load(self, cleanup=True):
        self.log.debug("Loading sites...")
        self.loaded = False
        from Site import Site
        if self.sites is None:
            self.sites = {}
        address_found = []
        added = 0
        # Load new adresses
        for address, settings in json.load(open("%s/sites.json" % config.data_dir)).iteritems():
            if address not in self.sites and os.path.isfile("%s/%s/content.json" % (config.data_dir, address)):
                s = time.time()
                try:
                    site = Site(address, settings=settings)
                    site.content_manager.contents.get("content.json")
                except Exception, err:
                    self.log.debug("Error loading site %s: %s" % (address, err))
                    continue
                self.sites[address] = site
                self.log.debug("Loaded site %s in %.3fs" % (address, time.time() - s))
                added += 1
            address_found.append(address)

        # Remove deleted adresses
        if cleanup:
            for address in self.sites.keys():
                if address not in address_found:
                    del(self.sites[address])
                    self.log.debug("Removed site: %s" % address)

            # Remove orpan sites from contentdb
            content_db = ContentDb.getContentDb()
            for row in content_db.execute("SELECT * FROM site"):
                address = row["address"]
                if address not in self.sites:
                    self.log.info("Deleting orphan site from content.db: %s" % address)
                    content_db.execute("DELETE FROM site WHERE ?", {"address": address})
                    if address in content_db.site_ids:
                        del content_db.site_ids[address]
                    if address in content_db.sites:
                        del content_db.sites[address]

        if added:
            self.log.debug("SiteManager added %s sites" % added)
        self.loaded = True

    def save(self):
        if not self.sites:
            self.log.debug("Save skipped: No sites found")
            return
        if not self.loaded:
            self.log.debug("Save skipped: Not loaded")
            return
        s = time.time()
        data = {}
        # Generate data file
        for address, site in self.list().iteritems():
            site.settings["size"] = site.content_manager.getTotalSize()  # Update site size
            data[address] = site.settings
            data[address]["cache"] = {}
            data[address]["cache"]["bad_files"] = site.bad_files
            data[address]["cache"]["hashfield"] = site.content_manager.hashfield.tostring().encode("base64")

        if data:
            helper.atomicWrite("%s/sites.json" % config.data_dir, json.dumps(data, indent=2, sort_keys=True))
        else:
            self.log.debug("Save error: No data")
        # Remove cache from site settings
        for address, site in self.list().iteritems():
            site.settings["cache"] = {}

        self.log.debug("Saved sites in %.2fs" % (time.time() - s))

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
            self.log.debug("Getting new site: %s)..." % address)
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
            self.log.debug("Added new site: %s" % address)
            site = Site(address)
            self.sites[address] = site
            if not site.settings["serving"]:  # Maybe it was deleted before
                site.settings["serving"] = True
            site.saveSettings()
            if all_file:  # Also download user files on first sync
                site.download(check_size=True, blind_includes=True)
        else:
            if all_file:
                site.download(check_size=True, blind_includes=True)

        return site

    def delete(self, address):
        self.log.debug("SiteManager deleted site: %s" % address)
        del(self.sites[address])
        # Delete from sites.json
        self.save()

    # Lazy load sites
    def list(self):
        if self.sites is None:  # Not loaded yet
            self.log.debug("Sites not loaded yet...")
            self.load()
        return self.sites


site_manager = SiteManager()  # Singletone

peer_blacklist = [("127.0.0.1", config.fileserver_port)]  # Dont add this peers

import json
import logging
import re
import os
import time
import atexit

import gevent

import util
from Plugin import PluginManager
from Content import ContentDb
from Config import config
from util import helper
from util import RateLimit
from util import Cached


@PluginManager.acceptPlugins
class SiteManager(object):
    def __init__(self):
        self.log = logging.getLogger("SiteManager")
        self.log.debug("SiteManager created.")
        self.sites = {}
        self.sites_changed = int(time.time())
        self.loaded = False
        gevent.spawn(self.saveTimer)
        atexit.register(lambda: self.save(recalculate_size=True))

    # Load all sites from data/sites.json
    @util.Noparallel()
    def load(self, cleanup=True, startup=False):
        from Debug import Debug
        self.log.info("Loading sites... (cleanup: %s, startup: %s)" % (cleanup, startup))
        self.loaded = False
        from .Site import Site
        address_found = []
        added = 0
        load_s = time.time()
        # Load new adresses
        try:
            json_path = "%s/sites.json" % config.data_dir
            data = json.load(open(json_path))
        except Exception as err:
            raise Exception("Unable to load %s: %s" % (json_path, err))

        sites_need = []

        for address, settings in data.items():
            if address not in self.sites:
                if os.path.isfile("%s/%s/content.json" % (config.data_dir, address)):
                    # Root content.json exists, try load site
                    s = time.time()
                    try:
                        site = Site(address, settings=settings)
                        site.content_manager.contents.get("content.json")
                    except Exception as err:
                        self.log.debug("Error loading site %s: %s" % (address, err))
                        continue
                    self.sites[address] = site
                    self.log.debug("Loaded site %s in %.3fs" % (address, time.time() - s))
                    added += 1
                elif startup:
                    # No site directory, start download
                    self.log.debug("Found new site in sites.json: %s" % address)
                    sites_need.append([address, settings])
                    added += 1

            address_found.append(address)

        # Remove deleted adresses
        if cleanup:
            for address in list(self.sites.keys()):
                if address not in address_found:
                    del(self.sites[address])
                    self.log.debug("Removed site: %s" % address)

            # Remove orpan sites from contentdb
            content_db = ContentDb.getContentDb()
            for row in content_db.execute("SELECT * FROM site").fetchall():
                address = row["address"]
                if address not in self.sites and address not in address_found:
                    self.log.info("Deleting orphan site from content.db: %s" % address)

                    try:
                        content_db.execute("DELETE FROM site WHERE ?", {"address": address})
                    except Exception as err:
                        self.log.error("Can't delete site %s from content_db: %s" % (address, err))

                    if address in content_db.site_ids:
                        del content_db.site_ids[address]
                    if address in content_db.sites:
                        del content_db.sites[address]

        self.loaded = True
        for address, settings in sites_need:
            gevent.spawn(self.need, address, settings=settings)
        if added:
            self.log.info("Added %s sites in %.3fs" % (added, time.time() - load_s))

    def saveDelayed(self):
        RateLimit.callAsync("Save sites.json", allowed_again=5, func=self.save)

    def save(self, recalculate_size=False):
        if not self.sites:
            self.log.debug("Save skipped: No sites found")
            return
        if not self.loaded:
            self.log.debug("Save skipped: Not loaded")
            return
        s = time.time()
        data = {}
        # Generate data file
        s = time.time()
        for address, site in list(self.list().items()):
            if recalculate_size:
                site.settings["size"], site.settings["size_optional"] = site.content_manager.getTotalSize()  # Update site size
            data[address] = site.settings
            data[address]["cache"] = site.getSettingsCache()
        time_generate = time.time() - s

        s = time.time()
        if data:
            helper.atomicWrite("%s/sites.json" % config.data_dir, helper.jsonDumps(data).encode("utf8"))
        else:
            self.log.debug("Save error: No data")
        time_write = time.time() - s

        # Remove cache from site settings
        for address, site in self.list().items():
            site.settings["cache"] = {}

        self.log.debug("Saved sites in %.2fs (generate: %.2fs, write: %.2fs)" % (time.time() - s, time_generate, time_write))

    def saveTimer(self):
        while 1:
            time.sleep(60 * 10)
            self.save(recalculate_size=True)

    # Checks if its a valid address
    def isAddress(self, address):
        return re.match("^[A-Za-z0-9]{26,35}$", address)

    def isDomain(self, address):
        return False

    @Cached(timeout=10)
    def isDomainCached(self, address):
        return self.isDomain(address)

    def resolveDomain(self, domain):
        return False

    @Cached(timeout=10)
    def resolveDomainCached(self, domain):
        return self.resolveDomain(domain)

    # Return: Site object or None if not found
    def get(self, address):
        if self.isDomainCached(address):
            address_resolved = self.resolveDomainCached(address)
            if address_resolved:
                address = address_resolved

        if not self.loaded:  # Not loaded yet
            self.log.debug("Loading site: %s)..." % address)
            self.load()
        site = self.sites.get(address)

        return site

    def add(self, address, all_file=True, settings=None, **kwargs):
        from .Site import Site
        self.sites_changed = int(time.time())
        # Try to find site with differect case
        for recover_address, recover_site in list(self.sites.items()):
            if recover_address.lower() == address.lower():
                return recover_site

        if not self.isAddress(address):
            return False  # Not address: %s % address
        self.log.debug("Added new site: %s" % address)
        config.loadTrackersFile()
        site = Site(address, settings=settings)
        self.sites[address] = site
        if not site.settings["serving"]:  # Maybe it was deleted before
            site.settings["serving"] = True
        site.saveSettings()
        if all_file:  # Also download user files on first sync
            site.download(check_size=True, blind_includes=True)
        return site

    # Return or create site and start download site files
    def need(self, address, *args, **kwargs):
        if self.isDomainCached(address):
            address_resolved = self.resolveDomainCached(address)
            if address_resolved:
                address = address_resolved

        site = self.get(address)
        if not site:  # Site not exist yet
            site = self.add(address, *args, **kwargs)
        return site

    def delete(self, address):
        self.sites_changed = int(time.time())
        self.log.debug("Deleted site: %s" % address)
        del(self.sites[address])
        # Delete from sites.json
        self.save()

    # Lazy load sites
    def list(self):
        if not self.loaded:  # Not loaded yet
            self.log.debug("Sites not loaded yet...")
            self.load(startup=True)
        return self.sites


site_manager = SiteManager()  # Singletone

if config.action == "main":  # Don't connect / add myself to peerlist
    peer_blacklist = [("127.0.0.1", config.fileserver_port), ("::1", config.fileserver_port)]
else:
    peer_blacklist = []


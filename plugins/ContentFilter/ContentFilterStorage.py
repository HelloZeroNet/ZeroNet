import os
import json
import logging
import collections
import time

from Debug import Debug
from Plugin import PluginManager
from Config import config
from util import helper

class ContentFilterStorage(object):
    def __init__(self, site_manager):
        self.log = logging.getLogger("ContentFilterStorage")
        self.file_path = "%s/filters.json" % config.data_dir
        self.site_manager = site_manager
        self.file_content = self.load()

        # Set default values for filters.json
        if not self.file_content:
            self.file_content = {}

        # Site blacklist renamed to site blocks
        if "site_blacklist" in self.file_content:
            self.file_content["siteblocks"] = self.file_content["site_blacklist"]
            del self.file_content["site_blacklist"]

        for key in ["mutes", "siteblocks", "includes"]:
            if key not in self.file_content:
                self.file_content[key] = {}

        self.include_filters = collections.defaultdict(set)  # Merged list of mutes and blacklists from all include
        self.includeUpdateAll(update_site_dbs=False)

    def load(self):
        # Rename previously used mutes.json -> filters.json
        if os.path.isfile("%s/mutes.json" % config.data_dir):
            self.log.info("Renaming mutes.json to filters.json...")
            os.rename("%s/mutes.json" % config.data_dir, self.file_path)
        if os.path.isfile(self.file_path):
            try:
                return json.load(open(self.file_path))
            except Exception as err:
                self.log.error("Error loading filters.json: %s" % err)
                return None
        else:
            return None

    def includeUpdateAll(self, update_site_dbs=True):
        s = time.time()
        new_include_filters = collections.defaultdict(set)

        # Load all include files data into a merged set
        for include_path in self.file_content["includes"]:
            address, inner_path = include_path.split("/", 1)
            try:
                content = self.site_manager.get(address).storage.loadJson(inner_path)
            except Exception as err:
                self.log.warning(
                    "Error loading include %s: %s" %
                    (include_path, Debug.formatException(err))
                )
                continue

            for key, val in content.items():
                if type(val) is not dict:
                    continue

                new_include_filters[key].update(val.keys())

        mutes_added = new_include_filters["mutes"].difference(self.include_filters["mutes"])
        mutes_removed = self.include_filters["mutes"].difference(new_include_filters["mutes"])

        self.include_filters = new_include_filters

        if update_site_dbs:
            for auth_address in mutes_added:
                self.changeDbs(auth_address, "remove")

            for auth_address in mutes_removed:
                if not self.isMuted(auth_address):
                    self.changeDbs(auth_address, "load")

        num_mutes = len(self.include_filters["mutes"])
        num_siteblocks = len(self.include_filters["siteblocks"])
        self.log.debug(
            "Loaded %s mutes, %s blocked sites from %s includes in %.3fs" %
            (num_mutes, num_siteblocks, len(self.file_content["includes"]), time.time() - s)
        )

    def includeAdd(self, address, inner_path, description=None):
        self.file_content["includes"]["%s/%s" % (address, inner_path)] = {
            "date_added": time.time(),
            "address": address,
            "description": description,
            "inner_path": inner_path
        }
        self.includeUpdateAll()
        self.save()

    def includeRemove(self, address, inner_path):
        del self.file_content["includes"]["%s/%s" % (address, inner_path)]
        self.includeUpdateAll()
        self.save()

    def save(self):
        s = time.time()
        helper.atomicWrite(self.file_path, json.dumps(self.file_content, indent=2, sort_keys=True).encode("utf8"))
        self.log.debug("Saved in %.3fs" % (time.time() - s))

    def isMuted(self, auth_address):
        if auth_address in self.file_content["mutes"] or auth_address in self.include_filters["mutes"]:
            return True
        else:
            return False

    def isSiteblocked(self, address):
        if address in self.file_content["siteblocks"] or address in self.include_filters["siteblocks"]:
            return True
        else:
            return False

    # Search and remove or readd files of an user
    def changeDbs(self, auth_address, action):
        self.log.debug("Mute action %s on user %s" % (action, auth_address))
        res = list(self.site_manager.list().values())[0].content_manager.contents.db.execute(
            "SELECT * FROM content LEFT JOIN site USING (site_id) WHERE inner_path LIKE :inner_path",
            {"inner_path": "%%/%s/%%" % auth_address}
        )
        for row in res:
            site = self.site_manager.sites.get(row["address"])
            if not site:
                continue
            dir_inner_path = helper.getDirname(row["inner_path"])
            for file_name in site.storage.walk(dir_inner_path):
                if action == "remove":
                    site.storage.onUpdated(dir_inner_path + file_name, False)
                else:
                    site.storage.onUpdated(dir_inner_path + file_name)
                site.onFileDone(dir_inner_path + file_name)

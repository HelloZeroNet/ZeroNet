import time
import os

import ContentDb

class ContentDbDict(dict):
    def __init__(self, site, *args, **kwargs):
        s = time.time()
        self.site = site
        self.cached_keys = []
        self.log = self.site.log
        self.db = ContentDb.getContentDb()
        self.db_id = self.db.needSite(site)
        self.num_loaded = 0
        super(ContentDbDict, self).__init__(self.db.loadDbDict(site))  # Load keys from database
        self.log.debug("ContentDb init: %.3fs, found files: %s, sites: %s" % (time.time() - s, len(self), len(self.db.site_ids)))

    def loadItem(self, key):
        try:
            self.num_loaded += 1
            if self.num_loaded % 100 == 0:
                self.log.debug("Loaded json: %s (latest: %s)" % (self.num_loaded, key))
            content = self.site.storage.loadJson(key)
            dict.__setitem__(self, key, content)
        except IOError:
            if dict.get(self, key):
                self.__delitem__(key)  # File not exists anymore
            raise KeyError(key)

        self.addCachedKey(key)
        self.checkLimit()

        return content

    def getItemSize(self, key):
        return self.site.storage.getSize(key)

    # Only keep last 50 accessed json in memory
    def checkLimit(self):
        if len(self.cached_keys) > 50:
            key_deleted = self.cached_keys.pop(0)
            dict.__setitem__(self, key_deleted, False)

    def addCachedKey(self, key):
        if key not in self.cached_keys and key != "content.json" and len(key) > 40:  # Always keep keys smaller than 40 char
            self.cached_keys.append(key)

    def __getitem__(self, key):
        val = dict.get(self, key)
        if val:  # Already loaded
            return val
        elif val is None:  # Unknown key
            raise KeyError(key)
        elif val is False:  # Loaded before, but purged from cache
            return self.loadItem(key)

    def __setitem__(self, key, val):
        self.addCachedKey(key)
        self.checkLimit()
        size = self.getItemSize(key)
        self.db.setContent(self.site, key, val, size)
        dict.__setitem__(self, key, val)

    def __delitem__(self, key):
        self.db.deleteContent(self.site, key)
        dict.__delitem__(self, key)
        try:
            self.cached_keys.remove(key)
        except ValueError:
            pass

    def iteritems(self):
        for key in dict.keys(self):
            try:
                val = self[key]
            except Exception, err:
                self.log.warning("Error loading %s: %s" % (key, err))
                continue
            yield key, val

    def items(self):
        back = []
        for key in dict.keys(self):
            try:
                val = self[key]
            except Exception, err:
                self.log.warning("Error loading %s: %s" % (key, err))
                continue
            back.append((key, val))
        return back

    def values(self):
        back = []
        for key, val in dict.iteritems(self):
            if not val:
                try:
                    val = self.loadItem(key)
                except Exception:
                    continue
            back.append(val)
        return back

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def execute(self, query, params={}):
        params["site_id"] = self.db_id
        return self.db.execute(query, params)

if __name__ == "__main__":
    import psutil
    process = psutil.Process(os.getpid())
    s_mem = process.memory_info()[0] / float(2 ** 20)
    root = "data-live/1MaiL5gfBM1cyb4a8e3iiL8L5gXmoAJu27"
    contents = ContentDbDict("1MaiL5gfBM1cyb4a8e3iiL8L5gXmoAJu27", root)
    print "Init len", len(contents)

    s = time.time()
    for dir_name in os.listdir(root + "/data/users/")[0:8000]:
        contents["data/users/%s/content.json" % dir_name]
    print "Load: %.3fs" % (time.time() - s)

    s = time.time()
    found = 0
    for key, val in contents.iteritems():
        found += 1
        assert key
        assert val
    print "Found:", found
    print "Iteritem: %.3fs" % (time.time() - s)

    s = time.time()
    found = 0
    for key in contents.keys():
        found += 1
        assert key in contents
    print "In: %.3fs" % (time.time() - s)

    print "Len:", len(contents.values()), len(contents.keys())

    print "Mem: +", process.memory_info()[0] / float(2 ** 20) - s_mem

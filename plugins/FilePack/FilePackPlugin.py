import os
import re

from Plugin import PluginManager
from Config import config
from util import helper


# Keep archive open for faster reponse times for large sites
archive_cache = {}


def closeArchive(archive_path):
    if archive_path in archive_cache:
        del archive_cache[archive_path]


def openArchive(archive_path, path_within):
    if archive_path not in archive_cache:
        if archive_path.endswith("tar.gz"):
            import tarfile
            archive_cache[archive_path] = tarfile.open(archive_path, "r:gz")
        elif archive_path.endswith("tar.bz2"):
            import tarfile
            archive_cache[archive_path] = tarfile.open(archive_path, "r:bz2")
        else:
            import zipfile
            archive_cache[archive_path] = zipfile.ZipFile(archive_path)
        helper.timer(5, lambda: closeArchive(archive_path))  # Close after 5 sec

    archive = archive_cache[archive_path]

    if archive_path.endswith(".zip"):
        return archive.open(path_within)
    else:
        return archive.extractfile(path_within.encode("utf8"))


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def actionSiteMedia(self, path, header_length=True):
        if ".zip/" in path or ".tar.gz/" in path:
            path_parts = self.parsePath(path)
            file_path = u"%s/%s/%s" % (config.data_dir, path_parts["address"], path_parts["inner_path"].decode("utf8"))
            match = re.match("^(.*\.(?:tar.gz|tar.bz2|zip))/(.*)", file_path)
            archive_path, path_within = match.groups()
            if not os.path.isfile(archive_path):
                site = self.server.site_manager.get(path_parts["address"])
                if not site:
                    self.error404(path)
                # Wait until file downloads
                result = site.needFile(site.storage.getInnerPath(archive_path), priority=10)
                # Send virutal file path download finished event to remove loading screen
                site.updateWebsocket(file_done=site.storage.getInnerPath(file_path))
                if not result:
                    return self.error404(path)
            try:
                file = openArchive(archive_path, path_within)
                content_type = self.getContentType(file_path)
                self.sendHeader(200, content_type=content_type)
                return self.streamFile(file)
            except Exception, err:
                self.log.debug("Error opening archive file: %s" % err)
                return self.error404(path)

        return super(UiRequestPlugin, self).actionSiteMedia(path, header_length=header_length)

    def streamFile(self, file):
        while 1:
            try:
                block = file.read(60 * 1024)
                if block:
                    yield block
                else:
                    raise StopIteration
            except StopIteration:
                file.close()
                break


@PluginManager.registerTo("SiteStorage")
class SiteStoragePlugin(object):
    def isFile(self, inner_path):
        if ".zip/" in inner_path or ".tar.gz/" in inner_path or ".tar.bz2/" in inner_path:
            match = re.match("^(.*\.(?:tar.gz|tar.bz2|zip))/(.*)", inner_path)
            inner_archive_path, path_within = match.groups()
            return super(SiteStoragePlugin, self).isFile(inner_archive_path)
        else:
            return super(SiteStoragePlugin, self).isFile(inner_path)

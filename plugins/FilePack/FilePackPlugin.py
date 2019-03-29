import os
import re

import gevent

from Plugin import PluginManager
from Config import config
from Debug import Debug

# Keep archive open for faster reponse times for large sites
archive_cache = {}


def closeArchive(archive_path):
    if archive_path in archive_cache:
        del archive_cache[archive_path]


def openArchive(archive_path, file_obj=None):
    if archive_path not in archive_cache:
        if archive_path.endswith("tar.gz"):
            import tarfile
            archive_cache[archive_path] = tarfile.open(archive_path, fileobj=file_obj, mode="r:gz")
        elif archive_path.endswith("tar.bz2"):
            import tarfile
            archive_cache[archive_path] = tarfile.open(archive_path, fileobj=file_obj, mode="r:bz2")
        else:
            import zipfile
            archive_cache[archive_path] = zipfile.ZipFile(file_obj or archive_path)
        gevent.spawn_later(5, lambda: closeArchive(archive_path))  # Close after 5 sec

    archive = archive_cache[archive_path]
    return archive


def openArchiveFile(archive_path, path_within, file_obj=None):
    archive = openArchive(archive_path, file_obj=file_obj)
    if archive_path.endswith(".zip"):
        return archive.open(path_within)
    else:
        return archive.extractfile(path_within)


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def actionSiteMedia(self, path, **kwargs):
        if ".zip/" in path or ".tar.gz/" in path:
            file_obj = None
            path_parts = self.parsePath(path)
            file_path = "%s/%s/%s" % (config.data_dir, path_parts["address"], path_parts["inner_path"])
            match = re.match("^(.*\.(?:tar.gz|tar.bz2|zip))/(.*)", file_path)
            archive_path, path_within = match.groups()
            if archive_path not in archive_cache:
                site = self.server.site_manager.get(path_parts["address"])
                if not site:
                    return self.actionSiteAddPrompt(path)
                archive_inner_path = site.storage.getInnerPath(archive_path)
                if not os.path.isfile(archive_path):
                    # Wait until file downloads
                    result = site.needFile(archive_inner_path, priority=10)
                    # Send virutal file path download finished event to remove loading screen
                    site.updateWebsocket(file_done=archive_inner_path)
                    if not result:
                        return self.error404(archive_inner_path)
                file_obj = site.storage.openBigfile(archive_inner_path)
                if file_obj == False:
                    file_obj = None

            header_allow_ajax = False
            if self.get.get("ajax_key"):
                requester_site = self.server.site_manager.get(path_parts["request_address"])
                if self.get["ajax_key"] == requester_site.settings["ajax_key"]:
                    header_allow_ajax = True
                else:
                    return self.error403("Invalid ajax_key")

            try:
                file = openArchiveFile(archive_path, path_within, file_obj=file_obj)
                content_type = self.getContentType(file_path)
                self.sendHeader(200, content_type=content_type, noscript=kwargs.get("header_noscript", False), allow_ajax=header_allow_ajax)
                return self.streamFile(file)
            except Exception as err:
                self.log.debug("Error opening archive file: %s" % Debug.formatException(err))
                return self.error404(path)

        return super(UiRequestPlugin, self).actionSiteMedia(path, **kwargs)

    def streamFile(self, file):
        for i in range(100):  # Read max 6MB
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
        if ".zip/" in inner_path or ".tar.gz/" in inner_path:
            match = re.match("^(.*\.(?:tar.gz|tar.bz2|zip))/(.*)", inner_path)
            archive_inner_path, path_within = match.groups()
            return super(SiteStoragePlugin, self).isFile(archive_inner_path)
        else:
            return super(SiteStoragePlugin, self).isFile(inner_path)

    def openArchive(self, inner_path):
        archive_path = self.getPath(inner_path)
        file_obj = None
        if archive_path not in archive_cache:
            if not os.path.isfile(archive_path):
                result = self.site.needFile(inner_path, priority=10)
                self.site.updateWebsocket(file_done=inner_path)
                if not result:
                    raise Exception("Unable to download file")
            file_obj = self.site.storage.openBigfile(inner_path)
            if file_obj == False:
                file_obj = None

        try:
            archive = openArchive(archive_path, file_obj=file_obj)
        except Exception as err:
            raise Exception("Unable to download file: %s" % Debug.formatException(err))

        return archive

    def walk(self, inner_path, *args, **kwags):
        if ".zip" in inner_path or ".tar.gz" in inner_path:
            match = re.match("^(.*\.(?:tar.gz|tar.bz2|zip))(.*)", inner_path)
            archive_inner_path, path_within = match.groups()
            archive = self.openArchive(archive_inner_path)
            path_within = path_within.lstrip("/")

            if archive_inner_path.endswith(".zip"):
                namelist = [name for name in archive.namelist() if not name.endswith("/")]
            else:
                namelist = [item.name for item in archive.getmembers() if not item.isdir()]

            namelist_relative = []
            for name in namelist:
                if not name.startswith(path_within):
                    continue
                name_relative = name.replace(path_within, "", 1).rstrip("/")
                namelist_relative.append(name_relative)

            return namelist_relative

        else:
            return super(SiteStoragePlugin, self).walk(inner_path, *args, **kwags)

    def list(self, inner_path, *args, **kwags):
        if ".zip" in inner_path or ".tar.gz" in inner_path:
            match = re.match("^(.*\.(?:tar.gz|tar.bz2|zip))(.*)", inner_path)
            archive_inner_path, path_within = match.groups()
            archive = self.openArchive(archive_inner_path)
            path_within = path_within.lstrip("/")

            if archive_inner_path.endswith(".zip"):
                namelist = [name for name in archive.namelist()]
            else:
                namelist = [item.name for item in archive.getmembers()]

            namelist_relative = []
            for name in namelist:
                if not name.startswith(path_within):
                    continue
                name_relative = name.replace(path_within, "", 1).rstrip("/")

                if "/" in name_relative:  # File is in sub-directory
                    continue

                namelist_relative.append(name_relative)
            return namelist_relative

        else:
            return super(SiteStoragePlugin, self).list(inner_path, *args, **kwags)

    def read(self, inner_path, mode="rb"):
        if ".zip/" in inner_path or ".tar.gz/" in inner_path:
            match = re.match("^(.*\.(?:tar.gz|tar.bz2|zip))(.*)", inner_path)
            archive_inner_path, path_within = match.groups()
            archive = self.openArchive(archive_inner_path)
            path_within = path_within.lstrip("/")

            if archive_inner_path.endswith(".zip"):
                return archive.open(path_within).read()
            else:
                return archive.extractfile(path_within).read()

        else:
            return super(SiteStoragePlugin, self).read(inner_path, mode)


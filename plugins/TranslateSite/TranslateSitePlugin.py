import time

from Plugin import PluginManager
from Translate import translate


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def actionSiteMedia(self, path, **kwargs):
        file_name = path.split("/")[-1].lower()
        if not file_name:  # Path ends with /
            file_name = "index.html"
        extension = file_name.split(".")[-1]

        if extension == "html":  # Always replace translate variables in html files
            should_translate = True
        elif extension == "js" and translate.lang != "en":
            should_translate = True
        else:
            should_translate = False

        if should_translate:
            path_parts = self.parsePath(path)
            kwargs["header_length"] = False
            file_generator = super(UiRequestPlugin, self).actionSiteMedia(path, **kwargs)
            if "__next__" in dir(file_generator):  # File found and generator returned
                site = self.server.sites.get(path_parts["address"])
                if not site or not site.content_manager.contents.get("content.json"):
                    return file_generator
                return self.actionPatchFile(site, path_parts["inner_path"], file_generator)
            else:
                return file_generator

        else:
            return super(UiRequestPlugin, self).actionSiteMedia(path, **kwargs)

    def actionUiMedia(self, path):
        file_generator = super(UiRequestPlugin, self).actionUiMedia(path)
        if translate.lang != "en" and path.endswith(".js"):
            s = time.time()
            data = b"".join(list(file_generator))
            data = translate.translateData(data.decode("utf8"))
            self.log.debug("Patched %s (%s bytes) in %.3fs" % (path, len(data), time.time() - s))
            return iter([data.encode("utf8")])
        else:
            return file_generator

    def actionPatchFile(self, site, inner_path, file_generator):
        content_json = site.content_manager.contents.get("content.json")
        lang_file = "languages/%s.json" % translate.lang
        lang_file_exist = False
        if site.settings.get("own"):  # My site, check if the file is exist (allow to add new lang without signing)
            if site.storage.isFile(lang_file):
                lang_file_exist = True
        else:  # Not my site the reference in content.json is enough (will wait for download later)
            if lang_file in content_json.get("files", {}):
                lang_file_exist = True

        if not lang_file_exist or inner_path not in content_json.get("translate", []):
            for part in file_generator:
                if inner_path.endswith(".html"):
                    yield part.replace(b"lang={lang}", b"lang=" + translate.lang.encode("utf8"))  # lang get parameter to .js file to avoid cache
                else:
                    yield part
        else:
            s = time.time()
            data = b"".join(list(file_generator)).decode("utf8")

            # if site.content_manager.contents["content.json"]["files"].get(lang_file):
            site.needFile(lang_file, priority=10)
            try:
                if inner_path.endswith("js"):
                    data = translate.translateData(data, site.storage.loadJson(lang_file), "js")
                else:
                    data = translate.translateData(data, site.storage.loadJson(lang_file), "html")
            except Exception as err:
                site.log.error("Error loading translation file %s: %s" % (lang_file, err))

            self.log.debug("Patched %s (%s bytes) in %.3fs" % (inner_path, len(data), time.time() - s))
            yield data.encode("utf8")

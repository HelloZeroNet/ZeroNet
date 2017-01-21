import urllib
import zipfile
import os
import sys
import ssl
import httplib
import socket
import re
import json
import cStringIO as StringIO

from gevent import monkey
monkey.patch_all()


def download():
    from src.util import helper

    urls = [
        "https://github.com/HelloZeroNet/ZeroNet/archive/master.zip",
        "https://gitlab.com/HelloZeroNet/ZeroNet/repository/archive.zip?ref=master",
        "https://try.gogs.io/ZeroNet/ZeroNet/archive/master.zip"
    ]

    zipdata = None
    for url in urls:
        print "Downloading from:", url,
        try:
            req = helper.httpRequest(url)
            data = StringIO.StringIO()
            while True:
                buff = req.read(1024 * 16)
                if not buff:
                    break
                data.write(buff)
                print ".",
            try:
                zipdata = zipfile.ZipFile(data)
                break  # Success
            except Exception, err:
                data.seek(0)
                print "Unpack error", err, data.read(256)
        except Exception, err:
            print "Error downloading update from %s: %s" % (url, err)

    if not zipdata:
        raise err

    print "Downloaded."

    return zipdata


def update():
    from Config import config
    if getattr(sys, 'source_update_dir', False):
        if not os.path.isdir(sys.source_update_dir):
            os.makedirs(sys.source_update_dir)
        os.chdir(sys.source_update_dir)  # New source code will be stored in different directory

    updatesite_path = config.data_dir + "/" + config.updatesite
    sites_json = json.load(open(config.data_dir + "/sites.json"))
    updatesite_bad_files = sites_json.get(config.updatesite, {}).get("cache", {}).get("bad_files", {})
    print "Update site path: %s, bad_files: %s" % (updatesite_path, len(updatesite_bad_files))
    if os.path.isfile(updatesite_path + "/content.json") and len(updatesite_bad_files) == 0 and sites_json.get(config.updatesite, {}).get("serving"):
        # Update site exists and no broken file
        print "Updating using site %s" % config.updatesite
        zipdata = False
        inner_paths = json.load(open(updatesite_path + "/content.json"))["files"].keys()
        # Keep file only in ZeroNet directory
        inner_paths = [inner_path for inner_path in inner_paths if inner_path.startswith("ZeroNet/")]
    else:
        # Fallback to download
        zipdata = download()
        inner_paths = zipdata.namelist()

    # Checking plugins
    plugins_enabled = []
    plugins_disabled = []
    if os.path.isdir("plugins"):
        for dir in os.listdir("plugins"):
            if dir.startswith("disabled-"):
                plugins_disabled.append(dir.replace("disabled-", ""))
            else:
                plugins_enabled.append(dir)
        print "Plugins enabled:", plugins_enabled, "disabled:", plugins_disabled

    print "Extracting to %s..." % os.getcwd(),
    for inner_path in inner_paths:
        if ".." in inner_path:
            continue
        inner_path = inner_path.replace("\\", "/")  # Make sure we have unix path
        print ".",
        dest_path = re.sub("^([^/]*-master.*?|ZeroNet)/", "", inner_path)  # Skip root zeronet-master-... like directories
        dest_path = dest_path.lstrip("/")
        if not dest_path:
            continue

        # Keep plugin disabled/enabled status
        match = re.match("plugins/([^/]+)", dest_path)
        if match:
            plugin_name = match.group(1).replace("disabled-", "")
            if plugin_name in plugins_enabled:  # Plugin was enabled
                dest_path = dest_path.replace("plugins/disabled-" + plugin_name, "plugins/" + plugin_name)
            elif plugin_name in plugins_disabled:  # Plugin was disabled
                dest_path = dest_path.replace("plugins/" + plugin_name, "plugins/disabled-" + plugin_name)
            print "P",

        dest_dir = os.path.dirname(dest_path)

        if dest_dir and not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)

        if dest_dir != dest_path.strip("/"):
            if zipdata:
                data = zipdata.read(inner_path)
            else:
                data = open(updatesite_path + "/" + inner_path, "rb").read()

            try:
                open(dest_path, 'wb').write(data)
            except Exception, err:
                print dest_path, err

    print "Done."
    return True


if __name__ == "__main__":
    # Fix broken gevent SSL
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))  # Imports relative to src
    from Config import config
    config.parse()
    from src.util import SslPatch

    try:
        update()
    except Exception, err:
        print "Update error: %s" % err
    raw_input("Press enter to exit")

import urllib
import zipfile
import os
import ssl
import httplib
import socket
import re
import cStringIO as StringIO

from gevent import monkey
monkey.patch_all()


def update():
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

    print "Extracting...",
    for inner_path in zipdata.namelist():
        if ".." in inner_path:
            continue
        inner_path = inner_path.replace("\\", "/")  # Make sure we have unix path
        print ".",
        dest_path = re.sub("^[^/]*-master.*?/", "", inner_path)  # Skip root zeronet-master-... like directories
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
            data = zipdata.read(inner_path)
            try:
                open(dest_path, 'wb').write(data)
            except Exception, err:
                print dest_path, err

    print "Done."
    return True


def update_needed(current_revision):
    "A function to see if ZeroNet needs to be updated"
    from src.util import helper

    config_urls = [
        "https://raw.githubusercontent.com/HelloZeroNet/ZeroNet/master/src/Config.py",
        "https://gitlab.com/HelloZeroNet/ZeroNet/raw/master/src/Config.py",
        "https://try.gogs.io/ZeroNet/ZeroNet/raw/master/src/Config.py"
    ]

    # Just check each URL to see if the revision number is higher
    for config_url in config_urls:
        try:
            req = helper.httpRequest(config_url)
            data = StringIO.StringIO()
            while True:
                buff = req.read(1024 * 16)
                if not buff:
                    break
                data.write(buff)
            regex = r"(?<=self.rev = )\d+"
            online_rev = int(re.findall(regex, data.getvalue())[0])
            should_update = online_rev > current_revision
            if should_update:
                return should_update
        except Exception, err:
            print "Error downloading update from %s: %s" % (config_url, err)

    return False


if __name__ == "__main__":
    # Fix broken gevent SSL
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))  # Imports relative to src
    from Config import config
    config.parse()
    from src.util import SslPatch

    should_update = update_needed(int(config.rev))

    if should_update:
        try:
            update()
        except Exception, err:
            print "Update error: %s" % err
    else:
        print "Update not needed"
    raw_input("Press enter to exit")

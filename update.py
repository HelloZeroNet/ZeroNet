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

    print "Downloading.",
    req = helper.httpRequest("https://github.com/HelloZeroNet/ZeroNet/archive/master.zip")
    data = StringIO.StringIO()
    while True:
        buff = req.read(1024 * 16)
        if not buff:
            break
        data.write(buff)
        print ".",
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
    try:
        zip = zipfile.ZipFile(data)
    except Exception, err:
        data.seek(0)
        print "Unpack error", err, data.read()
        return False
    for inner_path in zip.namelist():
        if ".." in inner_path:
            continue
        inner_path = inner_path.replace("\\", "/")  # Make sure we have unix path
        print ".",
        dest_path = inner_path.replace("ZeroNet-master/", "")
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
            data = zip.read(inner_path)
            try:
                open(dest_path, 'wb').write(data)
            except Exception, err:
                print dest_path, err

    print "Done."
    return True


if __name__ == "__main__":
    try:
        update()
    except Exception, err:
        print "Update error: %s" % err
    raw_input("Press enter to exit")

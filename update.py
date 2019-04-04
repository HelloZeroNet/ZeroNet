import os
import sys
import json
import re

def update():
    from Config import config

    if getattr(sys, 'source_update_dir', False):
        if not os.path.isdir(sys.source_update_dir):
            os.makedirs(sys.source_update_dir)
        source_path = sys.source_update_dir.rstrip("/")
    else:
        source_path = os.getcwd().rstrip("/")

    updatesite_path = config.data_dir + "/" + config.updatesite

    sites_json = json.load(open(config.data_dir + "/sites.json"))
    updatesite_bad_files = sites_json.get(config.updatesite, {}).get("cache", {}).get("bad_files", {})
    print(
        "Update site path: %s, bad_files: %s, source path: %s, dist type: %s" %
        (updatesite_path, len(updatesite_bad_files), source_path, config.dist_type)
    )

    inner_paths = json.load(open(updatesite_path + "/content.json"))["files"].keys()

    # Keep file only in ZeroNet directory
    inner_paths = [inner_path for inner_path in inner_paths if inner_path.startswith("core/")]

    # Checking plugins
    plugins_enabled = []
    plugins_disabled = []
    if os.path.isdir("%s/plugins" % source_path):
        for dir in os.listdir("%s/plugins" % source_path):
            if dir.startswith("disabled-"):
                plugins_disabled.append(dir.replace("disabled-", ""))
            else:
                plugins_enabled.append(dir)
        print("Plugins enabled:", plugins_enabled, "disabled:", plugins_disabled)

    for inner_path in inner_paths:
        if ".." in inner_path:
            continue
        inner_path = inner_path.replace("\\", "/")  # Make sure we have unix path
        print(".", end=" ")
        dest_path = source_path + "/" + re.sub("^(core|platform/[^/]+/)/", "", inner_path)
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
            print("P", end=" ")

        dest_dir = os.path.dirname(dest_path)
        print(updatesite_path + "/" + inner_path, "->", dest_path)
        if dest_dir and not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)

        if dest_dir != dest_path.strip("/"):
            data = open(updatesite_path + "/" + inner_path, "rb").read()

            try:
                open(dest_path, 'wb').write(data)
            except Exception as err:
                print(dest_path, err)

    print("Done.")

    return False

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))  # Imports relative to src

    from gevent import monkey
    monkey.patch_all()

    from Config import config
    config.parse(silent=True)

    try:
        update()
    except Exception as err:
        print("Update error: %s" % err)

import os
import sys
import json
import re


def update():
    from Config import config
    config.parse()

    if getattr(sys, 'source_update_dir', False):
        if not os.path.isdir(sys.source_update_dir):
            os.makedirs(sys.source_update_dir)
        source_path = sys.source_update_dir.rstrip("/")
    else:
        source_path = os.getcwd().rstrip("/")

    runtime_path = os.path.dirname(sys.executable)

    updatesite_path = config.data_dir + "/" + config.updatesite

    sites_json = json.load(open(config.data_dir + "/sites.json"))
    updatesite_bad_files = sites_json.get(config.updatesite, {}).get("cache", {}).get("bad_files", {})
    print(
        "Update site path: %s, bad_files: %s, source path: %s, runtime path: %s, dist type: %s" %
        (updatesite_path, len(updatesite_bad_files), source_path, runtime_path, config.dist_type)
    )

    updatesite_content_json = json.load(open(updatesite_path + "/content.json"))
    inner_paths = list(updatesite_content_json.get("files", {}).keys())
    inner_paths += list(updatesite_content_json.get("files_optional", {}).keys())

    # Keep file only in ZeroNet directory
    inner_paths = [inner_path for inner_path in inner_paths if re.match("^(core|bundle)", inner_path)]

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

    update_paths = {}

    for inner_path in inner_paths:
        if ".." in inner_path:
            continue
        inner_path = inner_path.replace("\\", "/").strip("/")  # Make sure we have unix path
        print(".", end=" ")
        if inner_path.startswith("core"):
            dest_path = source_path + "/" + re.sub("^core/", "", inner_path)
        elif inner_path.startswith(config.dist_type):
            dest_path = runtime_path + "/" + re.sub("^bundle[^/]+/", "", inner_path)
        else:
            continue

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
        if dest_dir and not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)

        if dest_dir != dest_path.strip("/"):
            update_paths[updatesite_path + "/" + inner_path] = dest_path

    num_ok = 0
    num_rename = 0
    num_error = 0
    for path_from, path_to in update_paths.items():
        print("-", path_from, "->", path_to)
        if not os.path.isfile(path_from):
            print("Missing file")
            continue

        data = open(path_from, "rb").read()

        try:
            open(path_to, 'wb').write(data)
            num_ok += 1
        except Exception as err:
            try:
                print("Error writing: %s. Renaming old file to avoid lock on Windows..." % err)
                path_to_tmp = path_to + "-old"
                if os.path.isfile(path_to_tmp):
                    os.unlink(path_to_tmp)
                os.rename(path_to, path_to_tmp)
                num_rename += 1
                open(path_to, 'wb').write(data)
                print("Write done after rename!")
                num_ok += 1
            except Exception as err:
                print("Write error after rename: %s" % err)
                num_error += 1
    print("* Updated files: %s, renamed: %s, error: %s" % (num_ok, num_rename, num_error))


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))  # Imports relative to src

    update()
import os
import subprocess
import re
import logging
import time
import functools

from Config import config
from util import helper


# Find files with extension in path
def findfiles(path, find_ext):
    def sorter(f1, f2):
        f1 = f1[0].replace(path, "")
        f2 = f2[0].replace(path, "")
        if f1 == "":
            return 1
        elif f2 == "":
            return -1
        else:
            return helper.cmp(f1.lower(), f2.lower())

    for root, dirs, files in sorted(os.walk(path, topdown=False), key=functools.cmp_to_key(sorter)):
        for file in sorted(files):
            file_path = root + "/" + file
            file_ext = file.split(".")[-1]
            if file_ext in find_ext and not file.startswith("all."):
                yield file_path.replace("\\", "/")


# Try to find coffeescript compiler in path
def findCoffeescriptCompiler():
    coffeescript_compiler = None
    try:
        import distutils.spawn
        coffeescript_compiler = helper.shellquote(distutils.spawn.find_executable("coffee")) + " --no-header -p"
    except:
        pass
    if coffeescript_compiler:
        return coffeescript_compiler
    else:
        return False


# Generates: all.js: merge *.js, compile coffeescript, all.css: merge *.css, vendor prefix features
def merge(merged_path):
    merged_path = merged_path.replace("\\", "/")
    merge_dir = os.path.dirname(merged_path)
    s = time.time()
    ext = merged_path.split(".")[-1]
    if ext == "js":  # If merging .js find .coffee too
        find_ext = ["js", "coffee"]
    else:
        find_ext = [ext]

    # If exist check the other files modification date
    if os.path.isfile(merged_path):
        merged_mtime = os.path.getmtime(merged_path)
    else:
        merged_mtime = 0

    changed = {}
    for file_path in findfiles(merge_dir, find_ext):
        if os.path.getmtime(file_path) > merged_mtime + 1:
            changed[file_path] = True
    if not changed:
        return  # Assets not changed, nothing to do

    old_parts = {}
    if os.path.isfile(merged_path):  # Find old parts to avoid unncessary recompile
        merged_old = open(merged_path, "rb").read()
        for match in re.findall(rb"(/\* ---- (.*?) ---- \*/(.*?)(?=/\* ----|$))", merged_old, re.DOTALL):
            old_parts[match[1].decode()] = match[2].strip(b"\n\r")

    logging.debug("Merging %s (changed: %s, old parts: %s)" % (merged_path, changed, len(old_parts)))
    # Merge files
    parts = []
    s_total = time.time()
    for file_path in findfiles(merge_dir, find_ext):
        file_relative_path = file_path.replace(merge_dir + "/", "")
        parts.append(b"\n/* ---- %s ---- */\n\n" % file_relative_path.encode("utf8"))
        if file_path.endswith(".coffee"):  # Compile coffee script
            if file_path in changed or file_relative_path not in old_parts:  # Only recompile if changed or its not compiled before
                if config.coffeescript_compiler is None:
                    config.coffeescript_compiler = findCoffeescriptCompiler()
                if not config.coffeescript_compiler:
                    logging.error("No coffeescript compiler defined, skipping compiling %s" % merged_path)
                    return False  # No coffeescript compiler, skip this file

                # Replace / with os separators and escape it
                file_path_escaped = helper.shellquote(file_path.replace("/", os.path.sep))

                if "%s" in config.coffeescript_compiler:  # Replace %s with coffeescript file
                    command = config.coffeescript_compiler.replace("%s", file_path_escaped)
                else:  # Put coffeescript file to end
                    command = config.coffeescript_compiler + " " + file_path_escaped

                # Start compiling
                s = time.time()
                compiler = subprocess.Popen(command, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
                out = compiler.stdout.read()
                compiler.wait()
                logging.debug("Running: %s (Done in %.2fs)" % (command, time.time() - s))

                # Check errors
                if out and out.startswith(b"("):  # No error found
                    parts.append(out)
                else:  # Put error message in place of source code
                    error = out
                    logging.error("%s Compile error: %s" % (file_relative_path, error))
                    error_escaped = re.escape(error).replace(b"\n", b"\\n").replace(br"\\n", br"\n")
                    parts.append(
                        b"alert('%s compile error: %s');" %
                        (file_relative_path.encode(), error_escaped)
                    )
            else:  # Not changed use the old_part
                parts.append(old_parts[file_relative_path])
        else:  # Add to parts
            parts.append(open(file_path, "rb").read())

    merged = b"\n".join(parts)
    if ext == "css":  # Vendor prefix css
        from lib.cssvendor import cssvendor
        merged = cssvendor.prefix(merged)
    merged = merged.replace(b"\r", b"")
    open(merged_path, "wb").write(merged)
    logging.debug("Merged %s (%.2fs)" % (merged_path, time.time() - s_total))


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    os.chdir("..")
    config.coffeescript_compiler = r'type "%s" | tools\coffee-node\bin\node.exe tools\coffee-node\bin\coffee --no-header -s -p'
    merge("data/12Hw8rTgzrNo4DSh2AkqwPRqDyTticwJyH/js/all.js")

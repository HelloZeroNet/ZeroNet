import os, subprocess, re, logging, time
from Config import config

# Find files with extension in path
def findfiles(path, find_ext):
	for root, dirs, files in os.walk(path, topdown = False):
		for file in sorted(files):
			file_path = root+"/"+file
			file_ext = file.split(".")[-1]
			if file_ext in find_ext and not file.startswith("all."): yield file_path.replace("\\", "/")


# Generates: all.js: merge *.js, compile coffeescript, all.css: merge *.css, vendor prefix features
def merge(merged_path):
	merge_dir = os.path.dirname(merged_path)
	s = time.time()
	ext = merged_path.split(".")[-1]
	if ext == "js": # If merging .js find .coffee too
		find_ext = ["js", "coffee"]
	else:
		find_ext = [ext]

	# If exits check the other files modification date
	if os.path.isfile(merged_path): 
		merged_mtime = os.path.getmtime(merged_path)
	else:
		merged_mtime = 0


	changed = {}
	for file_path in findfiles(merge_dir, find_ext):
		if os.path.getmtime(file_path) > merged_mtime: 
			changed[file_path] = True
	if not changed: return # Assets not changed, nothing to do

	if os.path.isfile(merged_path): # Find old parts to avoid unncessary recompile
		merged_old = open(merged_path, "rb").read().decode("utf8")
		old_parts = {}
		for match in re.findall("(/\* ---- (.*?) ---- \*/(.*?)(?=/\* ----|$))", merged_old, re.DOTALL):
			old_parts[match[1]] = match[2].strip("\n\r")

	# Merge files
	parts = []
	s_total = time.time()
	for file_path in findfiles(merge_dir, find_ext):
		parts.append("\n\n/* ---- %s ---- */\n\n" % file_path)
		if file_path.endswith(".coffee"): # Compile coffee script
			if file_path in changed or file_path not in old_parts: # Only recompile if changed or its not compiled before
				if not config.coffeescript_compiler: 
					logging.error("No coffeescript compiler definied, skipping compiling %s" % merged_path)
					return False # No coffeescript compiler, skip this file
				command = config.coffeescript_compiler % os.path.join(*file_path.split("/")) # Fix os path separator
				s = time.time()
				compiler = subprocess.Popen(command, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
				out = compiler.stdout.read().decode("utf8")
				logging.debug("Running: %s (Done in %.2fs)" % (command, time.time()-s))
				if out and out.startswith("("):
					parts.append(out)
				else:
					error = out
					logging.error("%s Compile error: %s" % (file_path, error))
					parts.append("alert('%s compile error: %s');" % (file_path, re.escape(error).replace("\n", "\\n").replace(r"\\n", r"\n") ) )
			else: # Not changed use the old_part
				parts.append(old_parts[file_path])
		else: # Add to parts
			parts.append(open(file_path).read().decode("utf8"))

	merged = u"\n".join(parts)
	if ext == "css": # Vendor prefix css
		from lib.cssvendor import cssvendor
		merged = cssvendor.prefix(merged)
	merged = merged.replace("\r", "")
	open(merged_path, "wb").write(merged.encode("utf8"))
	logging.debug("Merged %s (%.2fs)" % (merged_path, time.time()-s_total))


if __name__ == "__main__":
	logging.getLogger().setLevel(logging.DEBUG)
	os.chdir("..") 
	config.coffeescript_compiler = r'type "%s" | tools\coffee-node\bin\node.exe tools\coffee-node\bin\coffee --no-header -s -p'
	merge("data/12Hw8rTgzrNo4DSh2AkqwPRqDyTticwJyH/js/all.js")

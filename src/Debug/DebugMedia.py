import os, subprocess, re, logging, time
from Config import config

# Find files with extension in path
def findfiles(path, find_ext):
	for root, dirs, files in os.walk(path, topdown = False):
		for file in sorted(files):
			file_path = root+"/"+file
			file_ext = file.split(".")[-1]
			if file_ext in find_ext and not file.startswith("all."): yield file_path


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
		changed = False
		for file_path in findfiles(merge_dir, find_ext):
			if os.path.getmtime(file_path) > merged_mtime: 
				changed = True
				break
		if not changed: return # Assets not changed, nothing to do

	# Merge files
	parts = []
	for file_path in findfiles(merge_dir, find_ext):
		parts.append("\n\n/* ---- %s ---- */\n\n" % file_path.replace("\\", "/"))
		if file_path.endswith(".coffee"): # Compile coffee script
			if not config.coffeescript_compiler: 
				logging.error("No coffeescript compiler definied, skipping compiling %s" % merged_path)
				return False # No coffeescript compiler, skip this file
			command = config.coffeescript_compiler % file_path.replace("/", "\\")
			s = time.time()
			compiler = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
			logging.debug("Running: %s (Done in %.2fs)" % (command, time.time()-s))
			source = compiler.stdout.read()
			if source:
				parts.append(source)
			else:
				error = compiler.stderr.read()
				parts.append("alert('%s compile error: %s');" % (file_path, re.escape(error)) )
		else: # Add to parts
			parts.append(open(file_path).read())

	merged = "\n".join(parts)
	if ext == "css": # Vendor prefix css
		from lib.cssvendor import cssvendor
		merged = cssvendor.prefix(merged)
	merged = merged.replace("\r", "")
	open(merged_path, "wb").write(merged)
	logging.debug("Merged %s (%.2fs)" % (merged_path, time.time()-s))

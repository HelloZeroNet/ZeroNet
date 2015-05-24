import json, time, re, os, gevent, copy
from Debug import Debug
from Crypt import CryptHash
from Config import config

class ContentManager:
	def __init__(self, site):
		self.site = site
		self.log = self.site.log
		self.contents = {} # Known content.json (without files and includes)
		self.loadContent(add_bad_files = False)
		self.site.settings["size"] = self.getTotalSize()


	# Load content.json to self.content
	# Return: Changed files ["index.html", "data/messages.json"]
	def loadContent(self, content_inner_path = "content.json", add_bad_files = True, load_includes = True):
		content_inner_path = content_inner_path.strip("/") # Remove / from begning
		old_content = self.contents.get(content_inner_path)
		content_path = self.site.storage.getPath(content_inner_path)
		content_path_dir = self.toDir(self.site.storage.getPath(content_inner_path))
		content_dir = self.toDir(content_inner_path)

		if os.path.isfile(content_path):
			try:
				new_content = json.load(open(content_path))
			except Exception, err:
				self.log.error("%s load error: %s" % (content_path, Debug.formatException(err)))
				return False
		else:
			self.log.error("Content.json not exits: %s" % content_path)
			return False # Content.json not exits


		try:
			# Get the files where the sha512 changed
			changed = []
			for relative_path, info in new_content.get("files", {}).items():
				if "sha512" in info:
					hash_type = "sha512"
				else: # Backward compatiblity
					hash_type = "sha1"

				new_hash = info[hash_type]
				if old_content and old_content["files"].get(relative_path): # We have the file in the old content
					old_hash = old_content["files"][relative_path].get(hash_type)
				else: # The file is not in the old content
					old_hash = None
				if old_hash != new_hash: changed.append(content_dir+relative_path)

			# Load includes
			if load_includes and "includes" in new_content:
				for relative_path, info in new_content["includes"].items():
					include_inner_path = content_dir+relative_path
					if self.site.storage.isFile(include_inner_path): # Content.json exists, load it
						success = self.loadContent(include_inner_path, add_bad_files=add_bad_files)
						if success: changed += success # Add changed files
					else: # Content.json not exits, add to changed files
						self.log.debug("Missing include: %s" % include_inner_path)
						changed += [include_inner_path]

			# Load blind user includes (all subdir)
			if load_includes and "user_contents" in new_content:
				for relative_dir in os.listdir(content_path_dir):
					include_inner_path = content_dir+relative_dir+"/content.json"
					if not self.site.storage.isFile(include_inner_path): continue # Content.json not exits
					success = self.loadContent(include_inner_path, add_bad_files=add_bad_files, load_includes=False)
					if success: changed += success # Add changed files

			# Update the content
			self.contents[content_inner_path] = new_content
		except Exception, err:
			self.log.error("Content.json parse error: %s" % Debug.formatException(err))
			return False # Content.json parse error

		# Add changed files to bad files
		if add_bad_files:
			for inner_path in changed:
				self.site.bad_files[inner_path] = True

		if new_content["modified"] > self.site.settings.get("modified", 0):
			self.site.settings["modified"] = min(time.time()+60*10, new_content["modified"]) # Dont store modifications in the far future (more than 10 minute)

		return changed


	# Get total size of site
	# Return: 32819 (size of files in kb)
	def getTotalSize(self, ignore=None):
		total_size = 0
		for inner_path, content in self.contents.iteritems():
			if inner_path == ignore: continue
			total_size += self.site.storage.getSize(inner_path) # Size of content.json
			for file, info in content.get("files", {}).iteritems():
				total_size += info["size"]
		return total_size


	# Find the file info line from self.contents
	# Return: { "sha512": "c29d73d30ee8c9c1b5600e8a84447a6de15a3c3db6869aca4a2a578c1721f518", "size": 41 , "content_inner_path": "content.json"}
	def getFileInfo(self, inner_path):
		dirs = inner_path.split("/") # Parent dirs of content.json
		inner_path_parts = [dirs.pop()] # Filename relative to content.json
		while True:
			content_inner_path = "%s/content.json" % "/".join(dirs)
			content = self.contents.get(content_inner_path.strip("/"))
			if content and "files" in content: # Check if content.json exists
				back = content["files"].get("/".join(inner_path_parts))
				if back:
					back["content_inner_path"] = content_inner_path
					return back

			if content and "user_contents" in content: # User dir
				back = content["user_contents"]
				back["content_inner_path"] = re.sub("(.*)/.*?$", "\\1/content.json", inner_path) # Content.json is in the users dir
				return back

			# No inner path in this dir, lets try the parent dir
			if dirs: 
				inner_path_parts.insert(0, dirs.pop())
			else: # No more parent dirs
				break

		return False # Not found


	# Get rules for the file
	# Return: The rules for the file or False if not allowed
	def getRules(self, inner_path, content=None):
		if not inner_path.endswith("content.json"): # Find the files content.json first
			file_info = self.getFileInfo(inner_path)
			if not file_info: return False # File not found
			inner_path = file_info["content_inner_path"]
		dirs = inner_path.split("/") # Parent dirs of content.json
		inner_path_parts = [dirs.pop()] # Filename relative to content.json
		inner_path_parts.insert(0, dirs.pop()) # Dont check in self dir
		while True:
			content_inner_path = "%s/content.json" % "/".join(dirs)
			parent_content = self.contents.get(content_inner_path.strip("/"))
			if parent_content and "includes" in parent_content:
				return parent_content["includes"].get("/".join(inner_path_parts))
			elif parent_content and "user_contents" in parent_content:
				return self.getUserContentRules(parent_content, inner_path, content)
			else: # No inner path in this dir, lets try the parent dir
				if dirs: 
					inner_path_parts.insert(0, dirs.pop())
				else: # No more parent dirs
					break

		return False


	# Get rules for a user file
	# Return: The rules of the file or False if not allowed
	def getUserContentRules(self, parent_content, inner_path, content):
		user_contents = parent_content["user_contents"]
		user_address = re.match(".*/([A-Za-z0-9]*?)/.*?$", inner_path).group(1) # Delivered for directory

		try:
			if not content: content = self.site.storage.loadJson(inner_path) # Read the file if no content specificed
		except: # Content.json not exits
			return { "signers": [user_address], "user_address": user_address } # Return information that we know for sure

		"""if not "cert_user_name" in content: # New file, unknown user
			content["cert_auth_type"] = "unknown"
			content["cert_user_name"] = "unknown@unknown"
		"""
		user_urn = "%s/%s" % (content["cert_auth_type"], content["cert_user_id"]) # web/nofish@zeroid.bit

		rules = copy.copy(user_contents["permissions"].get(content["cert_user_id"], {})) # Default rules by username
		if rules == False: return False # User banned
		if "signers" in rules: rules["signers"] = rules["signers"][:] # Make copy of the signers
		for permission_pattern, permission_rules in user_contents["permission_rules"].items(): # Regexp rules
			if not re.match(permission_pattern, user_urn): continue # Rule is not valid for user
			# Update rules if its better than current recorded ones
			for key, val in permission_rules.iteritems():
				if key not in rules: 
					if type(val) is list:
						rules[key] = val[:] # Make copy
					else:
						rules[key] = val
				elif type(val) is int: # Int, update if larger
					if val > rules[key]: rules[key] = val
				elif hasattr(val, "startswith"): # String, update if longer
					if len(val) > len(rules[key]): rules[key] = val
				elif type(val) is list: # List, append
					rules[key] += val

		rules["cert_signers"] = user_contents["cert_signers"] # Add valid cert signers
		if "signers" not in rules: rules["signers"] = []
		rules["signers"].append(user_address) # Add user as valid signer
		rules["user_address"] = user_address


		return rules



	# Create and sign a content.json
	# Return: The new content if filewrite = False
	def sign(self, inner_path = "content.json", privatekey=None, filewrite=True, update_changed_files=False, extend=None):
		content = self.contents.get(inner_path)
		if not content: # Content not exits yet, load default one
			self.log.info("File %s not exits yet, loading default values..." % inner_path)
			content = {"files": {}, "signs": {}} # Default content.json
			if inner_path == "content.json": # Its the root content.json, add some more fields
				content["title"] = "%s - ZeroNet_" % self.site.address
				content["description"] = ""
				content["signs_required"] = 1
				content["ignore"] = ""
			if extend: content.update(extend) # Add custom fields

		directory = self.toDir(self.site.storage.getPath(inner_path))
		self.log.info("Opening site data directory: %s..." % directory)

		hashed_files = {}
		changed_files = [inner_path]
		for root, dirs, files in os.walk(directory):
			for file_name in files:
				file_path = self.site.storage.getPath("%s/%s" % (root.strip("/"), file_name))
				file_inner_path = re.sub(re.escape(directory), "", file_path)

				if file_name == "content.json": ignored = True
				elif content.get("ignore") and re.match(content["ignore"], file_inner_path): ignored = True
				elif file_name.startswith("."): ignored = True
				else: ignored = False

				if ignored: # Ignore content.json, definied regexp and files starting with .
					self.log.info("- [SKIPPED] %s" % file_inner_path)
				else:
					sha512sum = CryptHash.sha512sum(file_path) # Calculate sha512 sum of file
					self.log.info("- %s (SHA512: %s)" % (file_inner_path, sha512sum))
					hashed_files[file_inner_path] = {"sha512": sha512sum, "size": os.path.getsize(file_path)}
					if file_inner_path in content["files"].keys() and hashed_files[file_inner_path]["sha512"] != content["files"][file_inner_path].get("sha512"):
						changed_files.append(file_path)

		
		self.log.debug("Changed files: %s" % changed_files)
		if update_changed_files:
			for file_path in changed_files:
				self.site.storage.onUpdated(file_path)

		# Generate new content.json
		self.log.info("Adding timestamp and sha512sums to new content.json...")

		new_content = content.copy() # Create a copy of current content.json
		new_content["files"] = hashed_files # Add files sha512 hash
		new_content["modified"] = time.time() # Add timestamp
		if inner_path == "content.json": 
			new_content["address"] = self.site.address
			new_content["zeronet_version"] = config.version
			new_content["signs_required"] = content.get("signs_required", 1)

		from Crypt import CryptBitcoin
		self.log.info("Verifying private key...")
		privatekey_address = CryptBitcoin.privatekeyToAddress(privatekey)
		valid_signers = self.getValidSigners(inner_path, new_content)
		if privatekey_address not in valid_signers:
			return self.log.error("Private key invalid! Valid signers: %s, Private key address: %s" % (valid_signers, privatekey_address))
		self.log.info("Correct %s in valid signers: %s" % (privatekey_address, valid_signers))

		if inner_path == "content.json" and privatekey_address == self.site.address: # If signing using the root key sign the valid signers
			new_content["signers_sign"] = CryptBitcoin.sign("%s:%s" % (new_content["signs_required"], ",".join(valid_signers)), privatekey)
			if not new_content["signers_sign"]: self.log.info("Old style address, signers_sign is none")

		self.log.info("Signing %s..." % inner_path)

		if "signs" in new_content: del(new_content["signs"]) # Delete old signs
		if "sign" in new_content: del(new_content["sign"]) # Delete old sign (backward compatibility)

		sign_content = json.dumps(new_content, sort_keys=True)
		sign = CryptBitcoin.sign(sign_content, privatekey)
		#new_content["signs"] = content.get("signs", {}) # TODO: Multisig
		if sign: # If signing is successful (not an old address)
			new_content["signs"] = {}
			new_content["signs"][privatekey_address] = sign
			
		if inner_path == "content.json":  # To root content.json add old format sign for backward compatibility
			oldsign_content = json.dumps(new_content, sort_keys=True)
			new_content["sign"] = CryptBitcoin.signOld(oldsign_content, privatekey)

		if not self.validContent(inner_path, new_content):
			self.log.error("Sign failed: Invalid content")
			return False

		if filewrite:
			self.log.info("Saving to %s..." % inner_path)
			self.site.storage.writeJson(inner_path, new_content)

		self.log.info("File %s signed!" % inner_path)

		if filewrite: # Written to file
			return True
		else: # Return the new content
			return new_content


	# The valid signers of content.json file
	# Return: ["1KRxE1s3oDyNDawuYWpzbLUwNm8oDbeEp6", "13ReyhCsjhpuCVahn1DHdf6eMqqEVev162"]
	def getValidSigners(self, inner_path, content=None):
		valid_signers = []
		if inner_path == "content.json": # Root content.json
			if "content.json" in self.contents and "signers" in self.contents["content.json"]:
				valid_signers += self.contents["content.json"]["signers"].keys()
		else:
			rules = self.getRules(inner_path, content)
			if rules and "signers" in rules:
				valid_signers += rules["signers"]

		if self.site.address not in valid_signers: valid_signers.append(self.site.address) # Site address always valid
		return valid_signers


	# Return: The required number of valid signs for the content.json
	def getSignsRequired(self, inner_path, content=None):
		return 1 # Todo: Multisig


	def verifyCert(self, inner_path, content):
		from Crypt import CryptBitcoin

		rules = self.getRules(inner_path, content)
		if not rules.get("cert_signers"): return True # Does not need cert

		name, domain = content["cert_user_id"].split("@")
		cert_address = rules["cert_signers"].get(domain)
		if not cert_address: # Cert signer not allowed
			self.log.error("Invalid cert signer: %s" % domain)
			return False
		return CryptBitcoin.verify("%s#%s/%s" % (rules["user_address"], content["cert_auth_type"], name), cert_address, content["cert_sign"])


	# Checks if the content.json content is valid
	# Return: True or False
	def validContent(self, inner_path, content):
		content_size = len(json.dumps(content)) + sum([file["size"] for file in content["files"].values()]) # Size of new content
		site_size = self.getTotalSize(ignore=inner_path)+content_size # Site size without old content
		if site_size > self.site.settings.get("size", 0): self.site.settings["size"] = site_size # Save to settings if larger

		site_size_limit = self.site.getSizeLimit()*1024*1024

		# Check total site size limit
		if site_size > site_size_limit:
			self.log.error("%s: Site too large %s > %s, aborting task..." % (inner_path, site_size, site_size_limit))
			task = self.site.worker_manager.findTask(inner_path)
			if task: # Dont try to download from other peers
				self.site.worker_manager.failTask(task)
			return False

		if inner_path == "content.json": return True # Root content.json is passed

		# Load include details
		rules = self.getRules(inner_path, content)
		if not rules: 
			self.log.error("%s: No rules" % inner_path)
			return False

		# Check include size limit
		if rules.get("max_size"): # Include size limit
			if content_size > rules["max_size"]: 
				self.log.error("%s: Include too large %s > %s" % (inner_path, content_size, rules["max_size"]))
				return False

		# Check if content includes allowed
		if rules.get("includes_allowed") == False and content.get("includes"): 
			self.log.error("%s: Includes not allowed" % inner_path)
			return False # Includes not allowed

		# Filename limit
		if rules.get("files_allowed"): 
			for file_inner_path in content["files"].keys():
				if not re.match("^%s$" % rules["files_allowed"], file_inner_path):
					self.log.error("%s: File not allowed" % file_inner_path)
					return False

		return True # All good



	# Verify file validity
	# Return: None = Same as before, False = Invalid, True = Valid
	def verifyFile(self, inner_path, file, ignore_same = True):
		if inner_path.endswith("content.json"): # content.json: Check using sign
			from Crypt import CryptBitcoin
			try:
				new_content = json.load(file)
				if inner_path in self.contents: 
					old_content = self.contents.get(inner_path)
					# Checks if its newer the ours
					if old_content["modified"] == new_content["modified"] and ignore_same: # Ignore, have the same content.json
						return None
					elif old_content["modified"] > new_content["modified"]: # We have newer
						self.log.debug("We have newer %s (Our: %s, Sent: %s)" % (inner_path, old_content["modified"], new_content["modified"]))
						gevent.spawn(self.site.publish, inner_path=inner_path) # Try to fix the broken peers
						return False
				if new_content["modified"] > time.time()+60*60*24: # Content modified in the far future (allow 1 day window)
					self.log.error("%s modify is in the future!" % inner_path)
					return False
				# Check sign
				sign = new_content.get("sign")
				signs = new_content.get("signs", {})
				if "sign" in new_content: del(new_content["sign"]) # The file signed without the sign
				if "signs" in new_content: del(new_content["signs"]) # The file signed without the signs
				sign_content = json.dumps(new_content, sort_keys=True) # Dump the json to string to remove whitepsace

				if not self.validContent(inner_path, new_content): return False # Content not valid (files too large, invalid files)

				if signs: # New style signing
					valid_signers = self.getValidSigners(inner_path, new_content)
					signs_required = self.getSignsRequired(inner_path, new_content)

					if inner_path == "content.json" and len(valid_signers) > 1: # Check signers_sign on root content.json 
						if not CryptBitcoin.verify("%s:%s" % (signs_required, ",".join(valid_signers)), self.site.address, new_content["signers_sign"]):
							self.log.error("%s invalid signers_sign!" % inner_path)
							return False

					if inner_path != "content.json" and not self.verifyCert(inner_path, new_content): # Check if cert valid
						self.log.error("%s invalid cert!" % inner_path)
						return False

					valid_signs = 0
					for address in valid_signers:
						if address in signs: valid_signs += CryptBitcoin.verify(sign_content, address, signs[address])
						if valid_signs >= signs_required: break # Break if we has enough signs



					return valid_signs >= signs_required
				else: # Old style signing
					return CryptBitcoin.verify(sign_content, self.site.address, sign)

			except Exception, err:
				self.log.error("Verify sign error: %s" % Debug.formatException(err))
				return False

		else: # Check using sha512 hash
			file_info = self.getFileInfo(inner_path)
			if file_info:
				if "sha512" in file_info:
					hash_valid = CryptHash.sha512sum(file) == file_info["sha512"]
				elif "sha1" in file_info: # Backward compatibility
					hash_valid = CryptHash.sha1sum(file) == file_info["sha1"]
				else:
					hash_valid = False
				if file_info["size"] != file.tell():
					self.log.error("%s file size does not match %s <> %s, Hash: %s" % (inner_path, file.tell(), file_info["size"], hash_valid))
					return False
				return hash_valid
				
			else: # File not in content.json
				self.log.error("File not in content.json: %s" % inner_path)
				return False


	# Get dir from file
	# Return: data/site/content.json -> data/site
	def toDir(self, inner_path):
		file_dir = re.sub("[^/]*?$", "", inner_path).strip("/")
		if file_dir: file_dir += "/" # Add / at end if its not the root
		return file_dir




def testSign():
	global config
	from Config import config
	from Site import Site
	site = Site("12Hw8rTgzrNo4DSh2AkqwPRqDyTticwJyH")
	content_manager = ContentManager(site)
	content_manager.sign("data/users/1KRxE1s3oDyNDawuYWpzbLUwNm8oDbeEp6/content.json", "5JCGE6UUruhfmAfcZ2GYjvrswkaiq7uLo6Gmtf2ep2Jh2jtNzWR")


def testVerify():
	from Config import config
	from Site import Site
	#site = Site("1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr")
	site = Site("12Hw8rTgzrNo4DSh2AkqwPRqDyTticwJyH")

	content_manager = ContentManager(site)
	print "Loaded contents:", content_manager.contents.keys()

	file = open(site.storage.getPath("data/users/1KRxE1s3oDyNDawuYWpzbLUwNm8oDbeEp6/content.json"))
	print "content.json valid:", content_manager.verifyFile("data/users/1KRxE1s3oDyNDawuYWpzbLUwNm8oDbeEp6/content.json", file, ignore_same=False)

	file = open(site.storage.getPath("data/users/1KRxE1s3oDyNDawuYWpzbLUwNm8oDbeEp6/messages.json"))
	print "messages.json valid:", content_manager.verifyFile("data/users/1KRxE1s3oDyNDawuYWpzbLUwNm8oDbeEp6/messages.json", file, ignore_same=False)


def testInfo():
	from Config import config
	from Site import Site
	site = Site("12Hw8rTgzrNo4DSh2AkqwPRqDyTticwJyH")

	content_manager = ContentManager(site)
	print content_manager.contents.keys()

	print content_manager.getFileInfo("index.html")
	print content_manager.getIncludeInfo("data/users/1KRxE1s3oDyNDawuYWpzbLUwNm8oDbeEp6/content.json")
	print content_manager.getValidSigners("data/users/1KRxE1s3oDyNDawuYWpzbLUwNm8oDbeEp6/content.json")
	print content_manager.getValidSigners("data/users/content.json")
	print content_manager.getValidSigners("content.json")


if __name__ == "__main__":
	import os, sys, logging
	os.chdir("../..")
	sys.path.insert(0, os.path.abspath("."))
	sys.path.insert(0, os.path.abspath("src"))
	logging.basicConfig(level=logging.DEBUG)
	from Debug import Debug
	from Crypt import CryptHash

	#testSign()
	testVerify()
	#testInfo()

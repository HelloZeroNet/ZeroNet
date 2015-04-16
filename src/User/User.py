import logging, json, time
from Crypt import CryptBitcoin
from Plugin import PluginManager

@PluginManager.acceptPlugins
class User(object):
	def __init__(self, master_address=None, master_seed=None):
		if master_seed:
			self.master_seed = master_seed
			self.master_address = CryptBitcoin.privatekeyToAddress(self.master_seed)
		elif master_address:
			self.master_address = master_address
			self.master_seed = None
		else:
			self.master_seed = CryptBitcoin.newSeed()
			self.master_address = CryptBitcoin.privatekeyToAddress(self.master_seed)
		self.sites = {}
		self.log = logging.getLogger("User:%s" % self.master_address)


	# Save to data/users.json
	def save(self):
		users = json.load(open("data/users.json"))
		if not self.master_address in users: users[self.master_address] = {} # Create if not exits

		user_data = users[self.master_address]
		if self.master_seed: user_data["master_seed"] = self.master_seed
		user_data["sites"] = self.sites
		open("data/users.json", "w").write(json.dumps(users, indent=2, sort_keys=True))
		self.log.debug("Saved")


	# Get user site data
	# Return: {"auth_address": "xxx", "auth_privatekey": "xxx"}
	def getSiteData(self, address, create=True):
		if not address in self.sites: # Genreate new BIP32 child key based on site address
			if not create: return {"auth_address": None, "auth_privatekey": None} # Dont create user yet
			s = time.time()
			address_id = int(address.encode("hex"), 16) # Convert site address to int
			auth_privatekey = CryptBitcoin.hdPrivatekey(self.master_seed, address_id)
			self.sites[address] = {
				"auth_address": CryptBitcoin.privatekeyToAddress(auth_privatekey),
				"auth_privatekey": auth_privatekey
			}
			self.save()
			self.log.debug("Added new site: %s in %.3fs" % (address, time.time()-s))
		return self.sites[address]


	# Get BIP32 address from site address
	# Return: BIP32 auth address
	def getAuthAddress(self, address, create=True):
		return self.getSiteData(address, create)["auth_address"]


	def getAuthPrivatekey(self, address, create=True):
		return self.getSiteData(address, create)["auth_privatekey"]


	# Set user attributes from dict
	def setData(self, data):
		for key, val in data.items():
			setattr(self, key, val)

from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import time, json, os, sys, re, socket, json

# Either returns domain's address or none if it doesn't exist
# Supports subdomains and .bit on the end
def lookupDomain(domain):
	domain = domain.lower()
	
	#remove .bit on end
	if domain[-4:] == ".bit":
		domain = domain[0:-4]
		
	#check for subdomain
	if domain.find(".") != -1:
		subdomain = domain[0:domain.find(".")]
		domain = domain[domain.find(".")+1:]
	else:
		subdomain = ""
	
	try:
		domain_object = rpc.name_show("d/"+domain)
	except:
		#domain doesn't exist
		return None
	
	domain_json = json.loads(domain_object['value'])
	
	try:
		domain_address = domain_json["zeronet"][subdomain]
	except:
		#domain exists but doesn't have any zeronet value
		return None
	
	return domain_address

# Loading config...

# Check whether platform is on windows or linux
# On linux namecoin is installed under ~/.namecoin, while on on windows it is in %appdata%/Namecoin

if sys.platform == "win32":
    namecoin_location = os.getenv('APPDATA') + "/Namecoin/"
else:
    namecoin_location = os.path.expanduser("~/.namecoin/")

# Getting rpc connect details
namecoin_conf = open(namecoin_location + "namecoin.conf").read()

# Connecting to RPC
rpc_user = re.search("rpcuser=(.*)$", namecoin_conf, re.M).group(1)
rpc_pass = re.search("rpcpassword=(.*)$", namecoin_conf, re.M).group(1)
rpc_url = "http://%s:%s@127.0.0.1:8336" % (rpc_user, rpc_pass)

rpc = AuthServiceProxy(rpc_url, timeout=60*5)

"""
while 1:
	print "Waiting for new block",
	sys.stdout.flush()
	while 1:
		try:
			rpc = AuthServiceProxy(rpc_url, timeout=60*5)
			if (int(rpc.getinfo()["blocks"]) > last_block): break
			time.sleep(1)
			rpc.waitforblock()
			print "Found"
			break # Block found
		except socket.timeout: # Timeout
			print ".",
			sys.stdout.flush()
		except Exception, err:
			print "Exception", err.__class__, err
			time.sleep(5)

	last_block = int(rpc.getinfo()["blocks"])
	for block_id in range(config["lastprocessed"]+1, last_block+1):
		processBlock(block_id)

	config["lastprocessed"] = last_block
	open(config_path, "w").write(json.dumps(config, indent=2))
"""
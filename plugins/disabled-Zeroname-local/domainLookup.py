from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import time, json, os, sys, re, socket

# Connecting to RPC
def initRpc(config):
    """Initialize Namecoin RPC"""
    rpc_data = {
        'connect': '127.0.0.1',
        'port': '8336',
        'user': 'PLACEHOLDER',
        'password': 'PLACEHOLDER',
        'clienttimeout': '900'
    }
    try:
        fptr = open(config, 'r')
        lines = fptr.readlines()
        fptr.close()
    except:
        return None  # Or take some other appropriate action

    for line in lines:
        if not line.startswith('rpc'):
            continue
        key_val = line.split(None, 1)[0]
        (key, val) = key_val.split('=', 1)
        if not key or not val:
            continue
        rpc_data[key[3:]] = val

    url = 'http://%(user)s:%(password)s@%(connect)s:%(port)s' % rpc_data

    return url, int(rpc_data['clienttimeout'])

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

    domain_json = json.loads(domain_object["value"])

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

# Initialize rpc connection
rpc_auth, rpc_timeout = initRpc(namecoin_location + "namecoin.conf")
rpc = AuthServiceProxy(rpc_auth, timeout=rpc_timeout)

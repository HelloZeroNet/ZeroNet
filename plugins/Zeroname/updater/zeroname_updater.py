import time
import json
import os
import sys
import re
import socket

from subprocess import call
from bitcoinrpc.authproxy import AuthServiceProxy


def publish():
    print "* Signing and Publishing..."
    call(" ".join(command_sign_publish), shell=True)


def processNameOp(domain, value, test=False):
    if not value.strip().startswith("{"):
        return False
    try:
        data = json.loads(value)
    except Exception, err:
        print "Json load error: %s" % err
        return False
    if "zeronet" not in data:
        print "No zeronet in ", data.keys()
        return False
    if not isinstance(data["zeronet"], dict):
        print "Not dict: ", data["zeronet"]
        return False
    if not re.match("^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$", domain):
        print "Invalid domain: ", domain
        return False

    if test:
        return True

    if "slave" in sys.argv:
        print "Waiting for master update arrive"
        time.sleep(30)  # Wait 30 sec to allow master updater

    # Note: Requires the file data/names.json to exist and contain "{}" to work
    names_raw = open(names_path, "rb").read()
    names = json.loads(names_raw)
    for subdomain, address in data["zeronet"].items():
        subdomain = subdomain.lower()
        address = re.sub("[^A-Za-z0-9]", "", address)
        print subdomain, domain, "->", address
        if subdomain:
            if re.match("^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$", subdomain):
                names["%s.%s.bit" % (subdomain, domain)] = address
            else:
                print "Invalid subdomain:", domain, subdomain
        else:
            names["%s.bit" % domain] = address

    new_names_raw = json.dumps(names, indent=2, sort_keys=True)
    if new_names_raw != names_raw:
        open(names_path, "wb").write(new_names_raw)
        print "-", domain, "Changed"
        return True
    else:
        print "-", domain, "Not changed"
        return False


def processBlock(block_id, test=False):
    print "Processing block #%s..." % block_id
    s = time.time()
    block_hash = rpc.getblockhash(block_id)
    block = rpc.getblock(block_hash)

    print "Checking %s tx" % len(block["tx"])
    updated = 0
    for tx in block["tx"]:
        try:
            transaction = rpc.getrawtransaction(tx, 1)
            for vout in transaction.get("vout", []):
                if "scriptPubKey" in vout and "nameOp" in vout["scriptPubKey"] and "name" in vout["scriptPubKey"]["nameOp"]:
                    name_op = vout["scriptPubKey"]["nameOp"]
                    updated += processNameOp(name_op["name"].replace("d/", ""), name_op["value"], test)
        except Exception, err:
            print "Error processing tx #%s %s" % (tx, err)
    print "Done in %.3fs (updated %s)." % (time.time() - s, updated)
    return updated

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

# Loading config...

# Check whether platform is on windows or linux
# On linux namecoin is installed under ~/.namecoin, while on on windows it is in %appdata%/Namecoin

if sys.platform == "win32":
    namecoin_location = os.getenv('APPDATA') + "/Namecoin/"
else:
    namecoin_location = os.path.expanduser("~/.namecoin/")

config_path = namecoin_location + 'zeroname_config.json'
if not os.path.isfile(config_path):  # Create sample config
    open(config_path, "w").write(
        json.dumps({'site': 'site', 'zeronet_path': '/home/zeronet', 'privatekey': '', 'lastprocessed': 223910}, indent=2)
    )
    print "* Example config written to %s" % config_path
    sys.exit(0)

config = json.load(open(config_path))
names_path = "%s/data/%s/data/names.json" % (config["zeronet_path"], config["site"])
os.chdir(config["zeronet_path"])  # Change working dir - tells script where Zeronet install is.

# Parameters to sign and publish
command_sign_publish = [sys.executable, "zeronet.py", "siteSign", config["site"], config["privatekey"], "--publish"]
if sys.platform == 'win32':
    command_sign_publish = ['"%s"' % param for param in command_sign_publish]

# Initialize rpc connection
rpc_auth, rpc_timeout = initRpc(namecoin_location + "namecoin.conf")
rpc = AuthServiceProxy(rpc_auth, timeout=rpc_timeout)

while 1:
    try:
        time.sleep(1)
        last_block = int(rpc.getinfo()["blocks"])
        break # Connection succeeded
    except socket.timeout:  # Timeout
        print ".",
        sys.stdout.flush()
    except Exception, err:
        print "Exception", err.__class__, err
        time.sleep(5)
        rpc = AuthServiceProxy(rpc_auth, timeout=rpc_timeout)

if not config["lastprocessed"]:  # First startup: Start processing from last block
    config["lastprocessed"] = last_block


print "- Testing domain parsing..."
assert processBlock(223911, test=True) # Testing zeronetwork.bit
assert processBlock(227052, test=True) # Testing brainwallets.bit
assert not processBlock(236824, test=True) # Utf8 domain name (invalid should skip)
assert not processBlock(236752, test=True) # Uppercase domain (invalid should skip)
assert processBlock(236870, test=True) # Encoded domain (should pass)
# sys.exit(0)

print "- Parsing skipped blocks..."
should_publish = False
for block_id in range(config["lastprocessed"], last_block + 1):
    if processBlock(block_id):
        should_publish = True
config["lastprocessed"] = last_block

if should_publish:
    publish()

while 1:
    print "- Waiting for new block"
    sys.stdout.flush()
    while 1:
        try:
            time.sleep(1)
            rpc.waitforblock()
            print "Found"
            break  # Block found
        except socket.timeout:  # Timeout
            print ".",
            sys.stdout.flush()
        except Exception, err:
            print "Exception", err.__class__, err
            time.sleep(5)
            rpc = AuthServiceProxy(rpc_auth, timeout=rpc_timeout)

    last_block = int(rpc.getinfo()["blocks"])
    should_publish = False
    for block_id in range(config["lastprocessed"] + 1, last_block + 1):
        if processBlock(block_id):
            should_publish = True

    config["lastprocessed"] = last_block
    open(config_path, "w").write(json.dumps(config, indent=2))

    if should_publish:
        publish()

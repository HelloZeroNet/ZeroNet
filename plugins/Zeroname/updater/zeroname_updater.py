import time
import json
import os
import sys
import re
import socket

from bitcoinrpc.authproxy import AuthServiceProxy


def publish():
    print "* Signing..."
    os.system("python zeronet.py siteSign %s %s" % (config["site"], config["privatekey"]))
    print "* Publishing..."
    os.system("python zeronet.py sitePublish %s" % config["site"])


def processNameOp(domain, value):
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


def processBlock(block_id):
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
                    updated += processNameOp(name_op["name"].replace("d/", ""), name_op["value"])
        except Exception, err:
            print "Error processing tx #%s %s" % (tx, err)
    print "Done in %.3fs (updated %s)." % (time.time() - s, updated)
    if updated:
        publish()


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
        json.dumps({'site': 'site', 'zeronet_path': '/home/zeronet/', 'privatekey': '', 'lastprocessed': 223911}, indent=2)
    )
    print "Example config written to %s" % config_path
    sys.exit(0)

config = json.load(open(config_path))
names_path = "%s/data/%s/data/names.json" % (config["zeronet_path"], config["site"])
os.chdir(config["zeronet_path"])  # Change working dir - tells script where Zeronet install is.

# Getting rpc connect details
namecoin_conf = open(namecoin_location + "namecoin.conf").read()

# Connecting to RPC
rpc_user = re.search("rpcuser=(.*)$", namecoin_conf, re.M).group(1)
rpc_pass = re.search("rpcpassword=(.*)$", namecoin_conf, re.M).group(1)
rpc_url = "http://%s:%s@127.0.0.1:8336" % (rpc_user, rpc_pass)

rpc = AuthServiceProxy(rpc_url, timeout=60 * 5)

last_block = int(rpc.getinfo()["blocks"])

if not config["lastprocessed"]:  # Start processing from last block
    config["lastprocessed"] = last_block

# Processing skipped blocks
print "Processing block from #%s to #%s..." % (config["lastprocessed"], last_block)
for block_id in range(config["lastprocessed"], last_block + 1):
    processBlock(block_id)

# processBlock(223911) # Testing zeronetwork.bit
# processBlock(227052) # Testing brainwallets.bit
# processBlock(236824) # Utf8 domain name (invalid should skip)
# processBlock(236752) # Uppercase domain (invalid should skip)
# processBlock(236870) # Encoded domain (should pass)
# sys.exit(0)

while 1:
    print "Waiting for new block",
    sys.stdout.flush()
    while 1:
        try:
            rpc = AuthServiceProxy(rpc_url, timeout=60 * 5)
            if (int(rpc.getinfo()["blocks"]) > last_block):
                break
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

    last_block = int(rpc.getinfo()["blocks"])
    for block_id in range(config["lastprocessed"] + 1, last_block + 1):
        processBlock(block_id)

    config["lastprocessed"] = last_block
    open(config_path, "w").write(json.dumps(config, indent=1))

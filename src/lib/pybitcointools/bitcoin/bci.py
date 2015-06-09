#!/usr/bin/python
import json, re
import random
import sys
try:
    from urllib.request import build_opener
except:
    from urllib2 import build_opener


# Makes a request to a given URL (first arg) and optional params (second arg)
def make_request(*args):
    opener = build_opener()
    opener.addheaders = [('User-agent',
                          'Mozilla/5.0'+str(random.randrange(1000000)))]
    try:
        return opener.open(*args).read().strip()
    except Exception as e:
        try:
            p = e.read().strip()
        except:
            p = e
        raise Exception(p)


def parse_addr_args(*args):
    # Valid input formats: blockr_unspent([addr1, addr2,addr3])
    #                      blockr_unspent(addr1, addr2, addr3)
    #                      blockr_unspent([addr1, addr2, addr3], network)
    #                      blockr_unspent(addr1, addr2, addr3, network)
    # Where network is 'btc' or 'testnet'
    network = 'btc'
    addr_args = args
    if len(args) >= 1 and args[-1] in ('testnet', 'btc'):
        network = args[-1]
        addr_args = args[:-1]
    if len(addr_args) == 1 and isinstance(addr_args, list):
        addr_args = addr_args[0]

    return network, addr_args


# Gets the unspent outputs of one or more addresses
def bci_unspent(*args):
    network, addrs = parse_addr_args(*args)
    u = []
    for a in addrs:
        try:
            data = make_request('https://blockchain.info/unspent?address='+a)
        except Exception as e:
            if str(e) == 'No free outputs to spend':
                continue
            else:
                raise Exception(e)
        try:
            jsonobj = json.loads(data)
            for o in jsonobj["unspent_outputs"]:
                h = o['tx_hash'].decode('hex')[::-1].encode('hex')
                u.append({
                    "output": h+':'+str(o['tx_output_n']),
                    "value": o['value']
                })
        except:
            raise Exception("Failed to decode data: "+data)
    return u


def blockr_unspent(*args):
    # Valid input formats: blockr_unspent([addr1, addr2,addr3])
    #                      blockr_unspent(addr1, addr2, addr3)
    #                      blockr_unspent([addr1, addr2, addr3], network)
    #                      blockr_unspent(addr1, addr2, addr3, network)
    # Where network is 'btc' or 'testnet'
    network, addr_args = parse_addr_args(*args)

    if network == 'testnet':
        blockr_url = 'https://tbtc.blockr.io/api/v1/address/unspent/'
    elif network == 'btc':
        blockr_url = 'https://btc.blockr.io/api/v1/address/unspent/'
    else:
        raise Exception(
            'Unsupported network {0} for blockr_unspent'.format(network))

    if len(addr_args) == 0:
        return []
    elif isinstance(addr_args[0], list):
        addrs = addr_args[0]
    else:
        addrs = addr_args
    res = make_request(blockr_url+','.join(addrs))
    data = json.loads(res)['data']
    o = []
    if 'unspent' in data:
        data = [data]
    for dat in data:
        for u in dat['unspent']:
            o.append({
                "output": u['tx']+':'+str(u['n']),
                "value": int(u['amount'].replace('.', ''))
            })
    return o


def helloblock_unspent(*args):
    network, addrs = parse_addr_args(*args)
    if network == 'testnet':
        url = 'https://testnet.helloblock.io/v1/addresses/%s/unspents?limit=500&offset=%s'
    elif network == 'btc':
        url = 'https://mainnet.helloblock.io/v1/addresses/%s/unspents?limit=500&offset=%s'
    o = []
    for addr in addrs:
        for offset in xrange(0, 10**9, 500):
            res = make_request(url % (addr, offset))
            data = json.loads(res)["data"]
            if not len(data["unspents"]):
                break
            elif offset:
                sys.stderr.write("Getting more unspents: %d\n" % offset)
            for dat in data["unspents"]:
                o.append({
                    "output": dat["txHash"]+':'+str(dat["index"]),
                    "value": dat["value"],
                })
    return o


unspent_getters = {
    'bci': bci_unspent,
    'blockr': blockr_unspent,
    'helloblock': helloblock_unspent
}


def unspent(*args, **kwargs):
    f = unspent_getters.get(kwargs.get('source', ''), bci_unspent)
    return f(*args)


# Gets the transaction output history of a given set of addresses,
# including whether or not they have been spent
def history(*args):
    # Valid input formats: history([addr1, addr2,addr3])
    #                      history(addr1, addr2, addr3)
    if len(args) == 0:
        return []
    elif isinstance(args[0], list):
        addrs = args[0]
    else:
        addrs = args

    txs = []
    for addr in addrs:
        offset = 0
        while 1:
            data = make_request(
                'https://blockchain.info/address/%s?format=json&offset=%s' %
                (addr, offset))
            try:
                jsonobj = json.loads(data)
            except:
                raise Exception("Failed to decode data: "+data)
            txs.extend(jsonobj["txs"])
            if len(jsonobj["txs"]) < 50:
                break
            offset += 50
            sys.stderr.write("Fetching more transactions... "+str(offset)+'\n')
    outs = {}
    for tx in txs:
        for o in tx["out"]:
            if o['addr'] in addrs:
                key = str(tx["tx_index"])+':'+str(o["n"])
                outs[key] = {
                    "address": o["addr"],
                    "value": o["value"],
                    "output": tx["hash"]+':'+str(o["n"]),
                    "block_height": tx.get("block_height", None)
                }
    for tx in txs:
        for i, inp in enumerate(tx["inputs"]):
            if inp["prev_out"]["addr"] in addrs:
                key = str(inp["prev_out"]["tx_index"]) + \
                    ':'+str(inp["prev_out"]["n"])
                if outs.get(key):
                    outs[key]["spend"] = tx["hash"]+':'+str(i)
    return [outs[k] for k in outs]


# Pushes a transaction to the network using https://blockchain.info/pushtx
def bci_pushtx(tx):
    if not re.match('^[0-9a-fA-F]*$', tx):
        tx = tx.encode('hex')
    return make_request('https://blockchain.info/pushtx', 'tx='+tx)


def eligius_pushtx(tx):
    if not re.match('^[0-9a-fA-F]*$', tx):
        tx = tx.encode('hex')
    s = make_request(
        'http://eligius.st/~wizkid057/newstats/pushtxn.php',
        'transaction='+tx+'&send=Push')
    strings = re.findall('string[^"]*"[^"]*"', s)
    for string in strings:
        quote = re.findall('"[^"]*"', string)[0]
        if len(quote) >= 5:
            return quote[1:-1]


def blockr_pushtx(tx, network='btc'):
    if network == 'testnet':
        blockr_url = 'https://tbtc.blockr.io/api/v1/tx/push'
    elif network == 'btc':
        blockr_url = 'https://btc.blockr.io/api/v1/tx/push'
    else:
        raise Exception(
            'Unsupported network {0} for blockr_pushtx'.format(network))

    if not re.match('^[0-9a-fA-F]*$', tx):
        tx = tx.encode('hex')
    return make_request(blockr_url, '{"hex":"%s"}' % tx)


def helloblock_pushtx(tx):
    if not re.match('^[0-9a-fA-F]*$', tx):
        tx = tx.encode('hex')
    return make_request('https://mainnet.helloblock.io/v1/transactions',
                        'rawTxHex='+tx)

pushtx_getters = {
    'bci': bci_pushtx,
    'blockr': blockr_pushtx,
    'helloblock': helloblock_pushtx
}


def pushtx(*args, **kwargs):
    f = pushtx_getters.get(kwargs.get('source', ''), bci_pushtx)
    return f(*args)


def last_block_height():
    data = make_request('https://blockchain.info/latestblock')
    jsonobj = json.loads(data)
    return jsonobj["height"]


# Gets a specific transaction
def bci_fetchtx(txhash):
    if not re.match('^[0-9a-fA-F]*$', txhash):
        txhash = txhash.encode('hex')
    data = make_request('https://blockchain.info/rawtx/'+txhash+'?format=hex')
    return data


def blockr_fetchtx(txhash, network='btc'):
    if network == 'testnet':
        blockr_url = 'https://tbtc.blockr.io/api/v1/tx/raw/'
    elif network == 'btc':
        blockr_url = 'https://btc.blockr.io/api/v1/tx/raw/'
    else:
        raise Exception(
            'Unsupported network {0} for blockr_fetchtx'.format(network))
    if not re.match('^[0-9a-fA-F]*$', txhash):
        txhash = txhash.encode('hex')
    jsondata = json.loads(make_request(blockr_url+txhash))
    return jsondata['data']['tx']['hex']


def helloblock_fetchtx(txhash, network='btc'):
    if not re.match('^[0-9a-fA-F]*$', txhash):
        txhash = txhash.encode('hex')
    if network == 'testnet':
        url = 'https://testnet.helloblock.io/v1/transactions/'
    elif network == 'btc':
        url = 'https://mainnet.helloblock.io/v1/transactions/'
    else:
        raise Exception(
            'Unsupported network {0} for helloblock_fetchtx'.format(network))
    data = json.loads(make_request(url + txhash))["data"]["transaction"]
    o = {
        "locktime": data["locktime"],
        "version": data["version"],
        "ins": [],
        "outs": []
    }
    for inp in data["inputs"]:
        o["ins"].append({
            "script": inp["scriptSig"],
            "outpoint": {
                "index": inp["prevTxoutIndex"],
                "hash": inp["prevTxHash"],
            },
            "sequence": 4294967295
        })
    for outp in data["outputs"]:
        o["outs"].append({
            "value": outp["value"],
            "script": outp["scriptPubKey"]
        })
    from bitcoin.transaction import serialize
    from bitcoin.transaction import txhash as TXHASH
    tx = serialize(o)
    assert TXHASH(tx) == txhash
    return tx


fetchtx_getters = {
    'bci': bci_fetchtx,
    'blockr': blockr_fetchtx,
    'helloblock': helloblock_fetchtx
}


def fetchtx(*args, **kwargs):
    f = fetchtx_getters.get(kwargs.get('source', ''), bci_fetchtx)
    return f(*args)


def firstbits(address):
    if len(address) >= 25:
        return make_request('https://blockchain.info/q/getfirstbits/'+address)
    else:
        return make_request(
            'https://blockchain.info/q/resolvefirstbits/'+address)


def get_block_at_height(height):
    j = json.loads(make_request("https://blockchain.info/block-height/" +
                   str(height)+"?format=json"))
    for b in j['blocks']:
        if b['main_chain'] is True:
            return b
    raise Exception("Block at this height not found")


def _get_block(inp):
    if len(str(inp)) < 64:
        return get_block_at_height(inp)
    else:
        return json.loads(make_request(
                          'https://blockchain.info/rawblock/'+inp))


def get_block_header_data(inp):
    j = _get_block(inp)
    return {
        'version': j['ver'],
        'hash': j['hash'],
        'prevhash': j['prev_block'],
        'timestamp': j['time'],
        'merkle_root': j['mrkl_root'],
        'bits': j['bits'],
        'nonce': j['nonce'],
    }

def blockr_get_block_header_data(height, network='btc'):
    if network == 'testnet':
        blockr_url = "https://tbtc.blockr.io/api/v1/block/raw/"
    elif network == 'btc':
        blockr_url = "https://btc.blockr.io/api/v1/block/raw/"
    else:
        raise Exception(
            'Unsupported network {0} for blockr_get_block_header_data'.format(network))

    k = json.loads(make_request(blockr_url + str(height)))
    j = k['data']
    return {
        'version': j['version'],
        'hash': j['hash'],
        'prevhash': j['previousblockhash'],
        'timestamp': j['time'],
        'merkle_root': j['merkleroot'],
        'bits': int(j['bits'], 16),
        'nonce': j['nonce'],
    }

def get_txs_in_block(inp):
    j = _get_block(inp)
    hashes = [t['hash'] for t in j['tx']]
    return hashes


def get_block_height(txhash):
    j = json.loads(make_request('https://blockchain.info/rawtx/'+txhash))
    return j['block_height']

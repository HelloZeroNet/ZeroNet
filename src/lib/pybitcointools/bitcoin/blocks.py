from .main import *


def serialize_header(inp):
    o = encode(inp['version'], 256, 4)[::-1] + \
        inp['prevhash'].decode('hex')[::-1] + \
        inp['merkle_root'].decode('hex')[::-1] + \
        encode(inp['timestamp'], 256, 4)[::-1] + \
        encode(inp['bits'], 256, 4)[::-1] + \
        encode(inp['nonce'], 256, 4)[::-1]
    h = bin_sha256(bin_sha256(o))[::-1].encode('hex')
    assert h == inp['hash'], (sha256(o), inp['hash'])
    return o.encode('hex')


def deserialize_header(inp):
    inp = inp.decode('hex')
    return {
        "version": decode(inp[:4][::-1], 256),
        "prevhash": inp[4:36][::-1].encode('hex'),
        "merkle_root": inp[36:68][::-1].encode('hex'),
        "timestamp": decode(inp[68:72][::-1], 256),
        "bits": decode(inp[72:76][::-1], 256),
        "nonce": decode(inp[76:80][::-1], 256),
        "hash": bin_sha256(bin_sha256(inp))[::-1].encode('hex')
    }


def mk_merkle_proof(header, hashes, index):
    nodes = [h.decode('hex')[::-1] for h in hashes]
    if len(nodes) % 2 and len(nodes) > 2:
        nodes.append(nodes[-1])
    layers = [nodes]
    while len(nodes) > 1:
        newnodes = []
        for i in range(0, len(nodes) - 1, 2):
            newnodes.append(bin_sha256(bin_sha256(nodes[i] + nodes[i+1])))
        if len(newnodes) % 2 and len(newnodes) > 2:
            newnodes.append(newnodes[-1])
        nodes = newnodes
        layers.append(nodes)
    # Sanity check, make sure merkle root is valid
    assert nodes[0][::-1].encode('hex') == header['merkle_root']
    merkle_siblings = \
        [layers[i][(index >> i) ^ 1] for i in range(len(layers)-1)]
    return {
        "hash": hashes[index],
        "siblings": [x[::-1].encode('hex') for x in merkle_siblings],
        "header": header
    }

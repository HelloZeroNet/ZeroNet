# pymerkletools
[![PyPI version](https://badge.fury.io/py/merkletools.svg)](https://badge.fury.io/py/merkletools) [![Build Status](https://travis-ci.org/Tierion/pymerkletools.svg?branch=master)](https://travis-ci.org/Tierion/pymerkletools)

This is a Python port of [merkle-tools](https://github.com/tierion/merkle-tools).

Tools for creating Merkle trees, generating merkle proofs, and verification of merkle proofs.

## Installation

```
pip install merkletools
```

### Create MerkleTools Object

```python
import merkletools

mt = MerkleTools(hash_type="md5")  # default is sha256 
# valid hashTypes include all crypto hash algorithms
# such as 'MD5', 'SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512'
# as well as the SHA3 family of algorithms
# including 'SHA3-224', 'SHA3-256', 'SHA3-384', and 'SHA3-512'
```

To use `sha3`, this module depends on [pysha3](https://pypi.python.org/pypi/pysha3). It will be installed as part of this module or you can install it manually with :
```bash
pip install pysha3==1.0b1
```


## Methods

### add_leaf(value, do_hash)

Adds a value as a leaf or a list of leafs to the tree. The value must be a hex string, otherwise set the optional `do_hash` to true to have your value hashed prior to being added to the tree. 

```python
hex_data = '05ae04314577b2783b4be98211d1b72476c59e9c413cfb2afa2f0c68e0d93911'
list_data = ['Some text data', 'perhaps']

mt.add_leaf(hexData)
mt.add_leaf(otherData, True)
```

### get_leaf_count()

Returns the number of leaves that are currently added to the tree. 

```python
leaf_count =  mt.get_leaf_count();
```

### get_leaf(index)

Returns the value of the leaf at the given index as a hex string.

```python
leaf_value =  mt.get_leaf(1)
```

### reset_tree()

Removes all the leaves from the tree, prepararing to to begin creating a new tree.

```python
mt.reset_tree()
```

### make_tree()

Generates the merkle tree using the leaves that have been added.

```python
mt.make_tree();
```

### is_ready 

`.is_ready` is a boolean property indicating if the tree is built and ready to supply its root and proofs. The `is_ready` state is `True` only after calling 'make_tree()'.  Adding leaves or resetting the tree will change the ready state to False.

```python
is_ready = mt.is_ready 
```

### get_merkle_root()

Returns the merkle root of the tree as a hex string. If the tree is not ready, `None` is returned.

```python
root_value = mt.get_merkle_root();
```

### get_proof(index)

Returns the proof as an array of hash objects for the leaf at the given index. If the tree is not ready or no leaf exists at the given index, null is returned.  

```python
proof = mt.get_proof(1)
```

The proof array contains a set of merkle sibling objects. Each object contains the sibling hash, with the key value of either right or left. The right or left value tells you where that sibling was in relation to the current hash being evaluated. This information is needed for proof validation, as explained in the following section.

### validate_proof(proof, target_hash, merkle_root)

Returns a boolean indicating whether or not the proof is valid and correctly connects the `target_hash` to the `merkle_root`. `proof` is a proof array as supplied by the `get_proof` method. The `target_hash` and `merkle_root` parameters must be a hex strings.

```python
proof = [
   { right: '09096dbc49b7909917e13b795ebf289ace50b870440f10424af8845fb7761ea5' },
   { right: 'ed2456914e48c1e17b7bd922177291ef8b7f553edf1b1f66b6fc1a076524b22f' },
   { left: 'eac53dde9661daf47a428efea28c81a021c06d64f98eeabbdcff442d992153a8' },
]
target_hash = '36e0fd847d927d68475f32a94efff30812ee3ce87c7752973f4dd7476aa2e97e'
merkle_root = 'b8b1f39aa2e3fc2dde37f3df04e829f514fb98369b522bfb35c663befa896766'

is_valid = mt.validate_proof(proof, targetHash, merkleRoot)
```

The proof process uses all the proof objects in the array to attempt to prove a relationship between the `target_hash` and the `merkle_root` values. The steps to validate a proof are:

1. Concatenate `target_hash` and the first hash in the proof array. The right or left designation specifies which side of the concatenation that the proof hash value should be on.
2. Hash the resulting value.
3. Concatenate the resulting hash with the next hash in the proof array, using the same left and right rules.
4. Hash that value and continue the process until you’ve gone through each item in the proof array.
5. The final hash value should equal the `merkle_root` value if the proof is valid, otherwise the proof is invalid.

## Common Usage

### Creating a tree and generating the proofs

```python
mt = MerkleTools()

mt.add_leaf("tierion", True)
mt.add_leaf(["bitcoin", "blockchain"], True)

mt.make_tree()

print "root:", mt.get_merkle_root()  # root: '765f15d171871b00034ee55e48ffdf76afbc44ed0bcff5c82f31351d333c2ed1'

print mt.get_proof(1)  # [{left: '2da7240f6c88536be72abe9f04e454c6478ee29709fc3729ddfb942f804fbf08'},
                       #  {right: 'ef7797e13d3a75526946a3bcf00daec9fc9c9c4d51ddc7cc5df888f74dd434d1'}] 

print mt.validate_proof(mt.get_proof(1), mt.get_leaf(1), mt.get_merkle_root())  # True
```

## Notes

### About tree generation

1. Internally, leaves are stored as `bytearray`. When the tree is build, it is generated by hashing together the `bytearray` values. 
2. Lonely leaf nodes are promoted to the next level up, as depicted below.

                         ROOT=Hash(H+E)
                         /        \
                        /          \
                 H=Hash(F+G)        E
                 /       \           \
                /         \           \
         F=Hash(A+B)    G=Hash(C+D)    E
          /     \        /     \        \
         /       \      /       \        \
        A         B    C         D        E


### Development
This module uses Python's `hashlib` for hashing. Inside a `MerkleTools` object all
hashes are stored as Python `bytearray`. This way hashes can be concatenated simply with `+` and the result
used as input for the hash function. But for
simplicity and easy to use `MerkleTools` methods expect that both input and outputs are hex
strings. We can convert from one type to the other using default Python string methods.
For example:
```python
hash = hashlib.sha256('a').digest()  # '\xca\x97\x81\x12\xca\x1b\xbd\xca\xfa\xc21\xb3\x9a#\xdcM\xa7\x86\xef\xf8\x14|Nr\xb9\x80w\x85\xaf\xeeH\xbb'
hex_string = hash.decode('hex')  # 'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'
back_to_hash = hash_string.decode('hex')  # '\xca\x97\x81\x12\xca\x1b\xbd\xca\xfa\xc21\xb3\x9a#\xdcM\xa7\x86\xef\xf8\x14|Nr\xb9\x80w\x85\xaf\xeeH\xbb'
```

from lib.BitcoinECC import BitcoinECC
from lib.pybitcointools import bitcoin as btctools


def newPrivatekey(uncompressed=True): # Return new private key
	privatekey = btctools.encode_privkey(btctools.random_key(), "wif")
	return privatekey


def newSeed():
	return btctools.random_key()


def hdPrivatekey(seed, child):
	masterkey = btctools.bip32_master_key(seed)
	childkey = btctools.bip32_ckd(masterkey, child % 100000000) # Too large child id could cause problems
	key = btctools.bip32_extract_key(childkey)
	return btctools.encode_privkey(key, "wif")


def privatekeyToAddress(privatekey): # Return address from private key
	if privatekey.startswith("23") and len(privatekey) > 52: # Backward compatibility to broken lib
		bitcoin = BitcoinECC.Bitcoin()
		bitcoin.BitcoinAddressFromPrivate(privatekey)
		return bitcoin.BitcoinAddresFromPublicKey()
	else:
		try:
			return btctools.privkey_to_address(privatekey)
		except Exception, err: # Invalid privatekey
			return False


def sign(data, privatekey): # Return sign to data using private key
	if privatekey.startswith("23") and len(privatekey) > 52: return None # Old style private key not supported
	sign = btctools.ecdsa_sign(data, privatekey)
	return sign


def signOld(data, privatekey): # Return sign to data using private key (backward compatible old style)
	bitcoin = BitcoinECC.Bitcoin()
	bitcoin.BitcoinAddressFromPrivate(privatekey)
	sign = bitcoin.SignECDSA(data)
	return sign


def verify(data, address, sign): # Verify data using address and sign
	if hasattr(sign, "endswith"):
		pub = btctools.ecdsa_recover(data, sign)
		sign_address = btctools.pubtoaddr(pub)
		return sign_address == address
	else: # Backward compatible old style
		bitcoin = BitcoinECC.Bitcoin()
		return bitcoin.VerifyMessageFromBitcoinAddress(address, data, sign)

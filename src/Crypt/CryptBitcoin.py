from src.lib.BitcoinECC import BitcoinECC


def newPrivatekey(uncompressed=True): # Return new private key
	from src.lib.BitcoinECC import newBitcoinECC # Use new lib to generate WIF compatible addresses, but keep using the old yet for backward compatiblility issues
	bitcoin = newBitcoinECC.Bitcoin()
	d = bitcoin.GenerateD()
	bitcoin.AddressFromD(d, uncompressed) 
	return bitcoin.PrivFromD(d, uncompressed)


def privatekeyToAddress(privatekey): # Return address from private key
	bitcoin = BitcoinECC.Bitcoin()
	bitcoin.BitcoinAddressFromPrivate(privatekey)
	return bitcoin.BitcoinAddresFromPublicKey()


def sign(data, privatekey): # Return sign to data using private key
	bitcoin = BitcoinECC.Bitcoin()
	bitcoin.BitcoinAddressFromPrivate(privatekey)
	sign = bitcoin.SignECDSA(data)
	return sign


def verify(data, address, sign): # Verify data using address and sign
	bitcoin = BitcoinECC.Bitcoin()
	return bitcoin.VerifyMessageFromBitcoinAddress(address, data, sign)

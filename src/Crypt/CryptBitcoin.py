from src.lib.BitcoinECC import BitcoinECC
import hashlib


def newPrivatekey(): # Return new private key
	bitcoin = BitcoinECC.Bitcoin()
	bitcoin.GeneratePrivateKey()
	return bitcoin.PrivateEncoding() 


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

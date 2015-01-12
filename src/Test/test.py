import sys, os, unittest, urllib, time
sys.path.append(os.path.abspath("src")) # Imports relative to src dir

from Crypt import CryptBitcoin
from Ui import UiRequest

class TestCase(unittest.TestCase):

	def testMediaRoute(self):
		try:
			urllib.urlopen("http://127.0.0.1:43110").read()
		except Exception, err:
			raise unittest.SkipTest(err)
		self.assertIn("Not Found", urllib.urlopen("http://127.0.0.1:43110/media//sites.json").read())
		self.assertIn("Not Found", urllib.urlopen("http://127.0.0.1:43110/media/./sites.json").read())
		self.assertIn("Not Found", urllib.urlopen("http://127.0.0.1:43110/media/../config.py").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/media/1P2rJhkQjYSHdHpWDDwxfRGYXaoWE8u1vV/../sites.json").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/media/1P2rJhkQjYSHdHpWDDwxfRGYXaoWE8u1vV/..//sites.json").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/media/1P2rJhkQjYSHdHpWDDwxfRGYXaoWE8u1vV/../../config.py").read())


	def testBitcoinSign(self):
		s = time.time()
		privatekey = "23DKQpDz7bXM7w5KN5Wnmz7bwRNqNHcdQjb2WwrdB1QtTf5gM3pFdf"
		privatekey_bad = "23DKQpDz7bXM7w5KN5Wnmz6bwRNqNHcdQjb2WwrdB1QtTf5gM3pFdf"

		address = CryptBitcoin.privatekeyToAddress(privatekey)
		self.assertEqual(address, "12vTsjscg4hYPewUL2onma5pgQmWPMs3ez")

		address_bad = CryptBitcoin.privatekeyToAddress(privatekey_bad)
		self.assertNotEqual(address_bad, "12vTsjscg4hYPewUL2onma5pgQmWPMs3ez")

		sign = CryptBitcoin.sign("hello", privatekey)

		self.assertTrue(CryptBitcoin.verify("hello", address, sign))
		self.assertFalse(CryptBitcoin.verify("not hello", address, sign))

		sign_bad = CryptBitcoin.sign("hello", privatekey_bad)
		self.assertFalse(CryptBitcoin.verify("hello", address, sign_bad))

		print "Taken: %.3fs, " % (time.time()-s),


if __name__ == "__main__":
	unittest.main(verbosity=2)


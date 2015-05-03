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
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/media/./sites.json").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/media/../config.py").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/media/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../sites.json").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/media/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/..//sites.json").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/media/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../../zeronet.py").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../sites.json").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/..//sites.json").read())
		self.assertIn("Forbidden", urllib.urlopen("http://127.0.0.1:43110/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr/../../zeronet.py").read())


	def testBitcoinSignOld(self):
		s = time.time()
		privatekey = "23DKQpDz7bXM7w5KN5Wnmz7bwRNqNHcdQjb2WwrdB1QtTf5gM3pFdf"
		privatekey_bad = "23DKQpDz7bXM7w5KN5Wnmz6bwRNqNHcdQjb2WwrdB1QtTf5gM3pFdf"

		address = CryptBitcoin.privatekeyToAddress(privatekey)
		self.assertEqual(address, "12vTsjscg4hYPewUL2onma5pgQmWPMs3ez")

		address_bad = CryptBitcoin.privatekeyToAddress(privatekey_bad)
		self.assertNotEqual(address_bad, "12vTsjscg4hYPewUL2onma5pgQmWPMs3ez")

		sign = CryptBitcoin.signOld("hello", privatekey)

		self.assertTrue(CryptBitcoin.verify("hello", address, sign))
		self.assertFalse(CryptBitcoin.verify("not hello", address, sign))

		sign_bad = CryptBitcoin.signOld("hello", privatekey_bad)
		self.assertFalse(CryptBitcoin.verify("hello", address, sign_bad))

		print "Taken: %.3fs, " % (time.time()-s),


	def testBitcoinSign(self):
		s = time.time()
		privatekey = "5K9S6dVpufGnroRgFrT6wsKiz2mJRYsC73eWDmajaHserAp3F1C"
		privatekey_bad = "5Jbm9rrusXyApAoM8YoM4Rja337zMMoBUMRJ1uijiguU2aZRnwC"

		address = CryptBitcoin.privatekeyToAddress(privatekey)
		self.assertEqual(address, "1MpDMxFeDUkiHohxx9tbGLeEGEuR4ZNsJz")

		address_bad = CryptBitcoin.privatekeyToAddress(privatekey_bad)
		self.assertNotEqual(address_bad, "1MpDMxFeDUkiHohxx9tbGLeEGEuR4ZNsJz")

		sign = CryptBitcoin.sign("hello", privatekey)

		self.assertTrue(CryptBitcoin.verify("hello", address, sign))
		self.assertFalse(CryptBitcoin.verify("not hello", address, sign))

		sign_bad = CryptBitcoin.sign("hello", privatekey_bad)
		self.assertFalse(CryptBitcoin.verify("hello", address, sign_bad))

		print "Taken: %.3fs, " % (time.time()-s),



	def testBitcoinSignCompressed(self):
		raise unittest.SkipTest("Not supported yet")
		s = time.time()
		privatekey = "Kwg4YXhL5gsNwarFWtzTKuUiwAhKbZAgWdpFo1UETZSKdgHaNN2J"
		privatekey_bad = "Kwg4YXhL5gsNwarFWtzTKuUiwAhKsZAgWdpFo1UETZSKdgHaNN2J"

		address = CryptBitcoin.privatekeyToAddress(privatekey)
		self.assertEqual(address, "1LSxsKfC9S9TVXGGNSM3vPHjyW82jgCX5f")

		address_bad = CryptBitcoin.privatekeyToAddress(privatekey_bad)
		self.assertNotEqual(address_bad, "1LSxsKfC9S9TVXGGNSM3vPHjyW82jgCX5f")

		sign = CryptBitcoin.sign("hello", privatekey)
		print sign

		self.assertTrue(CryptBitcoin.verify("hello", address, sign))
		self.assertFalse(CryptBitcoin.verify("not hello", address, sign))

		sign_bad = CryptBitcoin.sign("hello", privatekey_bad)
		self.assertFalse(CryptBitcoin.verify("hello", address, sign_bad))

		print "Taken: %.3fs, " % (time.time()-s),


	def testTrackers(self):
		raise unittest.SkipTest("Notyet")
		from Site import SiteManager
		from lib.subtl.subtl import UdpTrackerClient
		import hashlib

		ok = 0
		for protocol, ip, port in SiteManager.TRACKERS:
			address = "test"
			if protocol == "udp":
				tracker = UdpTrackerClient(ip, port)
				peers = None
				try:
					tracker.connect()
					tracker.poll_once()
					tracker.announce(info_hash=hashlib.sha1(address).hexdigest(), num_want=5)
					back = tracker.poll_once()
					peers = back["response"]["peers"]
				except Exception, err:
					peers = None
					print "Tracker error: %s://%s:%s %s" % (protocol, ip, port, err)
				if peers != None:
					ok += 1

		self.assertEqual(ok, len(SiteManager.TRACKERS))


	def testDb(self):
		print "Importing db..."
		from Db import Db
		for db_path in [os.path.abspath("data/test/zeronet.db"), "data/test/zeronet.db"]:
			print "Creating db using %s..." % db_path,
			schema = {
				"db_name": "TestDb",
				"db_file": "data/test/zeronet.db",
				"map": {
					"data.json": {
						"to_table": {
							"test": "test"
						}
					}
				},
				"tables": { 
					"test": {
						"cols": [
							["test_id", "INTEGER"],  
							["title", "TEXT"], 
						],
						"indexes": ["CREATE UNIQUE INDEX test_id ON test(test_id)"],
						"schema_changed": 1426195822
					}
				}
			}

			if os.path.isfile("data/test/zeronet.db"): os.unlink("data/test/zeronet.db")
			db = Db(schema, "data/test/zeronet.db")
			db.checkTables()
			db.close()

			# Cleanup
			os.unlink("data/test/zeronet.db")
			os.rmdir("data/test/")
			print "ok"


	def testContentManagerIncludes(self):
		from Site import Site
		from cStringIO import StringIO
		import json

		site = Site("1TaLk3zM7ZRskJvrh3ZNCDVGXvkJusPKQ")
		# Include info
		include_info = site.content_manager.getIncludeInfo("data/users/1BhcaqWViN1YBnNgXb5aq5NtEhKtKdKZMB/content.json")
		self.assertEqual(include_info["signers"], ['1BhcaqWViN1YBnNgXb5aq5NtEhKtKdKZMB'])
		self.assertEqual(include_info["user_name"], 'testuser4')
		self.assertEqual(include_info["max_size"], 10000)
		self.assertEqual(include_info["includes_allowed"], False)
		self.assertEqual(include_info["files_allowed"], 'data.json')
		# Valid signers
		self.assertEqual(
			site.content_manager.getValidSigners("data/users/1BhcaqWViN1YBnNgXb5aq5NtEhKtKdKZMB/content.json"), 
			['1BhcaqWViN1YBnNgXb5aq5NtEhKtKdKZMB', '1TaLk3zM7ZRskJvrh3ZNCDVGXvkJusPKQ']
		)
		self.assertEqual(site.content_manager.getValidSigners("data/content.json"), ['1TaLk3zM7ZRskJvrh3ZNCDVGXvkJusPKQ'])
		self.assertEqual(site.content_manager.getValidSigners("content.json"), ['1TaLk3zM7ZRskJvrh3ZNCDVGXvkJusPKQ'])

		# Data validation
		data_dict = {
		  "files": {
		    "data.json": {
		      "sha512": "be589f313e7b2d8b9b41280e603e8ba72c3f74d3cfdb771a7c418a0a64598035", 
		      "size": 216
		    }
		  }, 
		  "modified": 1428591454.423, 
		  "signs": {
		    "1BhcaqWViN1YBnNgXb5aq5NtEhKtKdKZMB": "HM1sv686/aIdgqyFF2t0NmZY5pv1TALo6H0zOmOJ63VOnNg2LSCpbuubb+IcHTUIJq3StUDo6okczJDeowyjOUo="
		  }
		}
		# Normal data
		data = StringIO(json.dumps(data_dict))
		self.assertEqual(site.content_manager.verifyFile("data/users/1BhcaqWViN1YBnNgXb5aq5NtEhKtKdKZMB/content.json", data, ignore_same=False), True)
		# Too large
		data_dict["files"]["data.json"]["size"] = 200000
		data = StringIO(json.dumps(data_dict))
		self.assertEqual(site.content_manager.verifyFile("data/users/1BhcaqWViN1YBnNgXb5aq5NtEhKtKdKZMB/content.json", data, ignore_same=False), False)
		data_dict["files"]["data.json"]["size"] = 216 # Reset
		# Not allowed file
		data_dict["files"]["data.html"] = data_dict["files"]["data.json"]
		data = StringIO(json.dumps(data_dict))
		self.assertEqual(site.content_manager.verifyFile("data/users/1BhcaqWViN1YBnNgXb5aq5NtEhKtKdKZMB/content.json", data, ignore_same=False), False)
		del data_dict["files"]["data.html"] # Reset
		# Should work again
		data = StringIO(json.dumps(data_dict))
		self.assertEqual(site.content_manager.verifyFile("data/users/1BhcaqWViN1YBnNgXb5aq5NtEhKtKdKZMB/content.json", data, ignore_same=False), True)



if __name__ == "__main__":
	import logging
	logging.getLogger().setLevel(level=logging.CRITICAL)
	unittest.main(verbosity=2, defaultTest="TestCase.testContentManagerIncludes")


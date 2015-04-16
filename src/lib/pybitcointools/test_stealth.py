import bitcoin as bc
import sys
import unittest

class TestStealth(unittest.TestCase):

    def setUp(self):
        
        if sys.getrecursionlimit() < 1000:
            sys.setrecursionlimit(1000)
        
        self.addr = 'vJmtjxSDxNPXL4RNapp9ARdqKz3uJyf1EDGjr1Fgqs9c8mYsVH82h8wvnA4i5rtJ57mr3kor1EVJrd4e5upACJd588xe52yXtzumxj'
        self.scan_pub = '025e58a31122b38c86abc119b9379fe247410aee87a533f9c07b189aef6c3c1f52'
        self.scan_priv = '3e49e7257cb31db997edb1cf8299af0f37e2663e2260e4b8033e49d39a6d02f2'
        self.spend_pub = '03616562c98e7d7b74be409a787cec3a912122f3fb331a9bee9b0b73ce7b9f50af'
        self.spend_priv = 'aa3db0cfb3edc94de4d10f873f8190843f2a17484f6021a95a7742302c744748'
        self.ephem_pub = '03403d306ec35238384c7e340393335f9bc9bb4a2e574eb4e419452c4ea19f14b0'
        self.ephem_priv = '9e63abaf8dcd5ea3919e6de0b6c544e00bf51bf92496113a01d6e369944dc091'
        self.shared_secret = 'a4047ee231f4121e3a99a3a3378542e34a384b865a9917789920e1f13ffd91c6'
        self.pay_pub = '02726112ad39cb6bf848b1b1ef30b88e35286bf99f746c2be575f96c0e02a9357c'
        self.pay_priv = '4e422fb1e5e1db6c1f6ab32a7706d368ceb385e7fab098e633c5c5949c3b97cd'
        
        self.testnet_addr = 'waPUuLLykSnY3itzf1AyrQZm42F7KyB7SR5zpfqmnzPXWhx9kXLzV3EcyqzDdpTwngiyCCMUqztS9S1d7XJs3JMt3MsHPDpBCudvx9'
        
    def test_address_encoding(self):

        sc_pub, sp_pub = bc.basic_stealth_address_to_pubkeys(self.addr)
        self.assertEqual(sc_pub, self.scan_pub)
        self.assertEqual(sp_pub, self.spend_pub)
        
        stealth_addr2 = bc.pubkeys_to_basic_stealth_address(sc_pub, sp_pub)
        self.assertEqual(stealth_addr2, self.addr)
        
        magic_byte_testnet = 43
        sc_pub, sp_pub = bc.basic_stealth_address_to_pubkeys(self.testnet_addr)
        self.assertEqual(sc_pub, self.scan_pub)
        self.assertEqual(sp_pub, self.spend_pub)
        
        stealth_addr2 = bc.pubkeys_to_basic_stealth_address(sc_pub, sp_pub, magic_byte_testnet)
        self.assertEqual(stealth_addr2, self.testnet_addr)
        
    def test_shared_secret(self):

        sh_sec = bc.shared_secret_sender(self.scan_pub, self.ephem_priv)
        self.assertEqual(sh_sec, self.shared_secret)

        sh_sec2 = bc.shared_secret_receiver(self.ephem_pub, self.scan_priv)
        self.assertEqual(sh_sec2, self.shared_secret)

    def test_uncover_pay_keys(self):

        pub = bc.uncover_pay_pubkey_sender(self.scan_pub, self.spend_pub, self.ephem_priv)
        pub2 = bc.uncover_pay_pubkey_receiver(self.scan_priv, self.spend_pub, self.ephem_pub)
        self.assertEqual(pub, self.pay_pub)
        self.assertEqual(pub2, self.pay_pub)

        priv = bc.uncover_pay_privkey(self.scan_priv, self.spend_priv, self.ephem_pub)
        self.assertEqual(priv, self.pay_priv)

    def test_stealth_metadata_script(self):

        nonce = int('deadbeef', 16)
        script = bc.mk_stealth_metadata_script(self.ephem_pub, nonce)
        self.assertEqual(script[6:], 'deadbeef' + self.ephem_pub)
        
        eph_pub = bc.ephem_pubkey_from_tx_script(script)
        self.assertEqual(eph_pub, self.ephem_pub)

    def test_stealth_tx_outputs(self):

        nonce = int('deadbeef', 16)
        value = 10**8
        outputs = bc.mk_stealth_tx_outputs(self.addr, value, self.ephem_priv, nonce)

        self.assertEqual(outputs[0]['value'], 0)
        self.assertEqual(outputs[0]['script'], '6a2606deadbeef' + self.ephem_pub)
        self.assertEqual(outputs[1]['address'], bc.pubkey_to_address(self.pay_pub))
        self.assertEqual(outputs[1]['value'], value)
        
        outputs = bc.mk_stealth_tx_outputs(self.testnet_addr, value, self.ephem_priv, nonce, 'testnet')
        
        self.assertEqual(outputs[0]['value'], 0)
        self.assertEqual(outputs[0]['script'], '6a2606deadbeef' + self.ephem_pub)
        self.assertEqual(outputs[1]['address'], bc.pubkey_to_address(self.pay_pub, 111))
        self.assertEqual(outputs[1]['value'], value)

        self.assertRaises(Exception, bc.mk_stealth_tx_outputs, self.testnet_addr, value, self.ephem_priv, nonce, 'btc')
        
        self.assertRaises(Exception, bc.mk_stealth_tx_outputs, self.addr, value, self.ephem_priv, nonce, 'testnet')
 
if __name__ == '__main__':
    unittest.main()

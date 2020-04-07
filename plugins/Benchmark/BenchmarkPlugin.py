import os
import time
import io
import math
import hashlib
import re
import sys

from Config import config
from Crypt import CryptHash
from Plugin import PluginManager
from Debug import Debug
from util import helper

plugin_dir = os.path.dirname(__file__)

benchmark_key = None


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    @helper.encodeResponse
    def actionBenchmark(self):
        global benchmark_key
        script_nonce = self.getScriptNonce()
        if not benchmark_key:
            benchmark_key = CryptHash.random(encoding="base64")
        self.sendHeader(script_nonce=script_nonce)

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            return

        data = self.render(
            plugin_dir + "/media/benchmark.html",
            script_nonce=script_nonce,
            benchmark_key=benchmark_key,
            filter=re.sub("[^A-Za-z0-9]", "", self.get.get("filter", ""))
        )
        yield data

    @helper.encodeResponse
    def actionBenchmarkResult(self):
        global benchmark_key
        if self.get.get("benchmark_key", "") != benchmark_key:
            return self.error403("Invalid benchmark key")

        self.sendHeader(content_type="text/plain", noscript=True)

        if "Multiuser" in PluginManager.plugin_manager.plugin_names and not config.multiuser_local:
            yield "This function is disabled on this proxy"
            return

        yield " " * 1024  # Head (required for streaming)

        import main
        s = time.time()

        for part in main.actions.testBenchmark(filter=self.get.get("filter", "")):
            yield part

        yield "\n - Total time: %.3fs" % (time.time() - s)


@PluginManager.registerTo("Actions")
class ActionsPlugin:
    def getMultiplerTitle(self, multipler):
        if multipler < 0.3:
            multipler_title = "Sloooow"
        elif multipler < 0.6:
            multipler_title = "Ehh"
        elif multipler < 0.8:
            multipler_title = "Goodish"
        elif multipler < 1.2:
            multipler_title = "OK"
        elif multipler < 1.7:
            multipler_title = "Fine"
        elif multipler < 2.5:
            multipler_title = "Fast"
        elif multipler < 3.5:
            multipler_title = "WOW"
        else:
            multipler_title = "Insane!!"
        return multipler_title

    def formatResult(self, taken, standard):
        if not standard:
            return " Done in %.3fs" % taken

        if taken > 0:
            multipler = standard / taken
        else:
            multipler = 99
        multipler_title = self.getMultiplerTitle(multipler)

        return " Done in %.3fs = %s (%.2fx)" % (taken, multipler_title, multipler)

    def getBenchmarkTests(self, online=False):
        if hasattr(super(), "getBenchmarkTests"):
            tests = super().getBenchmarkTests(online)
        else:
            tests = []

        tests.extend([
            {"func": self.testHdPrivatekey, "num": 50, "time_standard": 0.57},
            {"func": self.testSign, "num": 20, "time_standard": 0.46},
            {"func": self.testVerify, "kwargs": {"lib_verify": "sslcrypto_fallback"}, "num": 20, "time_standard": 0.38},
            {"func": self.testVerify, "kwargs": {"lib_verify": "sslcrypto"}, "num": 200, "time_standard": 0.30},
            {"func": self.testVerify, "kwargs": {"lib_verify": "libsecp256k1"}, "num": 200, "time_standard": 0.10},

            {"func": self.testPackMsgpack, "num": 100, "time_standard": 0.35},
            {"func": self.testUnpackMsgpackStreaming, "kwargs": {"fallback": False}, "num": 100, "time_standard": 0.35},
            {"func": self.testUnpackMsgpackStreaming, "kwargs": {"fallback": True}, "num": 10, "time_standard": 0.5},

            {"func": self.testPackZip, "num": 5, "time_standard": 0.065},
            {"func": self.testPackArchive, "kwargs": {"archive_type": "gz"}, "num": 5, "time_standard": 0.08},
            {"func": self.testPackArchive, "kwargs": {"archive_type": "bz2"}, "num": 5, "time_standard": 0.68},
            {"func": self.testPackArchive, "kwargs": {"archive_type": "xz"}, "num": 5, "time_standard": 0.47},
            {"func": self.testUnpackZip, "num": 20, "time_standard": 0.25},
            {"func": self.testUnpackArchive, "kwargs": {"archive_type": "gz"}, "num": 20, "time_standard": 0.28},
            {"func": self.testUnpackArchive, "kwargs": {"archive_type": "bz2"}, "num": 20, "time_standard": 0.83},
            {"func": self.testUnpackArchive, "kwargs": {"archive_type": "xz"}, "num": 20, "time_standard": 0.38},

            {"func": self.testCryptHash, "kwargs": {"hash_type": "sha256"}, "num": 10, "time_standard": 0.50},
            {"func": self.testCryptHash, "kwargs": {"hash_type": "sha512"}, "num": 10, "time_standard": 0.33},
            {"func": self.testCryptHashlib, "kwargs": {"hash_type": "sha3_256"}, "num": 10, "time_standard": 0.33},
            {"func": self.testCryptHashlib, "kwargs": {"hash_type": "sha3_512"}, "num": 10, "time_standard": 0.65},

            {"func": self.testRandom, "num": 100, "time_standard": 0.08},
        ])

        if online:
            tests += [
                {"func": self.testHttps, "num": 1, "time_standard": 2.1}
            ]
        return tests

    def testBenchmark(self, num_multipler=1, online=False, num_run=None, filter=None):
        """
        Run benchmark on client functions
        """
        tests = self.getBenchmarkTests(online=online)

        if filter:
            tests = [test for test in tests[:] if filter.lower() in test["func"].__name__.lower()]

        yield "\n"
        res = {}
        multiplers = []
        for test in tests:
            s = time.time()
            if num_run:
                num_run_test = num_run
            else:
                num_run_test = math.ceil(test["num"] * num_multipler)
            func = test["func"]
            func_name = func.__name__
            kwargs = test.get("kwargs", {})
            key = "%s %s" % (func_name, kwargs)
            if kwargs:
                yield "* Running %s (%s) x %s " % (func_name, kwargs, num_run_test)
            else:
                yield "* Running %s x %s " % (func_name, num_run_test)
            i = 0
            try:
                for progress in func(num_run_test, **kwargs):
                    i += 1
                    if num_run_test > 10:
                        should_print = i % (num_run_test / 10) == 0 or progress != "."
                    else:
                        should_print = True

                    if should_print:
                        if num_run_test == 1 and progress == ".":
                            progress = "..."
                        yield progress
                time_taken = time.time() - s
                if num_run:
                    time_standard = 0
                else:
                    time_standard = test["time_standard"] * num_multipler
                yield self.formatResult(time_taken, time_standard)
                yield "\n"
                res[key] = "ok"
                multiplers.append(time_standard / max(time_taken, 0.001))
            except Exception as err:
                res[key] = err
                yield "Failed!\n! Error: %s\n\n" % Debug.formatException(err)

        if not res:
            yield "! No tests found"
            if config.action == "test":
                sys.exit(1)
        else:
            num_failed = len([res_key for res_key, res_val in res.items() if res_val != "ok"])
            num_success = len([res_key for res_key, res_val in res.items() if res_val != "ok"])
            yield "* Result:\n"
            yield " - Total: %s tests\n" % len(res)
            yield " - Success: %s tests\n" % num_success
            yield " - Failed: %s tests\n" % num_failed
            if any(multiplers):
                multipler_avg = sum(multiplers) / len(multiplers)
                multipler_title = self.getMultiplerTitle(multipler_avg)
                yield " - Average speed factor: %.2fx (%s)" % (multipler_avg, multipler_title)
            if num_failed == 0 and config.action == "test":
                sys.exit(1)


    def testHttps(self, num_run=1):
        """
        Test https connection with valid and invalid certs
        """
        import urllib.request
        import urllib.error

        body = urllib.request.urlopen("https://google.com").read()
        assert len(body) > 100
        yield "."

        badssl_urls = [
            "https://expired.badssl.com/",
            "https://wrong.host.badssl.com/",
            "https://self-signed.badssl.com/",
            "https://untrusted-root.badssl.com/"
        ]
        for badssl_url in badssl_urls:
            try:
                body = urllib.request.urlopen(badssl_url).read()
                https_err = None
            except urllib.error.URLError as err:
                https_err = err
            assert https_err
            yield "."

    def testCryptHash(self, num_run=1, hash_type="sha256"):
        """
        Test hashing functions
        """
        yield "(5MB) "

        from Crypt import CryptHash

        hash_types = {
            "sha256": {"func": CryptHash.sha256sum, "hash_valid": "8cd629d9d6aff6590da8b80782a5046d2673d5917b99d5603c3dcb4005c45ffa"},
            "sha512": {"func": CryptHash.sha512sum, "hash_valid": "9ca7e855d430964d5b55b114e95c6bbb114a6d478f6485df93044d87b108904d"}
        }
        hash_func = hash_types[hash_type]["func"]
        hash_valid = hash_types[hash_type]["hash_valid"]

        data = io.BytesIO(b"Hello" * 1024 * 1024)  # 5MB
        for i in range(num_run):
            data.seek(0)
            hash = hash_func(data)
            yield "."
        assert hash == hash_valid, "%s != %s" % (hash, hash_valid)

    def testCryptHashlib(self, num_run=1, hash_type="sha3_256"):
        """
        Test SHA3 hashing functions
        """
        yield "x 5MB "

        hash_types = {
            "sha3_256": {"func": hashlib.sha3_256, "hash_valid": "c8aeb3ef9fe5d6404871c0d2a4410a4d4e23268e06735648c9596f436c495f7e"},
            "sha3_512": {"func": hashlib.sha3_512, "hash_valid": "b75dba9472d8af3cc945ce49073f3f8214d7ac12086c0453fb08944823dee1ae83b3ffbc87a53a57cc454521d6a26fe73ff0f3be38dddf3f7de5d7692ebc7f95"},
        }

        hash_func = hash_types[hash_type]["func"]
        hash_valid = hash_types[hash_type]["hash_valid"]

        data = io.BytesIO(b"Hello" * 1024 * 1024)  # 5MB
        for i in range(num_run):
            data.seek(0)
            h = hash_func()
            while 1:
                buff = data.read(1024 * 64)
                if not buff:
                    break
                h.update(buff)
            hash = h.hexdigest()
            yield "."
        assert hash == hash_valid, "%s != %s" % (hash, hash_valid)

    def testRandom(self, num_run=1):
        """
        Test generating random data
        """
        yield "x 1000 x 256 bytes "
        for i in range(num_run):
            data_last = None
            for y in range(1000):
                data = os.urandom(256)
                assert data != data_last
                assert len(data) == 256
                data_last = data
            yield "."

    def testHdPrivatekey(self, num_run=2):
        """
        Test generating deterministic private keys from a master seed
        """
        from Crypt import CryptBitcoin
        seed = "e180efa477c63b0f2757eac7b1cce781877177fe0966be62754ffd4c8592ce38"
        privatekeys = []
        for i in range(num_run):
            privatekeys.append(CryptBitcoin.hdPrivatekey(seed, i * 10))
            yield "."
        valid = "5JSbeF5PevdrsYjunqpg7kAGbnCVYa1T4APSL3QRu8EoAmXRc7Y"
        assert privatekeys[0] == valid, "%s != %s" % (privatekeys[0], valid)
        if len(privatekeys) > 1:
            assert privatekeys[0] != privatekeys[-1]

    def testSign(self, num_run=1):
        """
        Test signing data using a private key
        """
        from Crypt import CryptBitcoin
        data = "Hello" * 1024
        privatekey = "5JsunC55XGVqFQj5kPGK4MWgTL26jKbnPhjnmchSNPo75XXCwtk"
        for i in range(num_run):
            yield "."
            sign = CryptBitcoin.sign(data, privatekey)
            valid = "G1GXaDauZ8vX/N9Jn+MRiGm9h+I94zUhDnNYFaqMGuOiBHB+kp4cRPZOL7l1yqK5BHa6J+W97bMjvTXtxzljp6w="
            assert sign == valid, "%s != %s" % (sign, valid)

    def testVerify(self, num_run=1, lib_verify="btctools"):
        """
        Test verification of generated signatures
        """
        from Crypt import CryptBitcoin
        CryptBitcoin.loadLib(lib_verify, silent=True)

        data = "Hello" * 1024
        privatekey = "5JsunC55XGVqFQj5kPGK4MWgTL26jKbnPhjnmchSNPo75XXCwtk"
        address = CryptBitcoin.privatekeyToAddress(privatekey)
        sign = "G1GXaDauZ8vX/N9Jn+MRiGm9h+I94zUhDnNYFaqMGuOiBHB+kp4cRPZOL7l1yqK5BHa6J+W97bMjvTXtxzljp6w="

        for i in range(num_run):
            ok = CryptBitcoin.verify(data, address, sign, lib_verify=lib_verify)
            yield "."
            assert ok, "does not verify from %s" % address

    def testAll(self):
        """
        Run all tests to check system compatibility with ZeroNet functions
        """
        for progress in self.testBenchmark(online=not config.offline, num_run=1):
            yield progress


@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        back = super(ConfigPlugin, self).createArguments()
        if self.getCmdlineValue("test") == "benchmark":
            self.test_parser.add_argument(
                '--num_multipler', help='Benchmark run time multipler',
                default=1.0, type=float, metavar='num'
            )
            self.test_parser.add_argument(
                '--filter', help='Filter running benchmark',
                default=None, metavar='test name'
            )
        return back

import base64

from Crypt import CryptHash

sha512t_sum_hex = "2e9466d8aa1f340c91203b4ddbe9b6669879616a1b8e9571058a74195937598d"
sha512t_sum_bin = b".\x94f\xd8\xaa\x1f4\x0c\x91 ;M\xdb\xe9\xb6f\x98yaj\x1b\x8e\x95q\x05\x8at\x19Y7Y\x8d"
sha256_sum_hex = "340cd04be7f530e3a7c1bc7b24f225ba5762ec7063a56e1ae01a30d56722e5c3"


class TestCryptBitcoin:

    def testSha(self, site):
        file_path = site.storage.getPath("dbschema.json")
        assert CryptHash.sha512sum(file_path) == sha512t_sum_hex
        assert CryptHash.sha512sum(open(file_path, "rb")) == sha512t_sum_hex
        assert CryptHash.sha512sum(open(file_path, "rb"), format="digest") == sha512t_sum_bin

        assert CryptHash.sha256sum(file_path) == sha256_sum_hex
        assert CryptHash.sha256sum(open(file_path, "rb")) == sha256_sum_hex

        with open(file_path, "rb") as f:
            hash = CryptHash.Sha512t(f.read(100))
            hash.hexdigest() != sha512t_sum_hex
            hash.update(f.read(1024 * 1024))
            assert hash.hexdigest() == sha512t_sum_hex

    def testRandom(self):
        assert len(CryptHash.random(64)) == 64
        assert CryptHash.random() != CryptHash.random()
        assert bytes.fromhex(CryptHash.random(encoding="hex"))
        assert base64.b64decode(CryptHash.random(encoding="base64"))

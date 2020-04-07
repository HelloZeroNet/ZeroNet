import os
import io
from collections import OrderedDict

from Plugin import PluginManager
from Config import config
from util import Msgpack


@PluginManager.registerTo("Actions")
class ActionsPlugin:
    def createZipFile(self, path):
        import zipfile
        test_data = b"Test" * 1024
        file_name = b"\xc3\x81rv\xc3\xadzt\xc5\xb1r\xc5\x91%s.txt".decode("utf8")
        with zipfile.ZipFile(path, 'w') as archive:
            for y in range(100):
                zip_info = zipfile.ZipInfo(file_name % y, (1980, 1, 1, 0, 0, 0))
                zip_info.compress_type = zipfile.ZIP_DEFLATED
                zip_info.create_system = 3
                zip_info.flag_bits = 0
                zip_info.external_attr = 25165824
                archive.writestr(zip_info, test_data)

    def testPackZip(self, num_run=1):
        """
        Test zip file creating
        """
        yield "x 100 x 5KB "
        from Crypt import CryptHash
        zip_path = '%s/test.zip' % config.data_dir
        for i in range(num_run):
            self.createZipFile(zip_path)
            yield "."

        archive_size = os.path.getsize(zip_path) / 1024
        yield "(Generated file size: %.2fkB)" % archive_size

        hash = CryptHash.sha512sum(open(zip_path, "rb"))
        valid = "cb32fb43783a1c06a2170a6bc5bb228a032b67ff7a1fd7a5efb9b467b400f553"
        assert hash == valid, "Invalid hash: %s != %s<br>" % (hash, valid)
        os.unlink(zip_path)

    def testUnpackZip(self, num_run=1):
        """
        Test zip file reading
        """
        yield "x 100 x 5KB "
        import zipfile
        zip_path = '%s/test.zip' % config.data_dir
        test_data = b"Test" * 1024
        file_name = b"\xc3\x81rv\xc3\xadzt\xc5\xb1r\xc5\x91".decode("utf8")

        self.createZipFile(zip_path)
        for i in range(num_run):
            with zipfile.ZipFile(zip_path) as archive:
                for f in archive.filelist:
                    assert f.filename.startswith(file_name), "Invalid filename: %s != %s" % (f.filename, file_name)
                    data = archive.open(f.filename).read()
                    assert archive.open(f.filename).read() == test_data, "Invalid data: %s..." % data[0:30]
            yield "."

        os.unlink(zip_path)

    def createArchiveFile(self, path, archive_type="gz"):
        import tarfile
        import gzip

        # Monkey patch _init_write_gz to use fixed date in order to keep the hash independent from datetime
        def nodate_write_gzip_header(self):
            self._write_mtime = 0
            original_write_gzip_header(self)

        test_data_io = io.BytesIO(b"Test" * 1024)
        file_name = b"\xc3\x81rv\xc3\xadzt\xc5\xb1r\xc5\x91%s.txt".decode("utf8")

        original_write_gzip_header = gzip.GzipFile._write_gzip_header
        gzip.GzipFile._write_gzip_header = nodate_write_gzip_header
        with tarfile.open(path, 'w:%s' % archive_type) as archive:
            for y in range(100):
                test_data_io.seek(0)
                tar_info = tarfile.TarInfo(file_name % y)
                tar_info.size = 4 * 1024
                archive.addfile(tar_info, test_data_io)

    def testPackArchive(self, num_run=1, archive_type="gz"):
        """
        Test creating tar archive files
        """
        yield "x 100 x 5KB "
        from Crypt import CryptHash

        hash_valid_db = {
            "gz": "92caec5121a31709cbbc8c11b0939758e670b055bbbe84f9beb3e781dfde710f",
            "bz2": "b613f41e6ee947c8b9b589d3e8fa66f3e28f63be23f4faf015e2f01b5c0b032d",
            "xz": "ae43892581d770959c8d993daffab25fd74490b7cf9fafc7aaee746f69895bcb",
        }
        archive_path = '%s/test.tar.%s' % (config.data_dir, archive_type)
        for i in range(num_run):
            self.createArchiveFile(archive_path, archive_type=archive_type)
            yield "."

        archive_size = os.path.getsize(archive_path) / 1024
        yield "(Generated file size: %.2fkB)" % archive_size

        hash = CryptHash.sha512sum(open("%s/test.tar.%s" % (config.data_dir, archive_type), "rb"))
        valid = hash_valid_db[archive_type]
        assert hash == valid, "Invalid hash: %s != %s<br>" % (hash, valid)

        if os.path.isfile(archive_path):
            os.unlink(archive_path)

    def testUnpackArchive(self, num_run=1, archive_type="gz"):
        """
        Test reading tar archive files
        """
        yield "x 100 x 5KB "
        import tarfile

        test_data = b"Test" * 1024
        file_name = b"\xc3\x81rv\xc3\xadzt\xc5\xb1r\xc5\x91%s.txt".decode("utf8")
        archive_path = '%s/test.tar.%s' % (config.data_dir, archive_type)
        self.createArchiveFile(archive_path, archive_type=archive_type)
        for i in range(num_run):
            with tarfile.open(archive_path, 'r:%s' % archive_type) as archive:
                for y in range(100):
                    assert archive.extractfile(file_name % y).read() == test_data
            yield "."
        if os.path.isfile(archive_path):
            os.unlink(archive_path)

    def testPackMsgpack(self, num_run=1):
        """
        Test msgpack encoding
        """
        yield "x 100 x 5KB "
        binary = b'fqv\xf0\x1a"e\x10,\xbe\x9cT\x9e(\xa5]u\x072C\x8c\x15\xa2\xa8\x93Sw)\x19\x02\xdd\t\xfb\xf67\x88\xd9\xee\x86\xa1\xe4\xb6,\xc6\x14\xbb\xd7$z\x1d\xb2\xda\x85\xf5\xa0\x97^\x01*\xaf\xd3\xb0!\xb7\x9d\xea\x89\xbbh8\xa1"\xa7]e(@\xa2\xa5g\xb7[\xae\x8eE\xc2\x9fL\xb6s\x19\x19\r\xc8\x04S\xd0N\xe4]?/\x01\xea\xf6\xec\xd1\xb3\xc2\x91\x86\xd7\xf4K\xdf\xc2lV\xf4\xe8\x80\xfc\x8ep\xbb\x82\xb3\x86\x98F\x1c\xecS\xc8\x15\xcf\xdc\xf1\xed\xfc\xd8\x18r\xf9\x80\x0f\xfa\x8cO\x97(\x0b]\xf1\xdd\r\xe7\xbf\xed\x06\xbd\x1b?\xc5\xa0\xd7a\x82\xf3\xa8\xe6@\xf3\ri\xa1\xb10\xf6\xd4W\xbc\x86\x1a\xbb\xfd\x94!bS\xdb\xaeM\x92\x00#\x0b\xf7\xad\xe9\xc2\x8e\x86\xbfi![%\xd31]\xc6\xfc2\xc9\xda\xc6v\x82P\xcc\xa9\xea\xb9\xff\xf6\xc8\x17iD\xcf\xf3\xeeI\x04\xe9\xa1\x19\xbb\x01\x92\xf5nn4K\xf8\xbb\xc6\x17e>\xa7 \xbbv'
        data = OrderedDict(
            sorted({"int": 1024 * 1024 * 1024, "float": 12345.67890, "text": "hello" * 1024, "binary": binary}.items())
        )
        data_packed_valid = b'\x84\xa6binary\xc5\x01\x00fqv\xf0\x1a"e\x10,\xbe\x9cT\x9e(\xa5]u\x072C\x8c\x15\xa2\xa8\x93Sw)\x19\x02\xdd\t\xfb\xf67\x88\xd9\xee\x86\xa1\xe4\xb6,\xc6\x14\xbb\xd7$z\x1d\xb2\xda\x85\xf5\xa0\x97^\x01*\xaf\xd3\xb0!\xb7\x9d\xea\x89\xbbh8\xa1"\xa7]e(@\xa2\xa5g\xb7[\xae\x8eE\xc2\x9fL\xb6s\x19\x19\r\xc8\x04S\xd0N\xe4]?/\x01\xea\xf6\xec\xd1\xb3\xc2\x91\x86\xd7\xf4K\xdf\xc2lV\xf4\xe8\x80\xfc\x8ep\xbb\x82\xb3\x86\x98F\x1c\xecS\xc8\x15\xcf\xdc\xf1\xed\xfc\xd8\x18r\xf9\x80\x0f\xfa\x8cO\x97(\x0b]\xf1\xdd\r\xe7\xbf\xed\x06\xbd\x1b?\xc5\xa0\xd7a\x82\xf3\xa8\xe6@\xf3\ri\xa1\xb10\xf6\xd4W\xbc\x86\x1a\xbb\xfd\x94!bS\xdb\xaeM\x92\x00#\x0b\xf7\xad\xe9\xc2\x8e\x86\xbfi![%\xd31]\xc6\xfc2\xc9\xda\xc6v\x82P\xcc\xa9\xea\xb9\xff\xf6\xc8\x17iD\xcf\xf3\xeeI\x04\xe9\xa1\x19\xbb\x01\x92\xf5nn4K\xf8\xbb\xc6\x17e>\xa7 \xbbv\xa5float\xcb@\xc8\x1c\xd6\xe61\xf8\xa1\xa3int\xce@\x00\x00\x00\xa4text\xda\x14\x00'
        data_packed_valid += b'hello' * 1024
        for y in range(num_run):
            for i in range(100):
                data_packed = Msgpack.pack(data)
            yield "."
        assert data_packed == data_packed_valid, "%s<br>!=<br>%s" % (repr(data_packed), repr(data_packed_valid))

    def testUnpackMsgpack(self, num_run=1):
        """
        Test msgpack decoding
        """
        yield "x 5KB "
        binary = b'fqv\xf0\x1a"e\x10,\xbe\x9cT\x9e(\xa5]u\x072C\x8c\x15\xa2\xa8\x93Sw)\x19\x02\xdd\t\xfb\xf67\x88\xd9\xee\x86\xa1\xe4\xb6,\xc6\x14\xbb\xd7$z\x1d\xb2\xda\x85\xf5\xa0\x97^\x01*\xaf\xd3\xb0!\xb7\x9d\xea\x89\xbbh8\xa1"\xa7]e(@\xa2\xa5g\xb7[\xae\x8eE\xc2\x9fL\xb6s\x19\x19\r\xc8\x04S\xd0N\xe4]?/\x01\xea\xf6\xec\xd1\xb3\xc2\x91\x86\xd7\xf4K\xdf\xc2lV\xf4\xe8\x80\xfc\x8ep\xbb\x82\xb3\x86\x98F\x1c\xecS\xc8\x15\xcf\xdc\xf1\xed\xfc\xd8\x18r\xf9\x80\x0f\xfa\x8cO\x97(\x0b]\xf1\xdd\r\xe7\xbf\xed\x06\xbd\x1b?\xc5\xa0\xd7a\x82\xf3\xa8\xe6@\xf3\ri\xa1\xb10\xf6\xd4W\xbc\x86\x1a\xbb\xfd\x94!bS\xdb\xaeM\x92\x00#\x0b\xf7\xad\xe9\xc2\x8e\x86\xbfi![%\xd31]\xc6\xfc2\xc9\xda\xc6v\x82P\xcc\xa9\xea\xb9\xff\xf6\xc8\x17iD\xcf\xf3\xeeI\x04\xe9\xa1\x19\xbb\x01\x92\xf5nn4K\xf8\xbb\xc6\x17e>\xa7 \xbbv'
        data = OrderedDict(
            sorted({"int": 1024 * 1024 * 1024, "float": 12345.67890, "text": "hello" * 1024, "binary": binary}.items())
        )
        data_packed = b'\x84\xa6binary\xc5\x01\x00fqv\xf0\x1a"e\x10,\xbe\x9cT\x9e(\xa5]u\x072C\x8c\x15\xa2\xa8\x93Sw)\x19\x02\xdd\t\xfb\xf67\x88\xd9\xee\x86\xa1\xe4\xb6,\xc6\x14\xbb\xd7$z\x1d\xb2\xda\x85\xf5\xa0\x97^\x01*\xaf\xd3\xb0!\xb7\x9d\xea\x89\xbbh8\xa1"\xa7]e(@\xa2\xa5g\xb7[\xae\x8eE\xc2\x9fL\xb6s\x19\x19\r\xc8\x04S\xd0N\xe4]?/\x01\xea\xf6\xec\xd1\xb3\xc2\x91\x86\xd7\xf4K\xdf\xc2lV\xf4\xe8\x80\xfc\x8ep\xbb\x82\xb3\x86\x98F\x1c\xecS\xc8\x15\xcf\xdc\xf1\xed\xfc\xd8\x18r\xf9\x80\x0f\xfa\x8cO\x97(\x0b]\xf1\xdd\r\xe7\xbf\xed\x06\xbd\x1b?\xc5\xa0\xd7a\x82\xf3\xa8\xe6@\xf3\ri\xa1\xb10\xf6\xd4W\xbc\x86\x1a\xbb\xfd\x94!bS\xdb\xaeM\x92\x00#\x0b\xf7\xad\xe9\xc2\x8e\x86\xbfi![%\xd31]\xc6\xfc2\xc9\xda\xc6v\x82P\xcc\xa9\xea\xb9\xff\xf6\xc8\x17iD\xcf\xf3\xeeI\x04\xe9\xa1\x19\xbb\x01\x92\xf5nn4K\xf8\xbb\xc6\x17e>\xa7 \xbbv\xa5float\xcb@\xc8\x1c\xd6\xe61\xf8\xa1\xa3int\xce@\x00\x00\x00\xa4text\xda\x14\x00'
        data_packed += b'hello' * 1024
        for y in range(num_run):
            data_unpacked = Msgpack.unpack(data_packed, decode=False)
            yield "."
        assert data_unpacked == data, "%s<br>!=<br>%s" % (data_unpacked, data)

    def testUnpackMsgpackStreaming(self, num_run=1, fallback=False):
        """
        Test streaming msgpack decoding
        """
        yield "x 1000 x 5KB "
        binary = b'fqv\xf0\x1a"e\x10,\xbe\x9cT\x9e(\xa5]u\x072C\x8c\x15\xa2\xa8\x93Sw)\x19\x02\xdd\t\xfb\xf67\x88\xd9\xee\x86\xa1\xe4\xb6,\xc6\x14\xbb\xd7$z\x1d\xb2\xda\x85\xf5\xa0\x97^\x01*\xaf\xd3\xb0!\xb7\x9d\xea\x89\xbbh8\xa1"\xa7]e(@\xa2\xa5g\xb7[\xae\x8eE\xc2\x9fL\xb6s\x19\x19\r\xc8\x04S\xd0N\xe4]?/\x01\xea\xf6\xec\xd1\xb3\xc2\x91\x86\xd7\xf4K\xdf\xc2lV\xf4\xe8\x80\xfc\x8ep\xbb\x82\xb3\x86\x98F\x1c\xecS\xc8\x15\xcf\xdc\xf1\xed\xfc\xd8\x18r\xf9\x80\x0f\xfa\x8cO\x97(\x0b]\xf1\xdd\r\xe7\xbf\xed\x06\xbd\x1b?\xc5\xa0\xd7a\x82\xf3\xa8\xe6@\xf3\ri\xa1\xb10\xf6\xd4W\xbc\x86\x1a\xbb\xfd\x94!bS\xdb\xaeM\x92\x00#\x0b\xf7\xad\xe9\xc2\x8e\x86\xbfi![%\xd31]\xc6\xfc2\xc9\xda\xc6v\x82P\xcc\xa9\xea\xb9\xff\xf6\xc8\x17iD\xcf\xf3\xeeI\x04\xe9\xa1\x19\xbb\x01\x92\xf5nn4K\xf8\xbb\xc6\x17e>\xa7 \xbbv'
        data = OrderedDict(
            sorted({"int": 1024 * 1024 * 1024, "float": 12345.67890, "text": "hello" * 1024, "binary": binary}.items())
        )
        data_packed = b'\x84\xa6binary\xc5\x01\x00fqv\xf0\x1a"e\x10,\xbe\x9cT\x9e(\xa5]u\x072C\x8c\x15\xa2\xa8\x93Sw)\x19\x02\xdd\t\xfb\xf67\x88\xd9\xee\x86\xa1\xe4\xb6,\xc6\x14\xbb\xd7$z\x1d\xb2\xda\x85\xf5\xa0\x97^\x01*\xaf\xd3\xb0!\xb7\x9d\xea\x89\xbbh8\xa1"\xa7]e(@\xa2\xa5g\xb7[\xae\x8eE\xc2\x9fL\xb6s\x19\x19\r\xc8\x04S\xd0N\xe4]?/\x01\xea\xf6\xec\xd1\xb3\xc2\x91\x86\xd7\xf4K\xdf\xc2lV\xf4\xe8\x80\xfc\x8ep\xbb\x82\xb3\x86\x98F\x1c\xecS\xc8\x15\xcf\xdc\xf1\xed\xfc\xd8\x18r\xf9\x80\x0f\xfa\x8cO\x97(\x0b]\xf1\xdd\r\xe7\xbf\xed\x06\xbd\x1b?\xc5\xa0\xd7a\x82\xf3\xa8\xe6@\xf3\ri\xa1\xb10\xf6\xd4W\xbc\x86\x1a\xbb\xfd\x94!bS\xdb\xaeM\x92\x00#\x0b\xf7\xad\xe9\xc2\x8e\x86\xbfi![%\xd31]\xc6\xfc2\xc9\xda\xc6v\x82P\xcc\xa9\xea\xb9\xff\xf6\xc8\x17iD\xcf\xf3\xeeI\x04\xe9\xa1\x19\xbb\x01\x92\xf5nn4K\xf8\xbb\xc6\x17e>\xa7 \xbbv\xa5float\xcb@\xc8\x1c\xd6\xe61\xf8\xa1\xa3int\xce@\x00\x00\x00\xa4text\xda\x14\x00'
        data_packed += b'hello' * 1024
        for i in range(num_run):
            unpacker = Msgpack.getUnpacker(decode=False, fallback=fallback)
            for y in range(1000):
                unpacker.feed(data_packed)
                for data_unpacked in unpacker:
                    pass
            yield "."
        assert data == data_unpacked, "%s != %s" % (data_unpacked, data)

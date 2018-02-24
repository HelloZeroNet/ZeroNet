import cStringIO as StringIO

import msgpack
import pytest

from Config import config
from util import StreamingMsgpack


class TestMsgpack:
    test_data = {"cmd": "fileGet", "params": {"site": "1Site"}}

    def testUnpackinkg(self):
        assert msgpack.unpackb(msgpack.packb(self.test_data)) == self.test_data

    @pytest.mark.parametrize("unpacker_class", [msgpack.Unpacker, msgpack.fallback.Unpacker])
    def testUnpacker(self, unpacker_class):
        unpacker = unpacker_class()

        data = msgpack.packb(self.test_data)
        data += msgpack.packb(self.test_data)

        messages = []
        for char in data:
            unpacker.feed(char)
            for message in unpacker:
                messages.append(message)

        assert len(messages) == 2
        assert messages[0] == self.test_data
        assert messages[0] == messages[1]

    def testStreaming(self):
        f = StreamingMsgpack.FilePart("%s/users.json" % config.data_dir)
        f.read_bytes = 10

        data = {"cmd": "response", "params": f}

        out_buff = StringIO.StringIO()
        StreamingMsgpack.stream(data, out_buff.write)
        out_buff.seek(0)

        data_packb = {"cmd": "response", "params": open("%s/users.json" % config.data_dir).read(10)}

        out_buff.seek(0)
        assert msgpack.unpackb(out_buff.read()) == data_packb

import time
import os

import gevent
import pytest
import mock

from Crypt import CryptConnection
from Connection import ConnectionServer
from Config import config
from Site import Site

@pytest.mark.usefixtures("resetTempSettings")
@pytest.mark.usefixtures("resetSettings")
class TestWorker:
    def testDownload(self, file_server, site, site_temp):
        client = ConnectionServer("127.0.0.1", 1545)
        assert site.storage.directory == config.data_dir+"/"+site.address
        assert site_temp.storage.directory == config.data_dir+"-temp/"+site.address

        # Init source server
        site.connection_server = file_server
        file_server.sites[site.address] = site

        # Init client server
        site_temp.connection_server = client
        site_temp.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net

        # Download to client from source
        site_temp.addPeer("127.0.0.1", 1544)
        site_temp.download().join(timeout=5)

        assert not site_temp.bad_files

        site_temp.storage.deleteFiles()

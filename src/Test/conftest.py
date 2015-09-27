import os
import sys
import urllib
import time
import logging

import pytest
import mock

# Config
if sys.platform == "win32":
    PHANTOMJS_PATH = "tools/phantomjs/bin/phantomjs.exe"
else:
    PHANTOMJS_PATH = "phantomjs"
SITE_URL = "http://127.0.0.1:43110"

# Imports relative to src dir
sys.path.append(
    os.path.abspath(os.path.dirname(__file__) + "/..")
)
from Config import config
config.argv = ["none"]  # Dont pass any argv to config parser
config.parse()
config.data_dir = "src/Test/testdata"  # Use test data for unittests
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

from Site import Site
from User import UserManager
from File import FileServer
from Connection import ConnectionServer
from Crypt import CryptConnection
import gevent
from gevent import monkey
monkey.patch_all(thread=False)


@pytest.fixture(scope="session")
def resetSettings(request):
    os.chdir(os.path.abspath(os.path.dirname(__file__) + "/../.."))  # Set working dir
    open("%s/sites.json" % config.data_dir, "w").write("{}")
    open("%s/users.json" % config.data_dir, "w").write("""
        {
            "15E5rhcAUD69WbiYsYARh4YHJ4sLm2JEyc": {
                "certs": {},
                "master_seed": "024bceac1105483d66585d8a60eaf20aa8c3254b0f266e0d626ddb6114e2949a",
                "sites": {}
            }
        }
    """)

    def cleanup():
        os.unlink("%s/sites.json" % config.data_dir)
        os.unlink("%s/users.json" % config.data_dir)
    request.addfinalizer(cleanup)


@pytest.fixture(scope="session")
def resetTempSettings(request):
    data_dir_temp = config.data_dir + "-temp"
    if not os.path.isdir(data_dir_temp):
        os.mkdir(data_dir_temp)
    open("%s/sites.json" % data_dir_temp, "w").write("{}")
    open("%s/users.json" % data_dir_temp, "w").write("""
        {
            "15E5rhcAUD69WbiYsYARh4YHJ4sLm2JEyc": {
                "certs": {},
                "master_seed": "024bceac1105483d66585d8a60eaf20aa8c3254b0f266e0d626ddb6114e2949a",
                "sites": {}
            }
        }
    """)

    def cleanup():
        os.unlink("%s/sites.json" % data_dir_temp)
        os.unlink("%s/users.json" % data_dir_temp)
    request.addfinalizer(cleanup)


@pytest.fixture(scope="session")
def site():
    site = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")
    return site


@pytest.fixture()
def site_temp(request):
    with mock.patch("Config.config.data_dir", config.data_dir+"-temp"):
        site_temp = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")
    def cleanup():
        site_temp.storage.deleteFiles()
    request.addfinalizer(cleanup)
    return site_temp


@pytest.fixture(scope="session")
def user():
    user = UserManager.user_manager.get()
    user.sites = {}  # Reset user data
    return user


@pytest.fixture(scope="session")
def browser():
    try:
        from selenium import webdriver
        browser = webdriver.PhantomJS(executable_path=PHANTOMJS_PATH, service_log_path=os.path.devnull)
        browser.set_window_size(1400, 1000)
    except Exception, err:
        raise pytest.skip("Test requires selenium + phantomjs: %s" % err)
    return browser


@pytest.fixture(scope="session")
def site_url():
    try:
        urllib.urlopen(SITE_URL).read()
    except Exception, err:
        raise pytest.skip("Test requires zeronet client running: %s" % err)
    return SITE_URL


@pytest.fixture(scope="session")
def file_server(request):
    CryptConnection.manager.loadCerts()  # Load and create certs
    request.addfinalizer(CryptConnection.manager.removeCerts)  # Remove cert files after end
    file_server = FileServer("127.0.0.1", 1544)
    gevent.spawn(lambda: ConnectionServer.start(file_server))
    time.sleep(0)  # Port opening
    assert file_server.running
    def stop():
        file_server.stop()
    request.addfinalizer(stop)
    return file_server


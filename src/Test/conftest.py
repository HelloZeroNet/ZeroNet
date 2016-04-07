import os
import sys
import urllib
import time
import logging
import json
import shutil

import pytest
import mock


def pytest_addoption(parser):
    parser.addoption("--slow", action='store_true', default=False, help="Also run slow tests")

# Config
if sys.platform == "win32":
    PHANTOMJS_PATH = "tools/phantomjs/bin/phantomjs.exe"
else:
    PHANTOMJS_PATH = "phantomjs"
SITE_URL = "http://127.0.0.1:43110"

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/../lib"))  # External modules directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))  # Imports relative to src dir

from Config import config
config.argv = ["none"]  # Dont pass any argv to config parser
config.parse()  # Plugins need to access the configuration
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

from Plugin import PluginManager
PluginManager.plugin_manager.loadPlugins()
config.loadPlugins()
config.parse()  # Parse again to add plugin configuration options

config.data_dir = "src/Test/testdata"  # Use test data for unittests
config.debug_socket = True  # Use test data for unittests
config.tor = "disabled"  # Don't start Tor client


import gevent
from gevent import monkey
monkey.patch_all(thread=False)

from Site import Site
from User import UserManager
from File import FileServer
from Connection import ConnectionServer
from Crypt import CryptConnection
from Ui import UiWebsocket
from Tor import TorManager


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


@pytest.fixture()
def site(request):
    site = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")

    # Always use original data
    assert "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT" in site.storage.getPath("")  # Make sure we dont delete everything
    shutil.rmtree(site.storage.getPath(""), True)
    shutil.copytree(site.storage.getPath("")+"-original", site.storage.getPath(""))
    def cleanup():
        site.storage.deleteFiles()
    request.addfinalizer(cleanup)

    site = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")  # Create new Site object to load content.json files
    return site


@pytest.fixture()
def site_temp(request):
    with mock.patch("Config.config.data_dir", config.data_dir + "-temp"):
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
    request.addfinalizer(CryptConnection.manager.removeCerts)  # Remove cert files after end
    file_server = FileServer("127.0.0.1", 1544)
    gevent.spawn(lambda: ConnectionServer.start(file_server))
    # Wait for port opening
    for retry in range(10):
        time.sleep(0.1)  # Port opening
        try:
            conn = file_server.getConnection("127.0.0.1", 1544)
            conn.close()
            break
        except Exception, err:
            print err
    assert file_server.running

    def stop():
        file_server.stop()
    request.addfinalizer(stop)
    return file_server


@pytest.fixture()
def ui_websocket(site, file_server, user):
    class WsMock:
        def __init__(self):
            self.result = None

        def send(self, data):
            self.result = json.loads(data)["result"]

    ws_mock = WsMock()
    ui_websocket = UiWebsocket(ws_mock, site, file_server, user, None)

    def testAction(action, *args, **kwargs):
        func = getattr(ui_websocket, "action%s" % action)
        func(0, *args, **kwargs)
        return ui_websocket.ws.result

    ui_websocket.testAction = testAction
    return ui_websocket


@pytest.fixture(scope="session")
def tor_manager():
    try:
        tor_manager = TorManager()
        assert tor_manager.connect()
        tor_manager.startOnions()
    except Exception, err:
        raise pytest.skip("Test requires Tor with ControlPort: %s, %s" % (config.tor_controller, err))
    return tor_manager

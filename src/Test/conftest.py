import os
import sys
import urllib
import time
import logging
import json
import shutil
import gc

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
config.parse(silent=True)  # Plugins need to access the configuration
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

from Plugin import PluginManager
PluginManager.plugin_manager.loadPlugins()
config.loadPlugins()
config.parse()  # Parse again to add plugin configuration options

config.data_dir = "src/Test/testdata"  # Use test data for unittests
config.debug_socket = True  # Use test data for unittests
config.verbose = True  # Use test data for unittests
config.tor = "disabled"  # Don't start Tor client
config.trackers = []

os.chdir(os.path.abspath(os.path.dirname(__file__) + "/../.."))  # Set working dir
# Cleanup content.db caches
if os.path.isfile("%s/content.db" % config.data_dir):
    os.unlink("%s/content.db" % config.data_dir)
if os.path.isfile("%s-temp/content.db" % config.data_dir):
    os.unlink("%s-temp/content.db" % config.data_dir)

import gevent
from gevent import monkey
monkey.patch_all(thread=False, subprocess=False)

from Site import Site
from Site import SiteManager
from User import UserManager
from File import FileServer
from Connection import ConnectionServer
from Crypt import CryptConnection
from Ui import UiWebsocket
from Tor import TorManager
from Content import ContentDb
from util import RateLimit
from Db import Db

# SiteManager.site_manager.load = mock.MagicMock(return_value=True)  # Don't try to load from sites.json
# SiteManager.site_manager.save = mock.MagicMock(return_value=True)  # Don't try to load from sites.json


@pytest.fixture(scope="session")
def resetSettings(request):
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
    threads_before = [obj for obj in gc.get_objects() if isinstance(obj, gevent.Greenlet)]
    # Reset ratelimit
    RateLimit.queue_db = {}
    RateLimit.called_db = {}

    site = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")
    site.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net

    # Always use original data
    assert "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT" in site.storage.getPath("")  # Make sure we dont delete everything
    shutil.rmtree(site.storage.getPath(""), True)
    shutil.copytree(site.storage.getPath("") + "-original", site.storage.getPath(""))
    def cleanup():
        site.storage.deleteFiles()
        site.content_manager.contents.db.deleteSite(site)
        del SiteManager.site_manager.sites["1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT"]
        site.content_manager.contents.db.close()
        db_path = "%s/content.db" % config.data_dir
        os.unlink(db_path)
        del ContentDb.content_dbs[db_path]
        gevent.killall([obj for obj in gc.get_objects() if isinstance(obj, gevent.Greenlet) and obj not in threads_before])
    request.addfinalizer(cleanup)

    site = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")  # Create new Site object to load content.json files
    if not SiteManager.site_manager.sites:
        SiteManager.site_manager.sites = {}
    SiteManager.site_manager.sites["1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT"] = site
    return site


@pytest.fixture()
def site_temp(request):
    threads_before = [obj for obj in gc.get_objects() if isinstance(obj, gevent.Greenlet)]
    with mock.patch("Config.config.data_dir", config.data_dir + "-temp"):
        site_temp = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")
        site_temp.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net

    def cleanup():
        site_temp.storage.deleteFiles()
        site_temp.content_manager.contents.db.deleteSite(site_temp)
        site_temp.content_manager.contents.db.close()
        db_path = "%s-temp/content.db" % config.data_dir
        os.unlink(db_path)
        del ContentDb.content_dbs[db_path]
        gevent.killall([obj for obj in gc.get_objects() if isinstance(obj, gevent.Greenlet) and obj not in threads_before])
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
        print "Starting phantomjs..."
        browser = webdriver.PhantomJS(executable_path=PHANTOMJS_PATH, service_log_path=os.path.devnull)
        print "Set window size..."
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


@pytest.fixture
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

@pytest.fixture()
def db(request):
    db_path = "%s/zeronet.db" % config.data_dir
    schema = {
        "db_name": "TestDb",
        "db_file": "%s/zeronet.db" % config.data_dir,
        "maps": {
            "data.json": {
                "to_table": [
                    "test",
                    {"node": "test", "table": "test_importfilter", "import_cols": ["test_id", "title"]}
                ]
            }
        },
        "tables": {
            "test": {
                "cols": [
                    ["test_id", "INTEGER"],
                    ["title", "TEXT"],
                    ["json_id", "INTEGER REFERENCES json (json_id)"]
                ],
                "indexes": ["CREATE UNIQUE INDEX test_id ON test(test_id)"],
                "schema_changed": 1426195822
            },
            "test_importfilter": {
                "cols": [
                    ["test_id", "INTEGER"],
                    ["title", "TEXT"],
                    ["json_id", "INTEGER REFERENCES json (json_id)"]
                ],
                "indexes": ["CREATE UNIQUE INDEX test_importfilter_id ON test_importfilter(test_id)"],
                "schema_changed": 1426195822
            }
        }
    }

    if os.path.isfile(db_path):
        os.unlink(db_path)
    db = Db(schema, db_path)
    db.checkTables()

    def stop():
        db.close()
        os.unlink(db_path)

    request.addfinalizer(stop)
    return db

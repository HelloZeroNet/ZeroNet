import os
import sys
import urllib.request
import time
import logging
import json
import shutil
import gc
import datetime
import atexit

import pytest
import mock

import gevent
import gevent.event
from gevent import monkey
monkey.patch_all(thread=False, subprocess=False)


def pytest_addoption(parser):
    parser.addoption("--slow", action='store_true', default=False, help="Also run slow tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--slow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --slow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)

# Config
if sys.platform == "win32":
    CHROMEDRIVER_PATH = "tools/chrome/chromedriver.exe"
else:
    CHROMEDRIVER_PATH = "chromedriver"
SITE_URL = "http://127.0.0.1:43110"

TEST_DATA_PATH  = 'src/Test/testdata'
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/../lib"))  # External modules directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))  # Imports relative to src dir

from Config import config
config.argv = ["none"]  # Dont pass any argv to config parser
config.parse(silent=True, parse_config=False)  # Plugins need to access the configuration
config.action = "test"

# Load plugins
from Plugin import PluginManager

config.data_dir = TEST_DATA_PATH  # Use test data for unittests
config.debug = True

os.chdir(os.path.abspath(os.path.dirname(__file__) + "/../.."))  # Set working dir

all_loaded = PluginManager.plugin_manager.loadPlugins()
assert all_loaded, "Not all plugin loaded successfully"

config.loadPlugins()
config.parse(parse_config=False)  # Parse again to add plugin configuration options

config.action = "test"
config.debug = True
config.debug_socket = True  # Use test data for unittests
config.verbose = True  # Use test data for unittests
config.tor = "disable"  # Don't start Tor client
config.trackers = []
config.data_dir = TEST_DATA_PATH  # Use test data for unittests
config.initLogging(console_logging=False)

# Set custom formatter with realative time format (via: https://stackoverflow.com/questions/31521859/python-logging-module-time-since-last-log)
class TimeFilter(logging.Filter):

    def filter(self, record):
        try:
            last = self.last
        except AttributeError:
            last = record.relativeCreated

        delta = datetime.datetime.fromtimestamp(record.relativeCreated / 1000.0) - datetime.datetime.fromtimestamp(last / 1000.0)

        record.relative = '{0:.3f}'.format(delta.seconds + delta.microseconds / 1000000.0)

        self.last = record.relativeCreated
        return True

log = logging.getLogger()
fmt = logging.Formatter(fmt='+%(relative)ss %(levelname)-8s %(name)s %(message)s')
[hndl.addFilter(TimeFilter()) for hndl in log.handlers]
[hndl.setFormatter(fmt) for hndl in log.handlers]

from Site.Site import Site
from Site import SiteManager
from User import UserManager
from File import FileServer
from Connection import ConnectionServer
from Crypt import CryptConnection
from Crypt import CryptBitcoin
from Ui import UiWebsocket
from Tor import TorManager
from Content import ContentDb
from util import RateLimit
from Db import Db
from Debug import Debug


def cleanup():
    Db.dbCloseAll()
    for dir_path in [config.data_dir, config.data_dir + "-temp"]:
        for file_name in os.listdir(dir_path):
            ext = file_name.rsplit(".", 1)[-1]
            if ext not in ["csr", "pem", "srl", "db", "json", "tmp"]:
                continue
            file_path = dir_path + "/" + file_name
            if os.path.isfile(file_path):
                os.unlink(file_path)

atexit.register(cleanup)

@pytest.fixture(scope="session")
def resetSettings(request):
    open("%s/sites.json" % config.data_dir, "w").write("{}")
    open("%s/filters.json" % config.data_dir, "w").write("{}")
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
    open("%s/filters.json" % data_dir_temp, "w").write("{}")
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
        os.unlink("%s/filters.json" % data_dir_temp)
    request.addfinalizer(cleanup)


@pytest.fixture()
def site(request):
    threads_before = [obj for obj in gc.get_objects() if isinstance(obj, gevent.Greenlet)]
    # Reset ratelimit
    RateLimit.queue_db = {}
    RateLimit.called_db = {}

    site = Site("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")

    # Always use original data
    assert "1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT" in site.storage.getPath("")  # Make sure we dont delete everything
    shutil.rmtree(site.storage.getPath(""), True)
    shutil.copytree(site.storage.getPath("") + "-original", site.storage.getPath(""))

    # Add to site manager
    SiteManager.site_manager.get("1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT")
    site.announce = mock.MagicMock(return_value=True)  # Don't try to find peers from the net

    def cleanup():
        site.storage.deleteFiles()
        site.content_manager.contents.db.deleteSite(site)
        del SiteManager.site_manager.sites["1TeSTvb4w2PWE81S2rEELgmX2GCCExQGT"]
        site.content_manager.contents.db.close()
        SiteManager.site_manager.sites.clear()
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
    if not user:
        user = UserManager.user_manager.create()
    user.sites = {}  # Reset user data
    return user


@pytest.fixture(scope="session")
def browser(request):
    try:
        from selenium import webdriver
        print("Starting chromedriver...")
        options = webdriver.chrome.options.Options()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920x1080")
        options.add_argument("--log-level=1")
        browser = webdriver.Chrome(executable_path=CHROMEDRIVER_PATH, service_log_path=os.path.devnull, options=options)

        def quit():
            browser.quit()
        request.addfinalizer(quit)
    except Exception as err:
        raise pytest.skip("Test requires selenium + chromedriver: %s" % err)
    return browser


@pytest.fixture(scope="session")
def site_url():
    try:
        urllib.request.urlopen(SITE_URL).read()
    except Exception as err:
        raise pytest.skip("Test requires zeronet client running: %s" % err)
    return SITE_URL


@pytest.fixture(params=['ipv4', 'ipv6'])
def file_server(request):
    if request.param == "ipv4":
        return request.getfixturevalue("file_server4")
    else:
        return request.getfixturevalue("file_server6")


@pytest.fixture
def file_server4(request):
    time.sleep(0.1)
    file_server = FileServer("127.0.0.1", 1544)
    file_server.ip_external = "1.2.3.4"  # Fake external ip

    def listen():
        ConnectionServer.start(file_server)
        ConnectionServer.listen(file_server)

    gevent.spawn(listen)
    # Wait for port opening
    for retry in range(10):
        time.sleep(0.1)  # Port opening
        try:
            conn = file_server.getConnection("127.0.0.1", 1544)
            conn.close()
            break
        except Exception as err:
            print("FileServer6 startup error", Debug.formatException(err))
    assert file_server.running
    file_server.ip_incoming = {}  # Reset flood protection

    def stop():
        file_server.stop()
    request.addfinalizer(stop)
    return file_server


@pytest.fixture
def file_server6(request):
    time.sleep(0.1)
    file_server6 = FileServer("::1", 1544)
    file_server6.ip_external = 'fca5:95d6:bfde:d902:8951:276e:1111:a22c'  # Fake external ip

    def listen():
        ConnectionServer.start(file_server6)
        ConnectionServer.listen(file_server6)

    gevent.spawn(listen)
    # Wait for port opening
    for retry in range(10):
        time.sleep(0.1)  # Port opening
        try:
            conn = file_server6.getConnection("::1", 1544)
            conn.close()
            break
        except Exception as err:
            print("FileServer6 startup error", Debug.formatException(err))
    assert file_server6.running
    file_server6.ip_incoming = {}  # Reset flood protection

    def stop():
        file_server6.stop()
    request.addfinalizer(stop)
    return file_server6


@pytest.fixture()
def ui_websocket(site, user):
    class WsMock:
        def __init__(self):
            self.result = gevent.event.AsyncResult()

        def send(self, data):
            self.result.set(json.loads(data)["result"])

        def getResult(self):
            back = self.result.get()
            self.result = gevent.event.AsyncResult()
            return back

    ws_mock = WsMock()
    ui_websocket = UiWebsocket(ws_mock, site, None, user, None)

    def testAction(action, *args, **kwargs):
        func = getattr(ui_websocket, "action%s" % action)
        func(0, *args, **kwargs)
        return ui_websocket.ws.result.get()

    ui_websocket.testAction = testAction
    return ui_websocket


@pytest.fixture(scope="session")
def tor_manager():
    try:
        tor_manager = TorManager(fileserver_port=1544)
        tor_manager.start()
        assert tor_manager.conn is not None
        tor_manager.startOnions()
    except Exception as err:
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
    db = Db.Db(schema, db_path)
    db.checkTables()

    def stop():
        db.close()
        os.unlink(db_path)

    request.addfinalizer(stop)
    return db


@pytest.fixture(params=["btctools", "openssl", "libsecp256k1"])
def crypt_bitcoin_lib(request, monkeypatch):
    monkeypatch.setattr(CryptBitcoin, "lib_verify_best", request.param)
    CryptBitcoin.loadLib(request.param)
    return CryptBitcoin

# Workaround for pytest>=0.4.1 bug when logging in atexit handlers (I/O operation on closed file)
@pytest.fixture(scope='session', autouse=True)
def disableLog():
    yield None  # Wait until all test done
    logging.getLogger('').setLevel(logging.getLevelName(logging.CRITICAL))

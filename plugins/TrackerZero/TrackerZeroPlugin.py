import atexit
import json
import logging
import re
import os
import time
import binascii

from util import helper

from Plugin import PluginManager
from .TrackerZeroDb import TrackerZeroDb
from Crypt import CryptRsa
from Config import config

class TrackerZero(object):
    def __init__(self):
        self.log = logging.getLogger("TrackerZero")
        self.log_once = set()
        self.enabled_addresses = []
        self.added_onions = set()
        self.config_file_path = "%s/tracker-zero.json" % config.data_dir
        self.config = None
        self.load()
        atexit.register(self.save)

    def addOnion(self, tor_manager, onion, private_key):
        # XXX: TorManager hangs if Tor returns a code different from 250 OK,
        # so we keep the list of already added onions to avoid adding them twice.
        # TODO: Report to the upstream.

        if onion in self.added_onions:
            return onion

        res = tor_manager.request(
            "ADD_ONION RSA1024:%s port=%s" % (private_key, tor_manager.fileserver_port)
        )
        match = re.search("ServiceID=([A-Za-z0-9]+)", res)
        if match:
            onion_address = match.groups()[0]
            self.added_onions.add(onion_address)
            return onion_address
        return None

    def logOnce(self, message):
        if message in self.log_once:
            return
        self.log_once.add(message)
        self.log.info(message)

    def getDefaultConfig(self):
        return {
            "settings": {
                "enable": False,
                "enable_only_in_tor_always_mode": True,
                "listen_on_public_ips": False,
                "listen_on_temporary_onion_address": False,
                "listen_on_persistent_onion_address": True
            }
        }

    def readJSON(self, file_path, default_value):
        if not os.path.isfile(file_path):
            try:
                self.writeJSON(file_path, default_value)
            except Exception as err:
                self.log.error("Error writing %s: %s" % (file_path, err))
            return default_value

        try:
            return json.load(open(file_path))
        except Exception as err:
            self.log.error("Error loading %s: %s" % (file_path, err))
            return default_value

    def writeJSON(self, file_path, value):
        helper.atomicWrite(file_path, json.dumps(value, indent=2, sort_keys=True).encode("utf8"))

    def load(self):
        self.config = self.readJSON(self.config_file_path, self.getDefaultConfig())

    def save(self):
        self.writeJSON(self.config_file_path, self.config)

    def checkOnionSigns(self, onions, onion_signs, onion_sign_this):
        if not onion_signs or len(onion_signs) != len(set(onions)):
            return False

        if time.time() - float(onion_sign_this) > 3 * 60:
            return False  # Signed out of allowed 3 minutes

        onions_signed = []
        # Check onion signs
        for onion_publickey, onion_sign in onion_signs.items():
            if CryptRsa.verify(onion_sign_this.encode(), onion_publickey, onion_sign):
                onions_signed.append(CryptRsa.publickeyToOnion(onion_publickey))
            else:
                break

        # Check if the same onion addresses signed as the announced onces
        if sorted(onions_signed) == sorted(set(onions)):
            return True
        else:
            return False

    def actionAnnounce(self, file_request, params):
        if len(self.enabled_addresses) < 1:
            file_request.actionUnknown("announce", params)
            return

        time_started = time.time()
        s = time.time()
        # Backward compatibility
        if "ip4" in params["add"]:
            params["add"].append("ipv4")
        if "ip4" in params["need_types"]:
            params["need_types"].append("ipv4")

        hashes = params["hashes"]

        all_onions_signed = self.checkOnionSigns(params.get("onions", []), params.get("onion_signs"), params.get("onion_sign_this"))

        time_onion_check = time.time() - s

        connection_server = file_request.server
        ip_type = connection_server.getIpType(file_request.connection.ip)

        if ip_type == "onion" or file_request.connection.ip in config.ip_local:
            is_port_open = False
        elif ip_type in params["add"]:
            is_port_open = True
        else:
            is_port_open = False

        s = time.time()
        # Separatley add onions to sites or at once if no onions present
        i = 0
        onion_to_hash = {}
        for onion in params.get("onions", []):
            if onion not in onion_to_hash:
                onion_to_hash[onion] = []
            onion_to_hash[onion].append(hashes[i])
            i += 1

        hashes_changed = 0
        for onion, onion_hashes in onion_to_hash.items():
            hashes_changed += db.peerAnnounce(
                ip_type="onion",
                address=onion,
                port=params["port"],
                hashes=onion_hashes,
                onion_signed=all_onions_signed
            )
        time_db_onion = time.time() - s

        s = time.time()

        if is_port_open:
            hashes_changed += db.peerAnnounce(
                ip_type=ip_type,
                address=file_request.connection.ip,
                port=params["port"],
                hashes=hashes,
                delete_missing_hashes=params.get("delete")
            )
        time_db_ip = time.time() - s

        s = time.time()
        # Query sites
        back = {}
        peers = []
        if params.get("onions") and not all_onions_signed and hashes_changed:
            back["onion_sign_this"] = "%.0f" % time.time()  # Send back nonce for signing

        if len(hashes) > 500 or not hashes_changed:
            limit = 5
            order = False
        else:
            limit = 30
            order = True
        for hash in hashes:
            if time.time() - time_started > 1:  # 1 sec limit on request
                file_request.connection.log("Announce time limit exceeded after %s/%s sites" % (len(peers), len(hashes)))
                break

            hash_peers = db.peerList(
                hash,
                address=file_request.connection.ip, onions=list(onion_to_hash.keys()), port=params["port"],
                limit=min(limit, params["need_num"]), need_types=params["need_types"], order=order
            )
            if "ip4" in params["need_types"]:  # Backward compatibility
                hash_peers["ip4"] = hash_peers["ipv4"]
                del(hash_peers["ipv4"])
            peers.append(hash_peers)
        time_peerlist = time.time() - s

        back["peers"] = peers
        file_request.connection.log(
            "Announce %s sites (onions: %s, onion_check: %.3fs, db_onion: %.3fs, db_ip: %.3fs, peerlist: %.3fs, limit: %s)" %
            (len(hashes), len(onion_to_hash), time_onion_check, time_db_onion, time_db_ip, time_peerlist, limit)
        )
        file_request.response(back)


    def getTrackerStorage(self):
        try:
            if "TrackerShare" in PluginManager.plugin_manager.plugin_names:
                from TrackerShare.TrackerSharePlugin import tracker_storage
                return tracker_storage
            elif "AnnounceShare" in PluginManager.plugin_manager.plugin_names:
                from AnnounceShare.AnnounceSharePlugin import tracker_storage
                return tracker_storage
        except Exception as err:
            self.log.error("%s" % Debug.formatException(err))

        return None

    def registerTrackerAddress(self, message, address, port):
        _tracker_storage = self.getTrackerStorage()
        if not _tracker_storage:
            return

        my_tracker_address = "zero://%s:%s" % (address, port)
        if _tracker_storage.onTrackerFound(my_tracker_address, my=True):
            self.logOnce("listening on %s: %s" % (message, my_tracker_address))
            self.enabled_addresses.append("%s:%s" % (address, port))

    def registerTrackerAddresses(self, file_server, port_open):
        _tracker_storage = self.getTrackerStorage()
        if not _tracker_storage:
            return

        tor_manager = file_server.tor_manager

        settings = self.config.get("settings", {})

        if not settings.get("enable"):
            self.logOnce("Plugin loaded, but disabled by the settings")
            return False

        if settings.get("enable_only_in_tor_always_mode") and not config.tor == "always":
            self.logOnce("Plugin loaded, but disabled from running in the modes other than 'tor = always'")
            return False

        self.enabled_addresses = []

        if settings.get("listen_on_public_ips") and port_open and not config.tor == "always":
            for ip in file_server.ip_external_list:
                self.registerTrackerAddress("public IP", ip, config.fileserver_port)

        if settings.get("listen_on_temporary_onion_address") and tor_manager.enabled:
            onion = tor_manager.getOnion(config.homepage)
            if onion:
                self.registerTrackerAddress("temporary onion address", "%s.onion" % onion, tor_manager.fileserver_port)

        if settings.get("listen_on_persistent_onion_address") and tor_manager.enabled:
            persistent_addresses = self.config.setdefault("persistent_addresses", {})
            if len(persistent_addresses) == 0:
                result = tor_manager.makeOnionAndKey()
                if result:
                    onion_address, onion_privatekey = result
                    persistent_addresses[onion_address] = {
                        "private_key": onion_privatekey
                    }
                    self.registerTrackerAddress("persistent onion address", "%s.onion" % onion_address, tor_manager.fileserver_port)
            else:
                for address, d in persistent_addresses.items():
                    private_key = d.get("private_key")
                    if not private_key:
                        continue
                    onion_address = self.addOnion(tor_manager, address, private_key)
                    if onion_address == address:
                        self.registerTrackerAddress("persistent onion address", "%s.onion" % onion_address, tor_manager.fileserver_port)

        return len(self.enabled_addresses) > 0

if "db" not in locals().keys():  # Share during reloads
    db = TrackerZeroDb()

if "tracker_zero" not in locals():
    tracker_zero = TrackerZero()



@PluginManager.registerTo("FileRequest")
class FileRequestPlugin(object):
    def actionAnnounce(self, params):
        tracker_zero.actionAnnounce(self, params)


@PluginManager.registerTo("FileServer")
class FileServerPlugin(object):
    def portCheck(self, *args, **kwargs):
        res = super(FileServerPlugin, self).portCheck(*args, **kwargs)
        tracker_zero.registerTrackerAddresses(self, res)
        return res


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):

    @helper.encodeResponse
    def actionStatsTrackerZero(self):
        self.sendHeader()

        # Style
        yield """
        <style>
         * { font-family: monospace; white-space: pre }
         table td, table th { text-align: right; padding: 0px 10px }
        </style>
        """

        hash_rows = db.execute("SELECT * FROM hash").fetchall()
        for hash_row in hash_rows:
            peer_rows = db.execute(
                "SELECT * FROM peer LEFT JOIN peer_to_hash USING (peer_id) WHERE hash_id = :hash_id",
                {"hash_id": hash_row["hash_id"]}
            ).fetchall()

            yield "<br>%s (added: %s, peers: %s)<br>" % (
                binascii.hexlify(hash_row["hash"]).decode("utf-8"), hash_row["date_added"], len(peer_rows)
            )
            for peer_row in peer_rows:
                yield " - {type: <6} {address: <30} {port: >5} added: {date_added}, announced: {date_announced}<br>".format(**dict(peer_row))

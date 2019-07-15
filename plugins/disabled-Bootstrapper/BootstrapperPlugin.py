import time

from util import helper

from Plugin import PluginManager
from .BootstrapperDb import BootstrapperDb
from Crypt import CryptRsa
from Config import config

if "db" not in locals().keys():  # Share during reloads
    db = BootstrapperDb()


@PluginManager.registerTo("FileRequest")
class FileRequestPlugin(object):
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

    def actionAnnounce(self, params):
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

        ip_type = helper.getIpType(self.connection.ip)

        if ip_type == "onion" or self.connection.ip in config.ip_local:
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
                address=self.connection.ip,
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
                self.connection.log("Announce time limit exceeded after %s/%s sites" % (len(peers), len(hashes)))
                break

            hash_peers = db.peerList(
                hash,
                address=self.connection.ip, onions=list(onion_to_hash.keys()), port=params["port"],
                limit=min(limit, params["need_num"]), need_types=params["need_types"], order=order
            )
            if "ip4" in params["need_types"]:  # Backward compatibility
                hash_peers["ip4"] = hash_peers["ipv4"]
                del(hash_peers["ipv4"])
            peers.append(hash_peers)
        time_peerlist = time.time() - s

        back["peers"] = peers
        self.connection.log(
            "Announce %s sites (onions: %s, onion_check: %.3fs, db_onion: %.3fs, db_ip: %.3fs, peerlist: %.3fs, limit: %s)" %
            (len(hashes), len(onion_to_hash), time_onion_check, time_db_onion, time_db_ip, time_peerlist, limit)
        )
        self.response(back)


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    @helper.encodeResponse
    def actionStatsBootstrapper(self):
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
                str(hash_row["hash"]).encode("hex"), hash_row["date_added"], len(peer_rows)
            )
            for peer_row in peer_rows:
                yield " - {ip4: <30} {onion: <30} added: {date_added}, announced: {date_announced}<br>".format(**dict(peer_row))

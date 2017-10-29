import time

from Plugin import PluginManager
from BootstrapperDb import BootstrapperDb
from Crypt import CryptRsa

if "db" not in locals().keys():  # Share durin reloads
    db = BootstrapperDb()


@PluginManager.registerTo("FileRequest")
class FileRequestPlugin(object):
    def actionAnnounce(self, params):
        time_started = time.time()
        s = time.time()
        hashes = params["hashes"]

        if "onion_signs" in params and len(params["onion_signs"]) == len(set(params["onions"])):
            # Check if all sign is correct
            if time.time() - float(params["onion_sign_this"]) < 3*60:  # Peer has 3 minute to sign the message
                onions_signed = []
                # Check onion signs
                for onion_publickey, onion_sign in params["onion_signs"].items():
                    if CryptRsa.verify(params["onion_sign_this"], onion_publickey, onion_sign):
                        onions_signed.append(CryptRsa.publickeyToOnion(onion_publickey))
                    else:
                        break
                # Check if the same onion addresses signed as the announced onces
                if sorted(onions_signed) == sorted(set(params["onions"])):
                    all_onions_signed = True
                else:
                    all_onions_signed = False
            else:
                # Onion sign this out of 3 minute
                all_onions_signed = False
        else:
            # Incorrect signs number
            all_onions_signed = False

        time_onion_check = time.time() - s

        if "ip4" in params["add"] and self.connection.ip != "127.0.0.1" and not self.connection.ip.endswith(".onion"):
            ip4 = self.connection.ip
        else:
            ip4 = None

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
        db.execute("BEGIN")
        for onion, onion_hashes in onion_to_hash.iteritems():
            hashes_changed += db.peerAnnounce(
                onion=onion,
                port=params["port"],
                hashes=onion_hashes,
                onion_signed=all_onions_signed
            )
        db.execute("END")
        time_db_onion = time.time() - s

        s = time.time()
        # Announce all sites if ip4 defined
        if ip4:
            hashes_changed += db.peerAnnounce(
                ip4=ip4,
                port=params["port"],
                hashes=hashes,
                delete_missing_hashes=params.get("delete")
            )
        time_db_ip4 = time.time() - s

        s = time.time()
        # Query sites
        back = {}
        peers = []
        if params.get("onions") and not all_onions_signed and hashes_changed:
            back["onion_sign_this"] = "%.0f" % time.time()  # Send back nonce for signing

        if len(hashes) > 500:
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
                ip4=self.connection.ip, onions=onion_to_hash.keys(), port=params["port"],
                limit=min(limit, params["need_num"]), need_types=params["need_types"], order=order
            )
            peers.append(hash_peers)
        time_peerlist = time.time() - s


        back["peers"] = peers
        self.connection.log(
            "Announce %s sites (onions: %s, onion_check: %.3fs, db_onion: %.3fs, db_ip4: %.3fs, peerlist: %.3fs)" %
            (len(hashes), len(onion_to_hash), time_onion_check, time_db_onion, time_db_ip4, time_peerlist)
        )
        self.response(back)


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
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

import time

from Plugin import PluginManager
from util import helper
from Crypt import CryptRsa
from Config import config

allow_reload = False  # No source reload supported in this plugin
time_full_announced = {}  # Tracker address: Last announced all site to tracker
connection_pool = {}  # Tracker address: Peer object


# We can only import plugin host clases after the plugins are loaded
@PluginManager.afterLoad
def importPeers():
    global Peer
    from Peer import Peer


# Process result got back from tracker
def processPeerRes(tracker_address, site, peers):
    added = 0
    # Ip4
    found_ip4 = 0
    for packed_address in peers["ip4"]:
        found_ip4 += 1
        peer_ip, peer_port = helper.unpackAddress(packed_address)
        if site.addPeer(peer_ip, peer_port):
            added += 1
    # Onion
    found_onion = 0
    for packed_address in peers["onion"]:
        found_onion += 1
        peer_onion, peer_port = helper.unpackOnionAddress(packed_address)
        if site.addPeer(peer_onion, peer_port):
            added += 1

    if added:
        site.worker_manager.onPeers()
        site.updateWebsocket(peers_added=added)
    return added


@PluginManager.registerTo("Site")
class SitePlugin(object):
    def announceTracker(self, tracker_protocol, tracker_address, fileserver_port=0, add_types=[], my_peer_id="", mode="start"):
        if tracker_protocol != "zero":
            return super(SitePlugin, self).announceTracker(
                tracker_protocol, tracker_address, fileserver_port, add_types, my_peer_id, mode
            )

        s = time.time()

        need_types = ["ip4"]
        if self.connection_server and self.connection_server.tor_manager and self.connection_server.tor_manager.enabled:
            need_types.append("onion")

        if mode == "start" or mode == "more":  # Single: Announce only this site
            sites = [self]
            full_announce = False
        else:  # Multi: Announce all currently serving site
            full_announce = True
            if time.time() - time_full_announced.get(tracker_address, 0) < 60 * 5:  # No reannounce all sites within 5 minute
                return True
            time_full_announced[tracker_address] = time.time()
            from Site import SiteManager
            sites = [site for site in SiteManager.site_manager.sites.values() if site.settings["serving"]]

        # Create request
        request = {
            "hashes": [], "onions": [], "port": fileserver_port, "need_types": need_types, "need_num": 20, "add": add_types
        }
        for site in sites:
            if "onion" in add_types:
                onion = self.connection_server.tor_manager.getOnion(site.address)
                request["onions"].append(onion)
            request["hashes"].append(site.address_hash)

        # Tracker can remove sites that we don't announce
        if full_announce:
            request["delete"] = True

        # Sent request to tracker
        tracker = connection_pool.get(tracker_address)  # Re-use tracker connection if possible
        if not tracker:
            tracker_ip, tracker_port = tracker_address.split(":")
            tracker = Peer(tracker_ip, tracker_port, connection_server=self.connection_server)
            connection_pool[tracker_address] = tracker
        res = tracker.request("announce", request)

        if not res or "peers" not in res:
            self.log.warning("Tracker error: zero://%s (%s)" % (tracker_address, res))
            if full_announce:
                time_full_announced[tracker_address] = 0
            return False

        # Add peers from response to site
        site_index = 0
        peers_added = 0
        for site_res in res["peers"]:
            site = sites[site_index]
            peers_added += processPeerRes(tracker_address, site, site_res)
            site_index += 1

        # Check if we need to sign prove the onion addresses
        if "onion_sign_this" in res:
            self.log.debug("Signing %s for %s to add %s onions" % (res["onion_sign_this"], tracker_address, len(sites)))
            request["onion_signs"] = {}
            request["onion_sign_this"] = res["onion_sign_this"]
            request["need_num"] = 0
            for site in sites:
                onion = self.connection_server.tor_manager.getOnion(site.address)
                publickey = self.connection_server.tor_manager.getPublickey(onion)
                if publickey not in request["onion_signs"]:
                    sign = CryptRsa.sign(res["onion_sign_this"], self.connection_server.tor_manager.getPrivatekey(onion))
                    request["onion_signs"][publickey] = sign
            res = tracker.request("announce", request)
            if not res or "onion_sign_this" in res:
                self.log.warning("Tracker error: %s (Announce onion address to failed: %s)" % (tracker_address, res))
                if full_announce:
                    time_full_announced[tracker_address] = 0
                return False

        if full_announce:
            tracker.remove()  # Close connection, we don't need it in next 5 minute

        self.log.debug(
            "Tracker result: zero://%s (sites: %s, new: %s)" %
            (tracker_address, site_index, peers_added)
        )

        return time.time() - s

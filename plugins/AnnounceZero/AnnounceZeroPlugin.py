import time
import itertools

from Plugin import PluginManager
from util import helper
from Crypt import CryptRsa

allow_reload = False  # No source reload supported in this plugin
time_full_announced = {}  # Tracker address: Last announced all site to tracker
connection_pool = {}  # Tracker address: Peer object


# We can only import plugin host clases after the plugins are loaded
@PluginManager.afterLoad
def importHostClasses():
    global Peer, AnnounceError
    from Peer import Peer
    from Site.SiteAnnouncer import AnnounceError


# Process result got back from tracker
def processPeerRes(tracker_address, site, peers):
    added = 0
    # Ip4
    found_ipv4 = 0
    peers_normal = itertools.chain(peers.get("ip4", []), peers.get("ipv4", []), peers.get("ipv6", []))
    for packed_address in peers_normal:
        found_ipv4 += 1
        peer_ip, peer_port = helper.unpackAddress(packed_address)
        if site.addPeer(peer_ip, peer_port, source="tracker"):
            added += 1
    # Onion
    found_onion = 0
    for packed_address in peers["onion"]:
        found_onion += 1
        peer_onion, peer_port = helper.unpackOnionAddress(packed_address)
        if site.addPeer(peer_onion, peer_port, source="tracker"):
            added += 1

    if added:
        site.worker_manager.onPeers()
        site.updateWebsocket(peers_added=added)
    return added


@PluginManager.registerTo("SiteAnnouncer")
class SiteAnnouncerPlugin(object):
    def getTrackerHandler(self, protocol):
        if protocol == "zero":
            return self.announceTrackerZero
        else:
            return super(SiteAnnouncerPlugin, self).getTrackerHandler(protocol)

    def announceTrackerZero(self, tracker_address, mode="start", num_want=10):
        global time_full_announced
        s = time.time()

        need_types = ["ip4"]   # ip4 for backward compatibility reasons
        need_types += self.site.connection_server.supported_ip_types
        if self.site.connection_server.tor_manager.enabled:
            need_types.append("onion")

        if mode == "start" or mode == "more":  # Single: Announce only this site
            sites = [self.site]
            full_announce = False
        else:  # Multi: Announce all currently serving site
            full_announce = True
            if time.time() - time_full_announced.get(tracker_address, 0) < 60 * 15:  # No reannounce all sites within short time
                return None
            time_full_announced[tracker_address] = time.time()
            from Site import SiteManager
            sites = [site for site in SiteManager.site_manager.sites.values() if site.isServing()]

        # Create request
        add_types = self.getOpenedServiceTypes()
        request = {
            "hashes": [], "onions": [], "port": self.fileserver_port, "need_types": need_types, "need_num": 20, "add": add_types
        }
        for site in sites:
            if "onion" in add_types:
                onion = self.site.connection_server.tor_manager.getOnion(site.address)
                request["onions"].append(onion)
            request["hashes"].append(site.address_hash)

        # Tracker can remove sites that we don't announce
        if full_announce:
            request["delete"] = True

        # Sent request to tracker
        tracker_peer = connection_pool.get(tracker_address)  # Re-use tracker connection if possible
        if not tracker_peer:
            tracker_ip, tracker_port = tracker_address.rsplit(":", 1)
            tracker_peer = Peer(str(tracker_ip), int(tracker_port), connection_server=self.site.connection_server)
            tracker_peer.is_tracker_connection = True
            connection_pool[tracker_address] = tracker_peer

        res = tracker_peer.request("announce", request)

        if not res or "peers" not in res:
            if full_announce:
                time_full_announced[tracker_address] = 0
            raise AnnounceError("Invalid response: %s" % res)

        # Add peers from response to site
        site_index = 0
        peers_added = 0
        for site_res in res["peers"]:
            site = sites[site_index]
            peers_added += processPeerRes(tracker_address, site, site_res)
            site_index += 1

        # Check if we need to sign prove the onion addresses
        if "onion_sign_this" in res:
            self.site.log.debug("Signing %s for %s to add %s onions" % (res["onion_sign_this"], tracker_address, len(sites)))
            request["onion_signs"] = {}
            request["onion_sign_this"] = res["onion_sign_this"]
            request["need_num"] = 0
            for site in sites:
                onion = self.site.connection_server.tor_manager.getOnion(site.address)
                publickey = self.site.connection_server.tor_manager.getPublickey(onion)
                if publickey not in request["onion_signs"]:
                    sign = CryptRsa.sign(res["onion_sign_this"].encode("utf8"), self.site.connection_server.tor_manager.getPrivatekey(onion))
                    request["onion_signs"][publickey] = sign
            res = tracker_peer.request("announce", request)
            if not res or "onion_sign_this" in res:
                if full_announce:
                    time_full_announced[tracker_address] = 0
                raise AnnounceError("Announce onion address to failed: %s" % res)

        if full_announce:
            tracker_peer.remove()  # Close connection, we don't need it in next 5 minute

        self.site.log.debug(
            "Tracker announce result: zero://%s (sites: %s, new peers: %s, add: %s) in %.3fs" %
            (tracker_address, site_index, peers_added, add_types, time.time() - s)
        )

        return True

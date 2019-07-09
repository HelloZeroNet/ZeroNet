import time
import urllib.request
import struct
import socket

import bencode
from lib.subtl.subtl import UdpTrackerClient
import socks
import sockshandler
import gevent

from Plugin import PluginManager
from Config import config
from Debug import Debug
from util import helper


# We can only import plugin host clases after the plugins are loaded
@PluginManager.afterLoad
def importHostClasses():
    global Peer, AnnounceError
    from Peer import Peer
    from Site.SiteAnnouncer import AnnounceError


@PluginManager.registerTo("SiteAnnouncer")
class SiteAnnouncerPlugin(object):
    def getSupportedTrackers(self):
        trackers = super(SiteAnnouncerPlugin, self).getSupportedTrackers()
        if config.disable_udp or config.trackers_proxy != "disable":
            trackers = [tracker for tracker in trackers if not tracker.startswith("udp://")]

        return trackers

    def getTrackerHandler(self, protocol):
        if protocol == "udp":
            handler = self.announceTrackerUdp
        elif protocol == "http":
            handler = self.announceTrackerHttp
        elif protocol == "https":
            handler = self.announceTrackerHttps
        else:
            handler = super(SiteAnnouncerPlugin, self).getTrackerHandler(protocol)
        return handler

    def announceTrackerUdp(self, tracker_address, mode="start", num_want=10):
        s = time.time()
        if config.disable_udp:
            raise AnnounceError("Udp disabled by config")
        if config.trackers_proxy != "disable":
            raise AnnounceError("Udp trackers not available with proxies")

        ip, port = tracker_address.split("/")[0].split(":")
        tracker = UdpTrackerClient(ip, int(port))
        if helper.getIpType(ip) in self.getOpenedServiceTypes():
            tracker.peer_port = self.fileserver_port
        else:
            tracker.peer_port = 0
        tracker.connect()
        if not tracker.poll_once():
            raise AnnounceError("Could not connect")
        tracker.announce(info_hash=self.site.address_sha1, num_want=num_want, left=431102370)
        back = tracker.poll_once()
        if not back:
            raise AnnounceError("No response after %.0fs" % (time.time() - s))
        elif type(back) is dict and "response" in back:
            peers = back["response"]["peers"]
        else:
            raise AnnounceError("Invalid response: %r" % back)

        return peers

    def httpRequest(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
            'Accept-Encoding': 'none',
            'Accept-Language': 'en-US,en;q=0.8',
            'Connection': 'keep-alive'
        }

        req = urllib.request.Request(url, headers=headers)

        if config.trackers_proxy == "tor":
            tor_manager = self.site.connection_server.tor_manager
            handler = sockshandler.SocksiPyHandler(socks.SOCKS5, tor_manager.proxy_ip, tor_manager.proxy_port)
            opener = urllib.request.build_opener(handler)
            return opener.open(req, timeout=50)
        elif config.trackers_proxy == "disable":
            return urllib.request.urlopen(req, timeout=25)
        else:
            proxy_ip, proxy_port = config.trackers_proxy.split(":")
            handler = sockshandler.SocksiPyHandler(socks.SOCKS5, proxy_ip, int(proxy_port))
            opener = urllib.request.build_opener(handler)
            return opener.open(req, timeout=50)

    def announceTrackerHttps(self, *args, **kwargs):
        kwargs["protocol"] = "https"
        return self.announceTrackerHttp(*args, **kwargs)

    def announceTrackerHttp(self, tracker_address, mode="start", num_want=10, protocol="http"):
        tracker_ip, tracker_port = tracker_address.rsplit(":", 1)
        if helper.getIpType(tracker_ip) in self.getOpenedServiceTypes():
            port = self.fileserver_port
        else:
            port = 1
        params = {
            'info_hash': self.site.address_sha1,
            'peer_id': self.peer_id, 'port': port,
            'uploaded': 0, 'downloaded': 0, 'left': 431102370, 'compact': 1, 'numwant': num_want,
            'event': 'started'
        }

        url = protocol + "://" + tracker_address + "?" + urllib.parse.urlencode(params)

        s = time.time()
        response = None
        # Load url
        if config.tor == "always" or config.trackers_proxy != "disable":
            timeout = 60
        else:
            timeout = 30

        with gevent.Timeout(timeout, False):  # Make sure of timeout
            req = self.httpRequest(url)
            response = req.read()
            req.close()
            req = None

        if not response:
            raise AnnounceError("No response after %.0fs" % (time.time() - s))

        # Decode peers
        try:
            peer_data = bencode.decode(response)["peers"]
            if type(peer_data) is not bytes:
                peer_data = peer_data.encode()
            response = None
            peer_count = int(len(peer_data) / 6)
            peers = []
            for peer_offset in range(peer_count):
                off = 6 * peer_offset
                peer = peer_data[off:off + 6]
                addr, port = struct.unpack('!LH', peer)
                peers.append({"addr": socket.inet_ntoa(struct.pack('!L', addr)), "port": port})
        except Exception as err:
            raise AnnounceError("Invalid response: %r (%s)" % (response, Debug.formatException(err)))

        return peers

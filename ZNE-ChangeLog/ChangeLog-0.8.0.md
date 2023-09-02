
## Core

**Support for Onion v3:**

* Add initial support of Onion v3 addresses. Thanks to @anonymoose and @zeroseed.
* Add a few Onion v3 tracker addresses.

**Network scalabily and performance issuses:**

* The connection handling code had several bugs that were hidden by silently ignored exceptions. These were fixed, but some new ones might be introduced.
* Reworked the algorithm of checking zite updates on startup / after the network outages / periodically. ZeroNet tries not to spam too many update queries at once in order to prevent network overload. (Which especially the issue when running over Tor.) At the same time, it tries to keep balance between frequent checks for frequently updating zites and ensuring that all the zites are checked in some reasonable time interval. Tests show that the full check cycle for a peer that hosts 800+ zites and is connected over Tor can take up to several hours. We cannot significantly reduce this time, since the Tor throughput is the bottleneck. Running more checks at once just results in more connections to fail. The other bottleneck is the HDD throughput. Increasing the parallelization doesn't help in this case as well. So the implemented solution do actually **decreases** the parallelization.
* Improved the Internet outage detection and the recovery procedures after the Internet be back. ZeroNet "steps back" and schedules rechecking zites that were checked shortly before the Internet connection get lost. The network outage detection normally has some lag, so the recently checked zites are better to be checked again.
* When the network is down, reduce the frequency of connection attempts to prevent overloading Tor with hanged connections.
* For each zite the activity rate is calculated based on the last modification time. The milestone values are 1 hour, 5 hours, 24 hours, 3 days and 7 days. The activity rate is used to scale frequency of various maintenance routines, including update checks, reannounces, dead connection checks etc.
* The activity rate is also used to calculate the minimum preferred number of active connections per each zite.
* The reannounce frequency is adjusted dynamically based on:
  * Activity. More activity ==> frequent announces.
  * Peer count. More peers  ==> rare announces.
  * Tracker count. More trackers ==> frequent announces to iterate over more trackers.
* For owned zites, the activity rate doesn't drop below 0.6 to force more frequent checks. This, however, can be used to investigate which peer belongs to the zite owner. A new commnd line option `--expose_no_ownership` is introduced to disable that behavior.
* When checking for updates, ZeroNet normally asks other peers for new data since the previous update. This however can result in losing some updates in specific conditions. To overcome this, ZeroNet now asks for the full site listing on every Nth update check.
* When asking a peer for updates, ZeroNet may detect that the other peer has outdated versions of some files. In this case, ZeroNet sends back the notification of the new versions available. This behaviour was improved in the following ways:
  * Prior to 0.8.0 ZeroNet always chose the first 5 files in the list. If peer rejects updating those files for some reason, this strategy led to pushing the same 5 files over and over again on very update check. Now files are  selected randomly. This should also improve spreading of "update waves" among peers.
  * The engine now keeps track of which files were already sent to a specific peer and doesn't send those again as long as the file timestamp hasn't changed. Now we do not try to resend files if a peer refuses to update them. The watchlist is currently limited to 5000 items.
  * Prior to 0.8.0 ZeroNet failed to detect the case when remote peer misses a file at all, not just has an older version. Now it is handled properly and those files also can be send back.
  * The previous changes should make the send back mechanism more efficient. So number of files to send at once reduced from 5 to 3 to reduce the network load.
* ZeroNet now tries harder in delivering updates to more peers in the background.
* ZeroNet also makes more efforts of searching the peers before publishing updates.

**Other scalabily and performance issuses:**

* Fix possible infinite growing of the `SafeRe` regexp cache by limiting the cache size.

**Changes in API and architecture:**

* Add method `SiteManager.isAddressBlocked()` available for overriding by content filter plugins in order for other plugins be able explicitly check site block status.
* Hard-coded logic related to the network operation modes (TOR mode, proxies, network address types etc) in many places replaced with appropriate method calls and lots of new methods introduced. These changes are made in order to make it someday possible implementing support for different types of overlay networks (first of all, we mean I2P) in plugins without hardcoding more stuff to the core. A lot of refactoring is yet to come. Changes include but are not limited to:
  * `helper.getIpType()`  moved to `ConnectionServer.getIpType()`.
  * New methods `ConnectionServer.getIpUnreachability()`,  `ConnectionServer.isIpReachable()`.
  * New methods `Peer.isConnected()`,  `Peer.isConnectable()`,  `Peer.isReachable()`,  `Peer.getIpType()`.

**Other changes:**

* Implement the log level overriding for separate modules for easier debugging.

## Docker Image

* The base image upgraded from `alpine:3.11` to `alpine:3.13`.
* Tor upgraded to 0.4.4.8.

## ZeroHello

The default ZeroHello address changed from [1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D/](http://127.0.0.1:43110/1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D/) to [1HeLLoPVbqF3UEj8aWXErwTxrwkyjwGtZN/](http://127.0.0.1:43110/1HeLLoPVbqF3UEj8aWXErwTxrwkyjwGtZN/). This is the first step in migrating away from the nofish's infrastructure which development seems to be stalled.

* Make #Dashboard .tracker-status wider to fit onion v3 addresses.
* Added link to /Stats to the menu.

## Plugins

### TrackerShare

The `AnnounceShare` plugin renamed to `TrackerShare` and redesigned. The new name is more consistent and better reflects the purpose of the plugin: sharing the list of known working trackers. Other `Announce`-like names are clearly related to zite announcing facilities: `AnnounceBitTorrent` (announce to a BitTorrent tracker), `AnnounceLocal` (announce in a Local Area Network), `AnnounceZero` (announce to a Zero tracker).

Changes in the plugin:

* The default total tracker limit increased up to 20 from 5. This reduces the probability of accidental splitting the network into segments that operate with disjoint sets of trackers.
* The plugin now shares any types of trackers, working both on IP and Onion networks, not limiting solely to Zero-based IP trackers.
* The plugin now takes into account not only the total number of known working trackers, but also does it on per protocol basis. The defaults are to keep 10 trackers for Zero protocol and 5 trackers per each other protocol. The available protocols are detected automatically. (For example, UDP is considered disabled, when working in the Tor-always mode.) The following protocols are recognized: `zero://` (Zero Tracker), `udp://` (UDP-based BitTorrent tracker), `http://` or `https://` (HTTP or HTTPS-based BitTorrent tracker; considered the same protocol). In case of new protocols implemented by third-party plugins, trackers are grouped automatically by the protocol prefix.
* Reworked the interaction of this plugin and the Zero tracker (`Bootstrapper`) plugin. Previously: `AnnounceShare` checks if `Bootstrapper` is running and adds its addresses to the list. Now: `Bootstrapper` explicitly asks `TrackerShare` to add its addresses.
* The plugin allows adjusting the behaviour per each tracker entry with the following boolean fields:
  * `my` — "My" trackers get never deleted on announce errors, but aren't saved between restarts. Designed to be used by tracker implementation plugins. `TrackerShare` acts more persistently in recommending "my" trackers to other peers.
  * `persistent` — "Persistent" trackers get never deleted, when unresponsive.
  * `private` — "Private" trackers are never exposed to other peers in response of the getTrackers command.

### TrackerZero

`TrackerZero` is an attempt of implementing the better version of the `Bootstrapper` plugin to make setting up and launching a new tracker possible in a couple of mouse clicks. Work in progress, so no detailed change log yet. The `Bootstrapper` plugin itself is kept untouched.

The plugin has the following self-explanatory options:

```
enable
enable_only_in_tor_always_mode
listen_on_public_ips
listen_on_temporary_onion_address
listen_on_persistent_onion_address
```

Running over TOR doesn't seem to be stable so far. Any investigations and bug reports are welcome.

### TrackerList

`TrackerList` is a new plugin for fetching tracker lists. By default is list is fetched from [https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all_ip.txt](https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all_ip.txt).

TODO: add support of fetching from ZeroNet URLs

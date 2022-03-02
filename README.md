# ZeroNet [![tests](https://github.com/ZeroNetX/ZeroNet/actions/workflows/tests.yml/badge.svg)](https://github.com/ZeroNetX/ZeroNet/actions/workflows/tests.yml) [![Documentation](https://img.shields.io/badge/docs-faq-brightgreen.svg)](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/faq/) [![Help](https://img.shields.io/badge/keep_this_project_alive-donate-yellow.svg)](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/help_zeronet/donate/) [![Docker Pulls](https://img.shields.io/docker/pulls/canewsin/zeronet)](https://hub.docker.com/r/canewsin/zeronet) [![Support me on Patreon](https://img.shields.io/endpoint.svg?url=https%3A%2F%2Fshieldsio-patreon.vercel.app%2Fapi%3Fusername%3Dpramukesh%26type%3Dpatrons&style=flat)](https://www.patreon.com/PramUkesh)
<!--TODO: Update Onion Site -->
Decentralized websites using Bitcoin crypto and the BitTorrent network - https://zeronet.dev / [ZeroNet Site](http://127.0.0.1:43110/1ZeroNetyV5mKY9JF1gsm82TuBXHpfdLX/), Unlike Bitcoin, ZeroNet Doesn't need a blockchain to run, But uses cryptography used by BTC, to ensure data integrity and validation.


## Why?

* We believe in open, free, and uncensored network and communication.
* No single point of failure: Site remains online so long as at least 1 peer is
  serving it.
* No hosting costs: Sites are served by visitors.
* Impossible to shut down: It's nowhere because it's everywhere.
* Fast and works offline: You can access the site even if Internet is
  unavailable.


## Features
 * Real-time updated sites
 * Namecoin .bit domains support
 * Easy to setup: unpack & run
 * Clone websites in one click
 * Password-less [BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki)
   based authorization: Your account is protected by the same cryptography as your Bitcoin wallet
 * Built-in SQL server with P2P data synchronization: Allows easier site development and faster page load times
 * Anonymity: Full Tor network support with .onion hidden services instead of IPv4 addresses
 * TLS encrypted connections
 * Automatic uPnP port opening
 * Plugin for multiuser (openproxy) support
 * Works with any browser/OS


## How does it work?

* After starting `zeronet.py` you will be able to visit zeronet sites using
  `http://127.0.0.1:43110/{zeronet_address}` (eg.
  `http://127.0.0.1:43110/1HELLoE3sFD9569CLCbHEAVqvqV7U2Ri9d`).
* When you visit a new zeronet site, it tries to find peers using the BitTorrent
  network so it can download the site files (html, css, js...) from them.
* Each visited site is also served by you.
* Every site contains a `content.json` file which holds all other files in a sha512 hash
  and a signature generated using the site's private key.
* If the site owner (who has the private key for the site address) modifies the
  site and signs the new `content.json` and publishes it to the peers.
  Afterwards, the peers verify the `content.json` integrity (using the
  signature), they download the modified files and publish the new content to
  other peers.

####  [Slideshow about ZeroNet cryptography, site updates, multi-user sites »](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)
####  [Frequently asked questions »](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/faq/)

####  [ZeroNet Developer Documentation »](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/site_development/getting_started/)


## Screenshots

![Screenshot](https://i.imgur.com/H60OAHY.png)
![ZeroTalk](https://zeronet.io/docs/img/zerotalk.png)

#### [More screenshots in ZeroNet docs »](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/using_zeronet/sample_sites/)


## How to join

### Windows

 - Download [ZeroNet-win.zip](https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-win.zip) (26MB)
 - Unpack anywhere
 - Run `ZeroNet.exe`
 
### macOS

 - Download [ZeroNet-mac.zip](https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-mac.zip) (14MB)
 - Unpack anywhere
 - Run `ZeroNet.app`
 
### Linux (x86-64bit)
 - `wget https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-linux.zip`
 - `unzip ZeroNet-linux.zip`
 - `cd ZeroNet-linux`
 - Start with: `./ZeroNet.sh`
 - Open the ZeroHello landing page in your browser by navigating to: http://127.0.0.1:43110/
 
 __Tip:__ Start with `./ZeroNet.sh --ui_ip '*' --ui_restrict your.ip.address` to allow remote connections on the web interface.
 
 ### Android (arm, arm64, x86)
 - minimum Android version supported 21 (Android 5.0 Lollipop)
 - [<img src="https://play.google.com/intl/en_us/badges/images/generic/en_badge_web_generic.png" 
      alt="Download from Google Play" 
      height="80">](https://play.google.com/store/apps/details?id=in.canews.zeronetmobile)
 - APK download: https://github.com/canewsin/zeronet_mobile/releases

### Android (arm, arm64, x86) Thin Client for Preview Only (Size 1MB)
 - minimum Android version supported 16 (JellyBean)
 - [<img src="https://play.google.com/intl/en_us/badges/images/generic/en_badge_web_generic.png" 
      alt="Download from Google Play" 
      height="80">](https://play.google.com/store/apps/details?id=dev.zeronetx.app.lite)


#### Docker
There is an official image, built from source at: https://hub.docker.com/r/canewsin/zeronet/

### Install from source

 - `wget https://github.com/ZeroNetX/ZeroNet/releases/latest/download/ZeroNet-src.zip`
 - `unzip ZeroNet-src.zip`
 - `cd ZeroNet`
 - `sudo apt-get update`
 - `sudo apt-get install python3-pip`
 - `sudo python3 -m pip install -r requirements.txt`
 - Start with: `python3 zeronet.py`
 - Open the ZeroHello landing page in your browser by navigating to: http://127.0.0.1:43110/

## Current limitations

* File transactions are not compressed
* No private sites


## How can I create a ZeroNet site?

 * Click on **⋮** > **"Create new, empty site"** menu item on the site [ZeroHello](http://127.0.0.1:43110/1HELLoE3sFD9569CLCbHEAVqvqV7U2Ri9d).
 * You will be **redirected** to a completely new site that is only modifiable by you!
 * You can find and modify your site's content in **data/[yoursiteaddress]** directory
 * After the modifications open your site, drag the topright "0" button to left, then press **sign** and **publish** buttons on the bottom

Next steps: [ZeroNet Developer Documentation](https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/site_development/getting_started/)

## Help keep this project alive
- Bitcoin: 1ZeroNetyV5mKY9JF1gsm82TuBXHpfdLX (Preferred)
- LiberaPay: https://liberapay.com/PramUkesh
- Paypal: https://paypal.me/PramUkesh
- Others: [Donate](!https://docs.zeronet.dev/1DeveLopDZL1cHfKi8UXHh2UBEhzH6HhMp/help_zeronet/donate/#help-to-keep-zeronet-development-alive)

#### Thank you!

* More info, help, changelog, zeronet sites: https://www.reddit.com/r/zeronetx/
* Come, chat with us: [#zeronet @ FreeNode](https://kiwiirc.com/client/irc.freenode.net/zeronet) or on [gitter](https://gitter.im/canewsin/ZeroNet)
* Email: canews.in@gmail.com

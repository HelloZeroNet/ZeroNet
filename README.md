# ZeroNet [![Build Status](https://travis-ci.org/HelloZeroNet/ZeroNet.svg?branch=py3)](https://travis-ci.org/HelloZeroNet/ZeroNet) [![Documentation](https://img.shields.io/badge/docs-faq-brightgreen.svg)](https://zeronet.io/docs/faq/) [![Help](https://img.shields.io/badge/keep_this_project_alive-donate-yellow.svg)](https://zeronet.io/docs/help_zeronet/donate/) ![tests](https://github.com/HelloZeroNet/ZeroNet/workflows/tests/badge.svg) [![Docker Pulls](https://img.shields.io/docker/pulls/nofish/zeronet)](https://hub.docker.com/r/nofish/zeronet)

Decentralized websites using Bitcoin crypto and the BitTorrent network - https://zeronet.io


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
  `http://127.0.0.1:43110/1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D`).
* When you visit a new zeronet site, it tries to find peers using the BitTorrent
  network so it can download the site files (html, css, js...) from them.
* Each visited site is also served by you.
* Every site contains a `content.json` file which holds all other files in a sha512 hash
  and a signature generated using the site's private key.
* If the site owner (who has the private key for the site address) modifies the
  site, then he/she signs the new `content.json` and publishes it to the peers.
  Afterwards, the peers verify the `content.json` integrity (using the
  signature), they download the modified files and publish the new content to
  other peers.

####  [Slideshow about ZeroNet cryptography, site updates, multi-user sites »](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)
####  [Frequently asked questions »](https://zeronet.io/docs/faq/)

####  [ZeroNet Developer Documentation »](https://zeronet.io/docs/site_development/getting_started/)


## Screenshots

![Screenshot](https://i.imgur.com/H60OAHY.png)
![ZeroTalk](https://zeronet.io/docs/img/zerotalk.png)

#### [More screenshots in ZeroNet docs »](https://zeronet.io/docs/using_zeronet/sample_sites/)


## How to join

### Windows

 - Download [ZeroNet-py3-win64.zip](https://github.com/HelloZeroNet/ZeroNet-win/archive/dist-win64/ZeroNet-py3-win64.zip) (18MB)
 - Unpack anywhere
 - Run `ZeroNet.exe`
 
### macOS

 - Download [ZeroNet-dist-mac.zip](https://github.com/HelloZeroNet/ZeroNet-dist/archive/mac/ZeroNet-dist-mac.zip) (13.2MB)
 - Unpack anywhere
 - Run `ZeroNet.app`
 
### Linux (x86-64bit) 

__Warning:__ Never run ZeroNet as root user!

 - `wget https://github.com/HelloZeroNet/ZeroNet-linux/archive/dist-linux64/ZeroNet-py3-linux64.tar.gz`
 - `tar xvpfz ZeroNet-py3-linux64.tar.gz`
 - `cd ZeroNet-linux-dist-linux64/`
 - Start with: `./ZeroNet.sh`
 - Open the ZeroHello landing page in your browser by navigating to: http://127.0.0.1:43110/
 
 __Tip:__ Start with `./ZeroNet.sh --ui_ip '*' --ui_restrict your.ip.address` to allow remote connections on the web interface.
 
 ### Android (arm, arm64, x86)
 - minimum Android version supported 16 (JellyBean).
 - Google Play Store Link https://play.google.com/store/apps/details?id=in.canews.zeronet

[<img src="https://play.google.com/intl/en_us/badges/images/generic/en_badge_web_generic.png" 
      alt="Download from Google Play" 
      height="80">](https://play.google.com/store/apps/details?id=in.canews.zeronet)

#### Docker
There is an official image, built from source at: https://hub.docker.com/r/nofish/zeronet/

### Install from source

__Warning:__ Never run ZeroNet as root user!

 - `wget https://github.com/HelloZeroNet/ZeroNet/archive/py3/ZeroNet-py3.tar.gz`
 - `tar xvpfz ZeroNet-py3.tar.gz`
 - `cd ZeroNet-py3`
 - `sudo apt-get update`
 - `sudo apt-get install python3-pip`
 - `sudo python3 -m pip install -r requirements.txt`
 - Start with: `python3 zeronet.py`
 - Open the ZeroHello landing page in your browser by navigating to: http://127.0.0.1:43110/

## Current limitations

* ~~No torrent-like file splitting for big file support~~ (big file support added)
* ~~No more anonymous than Bittorrent~~ (built-in full Tor support added)
* File transactions are not compressed ~~or encrypted yet~~ (TLS encryption added)
* No private sites


## How can I create a ZeroNet site?

 * Click on **⋮** > **"Create new, empty site"** menu item on the site [ZeroHello](http://127.0.0.1:43110/1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D).
 * You will be **redirected** to a completely new site that is only modifiable by you!
 * You can find and modify your site's content in **data/[yoursiteaddress]** directory
 * After the modifications open your site, drag the topright "0" button to left, then press **sign** and **publish** buttons on the bottom

Next steps: [ZeroNet Developer Documentation](https://zeronet.io/docs/site_development/getting_started/)

## Help keep this project alive

- Bitcoin: 1QDhxQ6PraUZa21ET5fYUCPgdrwBomnFgX
- Paypal: https://zeronet.io/docs/help_zeronet/donate/

### Sponsors

* Better macOS/Safari compatibility made possible by [BrowserStack.com](https://www.browserstack.com)

#### Thank you!

* More info, help, changelog, zeronet sites: https://www.reddit.com/r/zeronet/
* Come, chat with us: [#zeronet @ FreeNode](https://kiwiirc.com/client/irc.freenode.net/zeronet) or on [gitter](https://gitter.im/HelloZeroNet/ZeroNet)
* Email: hello@zeronet.io (PGP: [960F FF2D 6C14 5AA6 13E8 491B 5B63 BAE6 CB96 13AE](https://zeronet.io/files/tamas@zeronet.io_pub.asc))

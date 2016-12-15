# ZeroNet [![Build Status](https://travis-ci.org/HelloZeroNet/ZeroNet.svg?branch=master)](https://travis-ci.org/HelloZeroNet/ZeroNet) [![Documentation](https://img.shields.io/badge/docs-faq-brightgreen.svg)](https://zeronet.readthedocs.org/en/latest/faq/) [![Help](https://img.shields.io/badge/keep_this_project_alive-donate-yellow.svg)](https://zeronet.readthedocs.org/en/latest/help_zeronet/donate/)

[简体中文](./README-zh-cn.md)

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
####  [Frequently asked questions »](https://zeronet.readthedocs.org/en/latest/faq/)

####  [ZeroNet Developer Documentation »](https://zeronet.readthedocs.org/en/latest/site_development/getting_started/)


## Screenshots

![Screenshot](https://i.imgur.com/H60OAHY.png)
![ZeroTalk](https://zeronet.readthedocs.org/en/latest/img/zerotalk.png)

#### [More screenshots in ZeroNet docs »](https://zeronet.readthedocs.org/en/latest/using_zeronet/sample_sites/)


## How to join

* Download ZeroBundle package:
  * [Microsoft Windows](https://github.com/HelloZeroNet/ZeroBundle/raw/master/dist/ZeroBundle-win.zip)
  * [Apple OS X](https://github.com/HelloZeroNet/ZeroBundle/raw/master/dist/ZeroBundle-mac-osx.zip)
  * [Linux 64bit](https://github.com/HelloZeroNet/ZeroBundle/raw/master/dist/ZeroBundle-linux64.tar.gz)
  * [Linux 32bit](https://github.com/HelloZeroNet/ZeroBundle/raw/master/dist/ZeroBundle-linux32.tar.gz)
* Unpack anywhere
* Run `ZeroNet.cmd` (win), `ZeroNet(.app)` (osx), `ZeroNet.sh` (linux)
* On OSX you may need to make the application executable via `chmod +x ZeroNet.app`

If you get "classic environment no longer supported" error on OS X: Open a Terminal window and drop ZeroNet.app on it

It downloads the latest version of ZeroNet then starts it automatically.

### Linux terminal

* `wget https://github.com/HelloZeroNet/ZeroBundle/raw/master/dist/ZeroBundle-linux64.tar.gz`
* `tar xvpfz ZeroBundle-linux64.tar.gz`
* `cd ZeroBundle`
* Start with `./ZeroNet.sh`

It downloads the latest version of ZeroNet then starts it automatically.

#### Manual install for Debian Linux

* `sudo apt-get update`
* `sudo apt-get install msgpack-python python-gevent`
* `wget https://github.com/HelloZeroNet/ZeroNet/archive/master.tar.gz`
* `tar xvpfz master.tar.gz`
* `cd ZeroNet-master`
* Start with `python zeronet.py`
* Open http://127.0.0.1:43110/ in your browser


### [Vagrant](https://www.vagrantup.com/)

* `vagrant up`
* Access VM with `vagrant ssh`
* `cd /vagrant`
* Run `python zeronet.py --ui_ip 0.0.0.0`
* Open http://127.0.0.1:43110/ in your browser

### [Docker](https://www.docker.com/)
* `docker run -d -v <local_data_folder>:/root/data -p 15441:15441 -p 127.0.0.1:43110:43110 nofish/zeronet`
* This Docker image includes the Tor proxy, which is disabled by default. Beware that some
hosting providers may not allow you running Tor in their servers. If you want to enable it,
set `ENABLE_TOR` environment variable to `true` (Default: `false`). E.g.:

 `docker run -d -e "ENABLE_TOR=true" -v <local_data_folder>:/root/data -p 15441:15441 -p 127.0.0.1:43110:43110 nofish/zeronet`
* Open http://127.0.0.1:43110/ in your browser

### [Virtualenv](https://virtualenv.readthedocs.org/en/latest/)

* `virtualenv env`
* `source env/bin/activate`
* `pip install msgpack-python gevent`
* `python zeronet.py`
* Open http://127.0.0.1:43110/ in your browser

## Current limitations

* No torrent-like file splitting for big file support
* ~~No more anonymous than Bittorrent~~ (built-in full Tor support added)
* File transactions are not compressed ~~or encrypted yet~~ (TLS encryption added)
* No private sites


## How can I create a ZeroNet site?

Shut down zeronet if you are running it already

```bash
$ zeronet.py siteCreate
...
- Site private key: 23DKQpzxhbVBrAtvLEc2uvk7DZweh4qL3fn3jpM3LgHDczMK2TtYUq
- Site address: 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
...
- Site created!
$ zeronet.py
...
```

Congratulations, you're finished! Now anyone can access your site using
`http://localhost:43110/13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2`

Next steps: [ZeroNet Developer Documentation](https://zeronet.readthedocs.org/en/latest/site_development/getting_started/)


## How can I modify a ZeroNet site?

* Modify files located in data/13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2 directory.
  After you're finished:

```bash
$ zeronet.py siteSign 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
- Signing site: 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2...
Private key (input hidden):
```

* Enter the private key you got when you created the site, then:

```bash
$ zeronet.py sitePublish 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
...
Site:13DNDk..bhC2 Publishing to 3/10 peers...
Site:13DNDk..bhC2 Successfuly published to 3 peers
- Serving files....
```

* That's it! You've successfully signed and published your modifications.


## Help keep this project alive

- Bitcoin: 1QDhxQ6PraUZa21ET5fYUCPgdrwBomnFgX
- Paypal: https://zeronet.readthedocs.org/en/latest/help_zeronet/donate/
- Gratipay: https://gratipay.com/zeronet/

### Sponsors

* Better OSX/Safari compatibility made possible by [BrowserStack.com](https://www.browserstack.com)

#### Thank you!

* More info, help, changelog, zeronet sites: https://www.reddit.com/r/zeronet/
* Come, chat with us: [#zeronet @ FreeNode](https://kiwiirc.com/client/irc.freenode.net/zeronet) or on [gitter](https://gitter.im/HelloZeroNet/ZeroNet)
* Email: hello@noloop.me

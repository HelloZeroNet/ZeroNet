# ZeroNet

Decentralized websites using Bitcoin crypto and the BitTorrent network - http://zeronet.io


## Why?

* We believe in open, free, and uncensored network and communication.
* No single point of failure: Site remains online so long as at least 1 peer
  serving it.
* No hosting costs: Sites are served by visitors.
* Impossible to shut down: It's nowhere because it's everywhere.
* Fast and works offline: You can access the site even if your internet is
  unavailable.


## Features
 * Real-time updated sites
 * Namecoin .bit domains support
 * Easy to setup: unpack & run
 * Password-less [BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki) 
   based authorization: Your account is protected by same cryptography as your Bitcoin wallet
 * Built-in SQL server with P2P data synchronization: Allows easier site development and faster page load times
 * Tor network support
 * Automatic, uPnP port opening
 * Plugin for multiuser (openproxy) support
 * Works with any browser/OS
 

## How does it work?

* After starting `zeronet.py` you will be able to visit zeronet sites using
  `http://127.0.0.1:43110/{zeronet_address}` (eg. 
  `http://127.0.0.1:43110/1EU1tbG9oC1A8jz2ouVwGZyQ5asrNsE4Vr`).
* When you visit a new zeronet site, it tries to find peers using the BitTorrent
  network so it can download the site files (html, css, js...) from them.
* Each visited site becomes also served by you.
* Every site contains a `site.json` which holds all other files in a sha512 hash
  and a signature generated using site's private key.
* If the site owner (who has the private key for the site address) modifies the
  site, then he/she signs the new `content.json` and publishes it to the peers.
  After the peers have verified the `content.json` integrity (using the
  signature), they download the modified files and publish the new content to
  other peers.

####  [Slideshow about ZeroNet cryptography, site updates, multi-user sites »](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)



## Screenshots

![Screenshot](http://zeronet.readthedocs.org/en/latest/img/zerohello.png)
![ZeroTalk](http://zeronet.readthedocs.org/en/latest/img/zerotalk.png)

#### [More screenshots in ZeroNet docs »](http://zeronet.readthedocs.org/en/latest/using_zeronet/sample_sites/)


## How to join?

### Windows

* [Download ZeroBundle package](https://github.com/HelloZeroNet/ZeroBundle/releases/download/0.1.0/ZeroBundle-v0.1.0.zip) that includes Python 2.7.9 and all required library
* Unpack to any directory
* Run `zeronet.cmd`

It downloads the latest version of ZeroNet then starts it automatically.


#### Alternative method for Windows by installing Python

* [Install Python 2.7](https://www.python.org/ftp/python/2.7.9/python-2.7.9.msi)
* [Install Python Greenlet](http://zeronet.io/files/windows/greenlet-0.4.5.win32-py2.7.exe)
* [Install Python Gevent](http://zeronet.io/files/windows/gevent-1.0.1.win32-py2.7.exe)
* [Install Python MsgPack](http://zeronet.io/files/windows/msgpack-python-0.4.2.win32-py2.7.exe)
* [Download and extract ZeroNet](https://codeload.github.com/HelloZeroNet/ZeroNet/zip/master) to any directory
* Run `start.py`

### Linux

#### Debian

* `sudo apt-get update`
* `sudo apt-get install msgpack-python python-gevent` 
* `wget https://github.com/HelloZeroNet/ZeroNet/archive/master.tar.gz`
* `tar xvpfz master.tar.gz`
* `cd ZeroNet-master`
* Start with `python zeronet.py`
* Open http://127.0.0.1:43110/ in your browser and enjoy! :)

#### Other Linux or without root access
* Check your python version using `python --version` if the returned version is not `Python 2.7.X` then try `python2` or `python2.7` command and use it from now
* `wget https://bootstrap.pypa.io/get-pip.py` 
* `python get-pip.py --user gevent msgpack-python`
* Start with `python zeronet.py`

### Mac

 * Install [brew](http://brew.sh/)
 * `brew install python`
 * `pip install gevent msgpack-python`
 * [Download](https://github.com/HelloZeroNet/ZeroNet/archive/master.zip), Unpack, run `python zeronet.py`
 
### Vagrant

* `vagrant up`
* Access VM with `vagrant ssh`
* `cd /vagrant`
* Run `python zeronet.py --ui_ip 0.0.0.0`
* Open http://127.0.0.1:43110/ in your browser

### Docker
* `docker run -p 15441:15441 -p 43110:43110 nofish/zeronet​`
* Open http://127.0.0.1:43110/ in your browser

## Current limitations

* No torrent-like, file splitting for big file support
* No more anonymous than Bittorrent
* File transactions are not compressed or encrypted yet
* No private sites
* ~~You must have an open port to publish new changes~~
* ~~Timeout problems on slow connections~~


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

Next steps: [ZeroNet Developer Documentation](http://zeronet.readthedocs.org/en/latest/site_development/getting_started/)


## How can I modify a ZeroNet site?

* Modify files located in data/13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2 directory.
  After you're finished:

```bash
$ zeronet.py siteSign 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
- Signing site: 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2...
Private key (input hidden):
```

* Enter the private key you got when created the site, then:

```bash
$ zeronet.py sitePublish 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
...
Site:13DNDk..bhC2 Publishing to 3/10 peers...
Site:13DNDk..bhC2 Successfuly published to 3 peers
- Serving files....
```

* That's it! You've successfully signed and published your modifications.


## If you want to help keep this project alive

Bitcoin: 1QDhxQ6PraUZa21ET5fYUCPgdrwBomnFgX


#### Thank you!

* More info, help, changelog, zeronet sites: http://www.reddit.com/r/zeronet/
* Come, chat with us: [#zeronet @ FreeNode](https://kiwiirc.com/client/irc.freenode.net/zeronet) or on [gitter](https://gitter.im/HelloZeroNet/ZeroNet)
* Email: hello@noloop.me

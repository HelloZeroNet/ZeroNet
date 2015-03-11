# ZeroNet

Decentralized websites using Bitcoin crypto and the BitTorrent network


## Why?

* We believe in open, free, and uncensored network and communication.
* No single point of failure: Site remains online so long as at least 1 peer
  serving it.
* No hosting costs: Sites are served by visitors.
* Impossible to shut down: It's nowhere because it's everywhere.
* Fast and works offline: You can access the site even if your internet is
  unavailable.


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


## Screenshot

![Screenshot](http://i.imgur.com/QaZhUCk.png)


## How to join?

### Windows

* [Install Python 2.7](https://www.python.org/ftp/python/2.7.9/python-2.7.9.msi)
* [Install Python ZeroMQ](http://zeronet.io/files/windows/pyzmq-14.4.1.win32-py2.7.exe)
* [Install Python Greenlet](http://zeronet.io/files/windows/greenlet-0.4.5.win32-py2.7.exe)
* [Install Python Gevent](http://zeronet.io/files/windows/gevent-1.0.1.win32-py2.7.exe)
* [Install Python MsgPack](http://zeronet.io/files/windows/msgpack-python-0.4.2.win32-py2.7.exe)
* Start `start.py`

### Linux

#### Debian

* `apt-get install python-dev python-pip` 
* `pip install pyzmq gevent msgpack-python`
* Start with `python zeronet.py`

#### Other Linux or without root access
* Check your python version using `python --version` if the returned version is not `Python 2.7.X` then try `python2` or `python2.7` command and use it from now
* `wget https://bootstrap.pypa.io/get-pip.py` 
* `python get-pip.py --user pyzmq gevent msgpack-python`
* Start with `python zeronet.py`

## Current limitations

* No torrent-like, file splitting for big file support
* No more anonymous than Bittorrent
* File transactions are not compressed or encrypted yet
* No private sites
* You must have an open port to publish new changes
* Timeout problems on slow connections


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

Next steps: [ZeroNet Developer Documentation](http://zeronet.readthedocs.org/en/latest/site_development/debug_mode/)


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

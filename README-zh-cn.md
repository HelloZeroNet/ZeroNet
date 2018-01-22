# ZeroNet [![Build Status](https://travis-ci.org/HelloZeroNet/ZeroNet.svg?branch=master)](https://travis-ci.org/HelloZeroNet/ZeroNet) [![Documentation](https://img.shields.io/badge/docs-faq-brightgreen.svg)](https://zeronet.readthedocs.org/en/latest/faq/) [![Help](https://img.shields.io/badge/keep_this_project_alive-donate-yellow.svg)](https://zeronet.readthedocs.org/en/latest/help_zeronet/donate/)

[English](./README.md)

使用 Bitcoin 加密和 BitTorrent 网络的去中心化网络 - https://zeronet.io


## 为什么?

* 我们相信开放，自由，无审查的网络
* 不会受单点故障影响：只要有在线的节点，站点就会保持在线
* 无托管费用: 站点由访问者托管
* 无法关闭: 因为节点无处不在
* 快速并可离线运行: 即使没有互联网连接也可以使用


## 功能
 * 实时站点更新
 * 支持 Namecoin 的 .bit 域名
 * 安装方便: 只需解压并运行
 * 一键克隆存在的站点
 * 无需密码、基于 [BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki) 的认证：用与比特币钱包相同的加密方法用来保护你的账户
你的账户被使用和比特币钱包相同的加密方法
 * 内建 SQL 服务器和 P2P 数据同步: 让开发更简单并提升加载速度
 * 匿名性: 完整的 Tor 网络支持，支持通过 .onion 隐藏服务相互连接而不是通过IPv4地址连接
 * TLS 加密连接
 * 自动打开 uPnP 端口
 * 插件和多用户 (开放式代理) 支持
 * 全平台兼容


## 原理

* 在你运行`zeronet.py`后你将可以通过`http://127.0.0.1:43110/{zeronet_address}` (比如.
`http://127.0.0.1:43110/1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D`)。访问 zeronet 中的站点。

* 在你浏览 zeronet 站点时，客户端会尝试通过 BitTorrent 网络来寻找可用的节点，从而下载需要的文件 (html, css, js...)

* 你将会储存每一个浏览过的站点
* 每个站点都包含一个名为 `content.json` ，它储存了其他所有文件的 sha512 hash 值
  和一个通过站点私钥建立的签名
* 如果站点的所有者 (拥有私钥的那个人) 修改了站点, 并且他/她签名了新的 `content.json` 然后推送至其他节点，
那么所有节点将会在验证 `content.json` 的真实性 (使用签名)后, 下载修改后的文件并推送至其他节点。

####  [有关于 ZeroNet 加密, 站点更新, 多用户站点的幻灯片 »](https://docs.google.com/presentation/d/1qBxkroB_iiX2zHEn0dt-N-qRZgyEzui46XS2hEa3AA4/pub?start=false&loop=false&delayms=3000)
####  [常见问题 »](https://zeronet.readthedocs.org/en/latest/faq/)

####  [ZeroNet开发者文档 »](https://zeronet.readthedocs.org/en/latest/site_development/getting_started/)


## 屏幕截图

![Screenshot](https://i.imgur.com/H60OAHY.png)
![ZeroTalk](https://zeronet.readthedocs.org/en/latest/img/zerotalk.png)

#### [在 ZeroNet 文档里查看更多的屏幕截图 »](https://zeronet.readthedocs.org/en/latest/using_zeronet/sample_sites/)


## 如何加入 ？

* 下载 ZeroBundle 文件包:
  * [Microsoft Windows](https://github.com/HelloZeroNet/ZeroNet-win/archive/dist/ZeroNet-win.zip)
  * [Apple macOS](https://github.com/HelloZeroNet/ZeroNet-mac/archive/dist/ZeroNet-mac.zip)
  * [Linux 64bit](https://github.com/HelloZeroNet/ZeroBundle/raw/master/dist/ZeroBundle-linux64.tar.gz)
  * [Linux 32bit](https://github.com/HelloZeroNet/ZeroBundle/raw/master/dist/ZeroBundle-linux32.tar.gz)
* 解压缩
* 运行 `ZeroNet.exe` (win), `ZeroNet(.app)` (osx), `ZeroNet.sh` (linux)

### Linux 命令行

* `wget https://github.com/HelloZeroNet/ZeroBundle/raw/master/dist/ZeroBundle-linux64.tar.gz`
* `tar xvpfz ZeroBundle-linux64.tar.gz`
* `cd ZeroBundle`
* 执行 `./ZeroNet.sh` 来启动

在你打开时他将会自动下载最新版本的 ZeroNet 。

#### 在 Debian Linux 中手动安装

* `sudo apt-get update`
* `sudo apt-get install msgpack-python python-gevent`
* `wget https://github.com/HelloZeroNet/ZeroNet/archive/master.tar.gz`
* `tar xvpfz master.tar.gz`
* `cd ZeroNet-master`
* 执行 `python2 zeronet.py` 来启动
* 在你的浏览器中打开 http://127.0.0.1:43110/

### [FreeBSD](https://www.freebsd.org/)

* `pkg install zeronet` 或者 `cd /usr/ports/security/zeronet/ && make install clean`
* `sysrc zeronet_enable="YES"`
* `service zeronet start`
* 在你的浏览器中打开 http://127.0.0.1:43110/

### [Vagrant](https://www.vagrantup.com/)

* `vagrant up`
* 通过 `vagrant ssh` 连接到 VM
* `cd /vagrant`
* 运行 `python2 zeronet.py --ui_ip 0.0.0.0`
* 在你的浏览器中打开 http://127.0.0.1:43110/

### [Docker](https://www.docker.com/)
* `docker run -d -v <local_data_folder>:/root/data -p 15441:15441 -p 43110:43110 nofish/zeronet`
* 这个 Docker 镜像包含了 Tor ，但默认是禁用的，因为一些托管商不允许你在他们的服务器上运行 Tor。如果你希望启用它，
设置 `ENABLE_TOR` 环境变量为 `true` (默认: `false`). E.g.:

 `docker run -d -e "ENABLE_TOR=true" -v <local_data_folder>:/root/data -p 15441:15441 -p 43110:43110 nofish/zeronet`
* 在你的浏览器中打开 http://127.0.0.1:43110/

### [Virtualenv](https://virtualenv.readthedocs.org/en/latest/)

* `virtualenv env`
* `source env/bin/activate`
* `pip install msgpack-python gevent`
* `python2 zeronet.py`
* 在你的浏览器中打开 http://127.0.0.1:43110/

## 现有限制

* ~~没有类似于 BitTorrent 的文件拆分来支持大文件~~ (已添加大文件支持)
* ~~没有比 BitTorrent 更好的匿名性~~ (已添加内置的完整 Tor 支持)
* 传输文件时没有压缩~~和加密~~ (已添加 TLS 支持)
* 不支持私有站点


## 如何创建一个 ZeroNet 站点?


如果 zeronet 在运行，把它关掉
执行：
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

你已经完成了！ 现在任何人都可以通过
`http://localhost:43110/13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2`
来访问你的站点

下一步: [ZeroNet 开发者文档](https://zeronet.readthedocs.org/en/latest/site_development/getting_started/)


## 我要如何修改 ZeroNet 站点?

* 修改位于 data/13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2 的目录.
  在你改好之后:

```bash
$ zeronet.py siteSign 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
- Signing site: 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2...
Private key (input hidden):
```

* 输入你在创建站点时获得的私钥

```bash
$ zeronet.py sitePublish 13DNDkMUExRf9Xa9ogwPKqp7zyHFEqbhC2
...
Site:13DNDk..bhC2 Publishing to 3/10 peers...
Site:13DNDk..bhC2 Successfuly published to 3 peers
- Serving files....
```

* 就是这样! 你现在已经成功的签名并推送了你的更改。


## 帮助这个项目

- Bitcoin: 1QDhxQ6PraUZa21ET5fYUCPgdrwBomnFgX
- Paypal: https://zeronet.readthedocs.org/en/latest/help_zeronet/donate/

### 赞助商

* 在 OSX/Safari 下 [BrowserStack.com](https://www.browserstack.com) 带来更好的兼容性

#### 感谢!

* 更多信息, 帮助, 变更记录和 zeronet 站点: https://www.reddit.com/r/zeronet/
* 在: [#zeronet @ FreeNode](https://kiwiirc.com/client/irc.freenode.net/zeronet) 和我们聊天，或者使用 [gitter](https://gitter.im/HelloZeroNet/ZeroNet)
* [这里](https://gitter.im/ZeroNet-zh/Lobby)是一个 gitter 上的中文聊天室
* Email: hello@noloop.me

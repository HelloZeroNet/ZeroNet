# ZeroNet [![Build Status](https://travis-ci.org/HelloZeroNet/ZeroNet.svg?branch=py3)](https://travis-ci.org/HelloZeroNet/ZeroNet) [![Documentation](https://img.shields.io/badge/docs-faq-brightgreen.svg)](https://zeronet.io/docs/faq/) [![Help](https://img.shields.io/badge/keep_this_project_alive-donate-yellow.svg)](https://zeronet.io/docs/help_zeronet/donate/)

[English](./README.md)

使用 Bitcoin 加密和 BitTorrent 网络的去中心化网络 - https://zeronet.io


## 为什么？

* 我们相信开放，自由，无审查的网络和通讯
* 不会受单点故障影响：只要有在线的节点，站点就会保持在线
* 无托管费用：站点由访问者托管
* 无法关闭：因为节点无处不在
* 快速并可离线运行：即使没有互联网连接也可以使用


## 功能
 * 实时站点更新
 * 支持 Namecoin 的 .bit 域名
 * 安装方便：只需解压并运行
 * 一键克隆存在的站点
 * 无需密码、基于 [BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki)
   的认证：您的账户被与比特币钱包相同的加密方法保护
 * 内建 SQL 服务器和 P2P 数据同步：让开发更简单并提升加载速度
 * 匿名性：完整的 Tor 网络支持，支持通过 .onion 隐藏服务相互连接而不是通过 IPv4 地址连接
 * TLS 加密连接
 * 自动打开 uPnP 端口
 * 多用户（openproxy）支持的插件
 * 适用于任何浏览器 / 操作系统


## 原理

* 在运行 `zeronet.py` 后，您将可以通过
  `http://127.0.0.1:43110/{zeronet_address}`（例如：
  `http://127.0.0.1:43110/1HeLLoPVbqF3UEj8aWXErwTxrwkyjwGtZN`）访问 zeronet 中的站点
* 在您浏览 zeronet 站点时，客户端会尝试通过 BitTorrent 网络来寻找可用的节点，从而下载需要的文件（html，css，js...）
* 您将会储存每一个浏览过的站点
* 每个站点都包含一个名为 `content.json` 的文件，它储存了其他所有文件的 sha512 散列值以及一个通过站点私钥生成的签名
* 如果站点的所有者（拥有站点地址的私钥）修改了站点，并且他 / 她签名了新的 `content.json` 然后推送至其他节点，
  那么这些节点将会在使用签名验证 `content.json` 的真实性后，下载修改后的文件并将新内容推送至另外的节点

####  [关于 ZeroNet 加密，站点更新，多用户站点的幻灯片 »](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)
####  [常见问题 »](https://zeronet.io/docs/faq/)

####  [ZeroNet 开发者文档 »](https://zeronet.io/docs/site_development/getting_started/)


## 屏幕截图

![Screenshot](https://i.imgur.com/H60OAHY.png)
![ZeroTalk](https://zeronet.io/docs/img/zerotalk.png)

#### [ZeroNet 文档中的更多屏幕截图 »](https://zeronet.io/docs/using_zeronet/sample_sites/)


## 如何加入

### Windows

 - 下载 [ZeroNet-py3-win64.zip](https://github.com/HelloZeroNet/ZeroNet-win/archive/dist-win64/ZeroNet-py3-win64.zip) (18MB)
 - 在任意位置解压缩
 - 运行 `ZeroNet.exe`
 
### macOS

 - 下载 [ZeroNet-dist-mac.zip](https://github.com/HelloZeroNet/ZeroNet-dist/archive/mac/ZeroNet-dist-mac.zip) (13.2MB)
 - 在任意位置解压缩
 - 运行 `ZeroNet.app`
 
### Linux (x86-64bit)

 - `wget https://github.com/HelloZeroNet/ZeroNet-linux/archive/dist-linux64/ZeroNet-py3-linux64.tar.gz`
 - `tar xvpfz ZeroNet-py3-linux64.tar.gz`
 - `cd ZeroNet-linux-dist-linux64/`
 - 使用以下命令启动 `./ZeroNet.sh`
 - 在浏览器打开 http://127.0.0.1:43110/ 即可访问 ZeroHello 页面
 
 __提示：__ 若要允许在 Web 界面上的远程连接，使用以下命令启动 `./ZeroNet.sh --ui_ip '*' --ui_restrict your.ip.address`

### 从源代码安装

 - `wget https://github.com/HelloZeroNet/ZeroNet/archive/py3/ZeroNet-py3.tar.gz`
 - `tar xvpfz ZeroNet-py3.tar.gz`
 - `cd ZeroNet-py3`
 - `sudo apt-get update`
 - `sudo apt-get install python3-pip`
 - `sudo python3 -m pip install -r requirements.txt`
 - 使用以下命令启动 `python3 zeronet.py`
 - 在浏览器打开 http://127.0.0.1:43110/ 即可访问 ZeroHello 页面

## 现有限制

* ~~没有类似于 torrent 的文件拆分来支持大文件~~ （已添加大文件支持）
* ~~没有比 BitTorrent 更好的匿名性~~ （已添加内置的完整 Tor 支持）
* 传输文件时没有压缩~~和加密~~ （已添加 TLS 支持）
* 不支持私有站点


## 如何创建一个 ZeroNet 站点？

 * 点击 [ZeroHello](http://127.0.0.1:43110/1HeLLoPVbqF3UEj8aWXErwTxrwkyjwGtZN) 站点的 **⋮** > **「新建空站点」** 菜单项
 * 您将被**重定向**到一个全新的站点，该站点只能由您修改
 * 您可以在 **data/[您的站点地址]** 目录中找到并修改网站的内容
 * 修改后打开您的网站，将右上角的「0」按钮拖到左侧，然后点击底部的**签名**并**发布**按钮

接下来的步骤：[ZeroNet 开发者文档](https://zeronet.io/docs/site_development/getting_started/)

## 帮助这个项目

- Bitcoin: 1QDhxQ6PraUZa21ET5fYUCPgdrwBomnFgX
- Paypal: https://zeronet.io/docs/help_zeronet/donate/

### 赞助商

* [BrowserStack.com](https://www.browserstack.com) 使更好的 macOS/Safari 兼容性成为可能

#### 感谢您！

* 更多信息，帮助，变更记录和 zeronet 站点：https://www.reddit.com/r/zeronet/
* 前往 [#zeronet @ FreeNode](https://kiwiirc.com/client/irc.freenode.net/zeronet) 或 [gitter](https://gitter.im/HelloZeroNet/ZeroNet) 和我们聊天
* [这里](https://gitter.im/ZeroNet-zh/Lobby)是一个 gitter 上的中文聊天室
* Email: hello@zeronet.io (PGP: [960F FF2D 6C14 5AA6 13E8 491B 5B63 BAE6 CB96 13AE](https://zeronet.io/files/tamas@zeronet.io_pub.asc))

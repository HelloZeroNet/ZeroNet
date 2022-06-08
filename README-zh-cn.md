# zeronet-conservancy

**警告**：这个翻译已经过时了。请阅读英文版。对此翻译的任何贡献都将受到高度赞赏

[in English](README.md) | [em português](README-ptbr.md) | [по-русски](README-ru.md)

## 为什么？

* 我们相信开放，自由，无审查的网络和通讯
* 不会受单点故障影响：只要有在线的节点，站点就会保持在线
* 无托管费用：站点由访问者托管
* 无法关闭：因为节点无处不在
* 快速并可离线运行：即使没有互联网连接也可以使用


## 功能
 * 实时站点更新
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
  `http://127.0.0.1:43110/1HeLLo4uzjaLetFx6NH3PMwFP3qbRbTf3D`）访问 zeronet 中的站点
* 在您浏览 zeronet 站点时，客户端会尝试通过 BitTorrent 网络来寻找可用的节点，从而下载需要的文件（html，css，js...）
* 您将会储存每一个浏览过的站点
* 每个站点都包含一个名为 `content.json` 的文件，它储存了其他所有文件的 sha512 散列值以及一个通过站点私钥生成的签名
* 如果站点的所有者（拥有站点地址的私钥）修改了站点，并且他 / 她签名了新的 `content.json` 然后推送至其他节点，
  那么这些节点将会在使用签名验证 `content.json` 的真实性后，下载修改后的文件并将新内容推送至另外的节点

####  [关于 ZeroNet 加密，站点更新，多用户站点的幻灯片 »](https://docs.google.com/presentation/d/1_2qK1IuOKJ51pgBvllZ9Yu7Au2l551t3XBgyTSvilew/pub?start=false&loop=false&delayms=3000)
####  [常见问题 »](https://zeronet.io/docs/faq/)

####  [ZeroNet 开发者文档 »](https://zeronet.io/docs/site_development/getting_started/)


## 屏幕截图

#### [ZeroNet 文档中的更多屏幕截图 »](https://zeronet.io/docs/using_zeronet/sample_sites/)


## 如何加入



## 现有限制

* ~~没有类似于 torrent 的文件拆分来支持大文件~~ （已添加大文件支持）
* ~~没有比 BitTorrent 更好的匿名性~~ （已添加内置的完整 Tor 支持）
* 传输文件时没有压缩~~和加密~~ （已添加 TLS 支持）
* 不支持私有站点


## 如何创建一个 ZeroNet 站点？

 * 点击 [ZeroHello](http://127.0.0.1:43110/126NXcevn1AUehWFZLTBw7FrX1crEizQdr) 站点的 **⋮** > **「新建空站点」** 菜单项
 * 您将被**重定向**到一个全新的站点，该站点只能由您修改
 * 您可以在 **data/[您的站点地址]** 目录中找到并修改网站的内容
 * 修改后打开您的网站，将右上角的「0」按钮拖到左侧，然后点击底部的**签名**并**发布**按钮

接下来的步骤：[ZeroNet 开发者文档](https://zeronet.io/docs/site_development/getting_started/)

## 帮助这个项目

- Bitcoin: 1Kjuw3reZvxRVNs27Gen7jPJYCn6LY7Fg6

#### 感谢您！

* 更多信息，帮助，变更记录和 zeronet 站点：https://www.reddit.com/r/zeronet/

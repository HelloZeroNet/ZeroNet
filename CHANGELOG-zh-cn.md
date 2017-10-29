## ZeroNet 0.5.1 (2016-11-18)
### 新增
- 多语言界面
- 新插件：为站点 HTML 与 JS 文件提供的翻译助手
- 每个站点独立的 favicon

### 修复
- 并行可选文件下载

## ZeroNet 0.5.0 (2016-11-08)
### 新增
- 新插件：允许在 ZeroHello 列出/删除/固定/管理文件
- 新的 API 命令来关注用户的可选文件，与可选文件的请求统计
- 新的可选文件总大小限制
- 新插件：保存节点到数据库并在重启时保持它们，使得更快的可选文件搜索以及在没有 Tracker 的情况下工作
- 重写 UPnP 端口打开器 + 退出时关闭端口（感谢 sirMackk!）
- 通过懒惰 PeerHashfield 创建来减少内存占用
- 在 /Stats 页面加载 JSON 文件统计与数据库信息

### 更改
- 独立的锁定文件来获得更好的 Windows 兼容性
- 当执行 start.py 时，即使 ZeroNet 已经运行也打开浏览器
- 在重载时保持插件顺序来允许插件扩展另一个插件
- 只在完整加载 sites.json 时保存来避免数据丢失
- 将更多的 Tracker 更改为更可靠的 Tracker
- 更少的 findhashid CPU 使用率
- 合并下载大量可选文件
- 更多对于可选文件的其他优化
- 如果一个站点有 1000 个节点，更积极地清理
- 为验证错误使用警告而不是错误
- 首先推送更新到更新的客户端
- 损坏文件重置改进

### 修复
- 修复启动时出现的站点删除错误
- 延迟 WebSocket 消息直到连接上
- 修复如果文件包含额外数据时的数据库导入
- 修复大站点下载
- 修复 diff 发送 bug （跟踪它好长时间了）
- 修复当 JSON 文件包含 [] 字符时随机出现的发布错误
- 修复 siteDelete 与 siteCreate bug
- 修复文件写入确认对话框


## ZeroNet 0.4.1 (2016-09-05)
### 新增
- 更快启动与更少内存使用的内核改变
- 尝试连接丢失时重新连接 Tor
- 侧边栏滑入
- 尝试避免不完整的数据文件被覆盖
- 更快地打开数据库
- 在侧边栏显示用户文件大小
- 依赖 --connection_limit 的并发 worker 数量


### 更改
- 在空闲 5 分钟后关闭数据库
- 更好的站点大小计算
- 允许在域名中使用“-”符号
- 总是尝试为站点保持连接
- 移除已合并站点的合并权限
- 只扫描最后 3 天的新闻源来加快数据库请求
- 更新 ZeroBundle-win 到 Python 2.7.12


### 修复
- 修复重要的安全问题：允许任意用户无需有效的来自 ID 提供者的证书发布新内容，感谢 Kaffie 指出
- 修复在没有选择提供证书提供者时的侧边栏错误
- 在数据库重建时跳过无效文件
- 修复随机弹出的 WebSocket 连接错误
- 修复新的 siteCreate 命令
- 修复站点大小计算
- 修复计算机唤醒后的端口打开检查
- 修复 --size_limit 的命令行解析


## ZeroNet 0.4.0 (2016-08-11)
### 新增
- 合并站点插件
- Live source code reloading: Faster core development by allowing me to make changes in ZeroNet source code without restarting it.
- 为合并站点设计的新 JSON 表
- 从侧边栏重建数据库
- 允许直接在 JSON 表中存储自定义数据：更简单与快速的 SQL 查询
- 用户文件存档：允许站点拥有者存档不活跃的用户内容到单个文件（减少初始同步的时间/CPU/内存使用率）
- 在文件删除时同时触发数据库 onUpdated/update
- 从 ZeroFrame API 请求权限
- 允许使用 fileWrite API 命令在 content.json 存储额外数据
- 更快的可选文件下载
- 使用替代源 (Gogs, Gitlab) 来下载更新
- Track provided sites/connection and prefer to keep the ones with more sites to reduce connection number

### 更改
- 保持每个站点至少 5 个连接
- 将目标站点连接从 10 更改到 15
- ZeroHello 搜索功能稳定性/速度改进
- 提升机械硬盘下的客户端性能

### 修复
- 修复 IE11 wrapper nonce 错误
- 修复在移动设备上的侧边栏
- 修复站点大小计算
- 修复 IE10 兼容性
- Windows XP ZeroBundle 兼容性（感谢中国人民）


## ZeroNet 0.3.7 (2016-05-27)
### 更改
- 通过只传输补丁来减少带宽使用
- 其他 CPU /内存优化


## ZeroNet 0.3.6 (2016-05-27)
### 新增
- 新的 ZeroHello
- Newsfeed 函数

### 修复
- 安全性修复


## ZeroNet 0.3.5 (2016-02-02)
### 新增
- 带有 .onion 隐藏服务的完整 Tor 支持
- 使用 ZeroNet 协议的 Bootstrap

### 修复
- 修复 Gevent 1.0.2 兼容性


## ZeroNet 0.3.4 (2015-12-28)
### 新增
- AES, ECIES API 函数支持
- PushState 与 ReplaceState URL 通过 API 的操作支持
- 多用户 localstorage

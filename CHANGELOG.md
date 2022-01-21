### zeronet-conservancy 0.7.3 (2022-01-21) Rev5000
maintainers: @caryoscelus
- forked from the latest py3 branch of ZeroNet
- onion v3 support (thanks to @anonymoose, @zeroseed and @geekless)
- partial readme rewrite (thanks to @mitya57)
- disable updating through zite (unsafe)
- polish translation update (by Krzysztof Otręba)
- improved install instructions

### ZeroNet 0.7.2+ (latest official py3 branch)
maintainers: shortcutme a.k.a nofish a.k.a HelloZeroNet a.k.a Tamas Kocsis
- Update requirements.txt (#2617) (Jabba)
- Fix Cors permission request for connecting site
- Allow sites to request several CORS permissions at once (#2631) (Ivanq)
- Display library versions at /Env url endpoint
- Fix OpenSSL dll/so location find patcher
- Fix site listing show on big site visit
- Fix 404 error handler in UiFilePlugin (Ivanq)
- other fixes, improvements and translation updates (see more in git log)

### ZeroNet 0.7.2 2020-09-21 (Rev4528)
maintainers: shortcutme a.k.a nofish a.k.a HelloZeroNet a.k.a Tamas Kocsis
- Save content.json of site even if limit size is reached (#2114) (Lola Dam)
- fix #2107; Still save the content.json received even if site size limit is reached but dont download files (Lola Dam)
- Add multiuser admin status to server info
- Restrict blocked site addition when using mergerSiteAdd
- Open console with #ZeroNet:Console hash in url
- Fix compacting large json files
- Fix utf8 post data parsing
- Remove UiRequestPlugin from Zeroname plugin
- Fix shutdown errors on macOS
- Fix OpenSSL cert generation using LibreSSL
- Allow NOSANDBOX in local mode (#2238) (Filip Š)
- Remove limitations for img, font, media, style src in raw mode
- Use master seed to create new site from cli
- No restart after update (#2242) (Lola Dam)
- Upgrade to Python 3.8 (Christian Clauss)
- Allow all valid filenames to be added to content.json (#2141) (Josh)
- Fix loading screen scrolling on smaller screens
- Fix file rendering if content.json download failed
- Replace usage of deprecated API 'cgi.parse_qsl' (Natalia Fenclová)
- Handle announcer thread killing properly
- Move file writes and reads to separate thread
- Allow images from data uris
- Prefer connecting to non-onion peers
- Make sure we use local peers if possible
- Faster, async local ip discovery
- improve db access locks
- Fix memory leak when using sleep in threads
- more thread safety
- Validate json files in src and plugins dir
- Don't add escaping iframe message for link without target=_top
- Fix updateing deleted site in contentdb
- Don't allow parallel sites.json loading
- Fix incomplete loading of dbschema.json
- Added Custom Openssl Path for Native Clients and start_dir config (canewsin)
- Fixed "LookupError: 'hex' is not a text encoding" on /StatsBootstrapper page (#2442) (krzotr)
- Switch from gevent-websocket to gevent-ws (#2439) (Ivanq)
- Make ThreadPool a context manager to prevent memory leaks (Ivanq)
- Fix sslcrypto thread safety (#2454)
- Search for any OpenSSL version in LD_LIBRARY_PATH (Ivanq)
- Change to GPLv3 license
- Allow opening the sidebar while content.json is not loaded (Vadim Ushakov)
- UiPassword fixes
- Fix loading invalid site block list
- Fix wrapper_nonce adding to url
- Try to recover site privatekey from master seed when site owned switch enabled
- Fix not downloaded site delete on startup
- bad file download fixes
- UiFileManager plugin
- translation updates
- many other fixes and improvements (see git log for details)

### ZeroNet 0.7.1 (2019-07-01) Rev4206
### Added
 - Built-in logging console in the web UI to see what's happening in the background. (pull down top-right 0 button to see it)
 - Display database rebuild errors [Thanks to Lola]
 - New plugin system that allows to install and manage builtin/third party extensions to the ZeroNet client using the web interface.
 - Support multiple trackers_file
 - Add OpenSSL 1.1 support to CryptMessage plugin based on Bitmessage modifications [Thanks to radfish]
 - Display visual error message on startup errors
 - Fix max opened files changing on Windows platform
 - Display TLS1.3 compatibility on /Stats page
 - Add fake SNI and ALPN to peer connections to make it more like standard https connections
 - Hide and ignore tracker_proxy setting in Tor: Always mode as it's going to use Tor anyway.
 - Deny websocket connections from unknown origins
 - Restrict open_browser values to avoid RCE on sandbox escape
 - Offer access web interface by IP address in case of unknown host
 - Link to site's sidebar with "#ZeroNet:OpenSidebar" hash

### Changed
 - Allow .. in file names [Thanks to imachug]
 - Change unstable trackers
 - More clean errors on sites.json/users.json load error
 - Various tweaks for tracker rating on unstable connections
 - Use OpenSSL 1.1 dlls from default Python Windows distribution if possible
 - Re-factor domain resolving for easier domain plugins
 - Disable UDP connections if --proxy is used
 - New, decorator-based Websocket API permission system to avoid future typo mistakes

### Fixed
 - Fix parsing config lines that have no value
 - Fix start.py [Thanks to imachug]
 - Allow multiple values of the same key in the config file [Thanks ssdifnskdjfnsdjk for reporting]
 - Fix parsing config file lines that has % in the value [Thanks slrslr for reporting]
 - Fix bootstrapper plugin hash reloads [Thanks geekless for reporting]
 - Fix CryptMessage plugin OpenSSL dll loading on Windows (ZeroMail errors) [Thanks cxgreat2014 for reporting]
 - Fix startup error when using OpenSSL 1.1 [Thanks to imachug]
 - Fix a bug that did not loaded merged site data for 5 sec after the merged site got added
 - Fix typo that allowed to add new plugins in public proxy mode. [Thanks styromaniac for reporting]
 - Fix loading non-big files with "|all" postfix [Thanks to krzotr]
 - Fix OpenSSL cert generation error crash by change Windows console encoding to utf8

#### Wrapper html injection vulnerability [Reported by ivanq]

In ZeroNet before rev4188 the wrapper template variables was rendered incorrectly.

Result: The opened site was able to gain WebSocket connection with unrestricted ADMIN/NOSANDBOX access, change configuration values and possible RCE on client's machine.

Fix: Fixed the template rendering code, disallowed WebSocket connections from unknown locations, restricted open_browser configuration values to avoid possible RCE in case of sandbox escape.

Note: The fix is also back ported to ZeroNet Py 2.x version (Rev3870)


### ZeroNet 0.7.0 (2019-06-12) Rev4106 (First release targeting Python 3.4+)
### Added
 - 5-10x faster signature verification by using libsecp256k1 (Thanks to ZeroMux)
 - Generated SSL certificate randomization to avoid protocol filters (Thanks to ValdikSS)
 - Offline mode
 - P2P source code update using ZeroNet protocol
 - ecdsaSign/Verify commands to CryptMessage plugin (Thanks to imachug)
 - Efficient file rename: change file names instead of re-downloading the file.
 - Make redirect optional on site cloning (Thanks to Lola)
 - EccPrivToPub / EccPubToPriv functions (Thanks to imachug)
 - Detect and change dark/light theme based on OS setting (Thanks to filips123)

### Changed
 - Re-factored code to Python3 runtime (compatible with Python 3.4-3.8)
 - More safe database sync mode
 - Removed bundled third-party libraries where it's possible
 - Use lang=en instead of lang={lang} in urls to avoid url encode problems
 - Remove environment details from error page
 - Don't push content.json updates larger than 10kb to significantly reduce bw usage for site with many files

### Fixed
 - Fix sending files with \0 characters
 - Security fix: Escape error detail to avoid XSS (reported by krzotr)
 - Fix signature verification using libsecp256k1 for compressed addresses (mostly certificates generated in the browser)
 - Fix newsfeed if you have more than 1000 followed topic/post on one site.
 - Fix site download as zip file
 - Fix displaying sites with utf8 title
 - Error message if dbRebuild fails (Thanks to Lola)
 - Fix browser reopen if executing start.py again. (Thanks to imachug)


### ZeroNet 0.6.5 (2019-02-16) Rev3851 (Last release targeting Python 2.7.x)
### Added
 - IPv6 support in peer exchange, bigfiles, optional file finding, tracker sharing, socket listening and connecting (based on tangdou1 modifications)
 - New tracker database format with IPv6 support
 - Display notification if there is an unpublished modification for your site
 - Listen and shut down normally for SIGTERM (Thanks to blurHY)
 - Support tilde `~` in filenames (by d14na)
 - Support map for Namecoin subdomain names (Thanks to lola)
 - Add log level to config page
 - Support `{data}` for data dir variable in trackers_file value
 - Quick check content.db on startup and rebuild if necessary
 - Don't show meek proxy option if the tor client does not supports it

### Changed
 - Refactored port open checking with IPv6 support
 - Consider non-local IPs as external even is the open port check fails (for CJDNS and Yggdrasil support)
 - Add IPv6 tracker and change unstable tracker
 - Don't correct sent local time with the calculated time correction
 - Disable CSP for Edge
 - Only support CREATE commands in dbschema indexes node and SELECT from storage.query

### Fixed
 - Check the length of master seed when executing cryptGetPrivatekey CLI command
 - Only reload source code on file modification / creation
 - Detection and issue warning for latest no-script plugin
 - Fix atomic write of a non-existent file
 - Fix sql queries with lots of variables and sites with lots of content.json
 - Fix multi-line parsing of zeronet.conf
 - Fix site deletion from users.json
 - Fix site cloning before site downloaded (Reported by unsystemizer)
 - Fix queryJson for non-list nodes (Reported by MingchenZhang)


## ZeroNet 0.6.4 (2018-10-20) Rev3660
### Added
 - New plugin: UiConfig. A web interface that allows changing ZeroNet settings.
 - New plugin: AnnounceShare. Share trackers between users, automatically announce client's ip as tracker if Bootstrapper plugin is enabled.
 - Global tracker stats on ZeroHello: Include statistics from all served sites instead of displaying request statistics only for one site.
 - Support custom proxy for trackers. (Configurable with /Config)
 - Adding peers to sites manually using zeronet_peers get parameter
 - Copy site address with peers link on the sidebar.
 - Zip file listing and streaming support for Bigfiles.
 - Tracker statistics on /Stats page
 - Peer reputation save/restore to speed up sync time after startup.
 - Full support fileGet, fileList, dirList calls on tar.gz/zip files.
 - Archived_before support to user content rules to allow deletion of all user files before the specified date
 - Show and manage "Connecting" sites on ZeroHello
 - Add theme support to ZeroNet sites
 - Dark theme for ZeroHello, ZeroBlog, ZeroTalk

### Changed
 - Dynamic big file allocation: More efficient storage usage by don't pre-allocate the whole file at the beginning, but expand the size as the content downloads.
 - Reduce the request frequency to unreliable trackers.
 - Only allow 5 concurrent checkSites to run in parallel to reduce load under Tor/slow connection.
 - Stop site downloading if it reached 95% of site limit to avoid download loop for sites out of limit
 - The pinned optional files won't be removed from download queue after 30 retries and won't be deleted even if the site owner removes it.
 - Don't remove incomplete (downloading) sites on startup
 - Remove --pin_bigfile argument as big files are automatically excluded from optional files limit.

### Fixed
 - Trayicon compatibility with latest gevent
 - Request number counting for zero:// trackers
 - Peer reputation boost for zero:// trackers.
 - Blocklist of peers loaded from peerdb (Thanks tangdou1 for report)
 - Sidebar map loading on foreign languages (Thx tangdou1 for report)
 - FileGet on non-existent files (Thanks mcdev for reporting)
 - Peer connecting bug for sites with low amount of peers

#### "The Vacation" Sandbox escape bug [Reported by GitCenter / Krixano / ZeroLSTN]

In ZeroNet 0.6.3 Rev3615 and earlier as a result of invalid file type detection, a malicious site could escape the iframe sandbox.

Result: Browser iframe sandbox escape

Applied fix: Replaced the previous, file extension based file type identification with a proper one.

Affected versions: All versions before ZeroNet Rev3616


## ZeroNet 0.6.3 (2018-06-26)
### Added
 - New plugin: ContentFilter that allows to have shared site and user block list.
 - Support Tor meek proxies to avoid tracker blocking of GFW
 - Detect network level tracker blocking and easy setting meek proxy for tracker connections.
 - Support downloading 2GB+ sites as .zip (Thx to Radtoo)
 - Support ZeroNet as a transparent proxy (Thx to JeremyRand)
 - Allow fileQuery as CORS command (Thx to imachug)
 - Windows distribution includes Tor and meek client by default
 - Download sites as zip link to sidebar
 - File server port randomization
 - Implicit SSL for all connection
 - fileList API command for zip files
 - Auto download bigfiles size limit on sidebar
 - Local peer number to the sidebar
 - Open site directory button in sidebar

### Changed
 - Switched to Azure Tor meek proxy as Amazon one became unavailable
 - Refactored/rewritten tracker connection manager
 - Improved peer discovery for optional files without opened port
 - Also delete Bigfile's piecemap on deletion

### Fixed
 - Important security issue: Iframe sandbox escape [Reported by Ivanq / gitcenter]
 - Local peer discovery when running multiple clients on the same machine
 - Uploading small files with Bigfile plugin
 - Ctrl-c shutdown when running CLI commands
 - High CPU/IO usage when Multiuser plugin enabled
 - Firefox back button
 - Peer discovery on older Linux kernels
 - Optional file handling when multiple files have the same hash_id (first 4 chars of the hash)
 - Msgpack 0.5.5 and 0.5.6 compatibility

## ZeroNet 0.6.2 (2018-02-18)

### Added
 - New plugin: AnnounceLocal to make ZeroNet work without an internet connection on the local network.
 - Allow dbQuey and userGetSettings using the `as` API command on different sites with Cors permission
 - New config option: `--log_level` to reduce log verbosity and IO load
 - Prefer to connect to recent peers from trackers first
 - Mark peers with port 1 is also unconnectable for future fix for trackers that do not support port 0 announce

### Changed
 - Don't keep connection for sites that have not been modified in the last week
 - Change unreliable trackers to new ones
 - Send maximum 10 findhash request in one find optional files round (15sec)
 - Change "Unique to site" to "No certificate" for default option in cert selection dialog.
 - Dont print warnings if not in debug mode
 - Generalized tracker logging format
 - Only recover sites from sites.json if they had peers
 - Message from local peers does not means internet connection
 - Removed `--debug_gevent` and turned on Gevent block logging by default

### Fixed
 - Limit connections to 512 to avoid reaching 1024 limit on windows
 - Exception when logging foreign operating system socket errors
 - Don't send private (local) IPs on pex
 - Don't connect to private IPs in tor always mode
 - Properly recover data from msgpack unpacker on file stream start
 - Symlinked data directory deletion when deleting site using Windows
 - De-duplicate peers before publishing
 - Bigfile info for non-existing files


## ZeroNet 0.6.1 (2018-01-25)

### Added
 - New plugin: Chart
 - Collect and display charts about your contribution to ZeroNet network
 - Allow list as argument replacement in sql queries. (Thanks to imachug)
 - Newsfeed query time statistics (Click on "From XX sites in X.Xs on ZeroHello)
 - New UiWebsocket API command: As to run commands as other site
 - Ranged ajax queries for big files
 - Filter feed by type and site address
 - FileNeed, Bigfile upload command compatibility with merger sites
 - Send event on port open / tor status change
 - More description on permission request

### Changed
 - Reduce memory usage of sidebar geoip database cache
 - Change unreliable tracker to new one
 - Don't display Cors permission ask if it already granted
 - Avoid UI blocking when rebuilding a merger site
 - Skip listing ignored directories on signing
 - In Multiuser mode show the seed welcome message when adding new certificate instead of first visit
 - Faster async port opening on multiple network interfaces
 - Allow javascript modals
 - Only zoom sidebar globe if mouse button is pressed down

### Fixed
 - Open port checking error reporting (Thanks to imachug)
 - Out-of-range big file requests
 - Don't output errors happened on gevent greenlets twice
 - Newsfeed skip sites with no database
 - Newsfeed queries with multiple params
 - Newsfeed queries with UNION and UNION ALL
 - Fix site clone with sites larger that 10MB
 - Unreliable Websocket connection when requesting files from different sites at the same time


## ZeroNet 0.6.0 (2017-10-17)

### Added
 - New plugin: Big file support
 - Automatic pinning on Big file download
 - Enable TCP_NODELAY for supporting sockets
 - actionOptionalFileList API command arguments to list non-downloaded files or only big files
 - serverShowdirectory API command arguments to allow to display site's directory in OS file browser
 - fileNeed API command to initialize optional file downloading
 - wrapperGetAjaxKey API command to request nonce for AJAX request
 - Json.gz support for database files
 - P2P port checking (Thanks for grez911)
 - `--download_optional auto` argument to enable automatic optional file downloading for newly added site
 - Statistics for big files and protocol command requests on /Stats
 - Allow to set user limitation based on auth_address

### Changed
 - More aggressive and frequent connection timeout checking
 - Use out of msgpack context file streaming for files larger than 512KB
 - Allow optional files workers over the worker limit
 - Automatic redirection to wrapper on nonce_error
 - Send websocket event on optional file deletion
 - Optimize sites.json saving
 - Enable faster C-based msgpack packer by default
 - Major optimization on Bootstrapper plugin SQL queries
 - Don't reset bad file counter on restart, to allow easier give up on unreachable files
 - Incoming connection limit changed from 1000 to 500 to avoid reaching socket limit on Windows
 - Changed tracker boot.zeronet.io domain, because zeronet.io got banned in some countries

#### Fixed
 - Sub-directories in user directories

## ZeroNet 0.5.7 (2017-07-19)
### Added
 - New plugin: CORS to request read permission to other site's content
 - New API command: userSetSettings/userGetSettings to store site's settings in users.json
 - Avoid file download if the file size does not match with the requested one
 - JavaScript and wrapper less file access using /raw/ prefix ([Example](http://127.0.0.1:43110/raw/1AsRLpuRxr3pb9p3TKoMXPSWHzh6i7fMGi/en.tar.gz/index.html))
 - --silent command line option to disable logging to stdout


### Changed
 - Better error reporting on sign/verification errors
 - More test for sign and verification process
 - Update to OpenSSL v1.0.2l
 - Limit compressed files to 6MB to avoid zip/tar.gz bomb
 - Allow space, [], () characters in filenames
 - Disable cross-site resource loading to improve privacy. [Reported by Beardog108]
 - Download directly accessed Pdf/Svg/Swf files instead of displaying them to avoid wrapper escape using in JS in SVG file. [Reported by Beardog108]
 - Disallow potentially unsafe regular expressions to avoid ReDoS [Reported by MuxZeroNet]

### Fixed
 - Detecting data directory when running Windows distribution exe [Reported by Plasmmer]
 - OpenSSL loading under Android 6+
 - Error on exiting when no connection server started


## ZeroNet 0.5.6 (2017-06-15)
### Added
 - Callback for certSelect API command
 - More compact list formatting in json

### Changed
 - Remove obsolete auth_key_sha512 and signature format
 - Improved Spanish translation (Thanks to Pupiloho)

### Fixed
 - Opened port checking (Thanks l5h5t7 & saber28 for reporting)
 - Standalone update.py argument parsing (Thanks Zalex for reporting)
 - uPnP crash on startup (Thanks Vertux for reporting)
 - CoffeeScript 1.12.6 compatibility (Thanks kavamaken & imachug)
 - Multi value argument parsing
 - Database error when running from directory that contains special characters (Thanks Pupiloho for reporting)
 - Site lock violation logging


#### Proxy bypass during source upgrade [Reported by ZeroMux]

In ZeroNet before 0.5.6 during the client's built-in source code upgrade mechanism,
ZeroNet did not respect Tor and/or proxy settings.

Result: ZeroNet downloaded the update without using the Tor network and potentially leaked the connections.

Fix: Removed the problematic code line from the updater that removed the proxy settings from the socket library.

Affected versions: ZeroNet 0.5.5 and earlier, Fixed in: ZeroNet 0.5.6


#### XSS vulnerability using DNS rebinding. [Reported by Beardog108]

In ZeroNet before 0.5.6 the web interface did not validate the request's Host parameter.

Result: An attacker using a specially crafted DNS entry could have bypassed the browser's cross-site-scripting protection
and potentially gained access to user's private data stored on site.

Fix: By default ZeroNet only accept connections from 127.0.0.1 and localhost hosts.
If you bind the ui server to an external interface, then it also adds the first http request's host to the allowed host list
or you can define it manually using --ui_host.

Affected versions: ZeroNet 0.5.5 and earlier, Fixed in: ZeroNet 0.5.6


## ZeroNet 0.5.5 (2017-05-18)
### Added
- Outgoing socket binding by --bind parameter
- Database rebuilding progress bar
- Protect low traffic site's peers from cleanup closing
- Local site blacklisting
- Cloned site source code upgrade from parent
- Input placeholder support for displayPrompt
- Alternative interaction for wrapperConfirm

### Changed
- New file priorities for faster site display on first visit
- Don't add ? to url if push/replaceState url starts with #

### Fixed
- PermissionAdd/Remove admin command requirement
- Multi-line confirmation dialog


## ZeroNet 0.5.4 (2017-04-14)
### Added
- Major speed and CPU usage enhancements in Tor always mode
- Send skipped modifications to outdated clients

### Changed
- Upgrade libs to latest version
- Faster port opening and closing
- Deny site limit modification in MultiUser mode

### Fixed
- Filling database from optional files
- OpenSSL detection on systems with OpenSSL 1.1
- Users.json corruption on systems with slow hdd
- Fix leaking files in data directory by webui


## ZeroNet 0.5.3 (2017-02-27)
### Added
- Tar.gz/zip packed site support
- Utf8 filenames in archive files
- Experimental --db_mode secure database mode to prevent data loss on systems with unreliable power source.
- Admin user support in MultiUser mode
- Optional deny adding new sites in MultiUser mode

### Changed
- Faster update and publish times by new socket sharing algorithm

### Fixed
- Fix missing json_row errors when using Mute plugin


## ZeroNet 0.5.2 (2017-02-09)
### Added
- User muting
- Win/Mac signed exe/.app
- Signed commits

### Changed
- Faster site updates after startup
- New macOS package for 10.10 compatibility

### Fixed
- Fix "New version just released" popup on page first visit
- Fix disappearing optional files bug (Thanks l5h5t7 for reporting)
- Fix skipped updates on unreliable connections (Thanks P2P for reporting)
- Sandbox escape security fix (Thanks Firebox for reporting)
- Fix error reporting on async websocket functions


## ZeroNet 0.5.1 (2016-11-18)
### Added
- Multi language interface
- New plugin: Translation helper for site html and js files
- Per-site favicon

### Fixed
- Parallel optional file downloading


## ZeroNet 0.5.0 (2016-11-08)
### Added
- New Plugin: Allow list/delete/pin/manage files on ZeroHello
- New API commands to follow user's optional files, and query stats for optional files
- Set total size limit on optional files.
- New Plugin: Save peers to database and keep them between restarts to allow more faster optional file search and make it work without trackers
- Rewritten uPnP port opener + close port on exit (Thanks to sirMackk!)
- Lower memory usage by lazy PeerHashfield creation
- Loaded json files statistics and database info at /Stats page

### Changed
- Separate lock file for better Windows compatibility
- When executing start.py open browser even if ZeroNet is already running
- Keep plugin order after reload to allow plugins to extends an another plug-in
- Only save sites.json if fully loaded to avoid data loss
- Change aletorrenty tracker to a more reliable one
- Much lower findhashid CPU usage
- Pooled downloading of large amount of optional files
- Lots of other optional file changes to make it better
- If we have 1000 peers for a site make cleanup more aggressive
- Use warning instead of error on verification errors
- Push updates to newer clients first
- Bad file reset improvements

### Fixed
- Fix site deletion errors on startup
- Delay websocket messages until it's connected
- Fix database import if data file contains extra data
- Fix big site download
- Fix diff sending bug (been chasing it for a long time)
- Fix random publish errors when json file contained [] characters
- Fix site delete and siteCreate bug
- Fix file write confirmation dialog


## ZeroNet 0.4.1 (2016-09-05)
### Added
- Major core changes to allow fast startup and lower memory usage
- Try to reconnect to Tor on lost connection
- Sidebar fade-in
- Try to avoid incomplete data files overwrite
- Faster database open
- Display user file sizes in sidebar
- Concurrent worker number depends on --connection_limit

### Changed
- Close databases after 5 min idle time
- Better site size calculation
- Allow "-" character in domains
- Always try to keep connections for sites
- Remove merger permission from merged sites
- Newsfeed scans only last 3 days to speed up database queries
- Updated ZeroBundle-win to Python 2.7.12

### Fixed
- Fix for important security problem, which is allowed anyone to publish new content without valid certificate from ID provider. Thanks Kaffie for pointing it out!
- Fix sidebar error when no certificate provider selected
- Skip invalid files on database rebuilding
- Fix random websocket connection error popups
- Fix new siteCreate command
- Fix site size calculation
- Fix port open checking after computer wake up
- Fix --size_limit parsing from command line


## ZeroNet 0.4.0 (2016-08-11)
### Added
- Merger site plugin
- Live source code reloading: Faster core development by allowing me to make changes in ZeroNet source code without restarting it.
- New json table format for merger sites
- Database rebuild from sidebar.
- Allow to store custom data directly in json table: Much simpler and faster SQL queries.
- User file archiving: Allows the site owner to archive inactive user's content into single file. (Reducing initial sync time/cpu/memory usage)
- Also trigger onUpdated/update database on file delete.
- Permission request from ZeroFrame API.
- Allow to store extra data in content.json using fileWrite API command.
- Faster optional files downloading
- Use alternative sources (Gogs, Gitlab) to download updates
- Track provided sites/connection and prefer to keep the ones with more sites to reduce connection number

### Changed
- Keep at least 5 connection per site
- Changed target connection for sites to 10 from 15
- ZeroHello search function stability/speed improvements
- Improvements for clients with slower HDD

### Fixed
- Fix IE11 wrapper nonce errors
- Fix sidebar on mobile devices
- Fix site size calculation
- Fix IE10 compatibility
- Windows XP ZeroBundle compatibility (THX to people of China)


## ZeroNet 0.3.7 (2016-05-27)
### Changed
- Patch command to reduce bandwidth usage by transfer only the changed lines
- Other cpu/memory optimizations


## ZeroNet 0.3.6 (2016-05-27)
### Added
- New ZeroHello
- Newsfeed function

### Fixed
- Security fixes


## ZeroNet 0.3.5 (2016-02-02)
### Added
- Full Tor support with .onion hidden services
- Bootstrap using ZeroNet protocol

### Fixed
- Fix Gevent 1.0.2 compatibility


## ZeroNet 0.3.4 (2015-12-28)
### Added
- AES, ECIES API function support
- PushState and ReplaceState url manipulation support in API
- Multiuser localstorage

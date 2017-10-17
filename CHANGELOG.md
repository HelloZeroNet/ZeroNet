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

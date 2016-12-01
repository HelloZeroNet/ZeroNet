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

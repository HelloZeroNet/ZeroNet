import re
import os
import cgi
import sys
import math
import time
import json
try:
    import cStringIO as StringIO
except:
    import StringIO

import gevent

from Config import config
from Plugin import PluginManager
from Debug import Debug
from Translate import Translate
from util import helper

plugin_dir = "plugins/Sidebar"
media_dir = plugin_dir + "/media"
sys.path.append(plugin_dir)  # To able to load geoip lib

loc_cache = {}
if "_" not in locals():
    _ = Translate(plugin_dir + "/languages/")


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    # Inject our resources to end of original file streams
    def actionUiMedia(self, path):
        if path == "/uimedia/all.js" or path == "/uimedia/all.css":
            # First yield the original file and header
            body_generator = super(UiRequestPlugin, self).actionUiMedia(path)
            for part in body_generator:
                yield part

            # Append our media file to the end
            ext = re.match(".*(js|css)$", path).group(1)
            plugin_media_file = "%s/all.%s" % (media_dir, ext)
            if config.debug:
                # If debugging merge *.css to all.css and *.js to all.js
                from Debug import DebugMedia
                DebugMedia.merge(plugin_media_file)
            if ext == "js":
                yield _.translateData(open(plugin_media_file).read())
            else:
                for part in self.actionFile(plugin_media_file, send_header=False):
                    yield part
        elif path.startswith("/uimedia/globe/"):  # Serve WebGL globe files
            file_name = re.match(".*/(.*)", path).group(1)
            plugin_media_file = "%s-globe/%s" % (media_dir, file_name)
            if config.debug and path.endswith("all.js"):
                # If debugging merge *.css to all.css and *.js to all.js
                from Debug import DebugMedia
                DebugMedia.merge(plugin_media_file)
            for part in self.actionFile(plugin_media_file):
                yield part
        else:
            for part in super(UiRequestPlugin, self).actionUiMedia(path):
                yield part


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def sidebarRenderPeerStats(self, body, site):
        connected = len([peer for peer in site.peers.values() if peer.connection and peer.connection.connected])
        connectable = len([peer_id for peer_id in site.peers.keys() if not peer_id.endswith(":0")])
        onion = len([peer_id for peer_id in site.peers.keys() if ".onion" in peer_id])
        peers_total = len(site.peers)
        if peers_total:
            percent_connected = float(connected) / peers_total
            percent_connectable = float(connectable) / peers_total
            percent_onion = float(onion) / peers_total
        else:
            percent_connectable = percent_connected = percent_onion = 0

        body.append(_(u"""
            <li>
             <label>{_[Peers]}</label>
             <ul class='graph'>
              <li style='width: 100%' class='total back-black' title="{_[Total peers]}"></li>
              <li style='width: {percent_connectable:.0%}' class='connectable back-blue' title='{_[Connectable peers]}'></li>
              <li style='width: {percent_onion:.0%}' class='connected back-purple' title='{_[Onion]}'></li>
              <li style='width: {percent_connected:.0%}' class='connected back-green' title='{_[Connected peers]}'></li>
             </ul>
             <ul class='graph-legend'>
              <li class='color-green'><span>{_[Connected]}:</span><b>{connected}</b></li>
              <li class='color-blue'><span>{_[Connectable]}:</span><b>{connectable}</b></li>
              <li class='color-purple'><span>{_[Onion]}:</span><b>{onion}</b></li>
              <li class='color-black'><span>{_[Total]}:</span><b>{peers_total}</b></li>
             </ul>
            </li>
        """))

    def sidebarRenderTransferStats(self, body, site):
        recv = float(site.settings.get("bytes_recv", 0)) / 1024 / 1024
        sent = float(site.settings.get("bytes_sent", 0)) / 1024 / 1024
        transfer_total = recv + sent
        if transfer_total:
            percent_recv = recv / transfer_total
            percent_sent = sent / transfer_total
        else:
            percent_recv = 0.5
            percent_sent = 0.5

        body.append(_(u"""
            <li>
             <label>{_[Data transfer]}</label>
             <ul class='graph graph-stacked'>
              <li style='width: {percent_recv:.0%}' class='received back-yellow' title="{_[Received bytes]}"></li>
              <li style='width: {percent_sent:.0%}' class='sent back-green' title="{_[Sent bytes]}"></li>
             </ul>
             <ul class='graph-legend'>
              <li class='color-yellow'><span>{_[Received]}:</span><b>{recv:.2f}MB</b></li>
              <li class='color-green'<span>{_[Sent]}:</span><b>{sent:.2f}MB</b></li>
             </ul>
            </li>
        """))

    def sidebarRenderFileStats(self, body, site):
        body.append(_(u"<li><label>{_[Files]}</label><ul class='graph graph-stacked'>"))

        extensions = (
            ("html", "yellow"),
            ("css", "orange"),
            ("js", "purple"),
            ("Image", "green"),
            ("json", "darkblue"),
            ("User data", "blue"),
            ("Other", "white"),
            ("Total", "black")
        )
        # Collect stats
        size_filetypes = {}
        size_total = 0
        contents = site.content_manager.listContents()  # Without user files
        for inner_path in contents:
            content = site.content_manager.contents[inner_path]
            if "files" not in content:
                continue
            for file_name, file_details in content["files"].items():
                size_total += file_details["size"]
                ext = file_name.split(".")[-1]
                size_filetypes[ext] = size_filetypes.get(ext, 0) + file_details["size"]

        # Get user file sizes
        size_user_content = site.content_manager.contents.execute(
            "SELECT SUM(size) + SUM(size_files) AS size FROM content WHERE ?",
            {"not__inner_path": contents}
        ).fetchone()["size"]
        if not size_user_content:
            size_user_content = 0
        size_filetypes["User data"] = size_user_content
        size_total += size_user_content

        # The missing difference is content.json sizes
        if "json" in size_filetypes:
            size_filetypes["json"] += max(0, site.settings["size"] - size_total)
        size_total = size_other = site.settings["size"]

        # Bar
        for extension, color in extensions:
            if extension == "Total":
                continue
            if extension == "Other":
                size = max(0, size_other)
            elif extension == "Image":
                size = size_filetypes.get("jpg", 0) + size_filetypes.get("png", 0) + size_filetypes.get("gif", 0)
                size_other -= size
            else:
                size = size_filetypes.get(extension, 0)
                size_other -= size
            if size_total == 0:
                percent = 0
            else:
                percent = 100 * (float(size) / size_total)
            percent = math.floor(percent * 100) / 100  # Floor to 2 digits
            body.append(
                u"""<li style='width: %.2f%%' class='%s back-%s' title="%s"></li>""" %
                (percent, _[extension], color, _[extension])
            )

        # Legend
        body.append("</ul><ul class='graph-legend'>")
        for extension, color in extensions:
            if extension == "Other":
                size = max(0, size_other)
            elif extension == "Image":
                size = size_filetypes.get("jpg", 0) + size_filetypes.get("png", 0) + size_filetypes.get("gif", 0)
            elif extension == "Total":
                size = size_total
            else:
                size = size_filetypes.get(extension, 0)

            if extension == "js":
                title = "javascript"
            else:
                title = extension

            if size > 1024 * 1024 * 10:  # Format as mB is more than 10mB
                size_formatted = "%.0fMB" % (size / 1024 / 1024)
            else:
                size_formatted = "%.0fkB" % (size / 1024)

            body.append(u"<li class='color-%s'><span>%s:</span><b>%s</b></li>" % (color, _[title], size_formatted))

        body.append("</ul></li>")

    def sidebarRenderSizeLimit(self, body, site):
        free_space = helper.getFreeSpace() / 1024 / 1024
        size = float(site.settings["size"]) / 1024 / 1024
        size_limit = site.getSizeLimit()
        percent_used = size / size_limit

        body.append(_(u"""
            <li>
             <label>{_[Size limit]} <small>({_[limit used]}: {percent_used:.0%}, {_[free space]}: {free_space:,d}MB)</small></label>
             <input type='text' class='text text-num' value="{size_limit}" id='input-sitelimit'/><span class='text-post'>MB</span>
             <a href='#Set' class='button' id='button-sitelimit'>{_[Set]}</a>
            </li>
        """))

    def sidebarRenderOptionalFileStats(self, body, site):
        size_total = float(site.settings["size_optional"])
        size_downloaded = float(site.settings["optional_downloaded"])

        if not size_total:
            return False

        percent_downloaded = size_downloaded / size_total

        size_formatted_total = size_total / 1024 / 1024
        size_formatted_downloaded = size_downloaded / 1024 / 1024

        body.append(_(u"""
            <li>
             <label>{_[Optional files]}</label>
             <ul class='graph'>
              <li style='width: 100%' class='total back-black' title="{_[Total size]}"></li>
              <li style='width: {percent_downloaded:.0%}' class='connected back-green' title='{_[Downloaded files]}'></li>
             </ul>
             <ul class='graph-legend'>
              <li class='color-green'><span>{_[Downloaded]}:</span><b>{size_formatted_downloaded:.2f}MB</b></li>
              <li class='color-black'><span>{_[Total]}:</span><b>{size_formatted_total:.2f}MB</b></li>
             </ul>
            </li>
        """))

        return True

    def sidebarRenderOptionalFileSettings(self, body, site):
        if self.site.settings.get("autodownloadoptional"):
            checked = "checked='checked'"
        else:
            checked = ""

        body.append(_(u"""
            <li>
             <label>{_[Download and help distribute all files]}</label>
             <input type="checkbox" class="checkbox" id="checkbox-autodownloadoptional" {checked}/><div class="checkbox-skin"></div>
            </li>
        """))

    def sidebarRenderBadFiles(self, body, site):
        body.append(_(u"""
            <li>
             <label>{_[Missing files]}:</label>
             <ul class='filelist'>
        """))

        i = 0
        for bad_file, tries in site.bad_files.iteritems():
            i += 1
            body.append(_(u"""<li class='color-red' title="{bad_file} ({tries})">{bad_file}</li>""", {
                "bad_file": cgi.escape(bad_file, True), "tries": _.pluralize(tries, "{} try", "{} tries")
            }))
            if i > 30:
                break

        if len(site.bad_files) > 30:
            num_bad_files = len(site.bad_files) - 30
            body.append(_(u"""<li class='color-red'>{_[+ {num_bad_files} more]}</li>""", nested=True))

        body.append("""
             </ul>
            </li>
        """)

    def sidebarRenderDbOptions(self, body, site):
        if site.storage.db:
            inner_path = site.storage.getInnerPath(site.storage.db.db_path)
            size = float(site.storage.getSize(inner_path)) / 1024
            feeds = len(site.storage.db.schema.get("feeds", {}))
        else:
            inner_path = _[u"No database found"]
            size = 0.0
            feeds = 0

        body.append(_(u"""
            <li>
             <label>{_[Database]} <small>({size:.2f}kB, {_[search feeds]}: {_[{feeds} query]})</small></label>
             <div class='flex'>
              <input type='text' class='text disabled' value="{inner_path}" disabled='disabled'/>
              <a href='#Reload' id="button-dbreload" class='button'>{_[Reload]}</a>
              <a href='#Rebuild' id="button-dbrebuild" class='button'>{_[Rebuild]}</a>
             </div>
            </li>
        """, nested=True))

    def sidebarRenderIdentity(self, body, site):
        auth_address = self.user.getAuthAddress(self.site.address)
        rules = self.site.content_manager.getRules("data/users/%s/content.json" % auth_address)
        if rules and rules.get("max_size"):
            quota = rules["max_size"] / 1024
            try:
                content = site.content_manager.contents["data/users/%s/content.json" % auth_address]
                used = len(json.dumps(content)) + sum([file["size"] for file in content["files"].values()])
            except:
                used = 0
            used = used / 1024
        else:
            quota = used = 0

        body.append(_(u"""
            <li>
             <label>{_[Identity address]} <small>({_[limit used]}: {used:.2f}kB / {quota:.2f}kB)</small></label>
             <div class='flex'>
              <span class='input text disabled'>{auth_address}</span>
              <a href='#Change' class='button' id='button-identity'>{_[Change]}</a>
             </div>
            </li>
        """))

    def sidebarRenderControls(self, body, site):
        auth_address = self.user.getAuthAddress(self.site.address)
        if self.site.settings["serving"]:
            class_pause = ""
            class_resume = "hidden"
        else:
            class_pause = "hidden"
            class_resume = ""

        body.append(_(u"""
            <li>
             <label>{_[Site control]}</label>
             <a href='#Update' class='button noupdate' id='button-update'>{_[Update]}</a>
             <a href='#Pause' class='button {class_pause}' id='button-pause'>{_[Pause]}</a>
             <a href='#Resume' class='button {class_resume}' id='button-resume'>{_[Resume]}</a>
             <a href='#Delete' class='button noupdate' id='button-delete'>{_[Delete]}</a>
            </li>
        """))

        site_address = self.site.address
        body.append(_(u"""
            <li>
             <label>{_[Site address]}</label><br>
             <div class='flex'>
              <span class='input text disabled'>{site_address}</span>
              <a href='bitcoin:{site_address}' class='button' id='button-donate'>{_[Donate]}</a>
             </div>
            </li>
        """))

    def sidebarRenderOwnedCheckbox(self, body, site):
        if self.site.settings["own"]:
            checked = "checked='checked'"
        else:
            checked = ""

        body.append(_(u"""
            <h2 class='owned-title'>{_[This is my site]}</h2>
            <input type="checkbox" class="checkbox" id="checkbox-owned" {checked}/><div class="checkbox-skin"></div>
        """))

    def sidebarRenderOwnSettings(self, body, site):
        title = cgi.escape(site.content_manager.contents.get("content.json", {}).get("title", ""), True)
        description = cgi.escape(site.content_manager.contents.get("content.json", {}).get("description", ""), True)
        privatekey = cgi.escape(self.user.getSiteData(site.address, create=False).get("privatekey", ""))

        body.append(_(u"""
            <li>
             <label for='settings-title'>{_[Site title]}</label>
             <input type='text' class='text' value="{title}" id='settings-title'/>
            </li>

            <li>
             <label for='settings-description'>{_[Site description]}</label>
             <input type='text' class='text' value="{description}" id='settings-description'/>
            </li>

            <li style='display: none'>
             <label>{_[Private key]}</label>
             <input type='text' class='text long' value="{privatekey}" placeholder='{_[Ask when signing]}'/>
            </li>

            <li>
             <a href='#Save' class='button' id='button-settings'>{_[Save site settings]}</a>
            </li>
        """))

    def sidebarRenderContents(self, body, site):
        body.append(_(u"""
            <li>
             <label>{_[Content publishing]}</label>
        """))

        # Choose content you want to sign
        contents = ["content.json"]
        contents += site.content_manager.contents.get("content.json", {}).get("includes", {}).keys()
        body.append(_(u"<div class='contents'>{_[Choose]}: "))
        for content in contents:
            content = cgi.escape(content, True)
            body.append(_("<a href='#{content}' onclick='$(\"#input-contents\").val(\"{content}\"); return false'>{content}</a> "))
        body.append("</div>")

        body.append(_(u"""
             <div class='flex'>
              <input type='text' class='text' value="content.json" id='input-contents'/>
              <a href='#Sign' class='button' id='button-sign'>{_[Sign]}</a>
              <a href='#Publish' class='button' id='button-publish'>{_[Publish]}</a>
             </div>
            </li>
        """))

    def actionSidebarGetHtmlTag(self, to):
        site = self.site

        body = []

        body.append("<div>")
        body.append("<h1>%s</h1>" % cgi.escape(site.content_manager.contents.get("content.json", {}).get("title", ""), True))

        body.append("<div class='globe loading'></div>")

        body.append("<ul class='fields'>")

        self.sidebarRenderPeerStats(body, site)
        self.sidebarRenderTransferStats(body, site)
        self.sidebarRenderFileStats(body, site)
        self.sidebarRenderSizeLimit(body, site)
        has_optional = self.sidebarRenderOptionalFileStats(body, site)
        if has_optional:
            self.sidebarRenderOptionalFileSettings(body, site)
        self.sidebarRenderDbOptions(body, site)
        self.sidebarRenderIdentity(body, site)
        self.sidebarRenderControls(body, site)
        if site.bad_files:
            self.sidebarRenderBadFiles(body, site)

        self.sidebarRenderOwnedCheckbox(body, site)
        body.append("<div class='settings-owned'>")
        self.sidebarRenderOwnSettings(body, site)
        self.sidebarRenderContents(body, site)
        body.append("</div>")
        body.append("</ul>")
        body.append("</div>")

        self.response(to, "".join(body))

    def downloadGeoLiteDb(self, db_path):
        import urllib
        import gzip
        import shutil
        from util import helper

        self.log.info("Downloading GeoLite2 City database...")
        self.cmd("notification", ["geolite-info", _["Downloading GeoLite2 City database (one time only, ~20MB)..."], 0])
        db_urls = [
            "https://geolite.maxmind.com/download/geoip/database/GeoLite2-City.mmdb.gz",
            "https://raw.githubusercontent.com/texnikru/GeoLite2-Database/master/GeoLite2-City.mmdb.gz"
        ]
        for db_url in db_urls:
            try:
                # Download
                response = helper.httpRequest(db_url)

                data = StringIO.StringIO()
                while True:
                    buff = response.read(1024 * 512)
                    if not buff:
                        break
                    data.write(buff)
                self.log.info("GeoLite2 City database downloaded (%s bytes), unpacking..." % data.tell())
                data.seek(0)

                # Unpack
                with gzip.GzipFile(fileobj=data) as gzip_file:
                    shutil.copyfileobj(gzip_file, open(db_path, "wb"))

                self.cmd("notification", ["geolite-done", _["GeoLite2 City database downloaded!"], 5000])
                time.sleep(2)  # Wait for notify animation
                return True
            except Exception, err:
                self.log.error("Error downloading %s: %s" % (db_url, err))
                pass
        self.cmd("notification", [
            "geolite-error",
            _["GeoLite2 City database download error: {}!<br>Please download manually and unpack to data dir:<br>{}"].format(err, db_urls[0]),
            0
        ])

    def actionSidebarGetPeers(self, to):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")
        try:
            import maxminddb
            db_path = config.data_dir + '/GeoLite2-City.mmdb'
            if not os.path.isfile(db_path) or os.path.getsize(db_path) == 0:
                if not self.downloadGeoLiteDb(db_path):
                    return False
            geodb = maxminddb.open_database(db_path)

            peers = self.site.peers.values()
            # Find avg ping
            ping_times = [
                peer.connection.last_ping_delay
                for peer in peers
                if peer.connection and peer.connection.last_ping_delay and peer.connection.last_ping_delay
            ]
            if ping_times:
                ping_avg = sum(ping_times) / float(len(ping_times))
            else:
                ping_avg = 0
            # Place bars
            globe_data = []
            placed = {}  # Already placed bars here
            for peer in peers:
                # Height of bar
                if peer.connection and peer.connection.last_ping_delay:
                    ping = min(0.20, math.log(1 + peer.connection.last_ping_delay / ping_avg, 300))
                else:
                    ping = -0.03

                # Query and cache location
                if peer.ip in loc_cache:
                    loc = loc_cache[peer.ip]
                else:
                    try:
                        loc = geodb.get(peer.ip)
                    except:
                        loc = None
                    loc_cache[peer.ip] = loc
                if not loc or "location" not in loc:
                    continue

                # Create position array
                lat, lon = (loc["location"]["latitude"], loc["location"]["longitude"])
                latlon = "%s,%s" % (lat, lon)
                if latlon in placed:  # Dont place more than 1 bar to same place, fake repos using ip address last two part
                    lat += float(128 - int(peer.ip.split(".")[-2])) / 50
                    lon += float(128 - int(peer.ip.split(".")[-1])) / 50
                    latlon = "%s,%s" % (lat, lon)
                placed[latlon] = True

                globe_data += (lat, lon, ping)
            # Append myself
            loc = geodb.get(config.ip_external)
            if loc and loc.get("location"):
                lat, lon = (loc["location"]["latitude"], loc["location"]["longitude"])
                globe_data += (lat, lon, -0.135)

            self.response(to, globe_data)
        except Exception, err:
            self.log.debug("sidebarGetPeers error: %s" % Debug.formatException(err))
            self.response(to, {"error": err})

    def actionSiteSetOwned(self, to, owned):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        self.site.settings["own"] = bool(owned)

    def actionSiteSetAutodownloadoptional(self, to, owned):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        self.site.settings["autodownloadoptional"] = bool(owned)
        self.site.bad_files = {}
        gevent.spawn(self.site.update, check_files=True)
        self.site.worker_manager.removeGoodFileTasks()

    def actionDbReload(self, to):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        self.site.storage.closeDb()
        self.site.storage.getDb()

        return self.response(to, "ok")

    def actionDbRebuild(self, to):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        self.site.storage.rebuildDb()

        return self.response(to, "ok")

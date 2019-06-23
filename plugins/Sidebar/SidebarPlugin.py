import re
import os
import html
import sys
import math
import time
import json
import io
import urllib
import urllib.parse

import gevent

from Config import config
from Plugin import PluginManager
from Debug import Debug
from Translate import Translate
from util import helper
from .ZipStream import ZipStream

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
                yield _.translateData(open(plugin_media_file).read()).encode("utf8")
            else:
                for part in self.actionFile(plugin_media_file, send_header=False):
                    yield part
        elif path.startswith("/uimedia/globe/"):  # Serve WebGL globe files
            file_name = re.match(".*/(.*)", path).group(1)
            plugin_media_file = "%s_globe/%s" % (media_dir, file_name)
            if config.debug and path.endswith("all.js"):
                # If debugging merge *.css to all.css and *.js to all.js
                from Debug import DebugMedia
                DebugMedia.merge(plugin_media_file)
            for part in self.actionFile(plugin_media_file):
                yield part
        else:
            for part in super(UiRequestPlugin, self).actionUiMedia(path):
                yield part

    def actionZip(self):
        address = self.get["address"]
        site = self.server.site_manager.get(address)
        if not site:
            return self.error404("Site not found")

        title = site.content_manager.contents.get("content.json", {}).get("title", "")
        filename = "%s-backup-%s.zip" % (title, time.strftime("%Y-%m-%d_%H_%M"))
        filename_quoted = urllib.parse.quote(filename)
        self.sendHeader(content_type="application/zip", extra_headers={'Content-Disposition': 'attachment; filename="%s"' % filename_quoted})

        return self.streamZip(site.storage.getPath("."))

    def streamZip(self, dir_path):
        zs = ZipStream(dir_path)
        while 1:
            data = zs.read()
            if not data:
                break
            yield data


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def __init__(self, *args, **kwargs):
        self.async_commands.add("sidebarGetPeers")
        return super(UiWebsocketPlugin, self).__init__(*args, **kwargs)

    def sidebarRenderPeerStats(self, body, site):
        connected = len([peer for peer in list(site.peers.values()) if peer.connection and peer.connection.connected])
        connectable = len([peer_id for peer_id in list(site.peers.keys()) if not peer_id.endswith(":0")])
        onion = len([peer_id for peer_id in list(site.peers.keys()) if ".onion" in peer_id])
        local = len([peer for peer in list(site.peers.values()) if helper.isPrivateIp(peer.ip)])
        peers_total = len(site.peers)

        # Add myself
        if site.isServing():
            peers_total += 1
            if any(site.connection_server.port_opened.values()):
                connectable += 1
            if site.connection_server.tor_manager.start_onions:
                onion += 1

        if peers_total:
            percent_connected = float(connected) / peers_total
            percent_connectable = float(connectable) / peers_total
            percent_onion = float(onion) / peers_total
        else:
            percent_connectable = percent_connected = percent_onion = 0

        if local:
            local_html = _("<li class='color-yellow'><span>{_[Local]}:</span><b>{local}</b></li>")
        else:
            local_html = ""

        peer_ips = [peer.key for peer in site.getConnectablePeers(20, allow_private=False)]
        peer_ips.sort(key=lambda peer_ip: ".onion:" in peer_ip)
        copy_link = "http://127.0.0.1:43110/%s/?zeronet_peers=%s" % (
            site.content_manager.contents["content.json"].get("domain", site.address),
            ",".join(peer_ips)
        )

        body.append(_("""
            <li>
             <label>
              {_[Peers]}
              <small class="label-right"><a href='{copy_link}' id='link-copypeers' class='link-right'>{_[Copy to clipboard]}</a></small>
             </label>
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
              {local_html}
              <li class='color-black'><span>{_[Total]}:</span><b>{peers_total}</b></li>
             </ul>
            </li>
        """.replace("{local_html}", local_html)))

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

        body.append(_("""
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
        body.append(_("""
            <li>
             <label>
              {_[Files]}
              <small class="label-right"><a href='#Site+directory' id='link-directory' class='link-right'>{_[Open site directory]}</a>
              <a href='/ZeroNet-Internal/Zip?address={site.address}' id='link-zip' class='link-right' download='site.zip'>{_[Save as .zip]}</a></small>
             </label>
             <ul class='graph graph-stacked'>
        """))

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
            if "files" not in content or content["files"] is None:
                continue
            for file_name, file_details in list(content["files"].items()):
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
                """<li style='width: %.2f%%' class='%s back-%s' title="%s"></li>""" %
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

            body.append("<li class='color-%s'><span>%s:</span><b>%s</b></li>" % (color, _[title], size_formatted))

        body.append("</ul></li>")

    def sidebarRenderSizeLimit(self, body, site):
        free_space = helper.getFreeSpace() / 1024 / 1024
        size = float(site.settings["size"]) / 1024 / 1024
        size_limit = site.getSizeLimit()
        percent_used = size / size_limit

        body.append(_("""
            <li>
             <label>{_[Size limit]} <small>({_[limit used]}: {percent_used:.0%}, {_[free space]}: {free_space:,.0f}MB)</small></label>
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

        body.append(_("""
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

        body.append(_("""
            <li>
             <label>{_[Download and help distribute all files]}</label>
             <input type="checkbox" class="checkbox" id="checkbox-autodownloadoptional" {checked}/><div class="checkbox-skin"></div>
        """))

        autodownload_bigfile_size_limit = int(site.settings.get("autodownload_bigfile_size_limit", config.autodownload_bigfile_size_limit))
        body.append(_("""
            <div class='settings-autodownloadoptional'>
             <label>{_[Auto download big file size limit]}</label>
             <input type='text' class='text text-num' value="{autodownload_bigfile_size_limit}" id='input-autodownload_bigfile_size_limit'/><span class='text-post'>MB</span>
             <a href='#Set' class='button' id='button-autodownload_bigfile_size_limit'>{_[Set]}</a>
            </div>
        """))
        body.append("</li>")

    def sidebarRenderBadFiles(self, body, site):
        body.append(_("""
            <li>
             <label>{_[Needs to be updated]}:</label>
             <ul class='filelist'>
        """))

        i = 0
        for bad_file, tries in site.bad_files.items():
            i += 1
            body.append(_("""<li class='color-red' title="{bad_file_path} ({tries})">{bad_filename}</li>""", {
                "bad_file_path": bad_file,
                "bad_filename": helper.getFilename(bad_file),
                "tries": _.pluralize(tries, "{} try", "{} tries")
            }))
            if i > 30:
                break

        if len(site.bad_files) > 30:
            num_bad_files = len(site.bad_files) - 30
            body.append(_("""<li class='color-red'>{_[+ {num_bad_files} more]}</li>""", nested=True))

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
            inner_path = _["No database found"]
            size = 0.0
            feeds = 0

        body.append(_("""
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
        auth_address = self.user.getAuthAddress(self.site.address, create=False)
        rules = self.site.content_manager.getRules("data/users/%s/content.json" % auth_address)
        if rules and rules.get("max_size"):
            quota = rules["max_size"] / 1024
            try:
                content = site.content_manager.contents["data/users/%s/content.json" % auth_address]
                used = len(json.dumps(content)) + sum([file["size"] for file in list(content["files"].values())])
            except:
                used = 0
            used = used / 1024
        else:
            quota = used = 0

        body.append(_("""
            <li>
             <label>{_[Identity address]} <small>({_[limit used]}: {used:.2f}kB / {quota:.2f}kB)</small></label>
             <div class='flex'>
              <span class='input text disabled'>{auth_address}</span>
              <a href='#Change' class='button' id='button-identity'>{_[Change]}</a>
             </div>
            </li>
        """))

    def sidebarRenderControls(self, body, site):
        auth_address = self.user.getAuthAddress(self.site.address, create=False)
        if self.site.settings["serving"]:
            class_pause = ""
            class_resume = "hidden"
        else:
            class_pause = "hidden"
            class_resume = ""

        body.append(_("""
            <li>
             <label>{_[Site control]}</label>
             <a href='#Update' class='button noupdate' id='button-update'>{_[Update]}</a>
             <a href='#Pause' class='button {class_pause}' id='button-pause'>{_[Pause]}</a>
             <a href='#Resume' class='button {class_resume}' id='button-resume'>{_[Resume]}</a>
             <a href='#Delete' class='button noupdate' id='button-delete'>{_[Delete]}</a>
            </li>
        """))

        donate_key = site.content_manager.contents.get("content.json", {}).get("donate", True)
        site_address = self.site.address
        body.append(_("""
            <li>
             <label>{_[Site address]}</label><br>
             <div class='flex'>
              <span class='input text disabled'>{site_address}</span>
        """))
        if donate_key == False or donate_key == "":
            pass
        elif (type(donate_key) == str or type(donate_key) == str) and len(donate_key) > 0:
            body.append(_("""
             </div>
            </li>
            <li>
             <label>{_[Donate]}</label><br>
             <div class='flex'>
             {donate_key}
            """))
        else:
            body.append(_("""
              <a href='bitcoin:{site_address}' class='button' id='button-donate'>{_[Donate]}</a>
            """))
        body.append(_("""
             </div>
            </li>
        """))

    def sidebarRenderOwnedCheckbox(self, body, site):
        if self.site.settings["own"]:
            checked = "checked='checked'"
        else:
            checked = ""

        body.append(_("""
            <h2 class='owned-title'>{_[This is my site]}</h2>
            <input type="checkbox" class="checkbox" id="checkbox-owned" {checked}/><div class="checkbox-skin"></div>
        """))

    def sidebarRenderOwnSettings(self, body, site):
        title = site.content_manager.contents.get("content.json", {}).get("title", "")
        description = site.content_manager.contents.get("content.json", {}).get("description", "")

        body.append(_("""
            <li>
             <label for='settings-title'>{_[Site title]}</label>
             <input type='text' class='text' value="{title}" id='settings-title'/>
            </li>

            <li>
             <label for='settings-description'>{_[Site description]}</label>
             <input type='text' class='text' value="{description}" id='settings-description'/>
            </li>

            <li>
             <a href='#Save' class='button' id='button-settings'>{_[Save site settings]}</a>
            </li>
        """))

    def sidebarRenderContents(self, body, site):
        has_privatekey = bool(self.user.getSiteData(site.address, create=False).get("privatekey"))
        if has_privatekey:
            tag_privatekey = _("{_[Private key saved.]} <a href='#Forgot+private+key' id='privatekey-forgot' class='link-right'>{_[Forgot]}</a>")
        else:
            tag_privatekey = _("<a href='#Add+private+key' id='privatekey-add' class='link-right'>{_[Add saved private key]}</a>")

        body.append(_("""
            <li>
             <label>{_[Content publishing]} <small class='label-right'>{tag_privatekey}</small></label>
        """.replace("{tag_privatekey}", tag_privatekey)))

        # Choose content you want to sign
        body.append(_("""
             <div class='flex'>
              <input type='text' class='text' value="content.json" id='input-contents'/>
              <a href='#Sign-and-Publish' id='button-sign-publish' class='button'>{_[Sign and publish]}</a>
              <a href='#Sign-or-Publish' id='menu-sign-publish'>\u22EE</a>
             </div>
        """))

        contents = ["content.json"]
        contents += list(site.content_manager.contents.get("content.json", {}).get("includes", {}).keys())
        body.append(_("<div class='contents'>{_[Choose]}: "))
        for content in contents:
            body.append(_("<a href='{content}' class='contents-content'>{content}</a> "))
        body.append("</div>")
        body.append("</li>")

    def actionSidebarGetHtmlTag(self, to):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        site = self.site

        body = []

        body.append("<div>")
        body.append("<a href='#Close' class='close'>&times;</a>")
        body.append("<h1>%s</h1>" % html.escape(site.content_manager.contents.get("content.json", {}).get("title", ""), True))

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

        body.append("<div class='menu template'>")
        body.append("<a href='#'' class='menu-item template'>Template</a>")
        body.append("</div>")

        self.response(to, "".join(body))

    def downloadGeoLiteDb(self, db_path):
        import gzip
        import shutil
        from util import helper

        if config.offline:
            return False

        self.log.info("Downloading GeoLite2 City database...")
        self.cmd("progress", ["geolite-info", _["Downloading GeoLite2 City database (one time only, ~20MB)..."], 0])
        db_urls = [
            "https://geolite.maxmind.com/download/geoip/database/GeoLite2-City.mmdb.gz",
            "https://raw.githubusercontent.com/texnikru/GeoLite2-Database/master/GeoLite2-City.mmdb.gz"
        ]
        for db_url in db_urls:
            downloadl_err = None
            try:
                # Download
                response = helper.httpRequest(db_url)
                data_size = response.getheader('content-length')
                data_recv = 0
                data = io.BytesIO()
                while True:
                    buff = response.read(1024 * 512)
                    if not buff:
                        break
                    data.write(buff)
                    data_recv += 1024 * 512
                    if data_size:
                        progress = int(float(data_recv) / int(data_size) * 100)
                        self.cmd("progress", ["geolite-info", _["Downloading GeoLite2 City database (one time only, ~20MB)..."], progress])
                self.log.info("GeoLite2 City database downloaded (%s bytes), unpacking..." % data.tell())
                data.seek(0)

                # Unpack
                with gzip.GzipFile(fileobj=data) as gzip_file:
                    shutil.copyfileobj(gzip_file, open(db_path, "wb"))

                self.cmd("progress", ["geolite-info", _["GeoLite2 City database downloaded!"], 100])
                time.sleep(2)  # Wait for notify animation
                self.log.info("GeoLite2 City database is ready at: %s" % db_path)
                return True
            except Exception as err:
                download_err = err
                self.log.error("Error downloading %s: %s" % (db_url, err))
                pass
        self.cmd("progress", [
            "geolite-info",
            _["GeoLite2 City database download error: {}!<br>Please download manually and unpack to data dir:<br>{}"].format(download_err, db_urls[0]),
            -100
        ])

    def getLoc(self, geodb, ip):
        global loc_cache

        if ip in loc_cache:
            return loc_cache[ip]
        else:
            try:
                loc_data = geodb.get(ip)
            except:
                loc_data = None

            if not loc_data or "location" not in loc_data:
                loc_cache[ip] = None
                return None

            loc = {
                "lat": loc_data["location"]["latitude"],
                "lon": loc_data["location"]["longitude"],
            }
            if "city" in loc_data:
                loc["city"] = loc_data["city"]["names"]["en"]

            if "country" in loc_data:
                loc["country"] = loc_data["country"]["names"]["en"]

            loc_cache[ip] = loc
            return loc

    def getGeoipDb(self):
        db_name = 'GeoLite2-City.mmdb'

        sys_db_paths = []
        if sys.platform == "linux":
            sys_db_paths += ['/usr/share/GeoIP/' + db_name]

        data_dir_db_path = os.path.join(config.data_dir, db_name)

        db_paths = sys_db_paths + [data_dir_db_path]

        for path in db_paths:
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                return path

        self.log.info("GeoIP database not found at [%s]. Downloading to: %s",
                " ".join(db_paths), data_dir_db_path)
        if self.downloadGeoLiteDb(data_dir_db_path):
            return data_dir_db_path
        return None

    def getPeerLocations(self, peers):
        import maxminddb

        db_path = self.getGeoipDb()
        if not db_path:
            self.log.debug("Not showing peer locations: no GeoIP database")
            return False

        self.log.info("Loading GeoIP database from: %s" % db_path)
        geodb = maxminddb.open_database(db_path)

        peers = list(peers.values())
        # Place bars
        peer_locations = []
        placed = {}  # Already placed bars here
        for peer in peers:
            # Height of bar
            if peer.connection and peer.connection.last_ping_delay:
                ping = round(peer.connection.last_ping_delay * 1000)
            else:
                ping = None
            loc = self.getLoc(geodb, peer.ip)

            if not loc:
                continue
            # Create position array
            lat, lon = loc["lat"], loc["lon"]
            latlon = "%s,%s" % (lat, lon)
            if latlon in placed and helper.getIpType(peer.ip) == "ipv4":  # Dont place more than 1 bar to same place, fake repos using ip address last two part
                lat += float(128 - int(peer.ip.split(".")[-2])) / 50
                lon += float(128 - int(peer.ip.split(".")[-1])) / 50
                latlon = "%s,%s" % (lat, lon)
            placed[latlon] = True
            peer_location = {}
            peer_location.update(loc)
            peer_location["lat"] = lat
            peer_location["lon"] = lon
            peer_location["ping"] = ping

            peer_locations.append(peer_location)

        # Append myself
        for ip in self.site.connection_server.ip_external_list:
            my_loc = self.getLoc(geodb, ip)
            if my_loc:
                my_loc["ping"] = 0
                peer_locations.append(my_loc)

        return peer_locations


    def actionSidebarGetPeers(self, to):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")
        try:
            peer_locations = self.getPeerLocations(self.site.peers)
            globe_data = []
            ping_times = [
                peer_location["ping"]
                for peer_location in peer_locations
                if peer_location["ping"]
            ]
            if ping_times:
                ping_avg = sum(ping_times) / float(len(ping_times))
            else:
                ping_avg = 0

            for peer_location in peer_locations:
                if peer_location["ping"] == 0:  # Me
                    height = -0.135
                elif peer_location["ping"]:
                    height = min(0.20, math.log(1 + peer_location["ping"] / ping_avg, 300))
                else:
                    height = -0.03

                globe_data += [peer_location["lat"], peer_location["lon"], height]

            self.response(to, globe_data)
        except Exception as err:
            self.log.debug("sidebarGetPeers error: %s" % Debug.formatException(err))
            self.response(to, {"error": str(err)})

    def actionSiteSetOwned(self, to, owned):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        if self.site.address == config.updatesite:
            return self.response(to, "You can't change the ownership of the updater site")

        self.site.settings["own"] = bool(owned)
        self.site.updateWebsocket(owned=owned)

    def actionUserSetSitePrivatekey(self, to, privatekey):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        site_data = self.user.sites[self.site.address]
        site_data["privatekey"] = privatekey
        self.site.updateWebsocket(set_privatekey=bool(privatekey))

        return "ok"

    def actionSiteSetAutodownloadoptional(self, to, owned):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        self.site.settings["autodownloadoptional"] = bool(owned)
        self.site.bad_files = {}
        gevent.spawn(self.site.update, check_files=True)
        self.site.worker_manager.removeSolvedFileTasks()

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

        try:
            self.site.storage.rebuildDb()
        except Exception as err:
            return self.response(to, {"error": str(err)})


        return self.response(to, "ok")

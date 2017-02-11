import json
import time
import sys
import hashlib
import os
import shutil
import re

import gevent

from Config import config
from Site import SiteManager
from Debug import Debug
from util import QueryJson, RateLimit
from Plugin import PluginManager
from Translate import translate as _


@PluginManager.acceptPlugins
class UiWebsocket(object):

    def __init__(self, ws, site, server, user, request):
        self.ws = ws
        self.site = site
        self.user = user
        self.log = site.log
        self.request = request
        self.permissions = []
        self.server = server
        self.next_message_id = 1
        self.waiting_cb = {}  # Waiting for callback. Key: message_id, Value: function pointer
        self.channels = []  # Channels joined to
        self.sending = False  # Currently sending to client
        self.send_queue = []  # Messages to send to client
        self.admin_commands = (
            "sitePause", "siteResume", "siteDelete", "siteList", "siteSetLimit", "siteClone",
            "channelJoinAllsite", "serverUpdate", "serverPortcheck", "serverShutdown", "certSet", "configSet",
            "actionPermissionAdd", "actionPermissionRemove"
        )
        self.async_commands = ("fileGet", "fileList")

    # Start listener loop
    def start(self):
        ws = self.ws
        if self.site.address == config.homepage and not self.site.page_requested:
            # Add open fileserver port message or closed port error to homepage at first request after start
            self.site.page_requested = True  # Dont add connection notification anymore
            file_server = sys.modules["main"].file_server
            if file_server.port_opened is None or file_server.tor_manager.start_onions is None:
                self.site.page_requested = False  # Not ready yet, check next time
            elif file_server.port_opened is True:
                self.site.notifications.append([
                    "done",
                    _["Congratulation, your port <b>{0}</b> is opened.<br>You are full member of ZeroNet network!"].format(config.fileserver_port),
                    10000
                ])
            elif config.tor == "always" and file_server.tor_manager.start_onions:
                self.site.notifications.append([
                    "done",
                    _(u"""
                    {_[Tor mode active, every connection using Onion route.]}<br>
                    {_[Successfully started Tor onion hidden services.]}
                    """),
                    10000
                ])
            elif config.tor == "always" and file_server.tor_manager.start_onions is not False:
                self.site.notifications.append([
                    "error",
                    _(u"""
                    {_[Tor mode active, every connection using Onion route.]}<br>
                    {_[Unable to start hidden services, please check your config.]}
                    """),
                    0
                ])
            elif file_server.port_opened is False and file_server.tor_manager.start_onions:
                self.site.notifications.append([
                    "done",
                    _(u"""
                    {_[Successfully started Tor onion hidden services.]}<br>
                    {_[For faster connections open <b>{0}</b> port on your router.]}
                    """).format(config.fileserver_port),
                    10000
                ])
            else:
                self.site.notifications.append([
                    "error",
                    _(u"""
                    {_[Your connection is restricted. Please, open <b>{0}</b> port on your router]}<br>
                    {_[or configure Tor to become full member of ZeroNet network.]}
                    """).format(config.fileserver_port),
                    0
                ])

        for notification in self.site.notifications:  # Send pending notification messages
            self.cmd("notification", notification)
        self.site.notifications = []
        while True:
            try:
                message = ws.receive()
            except Exception, err:
                return "Bye."  # Close connection

            if message:
                try:
                    self.handleRequest(message)
                except Exception, err:
                    if config.debug:  # Allow websocket errors to appear on /Debug
                        sys.modules["main"].DebugHook.handleError()
                    self.log.error("WebSocket handleRequest error: %s" % Debug.formatException(err))
                    self.cmd("error", "Internal error: %s" % Debug.formatException(err, "html"))

    # Has permission to run the command
    def hasCmdPermission(self, cmd):
        cmd = cmd[0].lower() + cmd[1:]

        if cmd in self.admin_commands and "ADMIN" not in self.permissions:
            return False
        else:
            return True

    # Has permission to access a site
    def hasSitePermission(self, address):
        if address != self.site.address and "ADMIN" not in self.site.settings["permissions"]:
            return False
        else:
            return True

    # Event in a channel
    def event(self, channel, *params):
        if channel in self.channels:  # We are joined to channel
            if channel == "siteChanged":
                site = params[0]  # Triggerer site
                site_info = self.formatSiteInfo(site)
                if len(params) > 1 and params[1]:  # Extra data
                    site_info.update(params[1])
                self.cmd("setSiteInfo", site_info)

    # Send response to client (to = message.id)
    def response(self, to, result):
        self.send({"cmd": "response", "to": to, "result": result})

    # Send a command
    def cmd(self, cmd, params={}, cb=None):
        self.send({"cmd": cmd, "params": params}, cb)

    # Encode to json and send message
    def send(self, message, cb=None):
        message["id"] = self.next_message_id  # Add message id to allow response
        self.next_message_id += 1
        if cb:  # Callback after client responded
            self.waiting_cb[message["id"]] = cb
        if self.sending:
            return  # Already sending
        self.send_queue.append(message)
        try:
            while self.send_queue:
                self.sending = True
                message = self.send_queue.pop(0)
                self.ws.send(json.dumps(message))
                self.sending = False
        except Exception, err:
            self.log.debug("Websocket send error: %s" % Debug.formatException(err))

    def getPermissions(self, req_id):
        permissions = self.site.settings["permissions"]
        if req_id >= 1000000:  # Its a wrapper command, allow admin commands
            permissions = permissions[:]
            permissions.append("ADMIN")
        return permissions

    def asyncWrapper(self, func):
        def asyncErrorWatcher(func, *args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception, err:
                if config.debug:  # Allow websocket errors to appear on /Debug
                    sys.modules["main"].DebugHook.handleError()
                self.log.error("WebSocket handleRequest error: %s" % Debug.formatException(err))
                self.cmd("error", "Internal error: %s" % Debug.formatException(err, "html"))

        def wrapper(*args, **kwargs):
            gevent.spawn(asyncErrorWatcher, func, *args, **kwargs)
        return wrapper

    # Handle incoming messages
    def handleRequest(self, data):
        req = json.loads(data)

        cmd = req.get("cmd")
        params = req.get("params")
        self.permissions = self.getPermissions(req["id"])

        if cmd == "response":  # It's a response to a command
            return self.actionResponse(req["to"], req["result"])
        elif not self.hasCmdPermission(cmd):  # Admin commands
            return self.response(req["id"], {"error": "You don't have permission to run %s" % cmd})
        else:  # Normal command
            func_name = "action" + cmd[0].upper() + cmd[1:]
            func = getattr(self, func_name, None)
            if not func:  # Unknown command
                self.response(req["id"], {"error": "Unknown command: %s" % cmd})
                return

        # Execute in parallel
        if cmd in self.async_commands:
            func = self.asyncWrapper(func)

        # Support calling as named, unnamed parameters and raw first argument too
        if type(params) is dict:
            func(req["id"], **params)
        elif type(params) is list:
            func(req["id"], *params)
        elif params:
            func(req["id"], params)
        else:
            func(req["id"])

    # Format site info
    def formatSiteInfo(self, site, create_user=True):
        content = site.content_manager.contents.get("content.json")
        if content:  # Remove unnecessary data transfer
            content = content.copy()
            content["files"] = len(content.get("files", {}))
            content["files_optional"] = len(content.get("files_optional", {}))
            content["includes"] = len(content.get("includes", {}))
            if "sign" in content:
                del(content["sign"])
            if "signs" in content:
                del(content["signs"])
            if "signers_sign" in content:
                del(content["signers_sign"])

        settings = site.settings.copy()
        del settings["wrapper_key"]  # Dont expose wrapper key
        del settings["auth_key"]  # Dont send auth key twice

        ret = {
            "auth_key": self.site.settings["auth_key"],  # Obsolete, will be removed
            "auth_key_sha512": hashlib.sha512(self.site.settings["auth_key"]).hexdigest()[0:64],  # Obsolete, will be removed
            "auth_address": self.user.getAuthAddress(site.address, create=create_user),
            "cert_user_id": self.user.getCertUserId(site.address),
            "address": site.address,
            "settings": settings,
            "content_updated": site.content_updated,
            "bad_files": len(site.bad_files),
            "size_limit": site.getSizeLimit(),
            "next_size_limit": site.getNextSizeLimit(),
            "peers": max(site.settings.get("peers", 0), len(site.peers)),
            "started_task_num": site.worker_manager.started_task_num,
            "tasks": len(site.worker_manager.tasks),
            "workers": len(site.worker_manager.workers),
            "content": content
        }
        if site.settings["own"]:
            ret["privatekey"] = bool(self.user.getSiteData(site.address, create=create_user).get("privatekey"))
        if site.settings["serving"] and content:
            ret["peers"] += 1  # Add myself if serving
        return ret

    def formatServerInfo(self):
        return {
            "ip_external": sys.modules["main"].file_server.port_opened,
            "platform": sys.platform,
            "fileserver_ip": config.fileserver_ip,
            "fileserver_port": config.fileserver_port,
            "tor_enabled": sys.modules["main"].file_server.tor_manager.enabled,
            "tor_status": sys.modules["main"].file_server.tor_manager.status,
            "ui_ip": config.ui_ip,
            "ui_port": config.ui_port,
            "version": config.version,
            "rev": config.rev,
            "language": config.language,
            "debug": config.debug,
            "plugins": PluginManager.plugin_manager.plugin_names
        }

    # - Actions -

    # Do callback on response {"cmd": "response", "to": message_id, "result": result}
    def actionResponse(self, to, result):
        if to in self.waiting_cb:
            self.waiting_cb[to](result)  # Call callback function
        else:
            self.log.error("Websocket callback not found: %s, %s" % (to, result))

    # Send a simple pong answer
    def actionPing(self, to):
        self.response(to, "pong")

    # Send site details
    def actionSiteInfo(self, to, file_status=None):
        ret = self.formatSiteInfo(self.site)
        if file_status:  # Client queries file status
            if self.site.storage.isFile(file_status):  # File exist, add event done
                ret["event"] = ("file_done", file_status)
        self.response(to, ret)

    # Join to an event channel
    def actionChannelJoin(self, to, channel):
        if channel not in self.channels:
            self.channels.append(channel)

    # Server variables
    def actionServerInfo(self, to):
        ret = self.formatServerInfo()
        self.response(to, ret)

    # Sign content.json
    def actionSiteSign(self, to, privatekey=None, inner_path="content.json", response_ok=True, update_changed_files=False, remove_missing_optional=False):
        self.log.debug("Signing: %s" % inner_path)
        site = self.site
        extend = {}  # Extended info for signing

        # Change to the file's content.json
        file_info = site.content_manager.getFileInfo(inner_path)
        if not inner_path.endswith("content.json"):
            if not file_info:
                raise Exception("Invalid content.json file: %s" % inner_path)
            inner_path = file_info["content_inner_path"]

        # Add certificate to user files
        if file_info and "cert_signers" in file_info and privatekey is None:
            cert = self.user.getCert(self.site.address)
            extend["cert_auth_type"] = cert["auth_type"]
            extend["cert_user_id"] = self.user.getCertUserId(site.address)
            extend["cert_sign"] = cert["cert_sign"]

        if (
            not site.settings["own"] and
            self.user.getAuthAddress(self.site.address) not in self.site.content_manager.getValidSigners(inner_path)
        ):
            return self.response(to, {"error": "Forbidden, you can only modify your own sites"})
        if privatekey == "stored":  # Get privatekey from sites.json
            privatekey = self.user.getSiteData(self.site.address).get("privatekey")
        if not privatekey:  # Get privatekey from users.json auth_address
            privatekey = self.user.getAuthPrivatekey(self.site.address)

        # Signing
        # Reload content.json, ignore errors to make it up-to-date
        site.content_manager.loadContent(inner_path, add_bad_files=False, force=True)
        # Sign using private key sent by user
        signed = site.content_manager.sign(inner_path, privatekey, extend=extend, update_changed_files=update_changed_files, remove_missing_optional=remove_missing_optional)
        if not signed:
            self.cmd("notification", ["error", _["Content signing failed"]])
            self.response(to, {"error": "Site sign failed"})
            return

        site.content_manager.loadContent(inner_path, add_bad_files=False)  # Load new content.json, ignore errors

        if update_changed_files:
            self.site.updateWebsocket(file_done=inner_path)

        if response_ok:
            self.response(to, "ok")

        return inner_path

    # Sign and publish content.json
    def actionSitePublish(self, to, privatekey=None, inner_path="content.json", sign=True):
        if sign:
            inner_path = self.actionSiteSign(to, privatekey, inner_path, response_ok=False)
            if not inner_path:
                return
        # Publishing
        if not self.site.settings["serving"]:  # Enable site if paused
            self.site.settings["serving"] = True
            self.site.saveSettings()
            self.site.announce()

        event_name = "publish %s %s" % (self.site.address, inner_path)
        called_instantly = RateLimit.isAllowed(event_name, 30)
        thread = RateLimit.callAsync(event_name, 30, self.doSitePublish, self.site, inner_path)  # Only publish once in 30 seconds
        notification = "linked" not in dir(thread)  # Only display notification on first callback
        thread.linked = True
        if called_instantly:  # Allowed to call instantly
            # At the end callback with request id and thread
            self.cmd("progress", ["publish", _["Content published to {0}/{1} peers."].format(0, 5), 0])
            thread.link(lambda thread: self.cbSitePublish(to, self.site, thread, notification, callback=notification))
        else:
            self.cmd(
                "notification",
                ["info", _["Content publish queued for {0:.0f} seconds."].format(RateLimit.delayLeft(event_name, 30)), 5000]
            )
            self.response(to, "ok")
            # At the end display notification
            thread.link(lambda thread: self.cbSitePublish(to, self.site, thread, notification, callback=False))

    def doSitePublish(self, site, inner_path):
        def cbProgress(published, limit):
            progress = int(float(published) / limit * 100)
            self.cmd("progress", [
                "publish",
                _["Content published to {0}/{1} peers."].format(published, limit),
                progress
            ])
        diffs = site.content_manager.getDiffs(inner_path)
        back = site.publish(limit=5, inner_path=inner_path, diffs=diffs, cb_progress=cbProgress)
        if back == 0:  # Failed to publish to anyone
            self.cmd("progress", ["publish", _["Content publish failed."], -100])
        else:
            cbProgress(back, back)
        return back

    # Callback of site publish
    def cbSitePublish(self, to, site, thread, notification=True, callback=True):
        published = thread.value
        if published > 0:  # Successfully published
            if notification:
                # self.cmd("notification", ["done", _["Content published to {0} peers."].format(published), 5000])
                site.updateWebsocket()  # Send updated site data to local websocket clients
            if callback:
                self.response(to, "ok")
        else:
            if len(site.peers) == 0:
                if sys.modules["main"].file_server.port_opened or sys.modules["main"].file_server.tor_manager.start_onions:
                    if notification:
                        self.cmd("notification", ["info", _["No peers found, but your content is ready to access."], 5000])
                    if callback:
                        self.response(to, "ok")
                else:
                    if notification:
                        self.cmd("notification", [
                            "info",
                            _("""{_[Your network connection is restricted. Please, open <b>{0}</b> port]}<br>
                            {_[on your router to make your site accessible for everyone.]}""").format(config.fileserver_port)
                        ])
                    if callback:
                        self.response(to, {"error": "Port not opened."})

            else:
                if notification:
                    self.response(to, {"error": "Content publish failed."})

    # Write a file to disk
    def actionFileWrite(self, to, inner_path, content_base64, ignore_bad_files=False):
        valid_signers = self.site.content_manager.getValidSigners(inner_path)
        auth_address = self.user.getAuthAddress(self.site.address)
        if not self.site.settings["own"] and auth_address not in valid_signers:
            self.log.debug("FileWrite forbidden %s not in %s" % (auth_address, valid_signers))
            return self.response(to, {"error": "Forbidden, you can only modify your own files"})

        # Try not to overwrite files currently in sync
        content_inner_path = re.sub("^(.*)/.*?$", "\\1/content.json", inner_path)  # Also check the content.json from same directory
        if (self.site.bad_files.get(inner_path) or self.site.bad_files.get(content_inner_path)) and not ignore_bad_files:
            found = self.site.needFile(inner_path, update=True, priority=10)
            if not found:
                self.cmd(
                    "confirm",
                    [_["This file still in sync, if you write it now, then the previous content may be lost."], _["Write content anyway"]],
                    lambda (res): self.actionFileWrite(to, inner_path, content_base64, ignore_bad_files=True)
                )
                return False

        try:
            import base64
            content = base64.b64decode(content_base64)
            # Save old file to generate patch later
            if (
                inner_path.endswith(".json") and not inner_path.endswith("content.json") and
                self.site.storage.isFile(inner_path) and not self.site.storage.isFile(inner_path + "-old")
            ):
                try:
                    self.site.storage.rename(inner_path, inner_path + "-old")
                except Exception:
                    # Rename failed, fall back to standard file write
                    f_old = self.site.storage.open(inner_path, "rb")
                    f_new = self.site.storage.open(inner_path + "-old", "wb")
                    shutil.copyfileobj(f_old, f_new)

            self.site.storage.write(inner_path, content)
        except Exception, err:
            return self.response(to, {"error": "Write error: %s" % Debug.formatException(err)})

        if inner_path.endswith("content.json"):
            self.site.content_manager.loadContent(inner_path, add_bad_files=False, force=True)

        self.response(to, "ok")

        # Send sitechanged to other local users
        for ws in self.site.websockets:
            if ws != self:
                ws.event("siteChanged", self.site, {"event": ["file_done", inner_path]})

    def actionFileDelete(self, to, inner_path):
        if (
            not self.site.settings["own"] and
            self.user.getAuthAddress(self.site.address) not in self.site.content_manager.getValidSigners(inner_path)
        ):
            return self.response(to, {"error": "Forbidden, you can only modify your own files"})

        file_info = self.site.content_manager.getFileInfo(inner_path)
        if file_info.get("optional"):
            self.log.debug("Deleting optional file: %s" % inner_path)
            relative_path = file_info["relative_path"]
            content_json = self.site.storage.loadJson(file_info["content_inner_path"])
            if relative_path in content_json.get("files_optional", {}):
                del content_json["files_optional"][relative_path]
                self.site.storage.writeJson(file_info["content_inner_path"], content_json)
                self.site.content_manager.loadContent(file_info["content_inner_path"], add_bad_files=False, force=True)

        try:
            self.site.storage.delete(inner_path)
        except Exception, err:
            return self.response(to, {"error": "Delete error: %s" % err})

        self.response(to, "ok")

        # Send sitechanged to other local users
        for ws in self.site.websockets:
            if ws != self:
                ws.event("siteChanged", self.site, {"event": ["file_deleted", inner_path]})

    # Find data in json files
    def actionFileQuery(self, to, dir_inner_path, query):
        # s = time.time()
        dir_path = self.site.storage.getPath(dir_inner_path)
        rows = list(QueryJson.query(dir_path, query))
        # self.log.debug("FileQuery %s %s done in %s" % (dir_inner_path, query, time.time()-s))
        return self.response(to, rows)

    # List files in directory
    def actionFileList(self, to, inner_path):
        return self.response(to, list(self.site.storage.list(inner_path)))

    # Sql query
    def actionDbQuery(self, to, query, params=None, wait_for=None):
        if config.debug:
            s = time.time()
        rows = []
        try:
            if not query.strip().upper().startswith("SELECT"):
                raise Exception("Only SELECT query supported")
            res = self.site.storage.query(query, params)
        except Exception, err:  # Response the error to client
            return self.response(to, {"error": str(err)})
        # Convert result to dict
        for row in res:
            rows.append(dict(row))
        if config.verbose and time.time() - s > 0.1:  # Log slow query
            self.log.debug("Slow query: %s (%.3fs)" % (query, time.time() - s))
        return self.response(to, rows)

    # Return file content
    def actionFileGet(self, to, inner_path, required=True, format="text", timeout=300):
        try:
            if required or inner_path in self.site.bad_files:
                with gevent.Timeout(timeout):
                    self.site.needFile(inner_path, priority=6)
            body = self.site.storage.read(inner_path)
        except Exception, err:
            self.log.debug("%s fileGet error: %s" % (inner_path, err))
            body = None
        if body and format == "base64":
            import base64
            body = base64.b64encode(body)
        return self.response(to, body)

    def actionFileRules(self, to, inner_path):
        rules = self.site.content_manager.getRules(inner_path)
        if inner_path.endswith("content.json") and rules:
            content = self.site.content_manager.contents.get(inner_path)
            if content:
                rules["current_size"] = len(json.dumps(content)) + sum([file["size"] for file in content["files"].values()])
            else:
                rules["current_size"] = 0
        return self.response(to, rules)

    # Add certificate to user
    def actionCertAdd(self, to, domain, auth_type, auth_user_name, cert):
        try:
            res = self.user.addCert(self.user.getAuthAddress(self.site.address), domain, auth_type, auth_user_name, cert)
            if res is True:
                self.cmd(
                    "notification",
                    ["done", _("{_[New certificate added]:} <b>{auth_type}/{auth_user_name}@{domain}</b>.")]
                )
                self.response(to, "ok")
            elif res is False:
                # Display confirmation of change
                cert_current = self.user.certs[domain]
                body = _("{_[Your current certificate]:} <b>{cert_current[auth_type]}/{cert_current[auth_user_name]}@{domain}</b>")
                self.cmd(
                    "confirm",
                    [body, _("Change it to {auth_type}/{auth_user_name}@{domain}")],
                    lambda (res): self.cbCertAddConfirm(to, domain, auth_type, auth_user_name, cert)
                )
            else:
                self.response(to, "Not changed")
        except Exception, err:
            self.response(to, {"error": err.message})

    def cbCertAddConfirm(self, to, domain, auth_type, auth_user_name, cert):
        self.user.deleteCert(domain)
        self.user.addCert(self.user.getAuthAddress(self.site.address), domain, auth_type, auth_user_name, cert)
        self.cmd(
            "notification",
            ["done", _("Certificate changed to: <b>{auth_type}/{auth_user_name}@{domain}</b>.")]
        )
        self.response(to, "ok")

    # Select certificate for site
    def actionCertSelect(self, to, accepted_domains=[], accept_any=False):
        accounts = []
        accounts.append(["", _["Unique to site"], ""])  # Default option
        active = ""  # Make it active if no other option found

        # Add my certs
        auth_address = self.user.getAuthAddress(self.site.address)  # Current auth address
        for domain, cert in self.user.certs.items():
            if auth_address == cert["auth_address"]:
                active = domain
            title = cert["auth_user_name"] + "@" + domain
            if domain in accepted_domains or not accepted_domains or accept_any:
                accounts.append([domain, title, ""])
            else:
                accounts.append([domain, title, "disabled"])

        # Render the html
        body = "<span style='padding-bottom: 5px; display: inline-block'>" + _["Select account you want to use in this site:"] + "</span>"
        # Accounts
        for domain, account, css_class in accounts:
            if domain == active:
                css_class += " active"  # Currently selected option
                title = _(u"<b>%s</b> <small>({_[currently selected]})</small>") % account
            else:
                title = "<b>%s</b>" % account
            body += "<a href='#Select+account' class='select select-close cert %s' title='%s'>%s</a>" % (css_class, domain, title)
        # More available  providers
        more_domains = [domain for domain in accepted_domains if domain not in self.user.certs]  # Domains we not displayed yet
        if more_domains:
            # body+= "<small style='margin-top: 10px; display: block'>Accepted authorization providers by the site:</small>"
            body += "<div style='background-color: #F7F7F7; margin-right: -30px'>"
            for domain in more_domains:
                body += _(u"""
                 <a href='/{domain}' onclick='wrapper.gotoSite(this)' class='select'>
                  <small style='float: right; margin-right: 40px; margin-top: -1px'>{_[Register]} &raquo;</small>{domain}
                 </a>
                """)
            body += "</div>"

        body += """
            <script>
             $(".notification .select.cert").on("click", function() {
                $(".notification .select").removeClass('active')
                wrapper.ws.cmd('certSet', [this.title])
                return false
             })
            </script>
        """

        # Send the notification
        self.cmd("notification", ["ask", body])

    # - Admin actions -

    def actionPermissionAdd(self, to, permission):
        if permission not in self.site.settings["permissions"]:
            self.site.settings["permissions"].append(permission)
            self.site.saveSettings()
            self.site.updateWebsocket(permission_added=permission)
        self.response(to, "ok")

    def actionPermissionRemove(self, to, permission):
        self.site.settings["permissions"].remove(permission)
        self.site.saveSettings()
        self.site.updateWebsocket(permission_removed=permission)
        self.response(to, "ok")

    # Set certificate that used for authenticate user for site
    def actionCertSet(self, to, domain):
        self.user.setCert(self.site.address, domain)
        self.site.updateWebsocket(cert_changed=domain)

    # List all site info
    def actionSiteList(self, to):
        ret = []
        SiteManager.site_manager.load()  # Reload sites
        for site in self.server.sites.values():
            if not site.content_manager.contents.get("content.json"):
                continue  # Broken site
            ret.append(self.formatSiteInfo(site, create_user=False))  # Dont generate the auth_address on listing
        self.response(to, ret)

    # Join to an event channel on all sites
    def actionChannelJoinAllsite(self, to, channel):
        if channel not in self.channels:  # Add channel to channels
            self.channels.append(channel)

        for site in self.server.sites.values():  # Add websocket to every channel
            if self not in site.websockets:
                site.websockets.append(self)

    # Update site content.json
    def actionSiteUpdate(self, to, address, check_files=False, since=None):
        def updateThread():
            site.update(check_files=check_files, since=since)
            self.response(to, "Updated")

        site = self.server.sites.get(address)
        if not site.settings["serving"]:
            site.settings["serving"] = True
            site.saveSettings()
        if site and (site.address == self.site.address or "ADMIN" in self.site.settings["permissions"]):
            gevent.spawn(updateThread)
        else:
            self.response(to, {"error": "Unknown site: %s" % address})

    # Pause site serving
    def actionSitePause(self, to, address):
        site = self.server.sites.get(address)
        if site:
            site.settings["serving"] = False
            site.saveSettings()
            site.updateWebsocket()
            site.worker_manager.stopWorkers()
            self.response(to, "Paused")
        else:
            self.response(to, {"error": "Unknown site: %s" % address})

    # Resume site serving
    def actionSiteResume(self, to, address):
        site = self.server.sites.get(address)
        if site:
            site.settings["serving"] = True
            site.saveSettings()
            gevent.spawn(site.update, announce=True)
            time.sleep(0.001)  # Wait for update thread starting
            site.updateWebsocket()
            self.response(to, "Resumed")
        else:
            self.response(to, {"error": "Unknown site: %s" % address})

    def actionSiteDelete(self, to, address):
        site = self.server.sites.get(address)
        if site:
            site.delete()
            self.user.deleteSiteData(address)
            self.response(to, "Deleted")
            import gc
            gc.collect(2)
        else:
            self.response(to, {"error": "Unknown site: %s" % address})

    def actionSiteClone(self, to, address, root_inner_path=""):
        self.cmd("notification", ["info", _["Cloning site..."]])
        site = self.server.sites.get(address)
        # Generate a new site from user's bip32 seed
        new_address, new_address_index, new_site_data = self.user.getNewSiteData()
        new_site = site.clone(new_address, new_site_data["privatekey"], address_index=new_address_index, root_inner_path=root_inner_path)
        new_site.settings["own"] = True
        new_site.saveSettings()
        self.cmd("notification", ["done", _["Site cloned"] + "<script>window.top.location = '/%s'</script>" % new_address])
        gevent.spawn(new_site.announce)

    def actionSiteSetLimit(self, to, size_limit):
        self.site.settings["size_limit"] = int(size_limit)
        self.site.saveSettings()
        self.response(to, _["Site size limit changed to {0}MB"].format(size_limit))
        self.site.download(blind_includes=True)

    def actionServerUpdate(self, to):
        self.cmd("updating")
        sys.modules["main"].update_after_shutdown = True
        if sys.modules["main"].file_server.tor_manager.tor_process:
            sys.modules["main"].file_server.tor_manager.stopTor()
        SiteManager.site_manager.save()
        sys.modules["main"].file_server.stop()
        sys.modules["main"].ui_server.stop()

    def actionServerPortcheck(self, to):
        sys.modules["main"].file_server.port_opened = None
        res = sys.modules["main"].file_server.openport()
        self.response(to, res)

    def actionServerShutdown(self, to):
        sys.modules["main"].file_server.stop()
        sys.modules["main"].ui_server.stop()

    def actionConfigSet(self, to, key, value):
        if key not in ["tor", "language"]:
            self.response(to, {"error": "Forbidden"})
            return

        config.saveValue(key, value)

        if key == "language":
            import Translate
            for translate in Translate.translates:
                translate.setLanguage(value)
            self.cmd("notification", ["done",
                _["You have successfully changed the web interface's language!"] + "<br>" +
                _["Due to the browser's caching, the full transformation could take some minute."]
            , 10000])
            config.language = value

        self.response(to, "ok")

import json
import time
import sys
import os
import shutil
import re
import copy

import gevent

from Config import config
from Site import SiteManager
from Debug import Debug
from util import QueryJson, RateLimit
from Plugin import PluginManager
from Translate import translate as _
from util import helper
from Content.ContentManager import VerifyError, SignError


@PluginManager.acceptPlugins
class UiWebsocket(object):
    admin_commands = set([
        "sitePause", "siteResume", "siteDelete", "siteList", "siteSetLimit", "siteAdd",
        "channelJoinAllsite", "serverUpdate", "serverPortcheck", "serverShutdown", "serverShowdirectory", "serverGetWrapperNonce",
        "certSet", "configSet", "permissionAdd", "permissionRemove", "announcerStats", "userSetGlobalSettings"
    ])
    async_commands = set(["fileGet", "fileList", "dirList", "fileNeed"])

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
        self.state = {"sending": False}  # Shared state of websocket connection
        self.send_queue = []  # Messages to send to client

    # Start listener loop
    def start(self):
        ws = self.ws
        if self.site.address == config.homepage and not self.site.page_requested:
            # Add open fileserver port message or closed port error to homepage at first request after start
            self.site.page_requested = True  # Dont add connection notification anymore
            file_server = sys.modules["main"].file_server
            if file_server.port_opened is None or file_server.tor_manager.start_onions is None:
                self.site.page_requested = False  # Not ready yet, check next time
            else:
                try:
                    self.addHomepageNotifications()
                except Exception, err:
                    self.log.error("Uncaught Exception: " + Debug.formatException(err))

        for notification in self.site.notifications:  # Send pending notification messages
            # send via WebSocket
            self.cmd("notification", notification)
            # just in case, log them to terminal
            if notification[0] == "error":
                self.log.error("\n*** %s\n" % self.dedent(notification[1]))

        self.site.notifications = []

        while True:
            try:
                if ws.closed:
                    break
                else:
                    message = ws.receive()
            except Exception, err:
                self.log.error("WebSocket receive error: %s" % Debug.formatException(err))
                break

            if message:
                try:
                    req = json.loads(message)
                    self.handleRequest(req)
                except Exception, err:
                    if config.debug:  # Allow websocket errors to appear on /Debug
                        sys.modules["main"].DebugHook.handleError()
                    self.log.error("WebSocket handleRequest error: %s \n %s" % (Debug.formatException(err), message))
                    if not self.hasPlugin("Multiuser"):
                        self.cmd("error", "Internal error: %s" % Debug.formatException(err, "html"))

    def dedent(self, text):
        return re.sub("[\\r\\n\\x20\\t]+", " ", text.strip().replace("<br>", " "))

    def addHomepageNotifications(self):
        if not(self.hasPlugin("Multiuser")) and not(self.hasPlugin("UiPassword")):
            bind_ip = getattr(config, "ui_ip", "")
            whitelist = getattr(config, "ui_restrict", [])
            # binds to the Internet, no IP whitelist, no UiPassword, no Multiuser
            if ("0.0.0.0" == bind_ip or "*" == bind_ip) and (not whitelist):
                self.site.notifications.append([
                    "error",
                    _(u"You are not going to set up a public gateway. However, <b>your Web UI is<br>" +
                        "open to the whole Internet.</b> " +
                        "Please check your configuration.")
                ])

        file_server = sys.modules["main"].file_server
        if file_server.port_opened is True:
            self.site.notifications.append([
                "done",
                _["Congratulations, your port <b>{0}</b> is opened.<br>You are a full member of the ZeroNet network!"].format(config.fileserver_port),
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
                {_[or configure Tor to become a full member of the ZeroNet network.]}
                """).format(config.fileserver_port),
                0
            ])

    def hasPlugin(self, name):
        return name in PluginManager.plugin_manager.plugin_names

    # Has permission to run the command
    def hasCmdPermission(self, cmd):
        cmd = cmd[0].lower() + cmd[1:]

        if cmd in self.admin_commands and "ADMIN" not in self.permissions:
            return False
        else:
            return True

    # Has permission to access a site
    def hasSitePermission(self, address, cmd=None):
        if address != self.site.address and "ADMIN" not in self.site.settings["permissions"]:
            return False
        else:
            return True

    def hasFilePermission(self, inner_path):
        valid_signers = self.site.content_manager.getValidSigners(inner_path)
        return self.site.settings["own"] or self.user.getAuthAddress(self.site.address) in valid_signers

    # Event in a channel
    def event(self, channel, *params):
        if channel in self.channels:  # We are joined to channel
            if channel == "siteChanged":
                site = params[0]
                site_info = self.formatSiteInfo(site, create_user=False)
                if len(params) > 1 and params[1]:  # Extra data
                    site_info.update(params[1])
                self.cmd("setSiteInfo", site_info)
            elif channel == "serverChanged":
                server_info = self.formatServerInfo()
                self.cmd("setServerInfo", server_info)
            elif channel == "announcerChanged":
                site = params[0]
                announcer_info = self.formatAnnouncerInfo(site)
                if len(params) > 1 and params[1]:  # Extra data
                    announcer_info.update(params[1])
                self.cmd("setAnnouncerInfo", announcer_info)

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
        self.send_queue.append(message)
        if self.state["sending"]:
            return  # Already sending
        try:
            while self.send_queue:
                self.state["sending"] = True
                message = self.send_queue.pop(0)
                self.ws.send(json.dumps(message))
                self.state["sending"] = False
        except Exception, err:
            self.log.debug("Websocket send error: %s" % Debug.formatException(err))
            self.state["sending"] = False

    def getPermissions(self, req_id):
        permissions = self.site.settings["permissions"]
        if req_id >= 1000000:  # Its a wrapper command, allow admin commands
            permissions = permissions[:]
            permissions.append("ADMIN")
        return permissions

    def asyncWrapper(self, func):
        def asyncErrorWatcher(func, *args, **kwargs):
            try:
                result = func(*args, **kwargs)
                if result is not None:
                    self.response(args[0], result)
            except Exception, err:
                if config.debug:  # Allow websocket errors to appear on /Debug
                    sys.modules["main"].DebugHook.handleError()
                self.log.error("WebSocket handleRequest error: %s" % Debug.formatException(err))
                self.cmd("error", "Internal error: %s" % Debug.formatException(err, "html"))

        def wrapper(*args, **kwargs):
            gevent.spawn(asyncErrorWatcher, func, *args, **kwargs)
        return wrapper

    # Handle incoming messages
    def handleRequest(self, req):

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
            result = func(req["id"], **params)
        elif type(params) is list:
            result = func(req["id"], *params)
        elif params:
            result = func(req["id"], params)
        else:
            result = func(req["id"])

        if result is not None:
            self.response(req["id"], result)

    # Format site info
    def formatSiteInfo(self, site, create_user=True):
        content = site.content_manager.contents.get("content.json", {})
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
        file_server = sys.modules["main"].file_server
        return {
            "ip_external": file_server.port_opened,
            "platform": sys.platform,
            "fileserver_ip": config.fileserver_ip,
            "fileserver_port": config.fileserver_port,
            "tor_enabled": file_server.tor_manager.enabled,
            "tor_status": file_server.tor_manager.status,
            "tor_has_meek_bridges": file_server.tor_manager.has_meek_bridges,
            "tor_use_bridges": config.tor_use_bridges,
            "ui_ip": config.ui_ip,
            "ui_port": config.ui_port,
            "version": config.version,
            "rev": config.rev,
            "timecorrection": file_server.timecorrection,
            "language": config.language,
            "debug": config.debug,
            "plugins": PluginManager.plugin_manager.plugin_names,
            "user_settings": self.user.settings
        }

    def formatAnnouncerInfo(self, site):
        return {"address": site.address, "stats": site.announcer.stats}

    # - Actions -

    def actionAs(self, to, address, cmd, params=[]):
        if not self.hasSitePermission(address, cmd=cmd):
            return self.response(to, "No permission for site %s" % address)
        req_self = copy.copy(self)
        req_self.site = self.server.sites.get(address)
        req_self.hasCmdPermission = self.hasCmdPermission  # Use the same permissions as current site
        req_obj = super(UiWebsocket, req_self)
        req = {"id": to, "cmd": cmd, "params": params}
        req_obj.handleRequest(req)

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
    def actionChannelJoin(self, to, channels):
        if type(channels) != list:
            channels = [channels]

        for channel in channels:
            if channel not in self.channels:
                self.channels.append(channel)

    # Server variables
    def actionServerInfo(self, to):
        back = self.formatServerInfo()
        self.response(to, back)

    # Create a new wrapper nonce that allows to load html file
    def actionServerGetWrapperNonce(self, to):
        wrapper_nonce = self.request.getWrapperNonce()
        self.response(to, wrapper_nonce)

    def actionAnnouncerInfo(self, to):
        back = self.formatAnnouncerInfo(self.site)
        self.response(to, back)

    def actionAnnouncerStats(self, to):
        back = {}
        trackers = self.site.announcer.getTrackers()
        for site in self.server.sites.values():
            for tracker, stats in site.announcer.stats.iteritems():
                if tracker not in trackers:
                    continue
                if tracker not in back:
                    back[tracker] = {}
                is_latest_data = bool(stats["time_request"] > back[tracker].get("time_request", 0) and stats["status"])
                for key, val in stats.iteritems():
                    if key.startswith("num_"):
                        back[tracker][key] = back[tracker].get(key, 0) + val
                    elif is_latest_data:
                        back[tracker][key] = val

        return back

    # Sign content.json
    def actionSiteSign(self, to, privatekey=None, inner_path="content.json", remove_missing_optional=False, update_changed_files=False, response_ok=True):
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

        if not self.hasFilePermission(inner_path):
            self.log.error("SiteSign error: you don't own this site & site owner doesn't allow you to do so.")
            return self.response(to, {"error": "Forbidden, you can only modify your own sites"})

        if privatekey == "stored":  # Get privatekey from sites.json
            privatekey = self.user.getSiteData(self.site.address).get("privatekey")
        if not privatekey:  # Get privatekey from users.json auth_address
            privatekey = self.user.getAuthPrivatekey(self.site.address)

        # Signing
        # Reload content.json, ignore errors to make it up-to-date
        site.content_manager.loadContent(inner_path, add_bad_files=False, force=True)
        # Sign using private key sent by user
        try:
            site.content_manager.sign(inner_path, privatekey, extend=extend, update_changed_files=update_changed_files, remove_missing_optional=remove_missing_optional)
        except (VerifyError, SignError) as err:
            self.cmd("notification", ["error", _["Content signing failed"] + "<br><small>%s</small>" % err])
            self.response(to, {"error": "Site sign failed: %s" % err})
            self.log.error("Site sign failed: %s: %s" % (inner_path, Debug.formatException(err)))
            return
        except Exception as err:
            self.cmd("notification", ["error", _["Content signing error"] + "<br><small>%s</small>" % Debug.formatException(err)])
            self.response(to, {"error": "Site sign error: %s" % Debug.formatException(err)})
            self.log.error("Site sign error: %s: %s" % (inner_path, Debug.formatException(err)))
            return

        site.content_manager.loadContent(inner_path, add_bad_files=False)  # Load new content.json, ignore errors

        if update_changed_files:
            self.site.updateWebsocket(file_done=inner_path)

        if response_ok:
            self.response(to, "ok")
        else:
            return inner_path

    # Sign and publish content.json
    def actionSitePublish(self, to, privatekey=None, inner_path="content.json", sign=True, remove_missing_optional=False, update_changed_files=False):
        if sign:
            inner_path = self.actionSiteSign(
                to, privatekey, inner_path, response_ok=False,
                remove_missing_optional=remove_missing_optional, update_changed_files=update_changed_files
            )
            if not inner_path:
                return
        # Publishing
        if not self.site.settings["serving"]:  # Enable site if paused
            self.site.settings["serving"] = True
            self.site.saveSettings()
            self.site.announce()

        if inner_path not in self.site.content_manager.contents:
            return self.response(to, {"error": "File %s not found" % inner_path})

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
                        self.cmd("notification", ["info", _["No peers found, but your content is ready to access."]])
                    if callback:
                        self.response(to, "ok")
                else:
                    if notification:
                        self.cmd("notification", [
                            "info",
                            _(u"""{_[Your network connection is restricted. Please, open <b>{0}</b> port]}<br>
                            {_[on your router to make your site accessible for everyone.]}""").format(config.fileserver_port)
                        ])
                    if callback:
                        self.response(to, {"error": "Port not opened."})

            else:
                if notification:
                    self.response(to, {"error": "Content publish failed."})

    def actionSiteReload(self, to, inner_path):
        self.site.content_manager.loadContent(inner_path, add_bad_files=False)
        self.site.storage.verifyFiles(quick_check=True)
        self.site.updateWebsocket()
        return "ok"

    # Write a file to disk
    def actionFileWrite(self, to, inner_path, content_base64, ignore_bad_files=False):
        valid_signers = self.site.content_manager.getValidSigners(inner_path)
        auth_address = self.user.getAuthAddress(self.site.address)
        if not self.hasFilePermission(inner_path):
            self.log.error("FileWrite forbidden %s not in valid_signers %s" % (auth_address, valid_signers))
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
            self.log.error("File write error: %s" % Debug.formatException(err))
            return self.response(to, {"error": "Write error: %s" % Debug.formatException(err)})

        if inner_path.endswith("content.json"):
            self.site.content_manager.loadContent(inner_path, add_bad_files=False, force=True)

        self.response(to, "ok")

        # Send sitechanged to other local users
        for ws in self.site.websockets:
            if ws != self:
                ws.event("siteChanged", self.site, {"event": ["file_done", inner_path]})

    def actionFileDelete(self, to, inner_path):
        if not self.hasFilePermission(inner_path):
            self.log.error("File delete error: you don't own this site & you are not approved by the owner.")
            return self.response(to, {"error": "Forbidden, you can only modify your own files"})

        need_delete = True
        file_info = self.site.content_manager.getFileInfo(inner_path)
        if file_info and file_info.get("optional"):
            # Non-existing optional files won't be removed from content.json, so we have to do it manually
            self.log.debug("Deleting optional file: %s" % inner_path)
            relative_path = file_info["relative_path"]
            content_json = self.site.storage.loadJson(file_info["content_inner_path"])
            if relative_path in content_json.get("files_optional", {}):
                del content_json["files_optional"][relative_path]
                self.site.storage.writeJson(file_info["content_inner_path"], content_json)
                self.site.content_manager.loadContent(file_info["content_inner_path"], add_bad_files=False, force=True)
                need_delete = self.site.storage.isFile(inner_path)  # File sill exists after removing from content.json (owned site)

        if need_delete:
            try:
                self.site.storage.delete(inner_path)
            except Exception, err:
                self.log.error("File delete error: %s" % err)
                return self.response(to, {"error": "Delete error: %s" % err})

        self.response(to, "ok")

        # Send sitechanged to other local users
        for ws in self.site.websockets:
            if ws != self:
                ws.event("siteChanged", self.site, {"event": ["file_deleted", inner_path]})

    # Find data in json files
    def actionFileQuery(self, to, dir_inner_path, query=None):
        # s = time.time()
        dir_path = self.site.storage.getPath(dir_inner_path)
        rows = list(QueryJson.query(dir_path, query or ""))
        # self.log.debug("FileQuery %s %s done in %s" % (dir_inner_path, query, time.time()-s))
        return self.response(to, rows)

    # List files in directory
    def actionFileList(self, to, inner_path):
        try:
            return list(self.site.storage.walk(inner_path))
        except Exception as err:
            return {"error": str(err)}

    # List directories in a directory
    def actionDirList(self, to, inner_path):
        try:
            return list(self.site.storage.list(inner_path))
        except Exception as err:
            return {"error": str(err)}

    # Sql query
    def actionDbQuery(self, to, query, params=None, wait_for=None):
        if config.debug or config.verbose:
            s = time.time()
        rows = []
        try:
            if not query.strip().upper().startswith("SELECT"):
                raise Exception("Only SELECT query supported")
            res = self.site.storage.query(query, params)
        except Exception, err:  # Response the error to client
            self.log.error("DbQuery error: %s" % err)
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
            body = self.site.storage.read(inner_path, "rb")
        except Exception, err:
            self.log.error("%s fileGet error: %s" % (inner_path, err))
            body = None
        if body and format == "base64":
            import base64
            body = base64.b64encode(body)
        self.response(to, body)

    def actionFileNeed(self, to, inner_path, timeout=300):
        try:
            with gevent.Timeout(timeout):
                self.site.needFile(inner_path, priority=6)
        except Exception, err:
            return self.response(to, {"error": str(err)})
        return self.response(to, "ok")

    def actionFileRules(self, to, inner_path, use_my_cert=False, content=None):
        if not content:  # No content defined by function call
            content = self.site.content_manager.contents.get(inner_path)

        if not content:  # File not created yet
            cert = self.user.getCert(self.site.address)
            if cert and cert["auth_address"] in self.site.content_manager.getValidSigners(inner_path):
                # Current selected cert if valid for this site, add it to query rules
                content = {}
                content["cert_auth_type"] = cert["auth_type"]
                content["cert_user_id"] = self.user.getCertUserId(self.site.address)
                content["cert_sign"] = cert["cert_sign"]

        rules = self.site.content_manager.getRules(inner_path, content)
        if inner_path.endswith("content.json") and rules:
            if content:
                rules["current_size"] = len(json.dumps(content)) + sum([file["size"] for file in content.get("files", {}).values()])
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
                self.user.setCert(self.site.address, domain)
                self.site.updateWebsocket(cert_changed=domain)
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
            self.log.error("CertAdd error: Exception - %s" % err.message)
            self.response(to, {"error": err.message})

    def cbCertAddConfirm(self, to, domain, auth_type, auth_user_name, cert):
        self.user.deleteCert(domain)
        self.user.addCert(self.user.getAuthAddress(self.site.address), domain, auth_type, auth_user_name, cert)
        self.cmd(
            "notification",
            ["done", _("Certificate changed to: <b>{auth_type}/{auth_user_name}@{domain}</b>.")]
        )
        self.user.setCert(self.site.address, domain)
        self.site.updateWebsocket(cert_changed=domain)
        self.response(to, "ok")

    # Select certificate for site
    def actionCertSelect(self, to, accepted_domains=[], accept_any=False):
        accounts = []
        accounts.append(["", _["No certificate"], ""])  # Default option
        active = ""  # Make it active if no other option found

        # Add my certs
        auth_address = self.user.getAuthAddress(self.site.address)  # Current auth address
        site_data = self.user.getSiteData(self.site.address)  # Current auth address
        for domain, cert in self.user.certs.items():
            if auth_address == cert["auth_address"] and domain == site_data.get("cert"):
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
                 <a href='/{domain}' onclick='zeroframe.certSelectGotoSite(this)' class='select'>
                  <small style='float: right; margin-right: 40px; margin-top: -1px'>{_[Register]} &raquo;</small>{domain}
                 </a>
                """)
            body += "</div>"

        body += """
            <script>
             $(".notification .select.cert").on("click", function() {
                $(".notification .select").removeClass('active')
                zeroframe.response(%s, this.title)
                return false
             })
            </script>
        """ % self.next_message_id

        # Send the notification
        self.cmd("notification", ["ask", body], lambda domain: self.actionCertSet(to, domain))

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

    def actionPermissionDetails(self, to, permission):
        if permission == "ADMIN":
            self.response(to, _["Modify your client's configuration and access all site"] + " <span style='color: red'>" + _["(Dangerous!)"] + "</span>")
        elif permission == "NOSANDBOX":
            self.response(to, _["Modify your client's configuration and access all site"] + " <span style='color: red'>" + _["(Dangerous!)"] + "</span>")
        else:
            self.response(to, "")

    # Set certificate that used for authenticate user for site
    def actionCertSet(self, to, domain):
        self.user.setCert(self.site.address, domain)
        self.site.updateWebsocket(cert_changed=domain)
        self.response(to, "ok")

    # List all site info
    def actionSiteList(self, to, connecting_sites=False):
        ret = []
        SiteManager.site_manager.load()  # Reload sites
        for site in self.server.sites.values():
            if not site.content_manager.contents.get("content.json") and not connecting_sites:
                continue  # Incomplete site
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
    def actionSiteUpdate(self, to, address, check_files=False, since=None, announce=False):
        def updateThread():
            site.update(announce=announce, check_files=check_files, since=since)
            self.response(to, "Updated")

        site = self.server.sites.get(address)
        if site and (site.address == self.site.address or "ADMIN" in self.site.settings["permissions"]):
            if not site.settings["serving"]:
                site.settings["serving"] = True
                site.saveSettings()

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

    def cbSiteClone(self, to, address, root_inner_path="", target_address=None):
        self.cmd("notification", ["info", _["Cloning site..."]])
        site = self.server.sites.get(address)
        if target_address:
            target_site = self.server.sites.get(target_address)
            privatekey = self.user.getSiteData(target_site.address).get("privatekey")
            site.clone(target_address, privatekey, root_inner_path=root_inner_path)
            self.cmd("notification", ["done", _["Site source code upgraded!"]])
            site.publish()
        else:
            # Generate a new site from user's bip32 seed
            new_address, new_address_index, new_site_data = self.user.getNewSiteData()
            new_site = site.clone(new_address, new_site_data["privatekey"], address_index=new_address_index, root_inner_path=root_inner_path)
            new_site.settings["own"] = True
            new_site.saveSettings()
            self.cmd("notification", ["done", _["Site cloned"] + "<script>window.top.location = '/%s'</script>" % new_address])
            gevent.spawn(new_site.announce)
        return "ok"

    def actionSiteClone(self, to, address, root_inner_path="", target_address=None):
        if not SiteManager.site_manager.isAddress(address):
            self.response(to, {"error": "Not a site: %s" % address})
            return

        if not self.server.sites.get(address):
            # Don't expose site existence
            return

        if "ADMIN" in self.getPermissions(to):
            self.cbSiteClone(to, address, root_inner_path, target_address)
        else:
            self.cmd(
                "confirm",
                [_["Clone site <b>%s</b>?"] % address, _["Clone"]],
                lambda (res): self.cbSiteClone(to, address, root_inner_path, target_address)
            )

    def actionSiteSetLimit(self, to, size_limit):
        self.site.settings["size_limit"] = int(size_limit)
        self.site.saveSettings()
        self.response(to, "ok")
        self.site.updateWebsocket()
        self.site.download(blind_includes=True)

    def actionSiteAdd(self, to, address):
        site_manager = SiteManager.site_manager
        if address in site_manager.sites:
            return {"error": "Site already added"}
        else:
            if site_manager.need(address):
                return "ok"
            else:
                return {"error": "Invalid address"}

    def actionUserGetSettings(self, to):
        settings = self.user.sites[self.site.address].get("settings", {})
        self.response(to, settings)

    def actionUserSetSettings(self, to, settings):
        self.user.setSiteSettings(self.site.address, settings)
        self.response(to, "ok")

    def actionUserGetGlobalSettings(self, to):
        settings = self.user.settings
        self.response(to, settings)

    def actionUserSetGlobalSettings(self, to, settings):
        self.user.settings = settings
        self.user.save()
        self.response(to, "ok")

    def actionServerUpdate(self, to):
        self.cmd("updating")
        sys.modules["main"].update_after_shutdown = True
        SiteManager.site_manager.save()
        sys.modules["main"].file_server.stop()
        sys.modules["main"].ui_server.stop()

    def actionServerPortcheck(self, to):
        sys.modules["main"].file_server.port_opened = None
        res = sys.modules["main"].file_server.openport()
        self.response(to, res)

    def actionServerShutdown(self, to, restart=False):
        if restart:
            sys.modules["main"].restart_after_shutdown = True
        sys.modules["main"].file_server.stop()
        sys.modules["main"].ui_server.stop()

    def actionServerShowdirectory(self, to, directory="backup", inner_path=""):
        if self.request.env["REMOTE_ADDR"] != "127.0.0.1":
            return self.response(to, {"error": "Only clients from 127.0.0.1 allowed to run this command"})

        import webbrowser
        if directory == "backup":
            path = os.path.abspath(config.data_dir)
        elif directory == "log":
            path = os.path.abspath(config.log_dir)
        elif directory == "site":
            path = os.path.abspath(self.site.storage.getPath(helper.getDirname(inner_path)))

        if os.path.isdir(path):
            self.log.debug("Opening: %s" % path)
            webbrowser.open('file://' + path)
            return self.response(to, "ok")
        else:
            return self.response(to, {"error": "Not a directory"})

    def actionConfigSet(self, to, key, value):
        if key not in config.keys_api_change_allowed:
            self.response(to, {"error": "Forbidden you cannot set this config key"})
            return

        config.saveValue(key, value)

        if key not in config.keys_restart_need:
            if value is None:  # Default value
                setattr(config, key, config.parser.get_default(key))
                setattr(config.arguments, key, config.parser.get_default(key))
            else:
                setattr(config, key, value)
                setattr(config.arguments, key, value)
        else:
            config.need_restart = True
            config.pending_changes[key] = value

        if key == "language":
            import Translate
            for translate in Translate.translates:
                translate.setLanguage(value)
            message = _["You have successfully changed the web interface's language!"] + "<br>"
            message += _["Due to the browser's caching, the full transformation could take some minute."]
            self.cmd("notification", ["done", message, 10000])

        if key == "tor_use_bridges":
            if value is None:
                value = False
            else:
                value = True
            tor_manager = sys.modules["main"].file_server.tor_manager
            tor_manager.request("SETCONF UseBridges=%i" % value)

        if key == "trackers_file":
            config.loadTrackersFile()

        self.response(to, "ok")

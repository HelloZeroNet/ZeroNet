import json
import time
import sys
import hashlib
import os
import shutil

import gevent

from Config import config
from Site import SiteManager
from Debug import Debug
from util import QueryJson, RateLimit
from Plugin import PluginManager


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
                    "Congratulation, your port <b>%s</b> is opened.<br>You are full member of ZeroNet network!" %
                    config.fileserver_port,
                    10000
                ])
            elif config.tor == "always" and file_server.tor_manager.start_onions:
                self.site.notifications.append([
                    "done",
                    """
                    Tor mode active, every connection using Onion route.<br>
                    Successfully started Tor onion hidden services.
                    """,
                    10000
                ])
            elif config.tor == "always" and file_server.tor_manager.start_onions is not False:
                self.site.notifications.append([
                    "error",
                    """
                    Tor mode active, every connection using Onion route.<br>
                    Unable to start hidden services, please check your config.
                    """,
                    0
                ])
            elif file_server.port_opened is False and file_server.tor_manager.start_onions:
                self.site.notifications.append([
                    "done",
                    """
                    Successfully started Tor onion hidden services.<br>
                    For faster connections open <b>%s</b> port on your router.
                    """ % config.fileserver_port,
                    10000
                ])
            else:
                self.site.notifications.append([
                    "error",
                    """
                    Your connection is restricted. Please, open <b>%s</b> port on your router<br>
                    or configure Tor to become full member of ZeroNet network.
                    """ % config.fileserver_port,
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

    # Handle incoming messages
    def handleRequest(self, data):
        req = json.loads(data)

        cmd = req.get("cmd")
        params = req.get("params")
        self.permissions = self.getPermissions(req["id"])

        admin_commands = (
            "sitePause", "siteResume", "siteDelete", "siteList", "siteSetLimit", "siteClone",
            "channelJoinAllsite", "serverUpdate", "serverPortcheck", "serverShutdown", "certSet", "configSet",
            "actionPermissionAdd", "actionPermissionRemove"
        )

        if cmd == "response":  # It's a response to a command
            return self.actionResponse(req["to"], req["result"])
        elif cmd in admin_commands and "ADMIN" not in self.permissions:  # Admin commands
            return self.response(req["id"], {"error:", "You don't have permission to run %s" % cmd})
        else:  # Normal command
            func_name = "action" + cmd[0].upper() + cmd[1:]
            func = getattr(self, func_name, None)
            if not func:  # Unknown command
                self.response(req["id"], {"error": "Unknown command: %s" % cmd})
                return

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
    def actionSiteSign(self, to, privatekey=None, inner_path="content.json", response_ok=True, update_changed_files=False):
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
        signed = site.content_manager.sign(inner_path, privatekey, extend=extend, update_changed_files=update_changed_files)
        if not signed:
            self.cmd("notification", ["error", "Content sign failed: invalid private key."])
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
            thread.link(lambda thread: self.cbSitePublish(to, self.site, thread, notification, callback=notification))
        else:
            self.cmd(
                "notification",
                ["info", "Content publish queued for %.0f seconds." % RateLimit.delayLeft(event_name, 30), 5000]
            )
            self.response(to, "ok")
            # At the end display notification
            thread.link(lambda thread: self.cbSitePublish(to, self.site, thread, notification, callback=False))

    def doSitePublish(self, site, inner_path):
        diffs = site.content_manager.getDiffs(inner_path)
        return site.publish(limit=5, inner_path=inner_path, diffs=diffs)

    # Callback of site publish
    def cbSitePublish(self, to, site, thread, notification=True, callback=True):
        published = thread.value
        if published > 0:  # Successfully published
            if notification:
                self.cmd("notification", ["done", "Content published to %s peers." % published, 5000])
                site.updateWebsocket()  # Send updated site data to local websocket clients
            if callback:
                self.response(to, "ok")
        else:
            if len(site.peers) == 0:
                if sys.modules["main"].file_server.port_opened or sys.modules["main"].file_server.tor_manager.start_onions:
                    if notification:
                        self.cmd("notification", ["info", "No peers found, but your content is ready to access.", 5000])
                    if callback:
                        self.response(to, "ok")
                else:
                    if notification:
                        self.cmd("notification", [
                            "info",
                            """Your network connection is restricted. Please, open <b>%s</b> port <br>
                            on your router to make your site accessible for everyone.""" % config.fileserver_port
                        ])
                    if callback:
                        self.response(to, {"error": "Port not opened."})

            else:
                if notification:
                    self.cmd("notification", ["error", "Content publish failed."])
                    self.response(to, {"error": "Content publish failed."})

    # Write a file to disk
    def actionFileWrite(self, to, inner_path, content_base64):
        valid_signers = self.site.content_manager.getValidSigners(inner_path)
        auth_address = self.user.getAuthAddress(self.site.address)
        if not self.site.settings["own"] and auth_address not in valid_signers:
            self.log.debug("FileWrite forbidden %s not in %s" % (auth_address, valid_signers))
            return self.response(to, {"error": "Forbidden, you can only modify your own files"})

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

    # Sql query
    def actionDbQuery(self, to, query, params=None, wait_for=None):
        rows = []
        try:
            assert query.strip().upper().startswith("SELECT"), "Only SELECT query supported"
            res = self.site.storage.query(query, params)
        except Exception, err:  # Response the error to client
            return self.response(to, {"error": str(err)})
        # Convert result to dict
        for row in res:
            rows.append(dict(row))
        return self.response(to, rows)

    # Return file content
    def actionFileGet(self, to, inner_path, required=True):
        try:
            if required or inner_path in self.site.bad_files:
                self.site.needFile(inner_path, priority=6)
            body = self.site.storage.read(inner_path)
        except Exception, err:
            self.log.debug("%s fileGet error: %s" % (inner_path, err))
            body = None
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
                    ["done", "New certificate added: <b>%s/%s@%s</b>." % (auth_type, auth_user_name, domain)]
                )
                self.response(to, "ok")
            elif res is False:
                # Display confirmation of change
                cert_current = self.user.certs[domain]
                body = "You current certificate: <b>%s/%s@%s</b>" % (cert_current["auth_type"], cert_current["auth_user_name"], domain)
                self.cmd(
                    "confirm",
                    [body, "Change it to %s/%s@%s" % (auth_type, auth_user_name, domain)],
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
            ["done", "Certificate changed to: <b>%s/%s@%s</b>." % (auth_type, auth_user_name, domain)]
        )
        self.response(to, "ok")

    # Select certificate for site
    def actionCertSelect(self, to, accepted_domains=[], accept_any=False):
        accounts = []
        accounts.append(["", "Unique to site", ""])  # Default option
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
        body = "<span style='padding-bottom: 5px; display: inline-block'>Select account you want to use in this site:</span>"
        # Accounts
        for domain, account, css_class in accounts:
            if domain == active:
                css_class += " active"  # Currently selected option
                title = "<b>%s</b> <small>(currently selected)</small>" % account
            else:
                title = "<b>%s</b>" % account
            body += "<a href='#Select+account' class='select select-close cert %s' title='%s'>%s</a>" % (css_class, domain, title)
        # More available  providers
        more_domains = [domain for domain in accepted_domains if domain not in self.user.certs]  # Domains we not displayed yet
        if more_domains:
            # body+= "<small style='margin-top: 10px; display: block'>Accepted authorization providers by the site:</small>"
            body += "<div style='background-color: #F7F7F7; margin-right: -30px'>"
            for domain in more_domains:
                body += """
                 <a href='/%s' onclick='wrapper.gotoSite(this)' class='select'>
                  <small style='float: right; margin-right: 40px; margin-top: -1px'>Register &raquo;</small>%s
                 </a>
                """ % (domain, domain)
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
        self.response(to, "ok")

    def actionPermissionRemove(self, to, permission):
        self.site.settings["permissions"].remove(permission)
        self.site.saveSettings()
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
    def actionSiteUpdate(self, to, address):
        def updateThread():
            site.update()
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
            site.settings["serving"] = False
            site.saveSettings()
            site.worker_manager.running = False
            site.worker_manager.stopWorkers()
            site.storage.deleteFiles()
            site.updateWebsocket()
            SiteManager.site_manager.delete(address)
            self.user.deleteSiteData(address)
            self.response(to, "Deleted")
        else:
            self.response(to, {"error": "Unknown site: %s" % address})

    def actionSiteClone(self, to, address):
        self.cmd("notification", ["info", "Cloning site..."])
        site = self.server.sites.get(address)
        # Generate a new site from user's bip32 seed
        new_address, new_address_index, new_site_data = self.user.getNewSiteData()
        new_site = site.clone(new_address, new_site_data["privatekey"], address_index=new_address_index)
        new_site.settings["own"] = True
        new_site.saveSettings()
        self.cmd("notification", ["done", "Site cloned<script>window.top.location = '/%s'</script>" % new_address])
        gevent.spawn(new_site.announce)

    def actionSiteSetLimit(self, to, size_limit):
        self.site.settings["size_limit"] = int(size_limit)
        self.site.saveSettings()
        self.response(to, "Site size limit changed to %sMB" % size_limit)
        self.site.download(blind_includes=True)

    def actionServerUpdate(self, to):
        self.cmd("updating")
        sys.modules["main"].update_after_shutdown = True
        if sys.modules["main"].file_server.tor_manager.tor_process:
            sys.modules["main"].file_server.tor_manager.stopTor()
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
        if key not in ["tor"]:
            self.response(to, "denied")
            return

        if not os.path.isfile(config.config_file):
            content = ""
        else:
            content = open(config.config_file).read()
        lines = content.splitlines()

        global_line_i = None
        key_line_i = None
        i = 0
        for line in lines:
            if line.strip() == "[global]":
                global_line_i = i
            if line.startswith(key + " = "):
                key_line_i = i
            i += 1

        if value is None:  # Delete line
            if key_line_i:
                del lines[key_line_i]
        else:  # Add / update
            new_line = "%s = %s" % (key, value.replace("\n", "").replace("\r", ""))
            if key_line_i:  # Already in the config, change the line
                lines[key_line_i] = new_line
            elif global_line_i is None:  # No global section yet, append to end of file
                lines.append("[global]")
                lines.append(new_line)
            else:  # Has global section, append the line after it
                lines.insert(global_line_i + 1, new_line)

        open(config.config_file, "w").write("\n".join(lines))
        self.response(to, "ok")

import re
import sys
import json

from Config import config
from Plugin import PluginManager
from Crypt import CryptBitcoin
from . import UserPlugin
from util.Flag import flag
from Translate import translate as _

# We can only import plugin host clases after the plugins are loaded
@PluginManager.afterLoad
def importPluginnedClasses():
    global UserManager
    from User import UserManager

try:
    local_master_addresses = set(json.load(open("%s/users.json" % config.data_dir)).keys())  # Users in users.json
except Exception as err:
    local_master_addresses = set()


@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def __init__(self, *args, **kwargs):
        self.user_manager = UserManager.user_manager
        super(UiRequestPlugin, self).__init__(*args, **kwargs)

    def parsePath(self, path):
        return super(UiRequestPlugin, self).parsePath(path)

    # Create new user and inject user welcome message if necessary
    # Return: Html body also containing the injection
    def actionWrapper(self, path, extra_headers=None):

        match = re.match("/(?P<address>[A-Za-z0-9\._-]+)(?P<inner_path>/.*|$)", path)
        if not match:
            return False

        inner_path = match.group("inner_path").lstrip("/")
        html_request = "." not in inner_path or inner_path.endswith(".html")  # Only inject html to html requests

        user_created = False
        if html_request:
            user = self.getCurrentUser()  # Get user from cookie
            if not user:  # No user found by cookie
                user = self.user_manager.create()
                user_created = True
        else:
            user = None

        # Disable new site creation if --multiuser_no_new_sites enabled
        if config.multiuser_no_new_sites:
            path_parts = self.parsePath(path)
            if not self.server.site_manager.get(match.group("address")) and (not user or user.master_address not in local_master_addresses):
                self.sendHeader(404)
                return self.formatError("Not Found", "Adding new sites disabled on this proxy", details=False)

        if user_created:
            if not extra_headers:
                extra_headers = {}
            extra_headers['Set-Cookie'] = "master_address=%s;path=/;max-age=2592000;" % user.master_address  # = 30 days

        loggedin = self.get.get("login") == "done"

        back_generator = super(UiRequestPlugin, self).actionWrapper(path, extra_headers)  # Get the wrapper frame output

        if not back_generator:  # Wrapper error or not string returned, injection not possible
            return False

        elif loggedin:
            back = next(back_generator)
            inject_html = """
                <!-- Multiser plugin -->
                <script nonce="{script_nonce}">
                 setTimeout(function() {
                    zeroframe.cmd("wrapperNotification", ["done", "{message}<br><small>You have been logged in successfully</small>", 5000])
                 }, 1000)
                </script>
                </body>
                </html>
            """.replace("\t", "")
            if user.master_address in local_master_addresses:
                message = "Hello master!"
            else:
                message = "Hello again!"
            inject_html = inject_html.replace("{message}", message)
            inject_html = inject_html.replace("{script_nonce}", self.getScriptNonce())
            return iter([re.sub(b"</body>\s*</html>\s*$", inject_html.encode(), back)])  # Replace the </body></html> tags with the injection

        else:  # No injection necessary
            return back_generator

    # Get the current user based on request's cookies
    # Return: User object or None if no match
    def getCurrentUser(self):
        cookies = self.getCookies()
        user = None
        if "master_address" in cookies:
            users = self.user_manager.list()
            user = users.get(cookies["master_address"])
        return user


@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def __init__(self, *args, **kwargs):
        if config.multiuser_no_new_sites:
            flag.no_multiuser(self.actionMergerSiteAdd)

        super(UiWebsocketPlugin, self).__init__(*args, **kwargs)

    # Let the page know we running in multiuser mode
    def formatServerInfo(self):
        server_info = super(UiWebsocketPlugin, self).formatServerInfo()
        server_info["multiuser"] = True
        if "ADMIN" in self.site.settings["permissions"]:
            server_info["master_address"] = self.user.master_address
            is_multiuser_admin = config.multiuser_local or self.user.master_address in local_master_addresses
            server_info["multiuser_admin"] = is_multiuser_admin
        return server_info

    # Show current user's master seed
    @flag.admin
    def actionUserShowMasterSeed(self, to):
        message = "<b style='padding-top: 5px; display: inline-block'>Your unique private key:</b>"
        message += "<div style='font-size: 84%%; background-color: #FFF0AD; padding: 5px 8px; margin: 9px 0px'>%s</div>" % self.user.master_seed
        message += "<small>(Save it, you can access your account using this information)</small>"
        self.cmd("notification", ["info", message])

    # Logout user
    @flag.admin
    def actionUserLogout(self, to):
        message = "<b>You have been logged out.</b> <a href='#Login' class='button' id='button_notification'>Login to another account</a>"
        self.cmd("notification", ["done", message, 1000000])  # 1000000 = Show ~forever :)

        script = "document.cookie = 'master_address=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/';"
        script += "$('#button_notification').on('click', function() { zeroframe.cmd(\"userLoginForm\", []); });"
        self.cmd("injectScript", script)
        # Delete from user_manager
        user_manager = UserManager.user_manager
        if self.user.master_address in user_manager.users:
            if not config.multiuser_local:
                del user_manager.users[self.user.master_address]
            self.response(to, "Successful logout")
        else:
            self.response(to, "User not found")

    @flag.admin
    def actionUserSet(self, to, master_address):
        user_manager = UserManager.user_manager
        user = user_manager.get(master_address)
        if not user:
            raise Exception("No user found")

        script = "document.cookie = 'master_address=%s;path=/;max-age=2592000;';" % master_address
        script += "zeroframe.cmd('wrapperReload', ['login=done']);"
        self.cmd("notification", ["done", "Successful login, reloading page..."])
        self.cmd("injectScript", script)

        self.response(to, "ok")

    @flag.admin
    def actionUserSelectForm(self, to):
        if not config.multiuser_local:
            raise Exception("Only allowed in multiuser local mode")
        user_manager = UserManager.user_manager
        body = "<span style='padding-bottom: 5px; display: inline-block'>" + "Change account:" + "</span>"
        for master_address, user in user_manager.list().items():
            is_active = self.user.master_address == master_address
            if user.certs:
                first_cert = next(iter(user.certs.keys()))
                title = "%s@%s" % (user.certs[first_cert]["auth_user_name"], first_cert)
            else:
                title = user.master_address
                if len(user.sites) < 2 and not is_active:  # Avoid listing ad-hoc created users
                    continue
            if is_active:
                css_class = "active"
            else:
                css_class = "noclass"
            body += "<a href='#Select+user' class='select select-close user %s' title='%s'>%s</a>" % (css_class, user.master_address, title)

        script = """
             $(".notification .select.user").on("click", function() {
                $(".notification .select").removeClass('active')
                zeroframe.response(%s, this.title)
                return false
             })
        """ % self.next_message_id

        self.cmd("notification", ["ask", body], lambda master_address: self.actionUserSet(to, master_address))
        self.cmd("injectScript", script)

    # Show login form
    def actionUserLoginForm(self, to):
        self.cmd("prompt", ["<b>Login</b><br>Your private key:", "password", "Login"], self.responseUserLogin)

    # Login form submit
    def responseUserLogin(self, master_seed):
        user_manager = UserManager.user_manager
        user = user_manager.get(CryptBitcoin.privatekeyToAddress(master_seed))
        if not user:
            user = user_manager.create(master_seed=master_seed)
        if user.master_address:
            script = "document.cookie = 'master_address=%s;path=/;max-age=2592000;';" % user.master_address
            script += "zeroframe.cmd('wrapperReload', ['login=done']);"
            self.cmd("notification", ["done", "Successful login, reloading page..."])
            self.cmd("injectScript", script)
        else:
            self.cmd("notification", ["error", "Error: Invalid master seed"])
            self.actionUserLoginForm(0)

    def hasCmdPermission(self, cmd):
        flags = flag.db.get(self.getCmdFuncName(cmd), ())
        is_public_proxy_user = not config.multiuser_local and self.user.master_address not in local_master_addresses
        if is_public_proxy_user and "no_multiuser" in flags:
            self.cmd("notification", ["info", _("This function ({cmd}) is disabled on this proxy!")])
            return False
        else:
            return super(UiWebsocketPlugin, self).hasCmdPermission(cmd)

    def actionCertAdd(self, *args, **kwargs):
        super(UiWebsocketPlugin, self).actionCertAdd(*args, **kwargs)
        master_seed = self.user.master_seed
        message = """
            <style>
            .masterseed {
                font-size: 85%; background-color: #FFF0AD; padding: 5px 8px; margin: 9px 0px; width: 100%;
                box-sizing: border-box; border: 0px; text-align: center; cursor: pointer;
            }
            </style>
            <b>Hello, welcome to ZeroProxy!</b><div style='margin-top: 8px'>A new, unique account created for you:</div>
            <input type='text' class='masterseed' id='button_notification_masterseed' value='Click here to show' readonly/>
            <div style='text-align: center; font-size: 85%; margin-bottom: 10px;'>
             or <a href='#Download' id='button_notification_download'
             class='masterseed_download' download='zeronet_private_key.backup'>Download backup as text file</a>
            </div>
            <div>
             This is your private key, <b>save it</b>, so you can login next time.<br>
             <b>Warning: Without this key, your account will be lost forever!</b>
            </div><br>
            <a href='#' class='button' style='margin-left: 0px'>Ok, Saved it!</a><br><br>
            <small>This site allows you to browse ZeroNet content, but if you want to secure your account <br>
            and help to keep the network alive, then please run your own <a href='https://zeronet.io' target='_blank'>ZeroNet client</a>.</small>
        """

        self.cmd("notification", ["info", message])

        script = """
            $("#button_notification_masterseed").on("click", function() {
                this.value = "{master_seed}"; this.setSelectionRange(0,100);
            })
            $("#button_notification_download").on("mousedown", function() {
                this.href = window.URL.createObjectURL(new Blob(["ZeroNet user master seed:\\r\\n{master_seed}"]))
            })
        """.replace("{master_seed}", master_seed)
        self.cmd("injectScript", script)

    def actionPermissionAdd(self, to, permission):
        is_public_proxy_user = not config.multiuser_local and self.user.master_address not in local_master_addresses
        if permission == "NOSANDBOX" and is_public_proxy_user:
            self.cmd("notification", ["info", "You can't disable sandbox on this proxy!"])
            self.response(to, {"error": "Denied by proxy"})
            return False
        else:
            return super(UiWebsocketPlugin, self).actionPermissionAdd(to, permission)


@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("Multiuser plugin")
        group.add_argument('--multiuser_local', help="Enable unsafe Ui functions and write users to disk", action='store_true')
        group.add_argument('--multiuser_no_new_sites', help="Denies adding new sites by normal users", action='store_true')

        return super(ConfigPlugin, self).createArguments()

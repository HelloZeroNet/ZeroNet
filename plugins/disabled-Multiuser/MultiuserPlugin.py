import re
import sys
import json

from Config import config
from Plugin import PluginManager
from Crypt import CryptBitcoin
import UserPlugin

try:
    local_master_addresses = set(json.load(open("%s/users.json" % config.data_dir)).keys())  # Users in users.json
except Exception, err:
    local_master_addresses = set()

@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def __init__(self, *args, **kwargs):
        self.user_manager = sys.modules["User.UserManager"].user_manager
        super(UiRequestPlugin, self).__init__(*args, **kwargs)

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
                extra_headers = []
            extra_headers.append(('Set-Cookie', "master_address=%s;path=/;max-age=2592000;" % user.master_address))  # = 30 days

        loggedin = self.get.get("login") == "done"

        back_generator = super(UiRequestPlugin, self).actionWrapper(path, extra_headers)  # Get the wrapper frame output

        if not back_generator:  # Wrapper error or not string returned, injection not possible
            return False

        if user_created:
            back = back_generator.next()
            master_seed = user.master_seed
            # Inject the welcome message
            inject_html = """
                <!-- Multiser plugin -->
                <style>
                 .masterseed { font-size: 95%; background-color: #FFF0AD; padding: 5px 8px; margin: 9px 0px }
                </style>
                <script>
                 hello_message = "<b>Hello, welcome to ZeroProxy!</b><div style='margin-top: 8px'>A new, unique account created for you:</div>"
                 hello_message+= "<div class='masterseed'>{master_seed}</div> <div>This is your private key, <b>save it</b>, so you can login next time.</div><br>"
                 hello_message+= "<a href='#' class='button' style='margin-left: 0px'>Ok, Saved it!</a> or <a href='#Login' onclick='wrapper.ws.cmd(\\"userLoginForm\\", []); return false'>Login</a><br><br>"
                 hello_message+= "<small>This site allows you to browse ZeroNet content, but if you want to secure your account <br>"
                 hello_message+= "and help to make a better network, then please run your own <a href='https://github.com/HelloZeroNet/ZeroNet' target='_blank'>ZeroNet client</a>.</small>"
                 setTimeout(function() {
                    wrapper.notifications.add("hello", "info", hello_message)
                    delete(hello_message)
                 }, 1000)
                </script>
                </body>
                </html>
            """.replace("\t", "")
            inject_html = inject_html.replace("{master_seed}", master_seed)  # Set the master seed in the message

            return iter([re.sub("</body>\s*</html>\s*$", inject_html, back)])  # Replace the </body></html> tags with the injection

        elif loggedin:
            back = back_generator.next()
            inject_html = """
                <!-- Multiser plugin -->
                <script>
                 setTimeout(function() {
                    wrapper.notifications.add("login", "done", "{message}<br><small>You have been logged in successfully</small>", 5000)
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
            return iter([re.sub("</body>\s*</html>\s*$", inject_html, back)])  # Replace the </body></html> tags with the injection

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
        self.multiuser_denied_cmds = (
            "siteDelete", "configSet", "serverShutdown", "serverUpdate", "siteClone",
            "siteSetOwned", "optionalLimitSet", "siteSetAutodownloadoptional", "dbReload", "dbRebuild",
            "mergerSiteDelete",
            "muteAdd", "muteRemove"
        )
        if config.multiuser_no_new_sites:
            self.multiuser_denied_cmds += ("MergerSiteAdd", )

        super(UiWebsocketPlugin, self).__init__(*args, **kwargs)

    # Let the page know we running in multiuser mode
    def formatServerInfo(self):
        server_info = super(UiWebsocketPlugin, self).formatServerInfo()
        server_info["multiuser"] = True
        if "ADMIN" in self.site.settings["permissions"]:
            server_info["master_address"] = self.user.master_address
        return server_info

    # Show current user's master seed
    def actionUserShowMasterSeed(self, to):
        if "ADMIN" not in self.site.settings["permissions"]:
            return self.response(to, "Show master seed not allowed")
        message = "<b style='padding-top: 5px; display: inline-block'>Your unique private key:</b>"
        message += "<div style='font-size: 84%%; background-color: #FFF0AD; padding: 5px 8px; margin: 9px 0px'>%s</div>" % self.user.master_seed
        message += "<small>(Save it, you can access your account using this information)</small>"
        self.cmd("notification", ["info", message])

    # Logout user
    def actionUserLogout(self, to):
        if "ADMIN" not in self.site.settings["permissions"]:
            return self.response(to, "Logout not allowed")
        message = "<b>You have been logged out.</b> <a href='#Login' class='button' onclick='wrapper.ws.cmd(\"userLoginForm\", []); return false'>Login to another account</a>"
        message += "<script>document.cookie = 'master_address=; expires=Thu, 01 Jan 1970 00:00:00 UTC'</script>"
        self.cmd("notification", ["done", message, 1000000])  # 1000000 = Show ~forever :)
        # Delete from user_manager
        user_manager = sys.modules["User.UserManager"].user_manager
        if self.user.master_address in user_manager.users:
            if not config.multiuser_local:
                del user_manager.users[self.user.master_address]
            self.response(to, "Successful logout")
        else:
            self.response(to, "User not found")

    # Show login form
    def actionUserLoginForm(self, to):
        self.cmd("prompt", ["<b>Login</b><br>Your private key:", "password", "Login"], self.responseUserLogin)

    # Login form submit
    def responseUserLogin(self, master_seed):
        user_manager = sys.modules["User.UserManager"].user_manager
        user = user_manager.get(CryptBitcoin.privatekeyToAddress(master_seed))
        if not user:
            user = user_manager.create(master_seed=master_seed)
        if user.master_address:
            message = "Successfull login, reloading page..."
            message += "<script>document.cookie = 'master_address=%s;path=/;max-age=2592000;'</script>" % user.master_address
            message += "<script>wrapper.reload('login=done')</script>"
            self.cmd("notification", ["done", message])
        else:
            self.cmd("notification", ["error", "Error: Invalid master seed"])
            self.actionUserLoginForm(0)

    def hasCmdPermission(self, cmd):
        if not config.multiuser_local and self.user.master_address not in local_master_addresses and cmd in self.multiuser_denied_cmds:
            self.cmd("notification", ["info", "This function is disabled on this proxy!"])
            return False
        else:
            return super(UiWebsocketPlugin, self).hasCmdPermission(cmd)


@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("Multiuser plugin")
        group.add_argument('--multiuser_local', help="Enable unsafe Ui functions and write users to disk", action='store_true')
        group.add_argument('--multiuser_no_new_sites', help="Denies adding new sites by normal users", action='store_true')

        return super(ConfigPlugin, self).createArguments()

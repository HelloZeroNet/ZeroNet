import string
import random
import time
import json
import re


from Config import config
from Plugin import PluginManager
from util import helper

if "sessions" not in locals().keys():  # To keep sessions between module reloads
    sessions = {}


def showPasswordAdvice(password):
    error_msgs = []
    if not password or not isinstance(password, str):
        error_msgs.append("You have enabled <b>UiPassword</b> plugin, but you forgot to set a password!")
    elif len(password) < 8:
        error_msgs.append("You are using a very short UI password!")
    return error_msgs

@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    sessions = sessions
    last_cleanup = time.time()

    def route(self, path):
        # Restict Ui access by ip
        if config.ui_restrict and self.env['REMOTE_ADDR'] not in config.ui_restrict:
            return self.error403(details=False)
        if path.endswith("favicon.ico"):
            return self.actionFile("src/Ui/media/img/favicon.ico")
        else:
            if config.ui_password:
                if time.time() - self.last_cleanup > 60 * 60:  # Cleanup expired sessions every hour
                    self.cleanup()
                # Validate session
                session_id = self.getCookies().get("session_id")
                if session_id not in self.sessions:  # Invalid session id, display login
                    return self.actionLogin()
            return super(UiRequestPlugin, self).route(path)

    # Action: Login
    @helper.encodeResponse
    def actionLogin(self):
        template = open("plugins/UiPassword/login.html").read()
        self.sendHeader()
        posted = self.getPosted()
        if posted:  # Validate http posted data
            if self.checkPassword(posted.get("password")):
                # Valid password, create session
                session_id = self.randomString(26)
                self.sessions[session_id] = {
                    "added": time.time(),
                    "keep": posted.get("keep")
                }

                # Redirect to homepage or referer
                url = self.env.get("HTTP_REFERER", "")
                if not url or re.sub(r"\?.*", "", url).endswith("/Login"):
                    url = "/" + config.homepage
                cookie_header = ('Set-Cookie', "session_id=%s;path=/;max-age=2592000;" % session_id)  # Max age = 30 days
                self.start_response('301 Redirect', [('Location', url), cookie_header])
                yield "Redirecting..."

            else:
                # Invalid password, show login form again
                template = template.replace("{result}", "bad_password")
        yield template

    def checkPassword(self, password):
        return password == config.ui_password

    def randomString(self, nchars):
        return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(nchars))

    @classmethod
    def cleanup(cls):
        cls.last_cleanup = time.time()
        for session_id, session in list(cls.sessions.items()):
            if session["keep"] and time.time() - session["added"] > 60 * 60 * 24 * 60:  # Max 60days for keep sessions
                del(cls.sessions[session_id])
            elif not session["keep"] and time.time() - session["added"] > 60 * 60 * 24:  # Max 24h for non-keep sessions
                del(cls.sessions[session_id])

    # Action: Display sessions
    def actionSessions(self):
        self.sendHeader()
        yield "<pre>"
        yield json.dumps(self.sessions, indent=4)

    # Action: Logout
    def actionLogout(self):
        # Session id has to passed as get parameter or called without referer to avoid remote logout
        session_id = self.getCookies().get("session_id")
        if not self.env.get("HTTP_REFERER") or session_id == self.get.get("session_id"):
            if session_id in self.sessions:
                del self.sessions[session_id]
            self.start_response('301 Redirect', [
                ('Location', "/"),
                ('Set-Cookie', "session_id=deleted; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT")
            ])
            yield "Redirecting..."
        else:
            self.sendHeader()
            yield "Error: Invalid session id"



@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("UiPassword plugin")
        group.add_argument('--ui_password', help='Password to access UiServer', default=None, metavar="password")

        return super(ConfigPlugin, self).createArguments()


from Translate import translate as lang
@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def actionUiLogout(self, to):
        permissions = self.getPermissions(to)
        if "ADMIN" not in permissions:
            return self.response(to, "You don't have permission to run this command")

        session_id = self.request.getCookies().get("session_id", "")
        self.cmd("redirect", '/Logout?session_id=%s' % session_id)

    def addHomepageNotifications(self):
        error_msgs = showPasswordAdvice(config.ui_password)
        for msg in error_msgs:
            self.site.notifications.append(["error", lang[msg]])

        return super(UiWebsocketPlugin, self).addHomepageNotifications()

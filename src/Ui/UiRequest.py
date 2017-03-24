import time
import re
import os
import mimetypes
import json
import cgi

from Config import config
from Site import SiteManager
from User import UserManager
from Plugin import PluginManager
from Ui.UiWebsocket import UiWebsocket
from Crypt import CryptHash

status_texts = {
    200: "200 OK",
    206: "206 Partial Content",
    400: "400 Bad Request",
    403: "403 Forbidden",
    404: "404 Not Found",
    500: "500 Internal Server Error",
}


@PluginManager.acceptPlugins
class UiRequest(object):

    def __init__(self, server, get, env, start_response):
        if server:
            self.server = server
            self.log = server.log
        self.get = get  # Get parameters
        self.env = env  # Enviroment settings
        # ['CONTENT_LENGTH', 'CONTENT_TYPE', 'GATEWAY_INTERFACE', 'HTTP_ACCEPT', 'HTTP_ACCEPT_ENCODING', 'HTTP_ACCEPT_LANGUAGE',
        #  'HTTP_COOKIE', 'HTTP_CACHE_CONTROL', 'HTTP_HOST', 'HTTP_HTTPS', 'HTTP_ORIGIN', 'HTTP_PROXY_CONNECTION', 'HTTP_REFERER',
        #  'HTTP_USER_AGENT', 'PATH_INFO', 'QUERY_STRING', 'REMOTE_ADDR', 'REMOTE_PORT', 'REQUEST_METHOD', 'SCRIPT_NAME',
        #  'SERVER_NAME', 'SERVER_PORT', 'SERVER_PROTOCOL', 'SERVER_SOFTWARE', 'werkzeug.request', 'wsgi.errors',
        #  'wsgi.input', 'wsgi.multiprocess', 'wsgi.multithread', 'wsgi.run_once', 'wsgi.url_scheme', 'wsgi.version']

        self.start_response = start_response  # Start response function
        self.user = None

    # Call the request handler function base on path
    def route(self, path):
        if config.ui_restrict and self.env['REMOTE_ADDR'] not in config.ui_restrict:  # Restict Ui access by ip
            return self.error403(details=False)

        path = re.sub("^http://zero[/]+", "/", path)  # Remove begining http://zero/ for chrome extension
        path = re.sub("^http://", "/", path)  # Remove begining http for chrome extension .bit access

        if self.env["REQUEST_METHOD"] == "OPTIONS":
            if "/" not in path.strip("/"):
                content_type = self.getContentType("index.html")
            else:
                content_type = self.getContentType(path)
            self.sendHeader(content_type=content_type)
            return ""

        if path == "/":
            return self.actionIndex()
        elif path == "/favicon.ico":
            return self.actionFile("src/Ui/media/img/favicon.ico")
        # Media
        elif path.startswith("/uimedia/"):
            return self.actionUiMedia(path)
        elif "/uimedia/" in path:
            # uimedia within site dir (for chrome extension)
            path = re.sub(".*?/uimedia/", "/uimedia/", path)
            return self.actionUiMedia(path)
        # Websocket
        elif path == "/Websocket":
            return self.actionWebsocket()
        # Debug
        elif path == "/Debug" and config.debug:
            return self.actionDebug()
        elif path == "/Console" and config.debug:
            return self.actionConsole()
        # Site media wrapper
        else:
            if self.get.get("wrapper_nonce"):
                return self.actionSiteMedia("/media" + path)  # Only serve html files with frame
            else:
                body = self.actionWrapper(path)
            if body:
                return body
            else:
                func = getattr(self, "action" + path.lstrip("/"), None)  # Check if we have action+request_path function
                if func:
                    return func()
                else:
                    return self.error404(path)

    # The request is proxied by chrome extension
    def isProxyRequest(self):
        return self.env["PATH_INFO"].startswith("http://")

    def isWebSocketRequest(self):
        return self.env.get("HTTP_UPGRADE") == "websocket"

    def isAjaxRequest(self):
        return self.env.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"

    # Get mime by filename
    def getContentType(self, file_name):
        content_type = mimetypes.guess_type(file_name)[0]

        if file_name.endswith(".css"):  # Force correct css content type
            content_type = "text/css"

        if not content_type:
            if file_name.endswith(".json"):  # Correct json header
                content_type = "application/json"
            else:
                content_type = "application/octet-stream"
        return content_type

    # Return: <dict> Posted variables
    def getPosted(self):
        if self.env['REQUEST_METHOD'] == "POST":
            return dict(cgi.parse_qsl(
                self.env['wsgi.input'].readline().decode()
            ))
        else:
            return {}

    # Return: <dict> Cookies based on self.env
    def getCookies(self):
        raw_cookies = self.env.get('HTTP_COOKIE')
        if raw_cookies:
            cookies = cgi.parse_qsl(raw_cookies)
            return {key.strip(): val for key, val in cookies}
        else:
            return {}

    def getCurrentUser(self):
        if self.user:
            return self.user  # Cache
        self.user = UserManager.user_manager.get()  # Get user
        if not self.user:
            self.user = UserManager.user_manager.create()
        return self.user

    # Send response headers
    def sendHeader(self, status=200, content_type="text/html", extra_headers=[]):
        headers = []
        headers.append(("Version", "HTTP/1.1"))
        headers.append(("Connection", "Keep-Alive"))
        headers.append(("Keep-Alive", "max=25, timeout=30"))
        if content_type != "text/html":
            headers.append(("Access-Control-Allow-Origin", "*"))  # Allow json access on non-html files
        headers.append(("X-Frame-Options", "SAMEORIGIN"))
        # headers.append(("Content-Security-Policy", "default-src 'self' data: 'unsafe-inline' ws://127.0.0.1:* http://127.0.0.1:* wss://tracker.webtorrent.io; sandbox allow-same-origin allow-top-navigation allow-scripts"))  # Only local connections
        if self.env["REQUEST_METHOD"] == "OPTIONS":
            # Allow json access
            headers.append(("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept, Cookie"))
            headers.append(("Access-Control-Allow-Credentials", "true"))

        if content_type == "text/html":
            content_type = "text/html; charset=utf-8"
        if content_type == "text/plain":
            content_type = "text/plain; charset=utf-8"

        cacheable_type = (
            content_type == "text/css" or content_type.startswith("image") or content_type.startswith("video") or
            self.env["REQUEST_METHOD"] == "OPTIONS" or content_type == "application/javascript"
        )

        if status in (200, 206) and cacheable_type:  # Cache Css, Js, Image files for 10min
            headers.append(("Cache-Control", "public, max-age=600"))  # Cache 10 min
        else:
            headers.append(("Cache-Control", "no-cache, no-store, private, must-revalidate, max-age=0"))  # No caching at all
        headers.append(("Content-Type", content_type))
        for extra_header in extra_headers:
            headers.append(extra_header)
        return self.start_response(status_texts[status], headers)

    # Renders a template
    def render(self, template_path, *args, **kwargs):
        template = open(template_path).read().decode("utf8")
        return template.format(**kwargs).encode("utf8")

    # - Actions -

    # Redirect to an url
    def actionRedirect(self, url):
        self.start_response('301 Redirect', [('Location', url)])
        yield "Location changed: %s" % url

    def actionIndex(self):
        return self.actionRedirect("/" + config.homepage)

    # Render a file from media with iframe site wrapper
    def actionWrapper(self, path, extra_headers=None):
        if not extra_headers:
            extra_headers = []

        match = re.match("/(?P<address>[A-Za-z0-9\._-]+)(?P<inner_path>/.*|$)", path)
        if match:
            address = match.group("address")
            inner_path = match.group("inner_path").lstrip("/")
            if "." in inner_path and not inner_path.endswith(".html"):
                return self.actionSiteMedia("/media" + path)  # Only serve html files with frame
            if self.isAjaxRequest():
                return self.error403("Ajax request not allowed to load wrapper")  # No ajax allowed on wrapper

            if self.isWebSocketRequest():
                return self.error403("WebSocket request not allowed to load wrapper")  # No websocket

            if "text/html" not in self.env.get("HTTP_ACCEPT", ""):
                return self.error403("Invalid Accept header to load wrapper")
            if "prefetch" in self.env.get("HTTP_X_MOZ", "") or "prefetch" in self.env.get("HTTP_PURPOSE", ""):
                return self.error403("Prefetch not allowed to load wrapper")

            site = SiteManager.site_manager.get(address)

            if (
                site and site.content_manager.contents.get("content.json") and
                (not site.getReachableBadFiles() or site.settings["own"])
            ):  # Its downloaded or own
                title = site.content_manager.contents["content.json"]["title"]
            else:
                title = "Loading %s..." % address
                site = SiteManager.site_manager.need(address)  # Start download site

                if not site:
                    return False

            self.sendHeader(extra_headers=extra_headers[:])
            return iter([self.renderWrapper(site, path, inner_path, title, extra_headers)])
            # Dont know why wrapping with iter necessary, but without it around 100x slower

        else:  # Bad url
            return False

    def renderWrapper(self, site, path, inner_path, title, extra_headers):
        file_inner_path = inner_path
        if not file_inner_path:
            file_inner_path = "index.html"  # If inner path defaults to index.html

        if file_inner_path.endswith("/"):
            file_inner_path = file_inner_path + "index.html"

        address = re.sub("/.*", "", path.lstrip("/"))
        if self.isProxyRequest() and (not path or "/" in path[1:]):
            file_url = re.sub(".*/", "", inner_path)
            if self.env["HTTP_HOST"] == "zero":
                root_url = "/" + address + "/"
            else:
                root_url = "/"

        else:
            file_url = "/" + address + "/" + inner_path
            root_url = "/" + address + "/"

        # Wrapper variable inits
        query_string = ""
        body_style = ""
        meta_tags = ""
        postmessage_nonce_security = "false"

        wrapper_nonce = self.getWrapperNonce()

        if self.env.get("QUERY_STRING"):
            query_string = "?%s&wrapper_nonce=%s" % (self.env["QUERY_STRING"], wrapper_nonce)
        else:
            query_string = "?wrapper_nonce=%s" % wrapper_nonce

        if self.isProxyRequest():  # Its a remote proxy request
            if self.env["REMOTE_ADDR"] == "127.0.0.1":  # Local client, the server address also should be 127.0.0.1
                server_url = "http://127.0.0.1:%s" % self.env["SERVER_PORT"]
            else:  # Remote client, use SERVER_NAME as server's real address
                server_url = "http://%s:%s" % (self.env["SERVER_NAME"], self.env["SERVER_PORT"])
            homepage = "http://zero/" + config.homepage
        else:  # Use relative path
            server_url = ""
            homepage = "/" + config.homepage

        if site.content_manager.contents.get("content.json"):  # Got content.json
            content = site.content_manager.contents["content.json"]
            if content.get("background-color"):
                body_style += "background-color: %s;" % \
                    cgi.escape(site.content_manager.contents["content.json"]["background-color"], True)
            if content.get("viewport"):
                meta_tags += '<meta name="viewport" id="viewport" content="%s">' % cgi.escape(content["viewport"], True)
            if content.get("favicon"):
                meta_tags += '<link rel="icon" href="%s%s">' % (root_url, cgi.escape(content["favicon"], True))
            if content.get("postmessage_nonce_security"):
                postmessage_nonce_security = "true"

        if site.settings.get("own"):
            sandbox_permissions = "allow-modals"  # For coffeescript compile errors
        else:
            sandbox_permissions = ""

        return self.render(
            "src/Ui/template/wrapper.html",
            server_url=server_url,
            inner_path=inner_path,
            file_url=re.escape(file_url),
            file_inner_path=re.escape(file_inner_path),
            address=site.address,
            title=cgi.escape(title, True),
            body_style=body_style,
            meta_tags=meta_tags,
            query_string=re.escape(query_string),
            wrapper_key=site.settings["wrapper_key"],
            wrapper_nonce=wrapper_nonce,
            postmessage_nonce_security=postmessage_nonce_security,
            permissions=json.dumps(site.settings["permissions"]),
            show_loadingscreen=json.dumps(not site.storage.isFile(file_inner_path)),
            sandbox_permissions=sandbox_permissions,
            rev=config.rev,
            lang=config.language,
            homepage=homepage
        )

    # Create a new wrapper nonce that allows to get one html file without the wrapper
    def getWrapperNonce(self):
        wrapper_nonce = CryptHash.random()
        self.server.wrapper_nonces.append(wrapper_nonce)
        return wrapper_nonce

    # Returns if media request allowed from that referer
    def isMediaRequestAllowed(self, site_address, referer):
        if not re.sub("^http[s]{0,1}://", "", referer).startswith(self.env["HTTP_HOST"]):
            return False
        referer_path = re.sub("http[s]{0,1}://.*?/", "/", referer).replace("/media", "")  # Remove site address
        return referer_path.startswith("/" + site_address)

    # Return {address: 1Site.., inner_path: /data/users.json} from url path
    def parsePath(self, path):
        path = path.replace("/index.html/", "/")  # Base Backward compatibility fix
        if path.endswith("/"):
            path = path + "index.html"

        if ".." in path:
            raise Exception("Invalid path")

        match = re.match("/media/(?P<address>[A-Za-z0-9\._-]+)/(?P<inner_path>.*)", path)
        if match:
            path_parts = match.groupdict()
            path_parts["request_address"] = path_parts["address"]  # Original request address (for Merger sites)
            return path_parts
        else:
            return None

    # Serve a media for site
    def actionSiteMedia(self, path, header_length=True):
        if ".." in path:  # File not in allowed path
            return self.error403("Invalid file path")

        path_parts = self.parsePath(path)

        # Check wrapper nonce
        content_type = self.getContentType(path_parts["inner_path"])
        if "htm" in content_type:  # Valid nonce must present to render html files
            wrapper_nonce = self.get.get("wrapper_nonce")
            if wrapper_nonce not in self.server.wrapper_nonces:
                return self.error403("Wrapper nonce error. Please reload the page.")
            self.server.wrapper_nonces.remove(self.get["wrapper_nonce"])

        referer = self.env.get("HTTP_REFERER")
        if referer and path_parts:  # Only allow same site to receive media
            if not self.isMediaRequestAllowed(path_parts["request_address"], referer):
                self.log.error("Media referrer error: %s not allowed from %s" % (path_parts["address"], referer))
                return self.error403("Media referrer error")  # Referrer not starts same address as requested path

        if path_parts:  # Looks like a valid path
            address = path_parts["address"]
            file_path = "%s/%s/%s" % (config.data_dir, address, path_parts["inner_path"])
            if config.debug and file_path.split("/")[-1].startswith("all."):
                # If debugging merge *.css to all.css and *.js to all.js
                site = self.server.sites.get(address)
                if site.settings["own"]:
                    from Debug import DebugMedia
                    DebugMedia.merge(file_path)
            if os.path.isfile(file_path):  # File exists
                return self.actionFile(file_path, header_length=header_length)
            elif os.path.isdir(file_path):  # If this is actually a folder, add "/" and redirect
                return self.actionRedirect("./{0}/".format(path_parts["inner_path"].split("/")[-1]))
            else:  # File not exists, try to download
                if address not in SiteManager.site_manager.sites:  # Only in case if site already started downloading
                    return self.error404(path_parts["inner_path"])

                site = SiteManager.site_manager.need(address)

                if path_parts["inner_path"].endswith("favicon.ico"):  # Default favicon for all sites
                    return self.actionFile("src/Ui/media/img/favicon.ico")

                result = site.needFile(path_parts["inner_path"], priority=5)  # Wait until file downloads
                if result:
                    return self.actionFile(file_path, header_length=header_length)
                else:
                    self.log.debug("File not found: %s" % path_parts["inner_path"])
                    # Site larger than allowed, re-add wrapper nonce to allow reload
                    if site.settings.get("size", 0) > site.getSizeLimit() * 1024 * 1024:
                        self.server.wrapper_nonces.append(self.get.get("wrapper_nonce"))
                    return self.error404(path_parts["inner_path"])

        else:  # Bad url
            return self.error404(path)

    # Serve a media for ui
    def actionUiMedia(self, path):
        match = re.match("/uimedia/(?P<inner_path>.*)", path)
        if match:  # Looks like a valid path
            file_path = "src/Ui/media/%s" % match.group("inner_path")
            allowed_dir = os.path.abspath("src/Ui/media")  # Only files within data/sitehash allowed
            if ".." in file_path or not os.path.dirname(os.path.abspath(file_path)).startswith(allowed_dir):
                # File not in allowed path
                return self.error403()
            else:
                if config.debug and match.group("inner_path").startswith("all."):
                    # If debugging merge *.css to all.css and *.js to all.js
                    from Debug import DebugMedia
                    DebugMedia.merge(file_path)
                return self.actionFile(file_path, header_length=False)  # Dont's send site to allow plugins append content
        else:  # Bad url
            return self.error400()

    # Stream a file to client
    def actionFile(self, file_path, block_size=64 * 1024, send_header=True, header_length=True):
        if os.path.isfile(file_path):
            # Try to figure out content type by extension
            content_type = self.getContentType(file_path)

            # TODO: Dont allow external access: extra_headers=
            # [("Content-Security-Policy", "default-src 'unsafe-inline' data: http://localhost:43110 ws://localhost:43110")]
            range = self.env.get("HTTP_RANGE")
            range_start = None
            if send_header:
                extra_headers = {}
                file_size = os.path.getsize(file_path)
                extra_headers["Accept-Ranges"] = "bytes"
                if header_length:
                    extra_headers["Content-Length"] = str(file_size)
                if range:
                    range_start = int(re.match(".*?([0-9]+)", range).group(1))
                    if re.match(".*?-([0-9]+)", range):
                        range_end = int(re.match(".*?-([0-9]+)", range).group(1)) + 1
                    else:
                        range_end = file_size
                    extra_headers["Content-Length"] = str(range_end - range_start)
                    extra_headers["Content-Range"] = "bytes %s-%s/%s" % (range_start, range_end - 1, file_size)
                if range:
                    status = 206
                else:
                    status = 200
                self.sendHeader(status, content_type=content_type, extra_headers=extra_headers.items())
            if self.env["REQUEST_METHOD"] != "OPTIONS":
                file = open(file_path, "rb")
                if range_start:
                    file.seek(range_start)
                while 1:
                    try:
                        block = file.read(block_size)
                        if block:
                            yield block
                        else:
                            raise StopIteration
                    except StopIteration:
                        file.close()
                        break
        else:  # File not exists
            yield self.error404(file_path)

    # On websocket connection
    def actionWebsocket(self):
        ws = self.env.get("wsgi.websocket")
        if ws:
            wrapper_key = self.get["wrapper_key"]
            # Find site by wrapper_key
            site = None
            for site_check in self.server.sites.values():
                if site_check.settings["wrapper_key"] == wrapper_key:
                    site = site_check

            if site:  # Correct wrapper key
                user = self.getCurrentUser()
                if not user:
                    self.log.error("No user found")
                    return self.error403()
                ui_websocket = UiWebsocket(ws, site, self.server, user, self)
                site.websockets.append(ui_websocket)  # Add to site websockets to allow notify on events
                ui_websocket.start()
                for site_check in self.server.sites.values():
                    # Remove websocket from every site (admin sites allowed to join other sites event channels)
                    if ui_websocket in site_check.websockets:
                        site_check.websockets.remove(ui_websocket)
                return "Bye."
            else:  # No site found by wrapper key
                self.log.error("Wrapper key not found: %s" % wrapper_key)
                return self.error403()
        else:
            self.start_response("400 Bad Request", [])
            return "Not a websocket!"

    # Debug last error
    def actionDebug(self):
        # Raise last error from DebugHook
        import sys
        last_error = sys.modules["main"].DebugHook.last_error
        if last_error:
            raise last_error[0], last_error[1], last_error[2]
        else:
            self.sendHeader()
            return "No error! :)"

    # Just raise an error to get console
    def actionConsole(self):
        import sys
        sites = self.server.sites
        main = sys.modules["main"]
        def bench(code, times=100):
            sites = self.server.sites
            main = sys.modules["main"]
            s = time.time()
            for _ in range(times):
                back = eval(code, globals(), locals())
            return ["%s run: %.3fs" % (times, time.time() - s), back]
        raise Exception("Here is your console")

    # - Tests -

    def actionTestStream(self):
        self.sendHeader()
        yield " " * 1080  # Overflow browser's buffer
        yield "He"
        time.sleep(1)
        yield "llo!"
        # yield "Running websockets: %s" % len(self.server.websockets)
        # self.server.sendMessage("Hello!")

    # - Errors -

    # Send bad request error
    def error400(self, message=""):
        self.sendHeader(400)
        return self.formatError("Bad Request", message)

    # You are not allowed to access this
    def error403(self, message="", details=True):
        self.sendHeader(403)
        self.log.debug("Error 403: %s" % message)
        return self.formatError("Forbidden", message, details=details)

    # Send file not found error
    def error404(self, path=""):
        self.sendHeader(404)
        return self.formatError("Not Found", cgi.escape(path.encode("utf8")), details=False)

    # Internal server error
    def error500(self, message=":("):
        self.sendHeader(500)
        return self.formatError("Server error", cgi.escape(message))

    def formatError(self, title, message, details=True):
        import sys
        import gevent

        if details:
            details = {key: val for key, val in self.env.items() if hasattr(val, "endswith") and "COOKIE" not in key}
            details["version_zeronet"] = "%s r%s" % (config.version, config.rev)
            details["version_python"] = sys.version
            details["version_gevent"] = gevent.__version__
            details["plugins"] = PluginManager.plugin_manager.plugin_names
            arguments = {key: val for key, val in vars(config.arguments).items() if "password" not in key}
            details["arguments"] = arguments
            return """
                <style>
                * { font-family: Consolas, Monospace; color: #333 }
                pre { padding: 10px; background-color: #EEE }
                </style>
                <h1>%s</h1>
                <h2>%s</h3>
                <h3>Please <a href="https://github.com/HelloZeroNet/ZeroNet/issues" target="_blank">report it</a> if you think this an error.</h3>
                <h4>Details:</h4>
                <pre>%s</pre>
            """ % (title, message, json.dumps(details, indent=4, sort_keys=True))
        else:
            return """
                <h1>%s</h1>
                <h2>%s</h3>
            """ % (title, message)


# - Reload for eaiser developing -
# def reload():
    # import imp, sys
    # global UiWebsocket
    # UiWebsocket = imp.load_source("UiWebsocket", "src/Ui/UiWebsocket.py").UiWebsocket
    # reload(sys.modules["User.UserManager"])
    # UserManager.reloadModule()
    # self.user = UserManager.user_manager.getCurrent()

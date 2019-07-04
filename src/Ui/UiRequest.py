import time
import re
import os
import mimetypes
import json
import html
import urllib

import gevent

from Config import config
from Site import SiteManager
from User import UserManager
from Plugin import PluginManager
from Ui.UiWebsocket import UiWebsocket
from Crypt import CryptHash
from util import helper

status_texts = {
    200: "200 OK",
    206: "206 Partial Content",
    400: "400 Bad Request",
    403: "403 Forbidden",
    404: "404 Not Found",
    500: "500 Internal Server Error",
}


class SecurityError(Exception):
    pass


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
        self.script_nonce = None  # Nonce for script tags in wrapper html

    def learnHost(self, host):
        self.server.allowed_hosts.add(host)
        self.server.log.info("Added %s as allowed host" % host)

    def isHostAllowed(self, host):
        if host in self.server.allowed_hosts:
            return True

        # Allow any IP address as they are not affected by DNS rebinding
        # attacks
        if helper.isIp(host):
            self.learnHost(host)
            return True

        if ":" in host and helper.isIp(host.rsplit(":", 1)[0]):  # Test without port
            self.learnHost(host)
            return True

        if self.isProxyRequest():  # Support for chrome extension proxy
            if self.server.site_manager.isDomain(host):
                return True
            else:
                return False

        return False

    # Call the request handler function base on path
    def route(self, path):
        # Restict Ui access by ip
        if config.ui_restrict and self.env['REMOTE_ADDR'] not in config.ui_restrict:
            return self.error403(details=False)

        # Check if host allowed to do request
        if not self.isHostAllowed(self.env.get("HTTP_HOST")):
            return self.error403("Invalid host: %s" % self.env.get("HTTP_HOST"), details=False)

        # Prepend .bit host for transparent proxy
        if self.server.site_manager.isDomain(self.env.get("HTTP_HOST")):
            path = re.sub("^/", "/" + self.env.get("HTTP_HOST") + "/", path)
        path = re.sub("^http://zero[/]+", "/", path)  # Remove begining http://zero/ for chrome extension
        path = re.sub("^http://", "/", path)  # Remove begining http for chrome extension .bit access

        # Sanitize request url
        path = path.replace("\\", "/")
        if "../" in path or "./" in path:
            return self.error403("Invalid path: %s" % path)

        if self.env["REQUEST_METHOD"] == "OPTIONS":
            if "/" not in path.strip("/"):
                content_type = self.getContentType("index.html")
            else:
                content_type = self.getContentType(path)

            extra_headers = {"Access-Control-Allow-Origin": "null"}

            self.sendHeader(content_type=content_type, extra_headers=extra_headers, noscript=True)
            return ""

        if path == "/":
            return self.actionIndex()
        elif path == "/favicon.ico":
            return self.actionFile("src/Ui/media/img/favicon.ico")
        # Internal functions
        elif "/ZeroNet-Internal/" in path:
            path = re.sub(".*?/ZeroNet-Internal/", "/", path)
            func = getattr(self, "action" + path.strip("/"), None)  # Check if we have action+request_path function
            if func:
                return func()
            else:
                return self.error404(path)
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
        # Wrapper-less static files
        elif path.startswith("/raw/"):
            return self.actionSiteMedia(path.replace("/raw", "/media", 1), header_noscript=True)

        elif path.startswith("/add/"):
            return self.actionSiteAdd()
        # Site media wrapper
        else:
            if self.get.get("wrapper_nonce"):
                if self.get["wrapper_nonce"] in self.server.wrapper_nonces:
                    self.server.wrapper_nonces.remove(self.get["wrapper_nonce"])
                    return self.actionSiteMedia("/media" + path)  # Only serve html files with frame
                else:
                    self.server.log.warning("Invalid wrapper nonce: %s" % self.get["wrapper_nonce"])
                    body = self.actionWrapper(path)
            else:
                body = self.actionWrapper(path)
            if body:
                return body
            else:
                func = getattr(self, "action" + path.strip("/"), None)  # Check if we have action+request_path function
                if func:
                    return func()
                else:
                    ret = self.error404(path)
                    return ret

    # The request is proxied by chrome extension or a transparent proxy
    def isProxyRequest(self):
        return self.env["PATH_INFO"].startswith("http://") or (self.server.allow_trans_proxy and self.server.site_manager.isDomain(self.env.get("HTTP_HOST")))

    def isWebSocketRequest(self):
        return self.env.get("HTTP_UPGRADE") == "websocket"

    def isAjaxRequest(self):
        return self.env.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"

    # Get mime by filename
    def getContentType(self, file_name):
        file_name = file_name.lower()
        ext = file_name.rsplit(".", 1)[-1]

        if ext == "css":  # Force correct css content type
            content_type = "text/css"
        elif ext == "js":  # Force correct javascript content type
            content_type = "text/javascript"
        elif ext == "json":  # Correct json header
            content_type = "application/json"
        elif ext in ("ttf", "woff", "otf", "woff2", "eot"):
            content_type = "application/font"
        else:
            content_type = mimetypes.guess_type(file_name)[0]

        if not content_type:
            content_type = "application/octet-stream"

        return content_type.lower()

    # Return: <dict> Posted variables
    def getPosted(self):
        if self.env['REQUEST_METHOD'] == "POST":
            return dict(urllib.parse.parse_qsl(
                self.env['wsgi.input'].readline().decode()
            ))
        else:
            return {}

    # Return: <dict> Cookies based on self.env
    def getCookies(self):
        raw_cookies = self.env.get('HTTP_COOKIE')
        if raw_cookies:
            cookies = urllib.parse.parse_qsl(raw_cookies)
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

    def getRequestUrl(self):
        if self.isProxyRequest():
            if self.env["PATH_INFO"].startswith("http://zero/"):
                return self.env["PATH_INFO"]
            else:  # Add http://zero to direct domain access
                return self.env["PATH_INFO"].replace("http://", "http://zero/", 1)
        else:
            return self.env["wsgi.url_scheme"] + "://" + self.env["HTTP_HOST"] + self.env["PATH_INFO"]

    def getReferer(self):
        referer = self.env.get("HTTP_REFERER")
        if referer and self.isProxyRequest() and not referer.startswith("http://zero/"):
            return referer.replace("http://", "http://zero/", 1)
        else:
            return referer

    def isScriptNonceSupported(self):
        user_agent = self.env.get("HTTP_USER_AGENT")
        if "Edge/" in user_agent:
            is_script_nonce_supported = False
        elif "Safari/" in user_agent and "Chrome/" not in user_agent:
            is_script_nonce_supported = False
        else:
            is_script_nonce_supported = True
        return is_script_nonce_supported

    # Send response headers
    def sendHeader(self, status=200, content_type="text/html", noscript=False, allow_ajax=False, script_nonce=None, extra_headers=[]):
        headers = {}
        headers["Version"] = "HTTP/1.1"
        headers["Connection"] = "Keep-Alive"
        headers["Keep-Alive"] = "max=25, timeout=30"
        headers["X-Frame-Options"] = "SAMEORIGIN"
        if content_type != "text/html" and self.env.get("HTTP_REFERER") and self.isSameOrigin(self.getReferer(), self.getRequestUrl()):
            headers["Access-Control-Allow-Origin"] = "*"  # Allow load font files from css
        if content_type == "text/javascript" and not self.env.get("HTTP_REFERER"):
            headers["Access-Control-Allow-Origin"] = "*"  # Allow loading JavaScript modules in Chrome

        if noscript:
            headers["Content-Security-Policy"] = "default-src 'none'; sandbox allow-top-navigation allow-forms; img-src 'self'; font-src 'self'; media-src 'self'; style-src 'self' 'unsafe-inline';"
        elif script_nonce and self.isScriptNonceSupported():
            headers["Content-Security-Policy"] = "default-src 'none'; script-src 'nonce-{0}'; img-src 'self'; style-src 'self' 'unsafe-inline'; connect-src *; frame-src 'self'".format(script_nonce)

        if allow_ajax:
            headers["Access-Control-Allow-Origin"] = "null"

        if self.env["REQUEST_METHOD"] == "OPTIONS":
            # Allow json access
            headers["Access-Control-Allow-Headers"] = "Origin, X-Requested-With, Content-Type, Accept, Cookie, Range"
            headers["Access-Control-Allow-Credentials"] = "true"

        if content_type == "text/html":
            content_type = "text/html; charset=utf-8"
        if content_type == "text/plain":
            content_type = "text/plain; charset=utf-8"

        # Download instead of display file types that can be dangerous
        if re.findall("/svg|/xml|/x-shockwave-flash|/pdf", content_type):
            headers["Content-Disposition"] = "attachment"

        cacheable_type = (
            content_type == "text/css" or content_type.startswith("image") or content_type.startswith("video") or
            self.env["REQUEST_METHOD"] == "OPTIONS" or content_type == "application/javascript"
        )

        if status in (200, 206) and cacheable_type:  # Cache Css, Js, Image files for 10min
            headers["Cache-Control"] = "public, max-age=600"  # Cache 10 min
        else:
            headers["Cache-Control"] = "no-cache, no-store, private, must-revalidate, max-age=0"  # No caching at all
        headers["Content-Type"] = content_type
        headers.update(extra_headers)
        return self.start_response(status_texts[status], list(headers.items()))

    # Renders a template
    def render(self, template_path, *args, **kwargs):
        template = open(template_path, encoding="utf8").read()
        for key, val in list(kwargs.items()):
            template = template.replace("{%s}" % key, "%s" % val)
        return template.encode("utf8")

    # - Actions -

    # Redirect to an url
    def actionRedirect(self, url):
        self.start_response('301 Redirect', [('Location', str(url))])
        yield b"Location changed: " + url.encode("utf8")

    def actionIndex(self):
        return self.actionRedirect("/" + config.homepage)

    # Render a file from media with iframe site wrapper
    def actionWrapper(self, path, extra_headers=None):
        if not extra_headers:
            extra_headers = {}
        script_nonce = self.getScriptNonce()

        match = re.match(r"/(?P<address>[A-Za-z0-9\._-]+)(?P<inner_path>/.*|$)", path)
        just_added = False
        if match:
            address = match.group("address")
            inner_path = match.group("inner_path").lstrip("/")

            if not inner_path or path.endswith("/"):  # It's a directory
                content_type = self.getContentType("index.html")
            else:  # It's a file
                content_type = self.getContentType(inner_path)

            is_html_file = "html" in content_type or "xhtml" in content_type

            if not is_html_file:
                return self.actionSiteMedia("/media" + path)  # Serve non-html files without wrapper

            if self.isAjaxRequest():
                return self.error403("Ajax request not allowed to load wrapper")  # No ajax allowed on wrapper

            if self.isWebSocketRequest():
                return self.error403("WebSocket request not allowed to load wrapper")  # No websocket

            if "text/html" not in self.env.get("HTTP_ACCEPT", ""):
                return self.error403("Invalid Accept header to load wrapper")
            if "prefetch" in self.env.get("HTTP_X_MOZ", "") or "prefetch" in self.env.get("HTTP_PURPOSE", ""):
                return self.error403("Prefetch not allowed to load wrapper")

            site = SiteManager.site_manager.get(address)

            if site and site.content_manager.contents.get("content.json"):
                title = site.content_manager.contents["content.json"]["title"]
            else:
                title = "Loading %s..." % address
                site = SiteManager.site_manager.get(address)
                if site:  # Already added, but not downloaded
                    if time.time() - site.announcer.time_last_announce > 5:
                        site.log.debug("Reannouncing site...")
                        gevent.spawn(site.update, announce=True)
                else:  # If not added yet
                    site = SiteManager.site_manager.need(address)
                    just_added = True

                if not site:
                    return False

            self.sendHeader(extra_headers=extra_headers, script_nonce=script_nonce)

            min_last_announce = (time.time() - site.announcer.time_last_announce) / 60
            if min_last_announce > 60 and site.isServing() and not just_added:
                site.log.debug("Site requested, but not announced recently (last %.0fmin ago). Updating..." % min_last_announce)
                gevent.spawn(site.update, announce=True)

            return iter([self.renderWrapper(site, path, inner_path, title, extra_headers, script_nonce=script_nonce)])
            # Make response be sent at once (see https://github.com/HelloZeroNet/ZeroNet/issues/1092)

        else:  # Bad url
            return False

    def getSiteUrl(self, address):
        if self.isProxyRequest():
            return "http://zero/" + address
        else:
            return "/" + address

    def processQueryString(self, site, query_string):
        match = re.search("zeronet_peers=(.*?)(&|$)", query_string)
        if match:
            query_string = query_string.replace(match.group(0), "")
            num_added = 0
            for peer in match.group(1).split(","):
                if not re.match(".*?:[0-9]+$", peer):
                    continue
                ip, port = peer.rsplit(":", 1)
                if site.addPeer(ip, int(port), source="query_string"):
                    num_added += 1
            site.log.debug("%s peers added by query string" % num_added)

        return query_string

    def renderWrapper(self, site, path, inner_path, title, extra_headers, show_loadingscreen=None, script_nonce=None):
        file_inner_path = inner_path
        if not file_inner_path:
            file_inner_path = "index.html"  # If inner path defaults to index.html

        if file_inner_path.endswith("/"):
            file_inner_path = file_inner_path + "index.html"

        address = re.sub("/.*", "", path.lstrip("/"))
        if self.isProxyRequest() and (not path or "/" in path[1:]):
            if self.env["HTTP_HOST"] == "zero":
                root_url = "/" + address + "/"
                file_url = "/" + address + "/" + inner_path
            else:
                file_url = "/" + inner_path
                root_url = "/"

        else:
            file_url = "/" + address + "/" + inner_path
            root_url = "/" + address + "/"

        # Wrapper variable inits
        body_style = ""
        meta_tags = ""
        postmessage_nonce_security = "false"

        wrapper_nonce = self.getWrapperNonce()
        inner_query_string = self.processQueryString(site, self.env.get("QUERY_STRING", ""))

        if inner_query_string:
            inner_query_string = "?%s&wrapper_nonce=%s" % (inner_query_string, wrapper_nonce)
        elif "?" in inner_path:
            inner_query_string = "&wrapper_nonce=%s" % wrapper_nonce
        else:
            inner_query_string = "?wrapper_nonce=%s" % wrapper_nonce

        if self.isProxyRequest():  # Its a remote proxy request
            if self.env["REMOTE_ADDR"] == "127.0.0.1":  # Local client, the server address also should be 127.0.0.1
                server_url = "http://127.0.0.1:%s" % self.env["SERVER_PORT"]
            else:  # Remote client, use SERVER_NAME as server's real address
                server_url = "http://%s:%s" % (self.env["SERVER_NAME"], self.env["SERVER_PORT"])
            homepage = "http://zero/" + config.homepage
        else:  # Use relative path
            server_url = ""
            homepage = "/" + config.homepage

        user = self.getCurrentUser()
        if user:
            theme = user.settings.get("theme", "light")
        else:
            theme = "light"

        themeclass = "theme-%-6s" % re.sub("[^a-z]", "", theme)

        if site.content_manager.contents.get("content.json"):  # Got content.json
            content = site.content_manager.contents["content.json"]
            if content.get("background-color"):
                background_color = content.get("background-color-%s" % theme, content["background-color"])
                body_style += "background-color: %s;" % html.escape(background_color)
            if content.get("viewport"):
                meta_tags += '<meta name="viewport" id="viewport" content="%s">' % html.escape(content["viewport"])
            if content.get("favicon"):
                meta_tags += '<link rel="icon" href="%s%s">' % (root_url, html.escape(content["favicon"]))
            if content.get("postmessage_nonce_security"):
                postmessage_nonce_security = "true"

        sandbox_permissions = ""

        if "NOSANDBOX" in site.settings["permissions"]:
            sandbox_permissions += " allow-same-origin"

        if show_loadingscreen is None:
            show_loadingscreen = not site.storage.isFile(file_inner_path)

        return self.render(
            "src/Ui/template/wrapper.html",
            server_url=server_url,
            inner_path=inner_path,
            file_url=re.escape(file_url),
            file_inner_path=re.escape(file_inner_path),
            address=site.address,
            title=html.escape(title),
            body_style=body_style,
            meta_tags=meta_tags,
            query_string=re.escape(inner_query_string),
            wrapper_key=site.settings["wrapper_key"],
            ajax_key=site.settings["ajax_key"],
            wrapper_nonce=wrapper_nonce,
            postmessage_nonce_security=postmessage_nonce_security,
            permissions=json.dumps(site.settings["permissions"]),
            show_loadingscreen=json.dumps(show_loadingscreen),
            sandbox_permissions=sandbox_permissions,
            rev=config.rev,
            lang=config.language,
            homepage=homepage,
            themeclass=themeclass,
            script_nonce=script_nonce
        )

    # Create a new wrapper nonce that allows to get one html file without the wrapper
    def getWrapperNonce(self):
        wrapper_nonce = CryptHash.random()
        self.server.wrapper_nonces.append(wrapper_nonce)
        return wrapper_nonce

    def getScriptNonce(self):
        if not self.script_nonce:
            self.script_nonce = CryptHash.random(encoding="base64")

        return self.script_nonce

    # Create a new wrapper nonce that allows to get one site
    def getAddNonce(self):
        add_nonce = CryptHash.random()
        self.server.add_nonces.append(add_nonce)
        return add_nonce

    def isSameOrigin(self, url_a, url_b):
        if not url_a or not url_b:
            return False
        origin_a = re.sub("http[s]{0,1}://(.*?/.*?/).*", "\\1", url_a)
        origin_b = re.sub("http[s]{0,1}://(.*?/.*?/).*", "\\1", url_b)
        return origin_a == origin_b

    # Return {address: 1Site.., inner_path: /data/users.json} from url path
    def parsePath(self, path):
        path = path.replace("\\", "/")
        path = path.replace("/index.html/", "/")  # Base Backward compatibility fix
        if path.endswith("/"):
            path = path + "index.html"

        if "../" in path or "./" in path:
            raise SecurityError("Invalid path")

        match = re.match(r"/media/(?P<address>[A-Za-z0-9]+[A-Za-z0-9\._-]+)(?P<inner_path>/.*|$)", path)
        if match:
            path_parts = match.groupdict()
            path_parts["request_address"] = path_parts["address"]  # Original request address (for Merger sites)
            path_parts["inner_path"] = path_parts["inner_path"].lstrip("/")
            if not path_parts["inner_path"]:
                path_parts["inner_path"] = "index.html"
            return path_parts
        else:
            return None

    # Serve a media for site
    def actionSiteMedia(self, path, header_length=True, header_noscript=False):
        try:
            path_parts = self.parsePath(path)
        except SecurityError as err:
            return self.error403(err)

        if not path_parts:
            return self.error404(path)

        address = path_parts["address"]
        file_path = "%s/%s/%s" % (config.data_dir, address, path_parts["inner_path"])

        if config.debug and file_path.split("/")[-1].startswith("all."):
            # If debugging merge *.css to all.css and *.js to all.js
            site = self.server.sites.get(address)
            if site and site.settings["own"]:
                from Debug import DebugMedia
                DebugMedia.merge(file_path)

        if not address or address == ".":
            return self.error403(path_parts["inner_path"])

        header_allow_ajax = False
        if self.get.get("ajax_key"):
            site = SiteManager.site_manager.get(path_parts["request_address"])
            if self.get["ajax_key"] == site.settings["ajax_key"]:
                header_allow_ajax = True
            else:
                return self.error403("Invalid ajax_key")

        file_size = helper.getFilesize(file_path)

        if file_size is not None:
            return self.actionFile(file_path, header_length=header_length, header_noscript=header_noscript, header_allow_ajax=header_allow_ajax, file_size=file_size, path_parts=path_parts)

        elif os.path.isdir(file_path):  # If this is actually a folder, add "/" and redirect
            if path_parts["inner_path"]:
                return self.actionRedirect("./%s/" % path_parts["inner_path"].split("/")[-1])
            else:
                return self.actionRedirect("./%s/" % path_parts["address"])

        else:  # File not exists, try to download
            if address not in SiteManager.site_manager.sites:  # Only in case if site already started downloading
                return self.actionSiteAddPrompt(path)

            site = SiteManager.site_manager.need(address)

            if path_parts["inner_path"].endswith("favicon.ico"):  # Default favicon for all sites
                return self.actionFile("src/Ui/media/img/favicon.ico")

            result = site.needFile(path_parts["inner_path"], priority=15)  # Wait until file downloads
            if result:
                file_size = helper.getFilesize(file_path)
                return self.actionFile(file_path, header_length=header_length, header_noscript=header_noscript, header_allow_ajax=header_allow_ajax, file_size=file_size, path_parts=path_parts)
            else:
                self.log.debug("File not found: %s" % path_parts["inner_path"])
                return self.error404(path_parts["inner_path"])

    # Serve a media for ui
    def actionUiMedia(self, path):
        match = re.match("/uimedia/(?P<inner_path>.*)", path)
        if match:  # Looks like a valid path
            file_path = "src/Ui/media/%s" % match.group("inner_path")
            allowed_dir = os.path.abspath("src/Ui/media")  # Only files within data/sitehash allowed
            if "../" in file_path or not os.path.dirname(os.path.abspath(file_path)).startswith(allowed_dir):
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

    def actionSiteAdd(self):
        post = dict(urllib.parse.parse_qsl(self.env["wsgi.input"].read()))
        if post["add_nonce"] not in self.server.add_nonces:
            return self.error403("Add nonce error.")
        self.server.add_nonces.remove(post["add_nonce"])
        SiteManager.site_manager.need(post["address"])
        return self.actionRedirect(post["url"])

    def actionSiteAddPrompt(self, path):
        path_parts = self.parsePath(path)
        if not path_parts or not self.server.site_manager.isAddress(path_parts["address"]):
            return self.error404(path)

        self.sendHeader(200, "text/html", noscript=True)
        template = open("src/Ui/template/site_add.html").read()
        template = template.replace("{url}", html.escape(self.env["PATH_INFO"]))
        template = template.replace("{address}", path_parts["address"])
        template = template.replace("{add_nonce}", self.getAddNonce())
        return template

    def replaceHtmlVariables(self, block, path_parts):
        user = self.getCurrentUser()
        themeclass = "theme-%-6s" % re.sub("[^a-z]", "", user.settings.get("theme", "light"))
        block = block.replace(b"{themeclass}", themeclass.encode("utf8"))

        if path_parts:
            site = self.server.sites.get(path_parts.get("address"))
            if site.settings["own"]:
                modified = int(time.time())
            else:
                modified = int(site.content_manager.contents["content.json"]["modified"])
            block = block.replace(b"{site_modified}", str(modified).encode("utf8"))

        return block

    # Stream a file to client
    def actionFile(self, file_path, block_size=64 * 1024, send_header=True, header_length=True, header_noscript=False, header_allow_ajax=False, file_size=None, file_obj=None, path_parts=None):
        file_name = os.path.basename(file_path)

        if file_size is None:
            file_size = helper.getFilesize(file_path)

        if file_size is not None:
            # Try to figure out content type by extension
            content_type = self.getContentType(file_name)

            range = self.env.get("HTTP_RANGE")
            range_start = None

            is_html_file = file_name.endswith(".html")
            if is_html_file:
                header_length = False

            if send_header:
                extra_headers = {}
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
                self.sendHeader(status, content_type=content_type, noscript=header_noscript, allow_ajax=header_allow_ajax, extra_headers=extra_headers)
            if self.env["REQUEST_METHOD"] != "OPTIONS":
                if not file_obj:
                    file_obj = open(file_path, "rb")

                if range_start:
                    file_obj.seek(range_start)
                while 1:
                    try:
                        block = file_obj.read(block_size)
                        if is_html_file:
                            block = self.replaceHtmlVariables(block, path_parts)
                        if block:
                            yield block
                        else:
                            raise StopIteration
                    except StopIteration:
                        file_obj.close()
                        break
        else:  # File not exists
            for part in self.error404(str(file_path)):
                yield part

    # On websocket connection
    def actionWebsocket(self):
        ws = self.env.get("wsgi.websocket")
        if ws:
            wrapper_key = self.get["wrapper_key"]
            # Find site by wrapper_key
            site = None
            for site_check in list(self.server.sites.values()):
                if site_check.settings["wrapper_key"] == wrapper_key:
                    site = site_check

            if site:  # Correct wrapper key
                try:
                    user = self.getCurrentUser()
                except Exception as err:
                    ws.send(json.dumps({"error": "Error in data/user.json: %s" % err}))
                    return self.error500("Error in data/user.json: %s" % err)
                if not user:
                    ws.send(json.dumps({"error": "No user found"}))
                    return self.error403("No user found")
                ui_websocket = UiWebsocket(ws, site, self.server, user, self)
                site.websockets.append(ui_websocket)  # Add to site websockets to allow notify on events
                self.server.websockets.append(ui_websocket)
                ui_websocket.start()
                self.server.websockets.remove(ui_websocket)
                for site_check in list(self.server.sites.values()):
                    # Remove websocket from every site (admin sites allowed to join other sites event channels)
                    if ui_websocket in site_check.websockets:
                        site_check.websockets.remove(ui_websocket)
                return "Bye."
            else:  # No site found by wrapper key
                ws.send(json.dumps({"error": "Wrapper key not found: %s" % wrapper_key}))
                return self.error403("Wrapper key not found: %s" % wrapper_key)
        else:
            self.start_response("400 Bad Request", [])
            return [b"Not a websocket request!"]

    # Debug last error
    def actionDebug(self):
        # Raise last error from DebugHook
        import main
        last_error = main.DebugHook.last_error
        if last_error:
            raise last_error[0](last_error[1]).with_traceback(last_error[2])
        else:
            self.sendHeader()
            return [b"No error! :)"]

    # Just raise an error to get console
    def actionConsole(self):
        import sys
        sites = self.server.sites
        main = sys.modules["main"]

        def bench(code, times=100, init=None):
            sites = self.server.sites
            main = sys.modules["main"]
            s = time.time()
            if init:
                eval(compile(init, '<string>', 'exec'), globals(), locals())
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
        self.sendHeader(400, noscript=True)
        self.log.error("Error 400: %s" % message)
        return self.formatError("Bad Request", message)

    # You are not allowed to access this
    def error403(self, message="", details=True):
        self.sendHeader(403, noscript=True)
        self.log.error("Error 403: %s" % message)
        return self.formatError("Forbidden", message, details=details)

    # Send file not found error
    def error404(self, path=""):
        self.sendHeader(404, noscript=True)
        return self.formatError("Not Found", path, details=False)

    # Internal server error
    def error500(self, message=":("):
        self.sendHeader(500, noscript=True)
        self.log.error("Error 500: %s" % message)
        return self.formatError("Server error", message)

    @helper.encodeResponse
    def formatError(self, title, message, details=True):
        import sys
        import gevent

        if details and config.debug:
            details = {key: val for key, val in list(self.env.items()) if hasattr(val, "endswith") and "COOKIE" not in key}
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
                <h3>Please <a href="https://github.com/HelloZeroNet/ZeroNet/issues" target="_top">report it</a> if you think this an error.</h3>
                <h4>Details:</h4>
                <pre>%s</pre>
            """ % (title, html.escape(message), html.escape(json.dumps(details, indent=4, sort_keys=True)))
        else:
            return """
                <h1>%s</h1>
                <h2>%s</h3>
            """ % (title, html.escape(message))

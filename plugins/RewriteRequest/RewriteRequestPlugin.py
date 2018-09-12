import re
import sys
import logging
import base64
import urllib2
from util import SafeRe, helper

from Plugin import PluginManager

# Loading TranslateSite before Zeroname because it breaks on domain names otherwise
# UiWSGIHandler error: AttributeError: 'NoneType' object has no attribute 'content_manager' in UiServer.py line 40 > pywsgi.py line 923 > pywsgi.py line 907 > TranslateSitePlugin.py line 39
try:
    import TranslateSite
except ImportError:
    pass

try:
    import Zeroname
except ImportError:
    # The Zeroname plugin is disabled
    pass

from Site import SiteManager

allow_reload = False

log = logging.getLogger("RewriteRequestPlugin")

# NOTE: This function is the uglyiest and should be rewritten
# This function is basically the same as doing match.expand(replacement) from the general re module
# It is expanded to support the special syntax $U0 or $<date>
def expand_match(match, replacement):
    # Small letter is for decoding, Caps are for encoding
    # b stands for base64, u for url
    applicable_function = {
        "b": lambda s: base64.urlsafe_b64decode(s).decode('utf8'),
        "B": lambda s: base64.urlsafe_b64encode(s.encode('utf8')),
        "u": lambda s: urllib2.unquote(s).decode('utf8'),
        "U": lambda s: urllib2.quote(s.encode('utf8'))
    }

    def replace_group (m):
        if m[0] == "\\$":
            return "$"
        elif m[2] != None:
            return applicable_function.get(m[1], lambda x: x)(match.group(int(m[2])))
        elif m[4] != None:
            return applicable_function.get(m[3], lambda x: x)(match.group(m[4]))
        return ""
    return re.sub(r'(\\\$|\$([bBuU])?([0-9]+)|\$([bBuU])?\<([^\>]+)\>)', lambda x: replace_group(x.groups()), replacement)

# Returns request_path, query_string and return_code as changed by the rewrite_rules
def rewrite_request(rewrite_rules, file_exists, request_path, query_string, return_code=200, site_log=None):
    # Rewrite Rules Length check
    if len(rewrite_rules) > 100:
        if site_log:
            site_log.error("The site has more that a hundred rewrite rules.")
        return (request_path, query_string, 500)
        
    old_request_path, old_query_string = request_path, query_string
    rewritten_finished = False
    remaining_rewrite_attempt = 100  # Max times a string is attempted to be rewritten
    while not rewritten_finished and remaining_rewrite_attempt > 0:
        for rrule in rewrite_rules:
            replacement = rrule.get("replace", request_path)
            replacement_qs = rrule.get("replace_query_string", query_string)
            replacement_whole = rrule.get("replace_whole", request_path + "?" + query_string)

            if "match_whole" in rrule:
                match = SafeRe.match(rrule["match_whole"], request_path + "?" + query_string)
            else:
                match = SafeRe.match(rrule["match"], request_path)
            if match:
                if "file_exists" in rrule and not file_exists(expand_match(match, rrule["file_exists"])):
                    continue
                if site_log:
                    site_log.debug("Path %s matched rewrite rule %s and expansion is %s with query string %s" % (request_path, rrule["match"], expand_match(match, replacement), expand_match(match, replacement_qs)))
                if "replace_whole" in rrule:
                    request_whole = expand_match(match, replacement_whole)
                    request_path, query_string = request_whole.split("?")[0:2]
                else:
                    request_path = expand_match(match, replacement)
                    query_string = expand_match(match, replacement_qs)
                if rrule.get("terminate", False):
                    rewritten_finished = True
                if "return_code" in rrule:
                    return_code = rrule["return_code"]
                break
        else:
            # No rule matches current URL, so we return it unchanged
            return (old_request_path, old_query_string, return_code)
        remaining_rewrite_attempt -= 1
    if not rewritten_finished and remaining_rewrite_attempt <= 0:
        if site_log:
            site_log.error("Max rewriting attempt exceeded for url %s" % inner_path)
        return (old_request_path, old_query_string, 500)
    return (request_path, query_string, return_code)

# Checks if a file should exists according to the various content.json
def file_exists (site, inner_path):
    for content_path, content in site.content_manager.contents.iteritems():
        for relative_path, _ in content.get("files", {}).items() + content.get("files_optional", {}).items():
            if inner_path == helper.getDirname(content_path) + relative_path:
                return True
    return False

@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def route(self, path):
        is_valid_site_address = lambda x: re.match("^1[A-Za-z0-9]+$", x) or ("Zeroname" in sys.modules and re.match("^[A-Za-z0-9\-\_\.]+?\.bit$", x))

        match = re.match(r"^(?P<ignore>/media|/raw)?/(?P<site_address>[^\/]+)/(?P<inner_path>.*)$", path)
        if match and is_valid_site_address(match.group('site_address')):
            ignore = match.group('ignore') if match.group('ignore') else ""
            site_address = match.group('site_address')
            inner_path = match.group('inner_path')
            log.log(5, "Intercepted request to %s decomposed as ignore: %s, site: %s, inner_path: %s" % (path, ignore, site_address, inner_path))
            site = SiteManager.site_manager.get(site_address)
            if not site:
                site = SiteManager.site_manager.need(site_address)
                if not site:
                    log.log(5, "Request to %s: site not available, using default route method." % path)
                    return super(UiRequestPlugin, self).route(path)

            # Use and execute rewrite rules if found in the content.json
            rewrite_rules = site.content_manager.contents.get("content.json", {}).get("rewrite_rules")
            if rewrite_rules:
                query_string = self.env.get("QUERY_STRING")
                inner_path, query_string, return_code = rewrite_request(rewrite_rules, lambda path: file_exists(site, path), inner_path, query_string, site_log=site.log)
                self.env["QUERY_STRING"] = query_string
                self.response_status = return_code
                path = ignore + "/" + site_address + "/" + inner_path
        return super(UiRequestPlugin, self).route(path)

    def sendHeader(self, status=200, **kwargs):
        response_status = getattr(self, "response_status", None)
        if response_status:
            status = response_status
            delattr(self, "response_status")
        return super(UiRequestPlugin, self).sendHeader(status, **kwargs)


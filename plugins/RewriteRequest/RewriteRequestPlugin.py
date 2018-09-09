import re
import sys
import logging

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

def expand_match(match, replacement):
    def replace_group (m):
        if m[0] == "\\$":
            return "$"
        elif m[1] != None:
            return match.group(int(m[1]))
        elif m[2] != None:
            return match.group(m[2])
        return ""
    return re.sub(r'(\\\$|\$([0-9]+)|\$\<([^\>]+)\>)', lambda x: replace_group(x.groups()), replacement)

# Returns request_path, query_string and return_code as changed by the rewrite_rules
def rewrite_request(rewrite_rules, request_path, query_string, return_code=200, site_log=None):
    old_request_path, old_query_string = request_path, query_string
    rewritten_finished = False
    remaining_rewrite_attempt = 100  # Max times a string is attempted to be rewritten
    while not rewritten_finished and remaining_rewrite_attempt > 0:
        for rrule in rewrite_rules:
            replacement = rrule.get("replace", request_path)
            replacement_qs = rrule.get("replace_query_string", query_string)
            replacement_whole = rrule.get("replace_whole", request_path + "?" + query_string)

            if "match_whole" in rrule:
                match = re.match(rrule["match_whole"], request_path + "?" + query_string)
            else:
                match = re.match(rrule["match"], request_path)
            if match:
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
        remaining_rewrite_attempt -= 1
    if not rewritten_finished and remaining_rewrite_attempt <= 0:
        if site_log:
            site_log.error("Max rewriting attempt exceeded for url %s" % inner_path)
        return (old_request_path, old_query_string, 500)
    return (request_path, query_string, return_code)

@PluginManager.registerTo("UiRequest")
class UiRequestPlugin(object):
    def route(self, path):
        return super(UiRequestPlugin, self).route(path)
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
            rewrite_rules = site.content_manager.contents["content.json"].get("rewrite_rules")
            if rewrite_rules:
                query_string = self.env.get("QUERY_STRING")
                inner_path, query_string, return_code = rewrite_request(rewrite_rules, inner_path, query_string, site_log=site.log)
                self.env["QUERY_STRING"] = query_string
                self.response_status = return_code
                path = ignore + "/" + site_address + "/" + inner_path
        return super(UiRequestPlugin, self).route(path)

    def sendHeader(self, status=200, **kwargs):
        if hasattr(self, "response_status"):
            status = self.response_status
            delattr(self, "response_status")
        return super(UiRequestPlugin, self).sendHeader(status, **kwargs)


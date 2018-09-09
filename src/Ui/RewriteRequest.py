import re

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
                    site_log.debug("Path %s matched rewrite rule %s and expansion is %s with query string %s" % (inner_path, rrule["match"], expand_match(match, replacement), expand_match(match, replacement_qs)))
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


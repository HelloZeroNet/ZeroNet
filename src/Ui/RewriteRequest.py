import re

# TODO: Rewrite the expand match with $0, $1, ..., $<group>
# Returns request_path, query_string and return_code as changed by the rewrite_rules
def rewrite_request(rewrite_rules, request_path, query_string, return_code=200, site_log=None):
    old_request_path, old_query_string = request_path, query_string
    rewritten_finished = False
    remaining_rewrite_attempt = 100  # Max times a string is attempted to be rewritten
    while not rewritten_finished and remaining_rewrite_attempt > 0:
        for rrule in rewrite_rules:
            replacement = re.sub(r"\$", r"\\", rrule["replace"]) if rrule.get("replace") else request_path
            replacement_qs = re.sub(r"\$", r"\\", rrule["replace_query_string"]) if rrule.get("replace_query_string") else query_string
            replacement_whole = re.sub(r"\$", r"\\", rrule["replace_whole"]) if rrule.get("replace_whole") else request_path + "?" + query_string

            if "match_whole" in rrule:
                match = re.match(rrule["match_whole"], request_path + "?" + query_string)
            else:
                match = re.match(rrule["match"], request_path)
            if match:
                if site_log:
                    site_log.debug("Path %s matched rewrite rule %s and expansion is %s with query string %s" % (inner_path, rrule["match"], match.expand(replacement), match.expand(replacement_qs)))
                if "replace_whole" in rrule:
                    request_whole = match.expand(replacement_whole)
                    request_path, query_string = request_whole.split("?")[0:2]
                else:
                    request_path = match.expand(replacement)
                    query_string = match.expand(replacement_qs)
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


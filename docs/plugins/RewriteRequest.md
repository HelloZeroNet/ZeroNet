# Documentation for RewriteRequest Plugin - Basic URL Rewriting for Zites
This plugin implements an URL Rewriting Feature.
That allows Zites to have an internal redirect feature like the one that is used inside `.htaccess` files in "regular" web.

The current implementation allows:
- Standard redirects based on requested path and/or query string
- Changing the pages return code (e.g. to create customized error pages)
- urlsafe-base64 encode/decode and urlencode/urldecode matched URL parts
- Redirection if a certain file exists

## Contacts and Issues
```
Maintainer: Dario Balboni - trenta3@zeroid.bit
Issue report to: ZeroNet GitHub Repository - https://github.com/HelloZeroNet/ZeroNet/issues
```

## About current documentation
```
Last Updated: 10 September 2018
Regarding version: RewriteRequest v1.0.0
Documents: Basic URL Rewriting, Custom Error Codes, Whole Match, Encoding and Decoding
```

# Usage
The things that the Plugin reads are the key `rewrite_rules` under the Zite **main** `content.json` that serves as a configuration, and the keys `files` and `files_optional` in each `content.json` to check if a certain file exists.

* The value the key `rewrite_rules` must be a list of rules with pattern matches and substitutions.
* The rules will be tried in the given order.
* If none of the rules matches the current string, it will be returned unchanged.
* Each rule must have exactly one of the keys `match` and `match_whole`.
  The value of these must be a string describing a valid "`re`" regexp.
  
  If the key `match` is specified, the regex is matched against the URL part following the site address, not including the initial slash nor the query string.
  
  If the key `match_whole` is specified, the regex is matched against the URL part following the site address, not including the initial slash, postfixed with a "?" and the query string for the request.
* Each rule can have the keys `replace`, `replace_query_string` or the key `replace_whole`.
  
  `replace` is the replacement pattern for the pre-query string URL, `replace_query_string` is the replacement for the query string part, and `replace_whole` is the replacement for the whole URL plus query string and should contain a single "?" sign.
  
  If only one of `replace` or `replace_query_string` is specified, the other URL part remains unchanged.
  
  Each of the replacement pattern can contain the references to the matched groups:
  - `$0` is replaced with the whole matched string
  - `$n` is replaced with the n-th capturing group
  - `$<groupname>` is replaced with the named capturing group `groupname`
  
  Between the dollar sign and the rest of the reference, there can be a single letter, specifying how the captured group should be transformed:
  - No letter (e.g. `$3`): the captured group is returned unchanged
  - Uppercase letter `B` (e.g. `$B3`): the captured group is encoded in urlsafe-base64
  - Lowercase letter `b` (e.g. `$b<groupname>`): the captured group is decoded from urlsafe-base64
  - Uppercase letter `U` (e.g. `$U<groupname>`): the captured group is urlencoded
  - Lowercase letter `u` (e.g. `$u3`): the captured group is urldecoded
* Each rule can have the key `file_exists`, which is a replacement pattern.
  The pattern is replaced and if such a file exists, then the rule is applied, otherwise no.
* Each rule can have the key `return_code`, which is an integer and a valid HTTP status code.
  If the rule is matched, the HTTP status is changed to the one specified by it.
* Each rule can have the key `terminate`, which must have a boolean value.
  If the rule is matched and `terminate` is set to `true`, the rewriting is terminated and the resulting URL is returned.
  If `terminate` is not set, it defaults to `false`.

# Usage examples
## Semantic URLs / Pretty URLs
```json
"rewrite_rules": [
	{ "match": "index.html", "terminate": true },
	{ "match": "(js|css)/.*", "terminate": true },
	{ "match": "post/(?P<year>.+?)/(?P<month>.+?)/(?P<day>.+?)(/.*)?$", "replace": "post.html", "replace_query_string": "year=$<year>&month=$<month>&day=$<day>", "terminate": true },
	{ "match": ".*", "replace": "index.html", "replace_query_string": "redirected_from=$0", "terminate": true }
]
```

Request examples:
```
index.html --> index.html
index.html?a=5 --> index.html
js/secret.txt --> js/secret.txt
post/2018/09/10/post-title?a=3 --> post.html?year=2018&month=09&day=10
otherpage.html --> index.html?redirected_from=otherpage.html
```

## Custom "Not Found" error page
```json
"rewrite_rules": [
	{ "match": ".*", "file_exists": "$0", "terminate": true },
	{ "match": ".*", "replace": "404.html", "return_code": 404, "replace_query_string": "missing=$U0", "terminate": true }
]
```

And suppose the Zite has the files `index.html`, `404.html`, `css/style.css`, `js/Site.js`.

Request examples:
```
index.html?a=2 --> index.html?a=2
css/style.css --> css/style.css
robot.txt --> 404.html?missing=robot.txt (HTTP status 404)
css/Style.css --> 404.html?missing=css/Style.css (HTTP status 404)
```

# Caveats
- Only redirects internal to the same Zite are allowed, i.e. it is not possible to link to an another Zite.
  Since the displayed URL from the UI doesn't change, this could in fact allow malicious sites to trick users in vaious ways.
- Only regexps that conform to `src/util/SafeRe.py` are allowed to avoid possible ReDoS attacks.
  Please see [this relevant issue](https://github.com/HelloZeroNet/ZeroNet/issues/989).
- There can only be a maximum of 100 rewrite rules per site.
  If there are more, the original URL is accessed with a 500 HTTP status code.
- The regexp rewriting chain is terminated after 100 attempt.
  After such time, the original URL is accessed with a 500 HTTP status code.

  This ensures that every request terminates in a decent timing and rules out any possibility of non-termination as for example the rule:
  ```json
  "rewrite_rules": [
    { "match": "recursive/(.*)", "replace": "recursive/$1" }
  ]
  ```
  which would otherwise lead to an unterminated chain of rewrites of the form
  ```
  recursive/something --> recursive/something --> ...
  ```

# Internals
- The plugin patches the class `UiRequest` methods `route` and `sendHeader`.
- It has to load `Zeroname` before because it needs to get `Site` object for `.bit` domains.
- The url rewriting occurs in the function `RewriteRequestPlugin.py#rewrite_request`.
- Files existance is checked against every "contents" file, in the keys `files` and `files_optional`.

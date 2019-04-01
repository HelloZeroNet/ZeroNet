import os
import json
import logging
import inspect
import re
import html
import string
import Resources

from Config import config

translates = []


class EscapeProxy(dict):
    # Automatically escape the accessed string values
    def __getitem__(self, key):
        val = dict.__getitem__(self, key)
        if type(val) in (str, str):
            return html.escape(val)
        elif type(val) is dict:
            return EscapeProxy(val)
        elif type(val) is list:
            return EscapeProxy(enumerate(val))  # Convert lists to dict
        else:
            return val


class Translate(dict):
    def __init__(self, lang_pkg=None, lang=None):
        if not lang_pkg:
            from . import languages
        self.lang_pkg = lang_pkg if lang_pkg else languages
        self.lang = lang if lang else config.language
        self.setLanguage(self.lang)
        self.formatter = string.Formatter()

        if config.debug:
            # Auto reload FileRequest on change
            from Debug import DebugReloader
            DebugReloader.watcher.addCallback(self.load)

        translates.append(self)

    def setLanguage(self, lang):
        self.lang = re.sub("[^a-z-]", "", lang)
        self.lang_file = "%s.json" % lang
        self.load()

    def __repr__(self):
        return "<translate %s>" % self.lang

    def load_dict(self, data):
        dict.__init__(self, data)
        if len(data) == 0: # not sure if necessary, but keeping
            self.clear()

    def load(self):
        if self.lang == "en":
            self.load_dict({})
            return

        try:
            data = json.load(Resources.open_text(self.lang_pkg, self.lang_file))
            self.load_dict(data)
            logging.debug("Loaded translate file: %s/%s (%s entries)" % \
                    (self.lang_pkg.__name__, self.lang_file, len(data)))
        except FileNotFoundError:
            logging.debug("No translation file %s/%s" % \
                    (self.lang_pkg.__name__, self.lang_file))
            self.load_dict({})
        except Exception as err:
            logging.error("Error loading translate resource %s/%s: %s" % \
                    (self.lang_pkg.__name__, self.lang_file, err))
            self.load({})

    def format(self, s, kwargs, nested=False):
        kwargs["_"] = self
        if nested:
            back = self.formatter.vformat(s, [], kwargs)  # PY3 TODO: Change to format_map
            return self.formatter.vformat(back, [], kwargs)
        else:
            return self.formatter.vformat(s, [], kwargs)

    def formatLocals(self, s, nested=False):
        kwargs = inspect.currentframe().f_back.f_locals
        return self.format(s, kwargs, nested=nested)

    def __call__(self, s, kwargs=None, nested=False, escape=True):
        if not kwargs:
            kwargs = inspect.currentframe().f_back.f_locals
        if escape:
            kwargs = EscapeProxy(kwargs)
        return self.format(s, kwargs, nested=nested)

    def __missing__(self, key):
        return key

    def pluralize(self, value, single, multi):
        if value > 1:
            return self[single].format(value)
        else:
            return self[multi].format(value)

    def translateData(self, data, translate_table=None, mode="js"):
        if not translate_table:
            translate_table = self

        patterns = []
        for key, val in list(translate_table.items()):
            if key.startswith("_("):  # Problematic string: only match if called between _(" ") function
                key = key.replace("_(", "").replace(")", "").replace(", ", '", "')
                translate_table[key] = "|" + val
            patterns.append(re.escape(key))

        def replacer(match):
            target = translate_table[match.group(1)]
            if mode == "js":
                if target and target[0] == "|":  # Strict string match
                    if match.string[match.start() - 2] == "_":  # Only if the match if called between _(" ") function
                        return '"' + target[1:] + '"'
                    else:
                        return '"' + match.group(1) + '"'
                return '"' + target + '"'
            else:
                return match.group(0)[0] + target + match.group(0)[-1]

        if mode == "html":
            pattern = '[">](' + "|".join(patterns) + ')["<]'
        else:
            pattern = '"(' + "|".join(patterns) + ')"'
        data = re.sub(pattern, replacer, data)

        if mode == "html":
            data = data.replace("lang={lang}", "lang=%s" % self.lang)  # lang get parameter to .js file to avoid cache

        return data

translate = Translate()

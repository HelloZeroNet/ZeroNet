import os
import json
import logging
import inspect
import re
import html
import string

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
    def __init__(self, lang_dir=None, lang=None):
        if not lang_dir:
            lang_dir = "src/Translate/languages/"
        if not lang:
            lang = config.language
        self.lang = lang
        self.lang_dir = lang_dir
        self.setLanguage(lang)
        self.formatter = string.Formatter()

        if config.debug:
            # Auto reload FileRequest on change
            from Debug import DebugReloader
            DebugReloader.watcher.addCallback(self.load)

        translates.append(self)

    def setLanguage(self, lang):
        self.lang = re.sub("[^a-z-]", "", lang)
        self.lang_file = self.lang_dir + "%s.json" % lang
        self.load()

    def __repr__(self):
        return "<translate %s>" % self.lang

    def load(self):
        if self.lang == "en":
            data = {}
            dict.__init__(self, data)
            self.clear()
        elif os.path.isfile(self.lang_file):
            try:
                data = json.load(open(self.lang_file, encoding="utf8"))
                logging.debug("Loaded translate file: %s (%s entries)" % (self.lang_file, len(data)))
            except Exception as err:
                logging.error("Error loading translate file %s: %s" % (self.lang_file, err))
                data = {}
            dict.__init__(self, data)
        else:
            data = {}
            dict.__init__(self, data)
            self.clear()
            logging.debug("Translate file not exists: %s" % self.lang_file)

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

import logging
import re

log_level_raising_rules = []

def addLogLevelRaisingRule(rule, level=None):
    if level is None:
        level = logging.INFO
    log_level_raising_rules.append({
        "rule": rule,
        "level": level
    })

def matchLogLevelRaisingRule(name):
    for rule in log_level_raising_rules:
        if isinstance(rule["rule"], re.Pattern):
            if rule["rule"].search(name):
                return rule["level"]
        else:
            if rule["rule"] == name:
                return rule["level"]
    return None

class SelectiveLogger(logging.getLoggerClass()):
    def __init__(self, name, level=logging.NOTSET):
        return super().__init__(name, level)

    def raiseLevel(self, level):
        raised_level = matchLogLevelRaisingRule(self.name)
        if raised_level is not None:
            if level < raised_level:
                level = raised_level
        return level

    def isEnabledFor(self, level):
        level = self.raiseLevel(level)
        return super().isEnabledFor(level)

    def _log(self, level, msg, args, **kwargs):
        level = self.raiseLevel(level)
        return super()._log(level, msg, args, **kwargs)

logging.setLoggerClass(SelectiveLogger)

import re


class UnsafePatternError(Exception):
    pass


def isSafePattern(pattern):
    if len(pattern) > 255:
        raise UnsafePatternError("Pattern too long: %s characters" % len(pattern))

    unsafe_pattern_match = re.search("[^\.][\*\{\+]", pattern)  # Always should be "." before "*{+" characters to avoid ReDoS
    if unsafe_pattern_match:
        raise UnsafePatternError("Potentially unsafe part of the pattern: %s" % unsafe_pattern_match.group(0))
    return True


def match(pattern, *args, **kwargs):
    if isSafePattern(pattern):
        return re.match(pattern, *args, **kwargs)

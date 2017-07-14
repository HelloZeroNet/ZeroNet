import re


class UnsafePatternError(Exception):
    pass

cached_patterns = {}


def isSafePattern(pattern):
    if len(pattern) > 255:
        raise UnsafePatternError("Pattern too long: %s characters" % len(pattern))

    unsafe_pattern_match = re.search("[^\.][\*\{\+]", pattern)  # Always should be "." before "*{+" characters to avoid ReDoS
    if unsafe_pattern_match:
        raise UnsafePatternError("Potentially unsafe part of the pattern: %s" % unsafe_pattern_match.group(0))

    repetitions = re.findall("\.[\*\{\+]", pattern)
    if len(repetitions) >= 10:
        raise UnsafePatternError("More than 10 repetitions of %s" % repetitions[0])

    return True


def match(pattern, *args, **kwargs):
    cached_pattern = cached_patterns.get(pattern)
    if cached_pattern:
        return cached_pattern.match(*args, **kwargs)
    else:
        if isSafePattern(pattern):
            cached_patterns[pattern] = re.compile(pattern)
            return cached_patterns[pattern].match(*args, **kwargs)

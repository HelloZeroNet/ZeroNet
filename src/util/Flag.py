from collections import defaultdict


class Flag(object):
    def __init__(self):
        self.valid_flags = set([
            "admin",  # Only allowed to run sites with ADMIN permission
            "async_run",  # Action will be ran async with gevent.spawn
            "no_multiuser"  # Action disabled if Multiuser plugin running in open proxy mode
        ])
        self.db = defaultdict(set)

    def __getattr__(self, key):
        def func(f):
            if key not in self.valid_flags:
                raise Exception("Invalid flag: %s (valid: %s)" % (key, self.valid_flags))
            self.db[f.__name__].add(key)
            return f
        return func


flag = Flag()

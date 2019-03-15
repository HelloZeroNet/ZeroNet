class Spy:
    def __init__(self, obj, func_name):
        self.obj = obj
        self.__name__ = func_name
        self.func_original = getattr(self.obj, func_name)
        self.calls = []

    def __enter__(self, *args, **kwargs):
        def loggedFunc(cls, *args, **kwargs):
            call = dict(enumerate(args, 1))
            call[0] = cls
            call.update(kwargs)
            print("Logging", call)
            self.calls.append(call)
            return self.func_original(cls, *args, **kwargs)
        setattr(self.obj, self.__name__, loggedFunc)
        return self.calls

    def __exit__(self, *args, **kwargs):
        setattr(self.obj, self.__name__, self.func_original)
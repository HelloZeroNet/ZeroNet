class Spy:
	def __init__(self, obj, func_name):
		self.obj = obj
		self.func_name = func_name
		self.func_original = getattr(self.obj, func_name)
		self.calls = []

	def __enter__(self, *args, **kwargs):
		def loggedFunc(cls, *args, **kwags):
			print "Logging", self, args, kwargs
			self.calls.append(args)
			return self.func_original(cls, *args, **kwargs)
		setattr(self.obj, self.func_name, loggedFunc)
		return self.calls

	def __exit__(self, *args, **kwargs):
		setattr(self.obj, self.func_name, self.func_original)
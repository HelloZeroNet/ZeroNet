# Based on http://stackoverflow.com/a/2022629

class Event(list):
	def __call__(self, *args, **kwargs):
		for f in self[:]:
			if "once" in dir(f) and f in self: 
				self.remove(f)
			f(*args, **kwargs)


	def __repr__(self):
		return "Event(%s)" % list.__repr__(self)


	def once(self, func, name=None):
		func.once = True
		func.name = None
		if name: # Dont function with same name twice
			names = [f.name for f in self if "once" in dir(f)]
			if name not in names:
				func.name = name
				self.append(func)
		else:
			self.append(func)
		return self


if __name__ == "__main__":
	def say(pre, text):
		print "%s Say: %s" % (pre, text)
	onChanged = Event()
	onChanged.once(lambda pre: say(pre, "once"))
	onChanged.once(lambda pre: say(pre, "once"))
	onChanged.once(lambda pre: say(pre, "namedonce"), "namedonce")
	onChanged.once(lambda pre: say(pre, "namedonce"), "namedonce")
	onChanged.append(lambda pre: say(pre, "always"))
	onChanged("#1")
	onChanged("#2")
	onChanged("#3")

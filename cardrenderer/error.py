import inspect

def name(f):
	if type(f) is str:
		return f
	if inspect.ismethod(f):
		return "{}.{}".format(f.im_class.__name__, f.__name__)
	else:
		return "{}".format(f.__name__)

__WARNINGS = set()
def warn(warning):
	if warning not in __WARNINGS:
		print "WARNING: ", warning
		__WARNINGS.add(warning)

def deprecated(*args):
	def decorator(func):
		if args:
			message = "{} is deprecated in favor of {}.".format(name(func), ", ".join([name(f) for f in args]))
		else:
			message = "{} is deprecated.".format(name(func))
		def inner(*args, **kwargs):
			warn(message)
			return func(*args, **kwargs)
		return inner
	return decorator

def unsupportedParameter(*args):
	def decorator(func):
		def inner(*inargs, **kwargs):
			for p in args:
				if p in kwargs and kwargs[p]:
					warn("Argument {} is not supported in {}".format(p, name(func)))
			return func(*inargs, **kwargs)
		return inner
	return decorator

def unsupportedFunction(func):
	def inner(*args, **kwargs):
		warn("Function {} is not supported.".format(name(func)))
		return func(*args, **kwargs)
	return inner

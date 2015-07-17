import hashlib

class MarkedDict(dict):

    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)
        self.used = set()

    def clearused(self):
        self.used = set()

    def __getitem__(self, key):
        return self.get(key, "???")

    def get(self, key, default):
        self.used.add(key)
        return dict.get(self, key, default)

    def weak_update(self, *args, **kwargs):
        for a in (args or []) + [kwargs]:
            for k, v in kwargs.iteritems():
                if k not in self:
                    self[k] = v

    def hash(self):
        s = "-".join([repr(self.get(k, "")) for k in self.keys()])
        return hashlib.md5(s).hexdigest()

    def repr(self):
        dictrepr = dict.__repr__(self)
        return '%s(%s)' % (type(self).__name__, dictrepr)

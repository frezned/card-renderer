import Image
import requests
import os, tempfile, multiprocessing
from reportlab.lib.units import inch, mm

import base64, hashlib
def hash(string):
	hasher = hashlib.sha1(string)
	return base64.urlsafe_b64encode(hasher.digest()[0:10]).replace("=", "")

class ImageResource:

	def __init__(self, url):
		self.url = url
		if url:
			if url.startswith("http"):
				pre, post = os.path.split(url)
				self.localfile = "{0}_{1}".format(hash(pre), post)
				self.downfile = "download/" + self.localfile
			else:
				self.localfile = self.url
				self.downfile = self.localfile

	def fetch(self):
		if not os.path.exists(self.downfile):
			if self.url and self.url.startswith("http"):
				print "Fetching", self.url
				r = requests.get(self.url, stream=True).raw
				tempfn = tempfile.mktemp()
				with open(tempfn, "wb") as f:
					buf = r.read(128)
					while buf:
						f.write(buf)
						buf = r.read(128)
				r.close()
				os.rename(tempfn, self.downfile)

	def getfilename(self, dpi):
		return "{0}dpi/{1}".format(dpi, self.localfile)

	def prepare(self, dpi, w, h):
		outfn = self.getfilename(dpi)
		if not os.path.exists(outfn):
			factor = dpi / inch
			size = (int(factor * w), int(factor * h))
			img = Image.open(self.downfile).resize(size, Image.ANTIALIAS)
			img.save(outfn)
	
def pool_fetch(r):
	r.fetch()

def pool_prepare(n):
	n[0].prepare(*n[1:])

class Resources:

	def __init__(self, directory):
		self.images = {}
		self.needed = []

	def markneeded(self, url, w, h):
		if url:
			if not url in self.images:
				self.images[url] = ImageResource(url)
				print (url, w, h)
			self.needed.append((self.images[url], w, h))

	def prepare(self, dpi):
		def mkdir(n):
			if not os.path.exists(n): os.mkdir(n)
		mkdir("download")
		pool = multiprocessing.Pool(processes=10)
		pool.map(pool_fetch, self.images.values())
		mkdir("{0}dpi".format(dpi))
		pool.map(pool_prepare, [(n[0], dpi, n[1], n[2]) for n in self.needed])

	def getfilename(self, url, dpi):
		if url:
			return self.images[url].getfilename(dpi)
		else:
			return ""



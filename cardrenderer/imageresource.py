from PIL import Image
import requests
import os, tempfile, multiprocessing
from reportlab.lib.units import inch, mm

import base64, hashlib
def hash(string):
	hasher = hashlib.sha1(string)
	return base64.urlsafe_b64encode(hasher.digest()[0:10]).replace("=", "")

def mkdir(n):
	if not os.path.exists(n): os.mkdir(n)

class ImageResource:

	def __init__(self, url):
		self.url = url
		self.files = {}
		if url:
			if url.startswith("http"):
				pre, post = os.path.split(url)
				self.localfile = "{0}_{1}".format(hash(pre), post)
				mkdir("download")
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
			else:
				print "Doesn't exist: ", self.url

	def getfilename(self, dpi):
		if dpi not in self.files:
			return ""
		else:
			return self.files[dpi]

	def prepare(self, dpi, w, h):
		if dpi not in self.files and os.path.exists(self.downfile):
			print "Scaling {0} for {1}dpi...".format(self.localfile, dpi),
			outfn = "{0}dpi/{1}".format(dpi, self.localfile)
			factor = dpi / inch
			size = (int(factor * w), int(factor * h))
			img = Image.open(self.downfile)
			if size[0] < img.size[0] and size[1] < img.size[1]:
				mkdir("{0}dpi".format(dpi))
				img.resize(size, Image.ANTIALIAS).save(outfn)
				self.files[dpi] = outfn
				print "OK"
			else:
				self.files[dpi] = self.downfile
				print "not needed."
	
def pool_fetch(r):
	try:
		r.fetch()
	except Exception as e:
		print e

def pool_prepare(n):
	try:
		n[0].prepare(*n[1:])
	except Exception as e:
		print e

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
		# pool = multiprocessing.Pool(processes=10)
		print "Fetching all images..."
		map(pool_fetch, self.images.values())
		print "Preparing all images..."
		map(pool_prepare, [(n[0], dpi, n[1], n[2]) for n in self.needed])

	def getfilename(self, url, dpi):
		if url:
			return self.images[url].getfilename(dpi)
		else:
			return ""



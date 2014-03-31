from PIL import Image
import requests
import os, sys, tempfile, multiprocessing

import base64, hashlib
def hash(string):
	hasher = hashlib.sha1(string)
	return base64.urlsafe_b64encode(hasher.digest()[0:10]).replace("=", "")

inch = 24.5

def mkdir(n):
	if not os.path.exists(n): os.mkdir(n)

class ImageResource:

	def __init__(self, url):
		self.url = url
		self.files = {}
		self.size = None
		if url:
			if url.startswith("http"):
				pre, post = os.path.split(url)
				self.localfile = "{0}_{1}".format(hash(pre), post)
				mkdir("download")
				self.downfile = "download/" + self.localfile
			else:
				self.localfile = self.url
				self.downfile = self.localfile
		if not self.needsfetch():
			self.cachesize()

	def needsfetch(self):
		return not os.path.exists(self.downfile)

	def cachesize(self):
		try:
			img = Image.open(self.downfile)
			self.size = img.size
		except Exception, e:
			self.size = (0, 0)
			print "ERROR:", self.downfile, e

	def fetch(self, countcurrent, counttotal):
		if self.needsfetch():
			if self.url and self.url.startswith("http"):
				print "\r[{cc:3}/{ct:3}][{bc:4}kb/{bt:4}kb]  {url:100}".format(bc=0, bt="??", cc=countcurrent, ct=counttotal, url=self.url),
				def update(current, total):
					print "\r[{cc:3}/{ct:3}][{bc:4}kb/{bt:4}kb]".format(bc=current, bt=total or "??", cc=countcurrent, ct=counttotal),
				update(0, 0)
				r = requests.get(self.url, stream=True).raw
				try:
					total = int(r.getheader('content-length'))/1024
				except:
					total = None
				current = 0
				tempfn = tempfile.mktemp()
				with open(tempfn, "wb") as f:
					buf = r.read(1024)
					while buf:
						current += 1
						if current % 10 == 0:
							update(current, total)
						f.write(buf)
						buf = r.read(1024)
				r.close()
				os.rename(tempfn, self.downfile)
				self.cachesize()
			else:
				print "Doesn't exist: ", self.url

	def getfilename(self, dpi):
		if dpi not in self.files:
			return ""
		else:
			return self.files[dpi]

	def prepare(self, dpi, w, h, ext=None):
		outfn = "{0}dpi/{1}".format(dpi, os.path.split(self.localfile)[1])
		if ext:
			outfn = os.path.splitext(outfn)[0] + ext
		if os.path.exists(outfn):
			self.files[dpi] = outfn
			return False
		elif dpi not in self.files and os.path.exists(self.downfile):
			factor = dpi / inch
			size = (int(factor * w), int(factor * h))
			if size[0] < self.size[0] and size[1] < self.size[1]:
				img = Image.open(self.downfile)
				mkdir("{0}dpi".format(dpi))
				img.resize(size, Image.ANTIALIAS).save(outfn, quality=100)
				self.files[dpi] = outfn
				return True
			else:
				self.files[dpi] = self.downfile
				return False
		else:
			return False

class Resources:

	def __init__(self, directory):
		self.images = {}
		self.needed = []

	def markneeded(self, url, w, h):
		if url:
			if not url in self.images:
				self.images[url] = ImageResource(url)
			tup = (self.images[url], w, h)
			if tup not in self.needed:
				self.needed.append(tup)

	def prepare(self, dpi, ext=None):
		fetches = [i for i in self.images.values() if i.needsfetch()]
		total = len(fetches)
		current = 0
		print "Fetching all images..."
		for idx, r in enumerate(fetches):
			try:
				r.fetch(idx+1, total)
			except Exception as e:
				print
				print e
		print

		print "Preparing all images for {0}dpi...".format(dpi)
		total = len(self.needed)
		resized = False
		for idx, n in enumerate(self.needed):
			try:
				print "\r[{3} {0:3}/{1:3}] {2:100}".format(idx+1,total, n[0].localfile, resized and "Y" or "N"),
				resized = n[0].prepare(dpi, *n[1:], ext=ext)
			except Exception as e:
				print e
		print

	def getfilename(self, url, dpi):
		if url:
			return self.images[url].getfilename(dpi)
		else:
			return ""



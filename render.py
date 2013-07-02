from reportlab.lib.units import inch, mm
from PIL import Image

import urllib2
import os
import sys
import json
import datetime
import optparse
import tempfile
import yaml
from string import Formatter

import progressbar

from pdfcanvas import PDFCanvas
from imagecanvas import ImageCanvas

# TODO: some of this stuff should be in the spec file
DPI = 300

CARD = (63*mm, 88*mm)
SIZES = dict(
	A4 = (210*mm, 297*mm),
	LETTER = (11*inch, 8.5*inch),
	CARD = ((63+6)*mm, (88+6)*mm)
)
FRAME = (63*mm, 88*mm)

CARDW = CARD[0]
CARDH = CARD[1]

import base64, hashlib
def hash(string):
	hasher = hashlib.sha1(string)
	return base64.urlsafe_b64encode(hasher.digest()[0:10]).replace("=", "")

class TemplateItem:

	def __init__(self, builder, data):
		self.builder = builder
		self.name = data.get('name', "")
		self.width = data.get('width', 0)*mm or CARDW
		self.height = data.get('height', 0)*mm or CARDH
		def coordormid(key, ref):
			val = data.get(key, 0)
			if val == "mid":
				return ref
			else:
				return val * mm
		self.x = coordormid('x', 0.5*(CARDW-self.width))
		self.y = coordormid('y', 0.5*(CARDH-self.height))
		if data.get('hcenter', False):
			self.x = (CARDW-self.width) / 2
	
	def format(self, fmtstring, data):
		return self.builder.format(fmtstring, data)

	def prepare(self, data):
		pass

class GraphicTemplateItem(TemplateItem):
	
	def __init__(self, builder, data):
		TemplateItem.__init__(self, builder, data)
		self.filename = data.get('filename', "")

	def get_local_url(self, data):
		url = self.format(self.filename, data)
		if url and url.startswith("http"):
			pre, post = os.path.split(url)
			filename = hash(pre) + "_" + post
			return os.path.join("download", filename)
		else:
			return url

	def prepare(self, data):
		url = self.format(self.filename, data)
		factor = 300 * (1 / inch)
		size = (int(self.width*factor), int(self.height*factor))
		if url and url.startswith("http"):
			outfn = self.get_local_url(data)
			if not os.path.exists(outfn):
				print "Fetch", url
				r = urllib2.urlopen(url)
				downf = tempfile.mktemp()
				with open(downf, "wb") as f:
					buf = r.read(128)
					while buf:
						f.write(buf)
						buf = r.read(128)
				r.close()
				art = Image.open(downf).resize(size, Image.ANTIALIAS)
				print outfn
				art.save(outfn)

	def render(self, canvas, data):
		filename = self.get_local_url(data)
		if os.path.exists(filename):
			canvas.drawImage(filename, self.x, self.y, self.width, self.height)

class TextTemplateItem(TemplateItem):

	def __init__(self, builder, data):
		TemplateItem.__init__(self, builder, data)
		self.textformat = data.get('format', "{" + self.name + "}")
		self.style = data.get('style', self.name)

	def render(self, canvas, data):
		string = self.format(self.textformat, data)
		canvas.renderText(string, self.style, self.x, self.y, self.width, self.height)

class Template:

	def __init__(self, data, builder):
		self.name = data.get('name', "")
		self.key = data.get('key', self.name)
		self.items = []
		for e in data.get('elements', []):
			if type(e) == str:
				other = builder.templates[e]
				for i in other.items:
					self.items.append(i)
			elif 'filename' in e:
				self.items.append(GraphicTemplateItem(builder, e))
			else:
				self.items.append(TextTemplateItem(builder, e))
		self.cards = []

	def render(self, canvas, data):
		for i in self.items:
			i.render(canvas, data)
	
	def prepare(self, data):
		for i in self.items:
			i.prepare(data)

class CardRenderer:

	def __init__(self):
		self.decks = {}
		self.styles = {}
		self.templates = {}
		self.keytemplates = {}
		self.readfiles = set()
		self.outputs = []
		self.name = ""
		self.data = dict(
				name="",
				date=datetime.datetime.now().strftime("%d-%b-%Y")
				)
		self.styles['note'] = dict(align='center', size=9)

	def format(self, fmtstring, data={}):
		merged_data = {}
		merged_data.update(self.data)
		merged_data.update(data)
		return Formatter().vformat(fmtstring, [], merged_data)

	def render_card(self, template, card):
		self.canvas.beginCard(card)
		template.render(self.canvas, card)
		self.canvas.endCard()

	def parse_templates(self, data):
		for sd in data.get('styles', []):
			self.styles[sd.get('name', "")] = sd

		for td in data.get('templates', []):
			t = Template(td, self)
			self.templates[t.name] = t
			self.keytemplates[t.key] = t

	def note(self):
		if self.notefmt:
			note = self.format(self.notefmt)
			self.canvas.renderText(note, self.notestyle, self.xoffsetx, self.offsety + CARDH + 1*mm, CARDW, 100)

	def all_cards_progress(self, function):
		i = 0
		cards = []
		for t in self.templates.values():
			for c in t.cards:
				cards.append((t, c))
		widgets = [progressbar.Percentage(), ' ', progressbar.Bar(marker='=', left='[', right=']')]
		bar = progressbar.ProgressBar(widgets=widgets, maxval=len(cards))
		bar.start()
		for c in cards:
			function(*c)
			i += 1
			bar.update(i)
		bar.finish()

	def prepare_cards(self):
		# ensure the destination folders exist
		def mkdir(n):
			if not os.path.exists(n): os.mkdir(n)
		mkdir("download")
		mkdir("tif")
		# prepare the cards
		print "Preparing card art..."
		def prepare(t, c):
			t.prepare(c)
		self.all_cards_progress(prepare)
		self.page = False

	def render(self, pagesize, outfile, note='', guides=True, drawbackground=False):
		if outfile.endswith(".pdf"):
			filename = self.format(outfile).replace(" ", "")
			self.canvas = PDFCanvas(CARDW, CARDH, filename, pagesize, (0,0))
		else:
			self.canvas = ImageCanvas(CARDW, CARDH, outfile, self.format)
		for s in self.styles:
			self.canvas.addStyle(self.styles[s])
		self.notefmt = note
		self.guides = guides
		self.drawbackground = drawbackground
		print "Rendering to {out}...".format(out=outfile)
		def render(t, c):
			for i in range(c.get('copies', 1)):
				self.render_card(t, c)
		self.all_cards_progress(render)
		self.canvas.finish()

	def readfile(self, filename):
		if filename not in self.readfiles:
			self.readfiles.add(filename)
			data = loaddata(filename)
			self.parse_use(data)
			self.parse_output(data)
			self.parse_templates(data)
			self.parse_decks(data)
			self.parse_data(data)

	def parse_data(self, data):
		self.data.update(data)

	def parse_use(self, data):
		if 'use' in data:
			use = data['use']
			if type(use) == str:
				self.readfile(use)
			else:
				for u in use:
					self.readfile(u)

	def parse_output(self, data):
		for o in data.get('output', []):
			self.outputs.append(o)

	def parse_decks(self, data):
		for d in data.get('decks', []):
			template = self.templates[d['template']]
			for c in d.get('cards', []):
				template.cards.append(c)
		for c in data.get('cards', []):
			template = self.keytemplates[c['type']]
			template.cards.append(c)

	def run(self):
		self.prepare_cards()
		for o in self.outputs:
			self.render(
					pagesize=SIZES[o.get('size', "A4")],
					outfile = o['filename'],
					note = o.get("note", ""),
					guides = o.get("guides", True),
					drawbackground = o.get("background", False)
				)

def loaddata(datafile):
	if datafile.startswith("http://") or datafile.startswith("https://"):
		print "Downloading", datafile
		r = urllib2.urlopen(datafile)
		data = yaml.load(r)
		r.close()
		return data
	else:
		with open(datafile) as f:
			data = yaml.load(f)
			return data

def main(datafile):
	maker = CardRenderer()
	maker.readfile(datafile)
	maker.run()

if __name__ == "__main__":
	parser = optparse.OptionParser()
	(options, args) = parser.parse_args()
	main(args[0])

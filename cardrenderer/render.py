from reportlab.lib.units import inch, mm
from PIL import Image

import requests
import os
import sys
import json
import datetime
import optparse
import tempfile
import yaml
import csv
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

import base64, hashlib
def hash(string):
	hasher = hashlib.sha1(string)
	return base64.urlsafe_b64encode(hasher.digest()[0:10]).replace("=", "")

class TemplateItem:

	def __init__(self, builder, data):
		self.builder = builder
		self.name = data.get('name', "")
		self.width = data.get('width', 0)*mm or builder.cardw
		self.height = data.get('height', 0)*mm or builder.cardh
		def coordormid(key, ref):
			val = data.get(key, 0)
			if val == "mid":
				return ref
			else:
				return val * mm
		self.x = coordormid('x', 0.5*(builder.cardw-self.width))
		self.y = coordormid('y', 0.5*(builder.cardh-self.height))
		if data.get('hcenter', False):
			self.x = (builder.cardw-self.width) / 2
	
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
				r = requests.get(url, stream=True).raw
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

	def use(self, urls, csv=False):
		if type(urls) == str:
			for c in loaddata(urls, csv):
				self.cards.append(c)
		else:
			for u in urls:
				self.use(u, csv)

	def sort(self):
		self.cards.sort(key=lambda x: x.get('title', x.get('name', None)))

class CardRenderer:

	def __init__(self):
		self.decks = {}
		self.styles = {}
		self.templates = {}
		self.keytemplates = {}
		self.readfiles = set()
		self.outputs = []
		self.name = ""
		self.cardw = CARD[0]
		self.cardh = CARD[1]
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
			self.canvas = PDFCanvas(self.cardw, self.cardh, filename, pagesize, (0,0), drawbackground, self.format(note))
		else:
			self.canvas = ImageCanvas(self.cardw, self.cardh, outfile, self.format)
		for s in self.styles:
			self.canvas.addStyle(self.styles[s])
		self.notefmt = note
		self.guides = guides
		self.drawbackground = drawbackground
		print "Rendering to {out}...".format(out=outfile)
		def render(t, c):
			for i in range(int(c.get('copies', 1))):
				self.render_card(t, c)
		self.all_cards_progress(render)
		self.canvas.finish()

	def readfile(self, filename):
		if filename not in self.readfiles:
			self.readfiles.add(filename)
			data = loaddata(filename)
			self.parse_data(data)
			self.parse_use(data)
			self.parse_output(data)
			self.parse_templates(data)
			self.parse_decks(data)

	def parse_data(self, data):
		if 'cardwidth' in data:
			self.cardw = data.get('cardwidth') * mm
		if 'cardheight' in data:
			self.cardh = data.get('cardheight') * mm
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
			if 'use' in d:
				template.use(d['use'])
			if 'use-csv' in d:
				template.use(d['use-csv'], True)
			template.sort()
		for c in data.get('cards', []):
			template = self.keytemplates[c['type']]
			template.cards.append(c)
			template.sort()

	def run(self, targets):
		self.prepare_cards()
		if not targets:
			outputs = self.outputs
		else:
			if type(targets) == str:
				targets = [targets]
			outputs = [o for o in self.outputs if o['name'] in targets]

		for o in outputs:
			self.render(
					pagesize=SIZES[o.get('size', "A4")],
					outfile = o['filename'],
					note = o.get("note", ""),
					guides = o.get("guides", True),
					drawbackground = o.get("background", False)
				)

def loaddata(datafile, force_csv=False):
	if datafile.startswith("http://") or datafile.startswith("https://"):
		print "Downloading", datafile
		f = requests.get(datafile, stream=True).raw
	else:
		print "Reading", datafile
		f = open(datafile)
	if force_csv or datafile.endswith(".csv"):
		# csv is always card definitions
		reader = csv.DictReader(f)
		data = []
		for row in reader:
			data.append({k: v.replace('|', '\n') for k, v in row.iteritems()})
	else:
		# assume it's yaml
		data = yaml.load(f)
	f.close()
	return data
	

from reportlab.lib.units import inch, mm
import Image

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
from imageresource import Resources

res = Resources("res")

CARD = (63*mm, 88*mm)
SIZES = {}
SIZES["A4"] = (210*mm, 297*mm)
SIZES["A4-P"] = (210*mm, 297*mm)
SIZES["A4-L"] = (297*mm, 210*mm)
SIZES["LETTER"] = (11*inch, 8.5*inch)
SIZES["LETTER-P"] = (8.5*inch, 11*inch)
SIZES["LETTER-L"] = (11*inch, 8.5*inch)
SIZES["CARD"] = ((63+6)*mm, (88+6)*mm)
FRAME = (63*mm, 88*mm)

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

	def prepare(self, data):
		url = self.format(self.filename, data)
		res.markneeded(url, self.width, self.height)

	def render(self, canvas, data):
		url = self.format(self.filename, data)
		filename = res.getfilename(url, canvas.dpi)
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
		self.cards.sort(key=lambda x: x.get('title', x.get('name', None)) or 'zzzzzzzzzzzzzz')

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
		# prepare the cards
		print "Preparing card art..."
		def prepare(t, c):
			t.prepare(c)
		self.all_cards_progress(prepare)
		self.page = False

	def render(self, pagesize, outfile, note='', guides=True, drawbackground=False, dpi=300):
		if outfile.endswith(".pdf"):
			filename = self.format(outfile).replace(" ", "")
			self.canvas = PDFCanvas(
					self.cardw, self.cardh, 
					filename, pagesize, 
					(0.25*inch,0.25*inch), 
					drawbackground, 
					self.format(note),
					dpi=dpi)
		else:
			self.canvas = ImageCanvas(self.cardw, self.cardh, outfile, self.format)
		for s in self.styles:
			self.canvas.addStyle(self.styles[s])
		self.notefmt = note
		self.guides = guides
		self.drawbackground = drawbackground
		res.prepare(dpi)
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
			size = o.get('size', "A4")
			if type(size) == str:
				size = SIZES[size]
			self.render(
					pagesize=size,
					outfile = o['filename'],
					dpi = o.get("dpi", 300),
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
	

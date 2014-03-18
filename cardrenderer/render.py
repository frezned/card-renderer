import requests
import os
import sys
import json
import datetime
import optparse
import tempfile
import yaml
import csv
import collections
import HTMLParser # for unescape
from string import Formatter

import progressbar

from pdfcanvas import PDFCanvas
from compositingcanvas import CompositingCanvas
from imagecanvas import ImageCanvas
from preparecanvas import PrepareCanvas
from imageresource import Resources

inch = 25.4

CARD = (63, 88)
SIZES = {}
SIZES["A4"] = (210, 297)
SIZES["A4-P"] = (210, 297)
SIZES["A4-L"] = (297, 210)
SIZES["LETTER"] = (11*inch, 8.5*inch)
SIZES["LETTER-P"] = (8.5*inch, 11*inch)
SIZES["LETTER-L"] = (11*inch, 8.5*inch)
SIZES["CARD"] = ((63+6), (88+6))
FRAME = (63, 88)

class TemplateItem:

	def __init__(self, builder, data):
		self.builder = builder
		self.name = data.get('name', "")
		self.width = data.get('width', 0) or builder.cardw
		self.height = data.get('height', 0) or builder.cardh
		def coordormid(key, ref):
			val = data.get(key, 0)
			if val == "mid":
				return ref
			else:
				return val
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

	def render(self, canvas, data):
		url = self.format(self.filename, data)
		if url:
			canvas.drawImage(url, self.x, self.y, self.width, self.height)
		else:
			print "ERROR: blank url", data.get("title", "??")

class TextTemplateItem(TemplateItem):

	def __init__(self, builder, data):
		TemplateItem.__init__(self, builder, data)
		self.textformat = data.get('format', "{" + self.name + "}")
		self.style = data.get('style', self.name)

	def render(self, canvas, data):
		string = self.format(self.textformat, data)
		string = HTMLParser.HTMLParser().unescape(string)
		canvas.renderText(string, self.style, self.x, self.y, self.width, self.height)

class FunctionTemplateItem(TemplateItem):

	def __init__(self, builder, data):
		TemplateItem.__init__(self, builder, data)
		self.callback = data.get('callback', None)

	def render(self, canvas, data):
		if self.callback:
			self.callback(self, canvas, data)

class Template:

	def __init__(self, data, builder):
		self.builder = builder
		self.name = data.get('name', "")
		self.key = data.get('key', self.name)
		self.items = []
		for e in data.get('elements', []):
			if type(e) == str:
				self.element(e)
			else:
				self.element(**e)
		self.cards = []

	def element(self, *args, **kwargs):
		if len(args) == 1 and type(args[0]) == str and len(kwargs)==0:
			other = self.builder.templates[args[0]]
			for i in other.items:
				self.items.append(i)
		elif 'callback' in kwargs:
			self.items.append(FunctionTemplateItem(self.builder, kwargs))
		elif 'filename' in kwargs:
			self.items.append(GraphicTemplateItem(self.builder, kwargs))
		else:
			self.items.append(TextTemplateItem(self.builder, kwargs))

	def render(self, canvas, data):
		for i in self.items:
			i.render(canvas, data)
	
	def prepare(self, data):
		for i in self.items:
			i.prepare(data)

	def card(self, **card):
		self.cards.append(card)

	def use(self, urls, csv=False):
		if type(urls) == str:
			for c in loaddata(urls, csv):
				self.card(**c)
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
		self.resources = Resources("res")

	def format(self, fmtstring, data={}):
		merged_data = {}
		merged_data.update(self.data)
		merged_data.update(data)
		dd = collections.defaultdict(lambda: '???', merged_data)
		return Formatter().vformat(fmtstring, [], dd)

	def render_card(self, template, card):
		self.canvas.beginCard(card)
		template.render(self.canvas, card)
		self.canvas.endCard()

	def parse_templates(self, data):
		for sd in data.get('styles', []):
			self.style(**sd)

		for td in data.get('templates', []):
			self.template(**td)

	def style(self, name, **descriptor):
		descriptor["name"] = name
		self.styles[name] = descriptor

	def template(self, **kwargs):
		t = Template(kwargs, self)
		self.templates[t.name] = t
		self.keytemplates[t.key] = t
		return t

	def all_cards_progress(self, function, check=None):
		i = 0
		cards = []
		for t in self.templates.values():
			for c in t.cards:
				cards.append((t, c))
		if check:
			cards = filter(check, cards)
		if cards:
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
		preparecanvas = PrepareCanvas(self.resources)
		def prepare(t, c):
			t.render(preparecanvas, c)
		self.all_cards_progress(prepare)
		self.page = False

	def render(self, pagesize, outfile, note='', guides=True, drawbackground=False, dpi=300, margin=0, filtercomp=None, filtertemplate=None, imageextension=None):
		if outfile.endswith(".pdf"):
			filename = self.format(outfile).replace(" ", "")
			self.canvas = CompositingCanvas(
					res=self.resources,
					cardw=self.cardw, cardh=self.cardh, 
					outfile=filename, pagesize=pagesize, margin=(margin, margin),
					background=drawbackground, 
					notefmt=self.format(note),
					guides=guides,
					dpi=dpi)
		else:
			self.canvas = ImageCanvas(self.resources, self.cardw, self.cardh, outfile, self.format)
		for s in self.styles:
			self.canvas.addStyle(self.styles[s])
		self.notefmt = note
		self.guides = guides
		self.drawbackground = drawbackground
		self.resources.prepare(dpi, imageextension)
		print "Rendering to {out}...".format(out=self.canvas.getfilename())
		def cardfilter(c):
			if filtertemplate:
				filt = self.format(filtertemplate, c)
				if filtercomp:
					return filt in filtercomp
				else:
					return filt
			else:
				return True
		def render(t, c):
			if cardfilter(c):
				for i in range(int(c.get('copies', 1))):
					self.render_card(t, c)
		self.all_cards_progress(render)
		return self.canvas.finish()

	def readfile(self, filename):
		if filename not in self.readfiles:
			self.readfiles.add(filename)
			data = loaddata(filename)
			self.parse_data(**data)
			self.parse_use(data.get('use', None))
			self.parse_output(data)
			self.parse_templates(data)
			self.parse_decks(data)

	def parse_data(self, cardwidth=None, cardheight=None, **kwargs):
		if cardwidth:
			self.cardw = cardwidth
		if cardheight:
			self.cardh = cardheight
		self.data.update(kwargs)

	def parse_use(self, filename=None):
		if filename:
			if type(filename) == str:
				self.readfile(filename)
			else:
				for u in filename:
					self.readfile(u)

	def parse_output(self, data):
		for o in data.get('output', []):
			self.output(**o)

	def output(self, filename, **kwargs):
		kwargs['filename'] = filename
		self.outputs.append(kwargs)

	def parse_decks(self, data):
		for d in data.get('decks', []):
			template = self.templates[d['template']]
			for c in d.get('cards', []):
				template.card(**c)
			if 'use' in d:
				template.use(d['use'])
			if 'use-csv' in d:
				template.use(d['use-csv'], True)
			template.sort()
		for c in data.get('cards', []):
			template = self.keytemplates[c['type']]
			template.card(**c)
			template.sort()

	def run(self, targets=None):
		self.prepare_cards()
		if not targets:
			outputs = self.outputs
		else:
			if type(targets) == str:
				targets = [targets]
			outputs = [o for o in self.outputs if o['name'] in targets]

		outfiles = []
		for o in outputs:
			size = o.get('size', "A4")
			if type(size) == str:
				size = SIZES[size]
			outfiles += self.render(
					pagesize=size,
					outfile = o['filename'],
					dpi = o.get("dpi", 300),
					note = o.get("note", ""),
					guides = o.get("guides", True),
					margin = o.get("margin", 0),
					drawbackground = o.get("background", False),
					filtertemplate = o.get("filtertemplate", None),
					filtercomp = o.get("filter", None),
					imageextension = o.get("imageextension", None)
				)
		return outfiles

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
	

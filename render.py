from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch, cm, mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

import Image

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

DATESTR = datetime.datetime.now().strftime("%d-%b-%Y")

import base64, hashlib
def hash(string):
	hasher = hashlib.sha1(string)
	return base64.urlsafe_b64encode(hasher.digest()[0:10]).replace("=", "")

class TemplateItem:

	def __init__(self, data):
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
	
	def prepare(self, data):
		pass

class GraphicTemplateItem(TemplateItem):
	
	def __init__(self, data):
		TemplateItem.__init__(self, data)
		self.filename = data.get('filename', "")

	def get_local_url(self, data):
		url = Formatter().vformat(self.filename, [], data)
		if url and url.startswith("http"):
			pre, post = os.path.split(url)
			filename = hash(pre) + "_" + post
			return os.path.join("download", filename)
		else:
			return url

	def prepare(self, data):
		url = Formatter().vformat(self.filename, [], data)
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

	def __init__(self, data, styles):
		TemplateItem.__init__(self, data)
		self.format = data.get('format', "{" + self.name + "}")
		stylename = data.get('style', self.name)
		self.style = styles[stylename]

	def render(self, canvas, data):
		string = Formatter().vformat(self.format, [], data)
		lines = string.splitlines()
		i = 0
		for l in lines:
			p = Paragraph(l, self.style)
			tx, ty = p.wrap(self.width, self.height)
			p.drawOn(canvas, self.x, self.y-ty*i+ty*0.5*len(lines))
			i += 1

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
				self.items.append(GraphicTemplateItem(e))
			else:
				self.items.append(TextTemplateItem(e, builder.styles))
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

		self.notestyle = ParagraphStyle('note')

	def prepare_canvas(self, pagesize, margin=(0,0)):
		self.pagesize = pagesize
		self.x = 0
		self.y = 0
		self.columns = int((pagesize[0]-margin[0]*2) / CARDW)
		self.rows = int((pagesize[1]-margin[1]*2) / CARDH)
		self.offsetx = (pagesize[0] - self.columns*CARDW) * 0.5
		self.offsety = (pagesize[1] - CARDH) - (pagesize[1] - self.rows*CARDH) * 0.5
		self.tempfile = tempfile.mktemp()
		self.canvas = canvas.Canvas(self.tempfile, pagesize=(pagesize[0], pagesize[1]))
		self.frames = {x: ("frame_{type}.tif".format(type=x)) for x in ("IT", "LO", "MO")}
		self.background = False

	def render_card(self, template, card):
		# ensure we're on a prepared page
		self.startpage()
		# render the card
		c = self.canvas
		c.saveState()
		c.translate(self.offsetx + self.x*CARDW, self.offsety - self.y*CARDH)
		template.render(c, card)
		c.restoreState()
		# advance the card position
		self.x += 1
		if self.x >= self.columns:
			self.x = 0
			self.y += 1
			if self.y >= self.rows:
				self.endpage()

	def parse_templates(self, data):
		for sd in data.get('styles', []):
			name = sd.get('name', "")
			s = ParagraphStyle(name)
			fontfile = sd.get('font', "Helvetica")
			if fontfile.endswith(".ttf") or fontfile.endswith(".otf"):
				fontname = os.path.splitext(fontfile)[0]
				pdfmetrics.registerFont(TTFont(fontname, fontfile))
				s.fontName = fontname
			else:
				s.fontName = fontfile
			s.fontSize = sd.get('size', 10)
			s.alignment = dict(center=TA_CENTER, left=TA_LEFT, right=TA_RIGHT)[sd.get('align', 'left')]
			if 'leading' in sd:
				s.leading = sd['leading']
			self.styles[name] = s

		for td in data.get('templates', []):
			t = Template(td, self)
			self.templates[t.name] = t
			self.keytemplates[t.key] = t

	def drawGuides(self):
		GUIDECOLOR = (0.5, 0.5, 0.5)
		c = self.canvas
		left = self.offsetx
		right = left + CARDW*self.columns
		top = self.offsety + CARDH
		bottom = top - CARDH*self.rows
		for ix in range(0, self.columns+1):
			x = self.offsetx + CARDW*ix
			c.setStrokeColorRGB(*GUIDECOLOR)
			c.line(x, self.pagesize[1], x, top)
			c.line(x, bottom, x, 0)
			c.setStrokeColorRGB(1, 1, 1)
			c.line(x, top, x, bottom)
		for iy in range(-1, self.rows):
			y = self.offsety - CARDH*iy
			c.setStrokeColorRGB(*GUIDECOLOR)
			c.line(0, y, left, y)
			c.line(right, y, self.pagesize[0], y)
			c.setStrokeColorRGB(1, 1, 1)
			c.line(left, y, right, y) 

	def note(self):
		if self.notefmt:
			note = self.notefmt.format(date=DATESTR, name=self.name)
			p = Paragraph(note, self.notestyle)
			tx, ty = p.wrap(CARDW, 100)
			p.drawOn(self.canvas, self.offsetx, self.offsety + CARDH + 0.1*cm)

	def startpage(self):
		if not self.page:
			if self.drawbackground:
				# render background
				self.canvas.setFillColorRGB(0, 0, 0)
				self.canvas.rect(0, 0, self.pagesize[0], self.pagesize[1], stroke=0, fill=1)
				self.background = True
			self.page = True

	def endpage(self):
		if self.page:
			if self.notefmt: 
				self.note()
			if self.guides:
				self.drawGuides()
			self.x = 0
			self.y = 0
			self.canvas.showPage()
			self.page = False

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

	def save(self, outfile):
		self.canvas.save()
		fn, ext = os.path.splitext(outfile)
		amt = 0
		while True:
			try:
				if os.path.exists(outfile):
					os.unlink(outfile)
				os.rename(self.tempfile, outfile)
				return
			except WindowsError as e:
				amt += 1
				outfile = "{0}_{1}{2}".format(fn, amt, ext)

	def render(self, pagesize, outfile, note='', guides=True, drawbackground=False):
		self.prepare_canvas(pagesize)
		self.notefmt = note
		self.guides = guides
		self.drawbackground = drawbackground
		print "Rendering to {out}...".format(out=outfile)
		def render(t, c):
			for i in range(c.get('copies', 1)):
				self.render_card(t, c)
		self.all_cards_progress(render)
		self.endpage()
		self.save(outfile)

	def readfile(self, filename):
		if filename not in self.readfiles:
			self.readfiles.add(filename)
			data = loaddata(filename)
			self.parse_use(data)
			self.parse_output(data)
			self.parse_templates(data)
			self.parse_decks(data)
			self.name = data.get('name', self.name)

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
					outfile = o['filename'].format(name=self.name, date=DATESTR).replace(" ", ""),
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

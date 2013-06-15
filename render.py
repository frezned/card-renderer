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

A4 = (210*mm, 297*mm)
LETTER = (11*inch, 8.5*inch)
CARDPAGE = ((63+6)*mm, (88+6)*mm)
CARD = (63*mm, 88*mm)
FRAME = (63*mm, 88*mm)

CARDW = CARD[0]
CARDH = CARD[1]

IMGSIZE = inch*2

DATESTR = datetime.datetime.now().strftime("%d-%b-%Y")

# TODO: dumb this down in favour of specfile
#		just note URL-types, fetch & mod dates
class Card:

	def __init__(self, data):
		self.title = data.get('title', "")
		self.copy = data.get('text', "")
		if 'cmyk' in data:
			self.imageurl = data['cmyk']
			self.cmyk = True
		else:
			self.imageurl = data.get('art', "")
			self.cmyk = False
		self.cid = data.get('id', "X")
		self.type = data['type']
		self.localimage = None
		self.chash = data.get('hash', "") or self.cid
		self.cname = "{0}_{1}".format(self.cid, self.chash or "")
		self.data = data

	def retrieve_image(self):
		if self.imageurl:
			c = ""
			if self.cmyk: c = "-cmyk"
			img = os.path.join("download"+c, self.cname + os.path.splitext(self.imageurl)[1])
			if not os.path.exists(img):
				print "Fetch", self.imageurl
				r = urllib2.urlopen(self.imageurl)
				downf = "download/temp"
				with open(downf, "wb") as f:
					buf = r.read(128)
					while buf:
						f.write(buf)
						buf = r.read(128)
				r.close()
				os.rename(downf, img)
			self.localimage = img

	def convert_image(self):
		if self.localimage and not self.convertedimage:
			outfn = os.path.splitext(os.path.split(self.localimage)[1])[0] + ".tif"
			outfn = os.path.join("gen", outfn)
			if not os.path.exists(outfn):
				cardimgs = int(IMGSIZE/inch*DPI)
				art = Image.open(self.localimage).resize((cardimgs, cardimgs), Image.ANTIALIAS)
				self.localimage = outfn
				art.save(self.localimage)

	def __getitem__(self, key):
		if key == 'filename':
			return self.localimage
		else:
			return self.data.get(key, "")

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

class GraphicTemplateItem(TemplateItem):
	
	def __init__(self, data):
		TemplateItem.__init__(self, data)
		self.filename = data.get('filename', "")

	def render(self, canvas, data):
		filename = Formatter().vformat(self.filename, [], data)
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

	def render(self, canvas, data):
		for i in self.items:
			i.render(canvas, data)

class DeckBuilder:

	def __init__(self, data):
		self.name = data.get('name', "")

		self.styles = {}
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

		self.templates = {}
		self.keytemplates = {}
		for td in data.get('templates', []):
			t = Template(td, self)
			self.templates[t.name] = t
			self.keytemplates[t.key] = t

	def render_card(self, canvas, card):
		canvas.saveState()
		template = self.keytemplates[card.type]
		template.render(canvas, card)
		canvas.restoreState()

class CardRenderer:

	def __init__(self):
		self.cards = []

		with open("storywar.yaml", 'r') as f:
			data = yaml.load(f)
			self.db = DeckBuilder(data)

	def prepare_canvas(self, pagesize, margin):
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

	def render_card(self, card):
		# ensure we're on a prepared page
		self.startpage()
		# render the card
		c = self.canvas
		c.saveState()
		c.translate(self.offsetx + self.x*CARDW, self.offsety - self.y*CARDH)
		self.db.render_card(c, card)
		c.restoreState()
		# advance the card position
		self.x += 1
		if self.x >= self.columns:
			self.x = 0
			self.y += 1
			if self.y >= self.rows:
				self.endpage()

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
			note = self.notefmt.format(date=DATESTR)
			p = Paragraph(note, self.copystyle)
			tx, ty = p.wrap(CARDW, 100)
			p.drawOn(self.canvas, self.offsetx, self.offsety + CARDH + 0.1*cm)

	def startpage(self):
		if not self.page:
			if self.drawbackground:
				# render background
				c.setFillColorRGB(0, 0, 0)
				c.rect(0, 0, self.pagesize[0], self.pagesize[1], stroke=0, fill=1)
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

	def add_card(self, c):
		self.cards.append(c)

	def all_cards_progress(self, function):
		i = 0
		widgets = [progressbar.Percentage(), ' ', progressbar.Bar(marker='=', left='[', right=']')]
		bar = progressbar.ProgressBar(widgets=widgets, maxval=len(self.cards))
		bar.start()
		for c in self.cards:
			function(c)
			i += 1
			bar.update(i)
		bar.finish()

	def prepare_cards(self, cmyk):
		# sort cards
		self.cards.sort(key=lambda c: c.type + (c.title or "zzz"))
		# ensure the destination folders exist
		def mkdir(n):
			if not os.path.exists(n): os.mkdir(n)
		mkdir("download")
		mkdir("download-cmyk")
		mkdir("tif")
		# prepare the cards
		print "Retrieving card art..."
		def retrieve(c):
			c.retrieve_image()
		self.all_cards_progress(retrieve)
		print "Converting to CMYK..."
		def convert(c):
			c.convert_image()
		self.all_cards_progress(convert)
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
		self.prepare_canvas(pagesize, (0, 0))
		self.notefmt = note
		self.guides = guides
		self.drawbackground = drawbackground
		print "Rendering to {out}...".format(out=outfile)
		def render(c):
			self.render_card(c)
		self.all_cards_progress(render)
		self.endpage()
		self.save(outfile)

def loaddata(datafile):
	if datafile.startswith("http://") or datafile.startswith("https://"):
		print "Downloading", datafile
		r = urllib2.urlopen(datafile)
		data = json.load(r)
		r.close()
		return data
	else:
		with open(datafile) as f:
			data = json.load(f)
			return data

def main(datafile, note, cmyk, outfile, pnp, card, blanks):
	maker = CardRenderer()
	data = loaddata(datafile)
	for d in data['cards']:
		maker.add_card(Card(d))
	if blanks:
		amount = 112 - len(maker.cards)
		if amount < 0 or amount % 4:
			raise Exception("weird number of cards")
		else:
			blankc = amount/4
			blankcounts = dict(MO=blankc*2, IT=blankc, LO=blankc)
			print blankcounts
			for t, amt in blankcounts.items():
				[maker.add_card(Card(dict(type=t))) for i in range(amt)]
	maker.prepare_cards(cmyk)
	if pnp:
		maker.render(A4, "%s_A4_%s.pdf" % (outfile, DATESTR), note=note)
		maker.render(LETTER, "%s_LTR_%s.pdf" % (outfile, DATESTR), note=note)
	if card:
		maker.render(CARDPAGE, "%s_CARD_%s.pdf" % (outfile, DATESTR), guides=False, drawbackground=True)

if __name__ == "__main__":
	parser = optparse.OptionParser()
	parser.add_option("-n", "--note", dest="note", action="store", default="Story War Print and Play {date}")
	parser.add_option("-c", "--cmyk", dest="cmyk", action="store_true", default=False, help="Convert images to CMYK.")
	parser.add_option("-o", "--outfile", dest="outfile", action="store")
	parser.add_option("--nopnp", dest="pnp", action="store_false", default=True)
	parser.add_option("--nocard", dest="card", action="store_false", default=True)
	parser.add_option("--noblanks", dest="blanks", action="store_false", default=True)
	(options, args) = parser.parse_args()

	main(args[0], note=options.note, cmyk=options.cmyk, outfile=options.outfile, blanks=options.blanks, pnp=options.pnp, card=options.card)

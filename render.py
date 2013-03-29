from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER

import Image
import urllib2
import os
import sys
import json
import datetime
import optparse

def style(source, font, size):
	pdfmetrics.registerFont(TTFont(font, font+'.ttf'))
	ss = getSampleStyleSheet()[source]
	ss.fontName = font
	ss.fontSize = size
	ss.alignment = TA_CENTER
	return ss

# TODO: load these from a settings file
COPYSTYLE = style('Normal', 'Candara', 8.5)
HEADERSTYLE = style('Heading1', 'Whitney-Bold', 14)
DPI = 300

A4 = (21*cm, 29.7*cm)
LETTER = (11*inch, 8.5*inch)
CARD = (2.5*inch, 3.5*inch)

CARDW = CARD[0]
CARDH = CARD[1]

IMGW = int(DPI * CARDW/inch)
IMGH = int(DPI * CARDH/inch)

DATESTR = datetime.datetime.now().strftime("%d-%b-%Y")

class Card:

	def __init__(self, data):
		self.title = data['title']
		self.copy = data['text']
		self.imageurl = data['art']
		self.id = data['id']
		self.type = data['type']
		self.localimage = None
		self.convertedimage = None

	def retrieve_image(self):
		img = os.path.join("download", str(self.id) + os.path.splitext(self.imageurl)[1])
		if not os.path.exists(img):
			r = urllib2.urlopen(self.imageurl)
			print "Fetch", self.imageurl
			downf = "download/temp"
			with open(downf, "wb") as f:
				buf = r.read(128)
				while buf:
					f.write(buf)
					buf = r.read(128)
			r.close()
			os.rename(downf, img)
		self.localimage = img

	def convert_image(self, cmyk):
		if not self.convertedimage:
			frame = Image.open("frame_%s.png" % self.type)
			mode = (cmyk and "CMYK") or "RGBA"
			new = Image.new(mode, frame.size)
			art = Image.open(self.localimage).resize((609, 609))
			new.paste((0, 0, 0))
			new.paste(art, (int((new.size[0]-art.size[0])*0.5), 175))
			new.paste(frame, mask=frame)
			new = new.resize((IMGW, IMGH))

			fn = os.path.splitext(os.path.split(self.localimage)[1])[0] + ".tif"
			self.convertedimage = os.path.join("gen", fn)
			new.save(self.convertedimage)

class CardMaker:

	def __init__(self):
		self.cards = []

	def prepare_canvas(self, outfile, pagesize, margin):
		self.pagesize = pagesize
		self.x = 0
		self.y = 0
		self.columns = int((pagesize[0]-margin[0]*2) / CARDW)
		self.rows = int((pagesize[1]-margin[1]*2) / CARDH)
		self.offsetx = (pagesize[0] - self.columns*CARDW) * 0.5
		self.offsety = (pagesize[1] - CARDH) - (pagesize[1] - self.rows*CARDH) * 0.5
		self.canvas = canvas.Canvas(outfile, pagesize=(pagesize[0], pagesize[1]))

	def render_card(self, card):
		x, y = (self.offsetx + self.x*CARDW, self.offsety - self.y*CARDH)
		c = self.canvas
		# render image
		c.drawImage(card.convertedimage, x, y, width=CARDW, height=CARDH)
		# render title
		p = Paragraph(card.title, HEADERSTYLE)
		p.wrap(2.5*inch, 100)
		p.drawOn(c, x, y+210.5)
		# render copy
		lines = card.copy.splitlines()
		i = 0
		for l in lines:
			p = Paragraph(l, COPYSTYLE)
			tx, ty = p.wrap(2.5*inch, 100)
			p.drawOn(c, x, y+28.25-ty*i+ty*0.5*len(lines))
			i += 1
		self.x += 1
		if self.x >= self.columns:
			self.x = 0
			self.y += 1
			if self.y >= self.rows:
				self.page()

	def drawGuides(self):
		# TODO: draw guides based on cmdline opts
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
		# TODO: cmdline opt note
		note = self.notefmt.format(date=DATESTR)
		p = Paragraph(note, COPYSTYLE)
		tx, ty = p.wrap(CARDW, 100)
		p.drawOn(self.canvas, self.offsetx, self.offsety + CARDH + 0.1*cm)

	def page(self):
		if self.notefmt: 
			self.note()
		if self.guides:
			self.drawGuides()
		print "--page--"
		self.x = 0
		self.y = 0
		self.canvas.showPage()

	def add_card(self, c):
		self.cards.append(c)

	def prepare_cards(self, cmyk):
		# ensure the destination folders exist
		if not os.path.exists("download"):
			os.mkdir("download")
		if not os.path.exists("gen"):
			os.mkdir("gen")
		# prepare the cards
		print "Retrieving card art..."
		for c in self.cards:
			c.retrieve_image()
		print "Converting to CMYK..."
		for c in self.cards:
			c.convert_image(cmyk)

	def save(self):
		self.canvas.save()

	def render(self, pagesize, outfile, margin=(0, 0), note="", guides=True):
		self.prepare_canvas(outfile, pagesize, margin)
		self.notefmt = note
		self.guides = guides
		print "Rendering to {out}...".format(out=outfile)
		for c in self.cards:
			print c.title
			self.render_card(c)
		if self.x or self.y:
			self.page()
		self.canvas.save()

def loaddata(datafile):
	if datafile.startswith("http://") or datafile.startswith("https://"):
		# TODO: load from web
		return dict(cards=[])
	else:
		with open(datafile) as f:
			data = json.load(f)
			return data

def main(datafile, note="", cmyk=False, outfile="out"):
	maker = CardMaker()
	data = loaddata(datafile)
	for d in data['cards']:
		maker.add_card(Card(d))
	maker.prepare_cards(cmyk)
	maker.render(A4, "%s_A4_%s.pdf" % (outfile, DATESTR), note=note)
	maker.render(LETTER, "%s_LTR_%s.pdf" % (outfile, DATESTR), note=note)
	maker.render(CARD, "%s_CARD_%s.pdf" % (outfile, DATESTR), guides=False)

if __name__ == "__main__":
	parser = optparse.OptionParser()
	parser.add_option("-n", "--note", dest="note", action="store", default="Story War BETA ({date})")
	parser.add_option("-c", "--cmyk", dest="cmyk", action="store_true", default=False, help="Convert images to CMYK.")
	parser.add_option("-o", "--outfile", dest="outfile", action="store")
	(options, args) = parser.parse_args()

	main(args[0], note=options.note, cmyk=options.cmyk, outfile=options.outfile)

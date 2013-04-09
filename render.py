from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch, cm, mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER

import Image
import urllib2
import os
import sys
import json
import datetime
import optparse

import progressbar

def style(source, fontstr):
	font, size = fontstr.split(":")
	pdfmetrics.registerFont(TTFont(font, font+'.ttf'))
	ss = getSampleStyleSheet()[source]
	ss.fontName = font
	ss.fontSize = float(size)
	ss.alignment = TA_CENTER
	return ss

DPI = 300

A4 = (210*mm, 297*mm)
LETTER = (11*inch, 8.5*inch)
CARDPAGE = ((63+6)*mm, (88+6)*mm)
CARD = (63*mm, 88*mm)
FRAME = (63*mm, 88*mm)

CARDW = CARD[0]
CARDH = CARD[1]

IMGSIZE = inch*2

PIXW = int(DPI * CARDW/inch)
PIXH = int(DPI * CARDH/inch)

DATESTR = datetime.datetime.now().strftime("%d-%b-%Y")

class Card:

	def __init__(self, data):
		self.title = data['title']
		self.copy = data['text']
		if data['cmyk']:
			self.imageurl = data['cmyk']
			self.cmyk = True
		else:
			self.imageurl = data['art']
			self.cmyk = False
		self.cid = data['id']
		self.type = data['type']
		self.localimage = None
		self.convertedimage = None
		self.chash = data['hash'] or self.cid
		self.cname = "{0}_{1}".format(self.cid, self.chash or "")

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
		else:
			print self.title, "- No url."

	def convert_image(self, cmyk):
		try:
			if self.localimage and not self.convertedimage:
				frame = Image.open("frame_%s.png" % self.type)
				mode = (cmyk and "CMYK") or "RGBA"
				new = Image.new(mode, frame.size)
				art = Image.open(self.localimage).resize((609, 609))
				new.paste((0, 0, 0))
				new.paste(art, (int((new.size[0]-art.size[0])*0.5), 175))
				new.paste(frame, mask=frame)
				new = new.resize((PIXW, PIXH))

				fn = os.path.splitext(os.path.split(self.localimage)[1])[0] + ".tif"
				self.convertedimage = os.path.join("gen", fn)
				new.save(self.convertedimage)
		except Exception as e:
			pass

class CardMaker:

	def __init__(self, hfont, cfont):
		self.cards = []
		self.headerstyle = style("Heading1", hfont)
		self.copystyle = style("Normal", cfont)
		self.copystyle.leading = 10

	def prepare_canvas(self, outfile, pagesize, margin):
		self.pagesize = pagesize
		self.x = 0
		self.y = 0
		self.columns = int((pagesize[0]-margin[0]*2) / CARDW)
		self.rows = int((pagesize[1]-margin[1]*2) / CARDH)
		self.offsetx = (pagesize[0] - self.columns*CARDW) * 0.5
		self.offsety = (pagesize[1] - CARDH) - (pagesize[1] - self.rows*CARDH) * 0.5
		self.canvas = canvas.Canvas(outfile, pagesize=(pagesize[0], pagesize[1]))

		self.frames = {x: ("frame_{type}.tif".format(type=x)) for x in ("IT", "LO", "MO")}
		self.background = False
	
	def render_card(self, card):
		x, y = (self.offsetx + self.x*CARDW, self.offsety - self.y*CARDH)
		c = self.canvas
		if self.drawbackground and not self.background:
			# render background
			c.setFillColorRGB(0, 0, 0)
			c.rect(0, 0, self.pagesize[0], self.pagesize[1], stroke=0, fill=1)
			self.background = True
		# render frame
		frameimg = self.frames[card.type]
		c.drawImage(frameimg, x, y, width=FRAME[0], height=FRAME[1])
		# render image
		try:
			c.drawImage(card.localimage, x+(CARDW-IMGSIZE)/2, y+21.6*mm, width=inch*2, height=inch*2)
		except Exception as e:
			print card.title
			print e
		# render title
		p = Paragraph(card.title, self.headerstyle)
		p.wrap(CARDW, 100)
		p.drawOn(c, x, y+208)
		# render copy
		lines = card.copy.splitlines()
		i = 0
		for l in lines:
			p = Paragraph(l, self.copystyle)
			tx, ty = p.wrap(CARDW, 100)
			p.drawOn(c, x, y+28.1-ty*i+ty*0.5*len(lines))
			i += 1
		self.x += 1
		if self.x >= self.columns:
			self.x = 0
			self.y += 1
			if self.y >= self.rows:
				self.page()

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
		note = self.notefmt.format(date=DATESTR)
		p = Paragraph(note, self.copystyle)
		tx, ty = p.wrap(CARDW, 100)
		p.drawOn(self.canvas, self.offsetx, self.offsety + CARDH + 0.1*cm)

	def page(self):
		if self.notefmt: 
			self.note()
		if self.guides:
			self.drawGuides()
		self.x = 0
		self.y = 0
		self.canvas.showPage()
		self.background = False

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
			c.convert_image(cmyk)
		# self.all_cards_progress(convert)

	def save(self):
		self.canvas.save()

	def render(self, pagesize, outfile, note='', guides=True, drawbackground=False):
		self.prepare_canvas(outfile, pagesize, (0, 0))
		self.notefmt = note
		self.guides = guides
		self.drawbackground = drawbackground
		print "Rendering to {out}...".format(out=outfile)
		def render(c):
			self.render_card(c)
		self.all_cards_progress(render)
		if self.x or self.y:
			self.page()
		self.canvas.save()

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

def main(datafile, note, cmyk, outfile, hfont, cfont, pnp, card):
	maker = CardMaker(hfont, cfont)
	data = loaddata(datafile)
	for d in data['cards']:
		maker.add_card(Card(d))
	maker.prepare_cards(cmyk)
	if pnp:
		maker.render(A4, "%s_A4_%s.pdf" % (outfile, DATESTR), note=note)
		maker.render(LETTER, "%s_LTR_%s.pdf" % (outfile, DATESTR), note=note)
	if card:
		maker.render(CARDPAGE, "%s_CARD_%s.pdf" % (outfile, DATESTR), guides=False, drawbackground=True)

if __name__ == "__main__":
	parser = optparse.OptionParser()
	parser.add_option("-n", "--note", dest="note", action="store", default="Story War BETA ({date})")
	parser.add_option("-c", "--cmyk", dest="cmyk", action="store_true", default=False, help="Convert images to CMYK.")
	parser.add_option("-o", "--outfile", dest="outfile", action="store")
	parser.add_option("--headerfont", dest="hfont", action="store", default="Whitney-Bold:14")
	parser.add_option("--copyfont", dest="cfont", action="store", default="Candara:8.5")
	parser.add_option("--nopnp", dest="pnp", action="store_false", default=True)
	parser.add_option("--nocard", dest="card", action="store_false", default=True)
	(options, args) = parser.parse_args()

	main(args[0], note=options.note, cmyk=options.cmyk, outfile=options.outfile, hfont=options.hfont, cfont=options.cfont, pnp=options.pnp, card=options.card)

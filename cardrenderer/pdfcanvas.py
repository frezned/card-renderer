import tempfile, os

from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import mm

from canvas import Canvas
import error

def tomm(num):
	if type(num) in (float, int):
		return num * mm
	else:
		return tuple([x * mm for x in num])

class PDFCanvas(Canvas):

	def __init__(self, res, cardw, cardh, outfile, pagesize, margin=(0,0), background=False, note=None, guides=(128, 128, 128), separators=(255, 255, 255), dpi=300, compat=False, **kwargs):
		self.outfile = outfile
		self.drawbackground = background
		self.pagesize = tomm(pagesize)
		self.margin = tomm(margin)
		self.x = 0
		self.y = 0
		self.page = False
		self.tempfile = tempfile.mktemp()
		self.canvas = canvas.Canvas(self.tempfile, pagesize=self.pagesize)
		self.styles = {}
		self.note = note
		if guides == True:
			guides = (255, 255, 255)
		self.guides = guides and tuple([x * (1/255.0) for x in guides])
		self.separators = separators and tuple([x * (1/255.0) for x in separators])
		if note:
			self.addStyle(dict(name='note', size=8, align='center'))
		self.dpi = dpi
		self.res = res
		self.compat = compat
		self.cardw = None
		self.cardh = None
		self.setSize(cardw, cardh)

	def setSize(self, cardw, cardh):
		cardw = tomm(cardw)
		cardh = tomm(cardh)
		if not (cardw == self.cardw and cardh == self.cardh):
			self.cardw = cardw
			self.cardh = cardh
			self.columns = int((self.pagesize[0]-self.margin[0]*2) / self.cardw)
			self.rows = int((self.pagesize[1]-self.margin[1]*2) / self.cardh)
			self.offsetx = (self.pagesize[0] - self.columns*self.cardw) * 0.5
			self.offsety = (self.pagesize[1] - self.cardh) - (self.pagesize[1] - self.rows*self.cardh) * 0.5
			if self.page:
				self.endPage()

	@error.unsupportedFunction
	def drawRect(self, *args, **kwargs):
		pass 

	@error.unsupportedParameter("mask")
	def drawImage(self, filename, x=0, y=0, width=None, height=None, mask=None):
		width = width or self.cardw
		height = height or self.cardh
		filename = self.res.getFilename(filename, self.dpi)
		if os.path.exists(filename):
			try:
				self.canvas.drawImage(filename, tomm(x), tomm(y), tomm(width), tomm(height))
			except Exception, a:
				print "ERROR:", filename, a
		else:
			print "ERROR: No file", filename

	def addStyle(self, data):
		def addFont(fontfile):
			if not fontfile:
				return None
			elif fontfile.endswith(".ttf") or fontfile.endswith(".otf"):
				fontname = os.path.splitext(fontfile)[0]
				pdfmetrics.registerFont(TTFont(fontname, fontfile))
				print "Registered", fontfile
				return fontname
			else:
				return fontfile
		name = data.get('name', "")
		s = ParagraphStyle(name)
		normal = addFont(data.get('font', "Helvetica"))
		bold = addFont(data.get('bold', None))
		italic = addFont(data.get('italic', None))
		bolditalic = addFont(data.get('bolditalic', None))
		pdfmetrics.registerFontFamily(normal, normal=normal, bold=bold or normal, italic=italic or normal, boldItalic=bolditalic or normal)
		s.fontName = normal
		s.fontSize = data.get('size', 10)
		s.alignment = dict(center=TA_CENTER, left=TA_LEFT, right=TA_RIGHT)[data.get('align', 'left')]
		s.leading = data.get('leading', s.leading)
		s.valign = data.get('valign', "top")
		s.textColor = data.get('color', "#ff000000")
		self.styles[name] = s

	def renderText(self, text, style=None, x=0, y=0, width=None, height=None):
		width = width or self.cardw
		height = height or self.cardh
		lines = text.splitlines()
		styledata = self.styles[style]
		if self.compat:
			i = 0
			for l in lines:
				p = Paragraph(l, styledata)
				tx, ty = p.wrap(tomm(width), tomm(height))
				voffset = ty*0.5*len(lines) - ty*i
				p.drawOn(self.canvas, tomm(x), tomm(y) + voffset)
				i += 1
		else:
			text = "<br />".join(lines)
			p = Paragraph(text, styledata)
			tx, ty = p.wrap(tomm(width), tomm(height))
			if styledata.valign == "top":
				offset = 0
			elif styledata.valign == "mid":
				offset = 0.5 * ty
			elif styledata.valign == "bottom":
				offset = ty
			p.drawOn(self.canvas, tomm(x), tomm(y) - offset)

	def beginCard(self, card):
		if not self.page:
			self.beginPage()
		self.canvas.saveState()
		self.canvas.translate(self.offsetx + self.x*self.cardw, self.offsety - self.y*self.cardh)

	def endCard(self):
		self.canvas.restoreState()
		# advance the card position
		self.x += 1
		if self.x >= self.columns:
			self.x = 0
			self.y += 1
			if self.y >= self.rows:
				self.endPage()

	def beginPage(self):
		assert not self.page
		if self.drawbackground:
			# render background
			self.canvas.setFillColorRGB(0, 0, 0)
			self.canvas.rect(0, 0, self.pagesize[0], self.pagesize[1], stroke=0, fill=1)
		self.page = True

	def endPage(self):
		assert self.page
		if self.note: 
			self.drawNote()
		if self.guides:
			self.drawGuides()
		self.x = 0
		self.y = 0
		self.canvas.showPage()
		self.page = False

	def drawGuides(self):
		canvas = self.canvas
		left = self.offsetx
		right = left + self.cardw*self.columns
		top = self.offsety + self.cardh
		bottom = top - self.cardh*self.rows
		for ix in range(0, self.columns+1):
			x = self.offsetx + self.cardw*ix
			canvas.setStrokeColorRGB(*self.guides)
			canvas.line(x, self.pagesize[1], x, top)
			canvas.line(x, bottom, x, 0)
			canvas.setStrokeColorRGB(*self.separators)
			canvas.line(x, top, x, bottom)
		for iy in range(-1, self.rows):
			y = self.offsety - self.cardh*iy
			canvas.setStrokeColorRGB(*self.guides)
			canvas.line(0, y, left, y)
			canvas.line(right, y, self.pagesize[0], y)
			canvas.setStrokeColorRGB(*self.separators)
			canvas.line(left, y, right, y) 

	def drawNote(self):
		if self.note:
			self.renderText(self.note, 'note', self.offsetx, self.offsety + self.cardh + 1*mm, self.cardw, 100)

	def getFilename(self):
		return self.outfile

	def finish(self):
		if self.page:
			self.endPage()
		self.canvas.save()
		outfile = self.outfile
		fn, ext = os.path.splitext(outfile)
		amt = 0
		while True:
			try:
				if os.path.exists(outfile):
					os.unlink(outfile)
				os.rename(self.tempfile, outfile)
				return [outfile]
			except WindowsError as e:
				amt += 1
				outfile = "{0}_{1}{2}".format(fn, amt, ext)

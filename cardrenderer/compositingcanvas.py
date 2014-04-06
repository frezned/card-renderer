
from canvas import Canvas
from pdfcanvas import PDFCanvas
from imagecanvas import ImageCanvas

class CompositingCanvas(Canvas):

	def __init__(self, **kwargs):
		self.pdf = PDFCanvas(**kwargs)
		self.image = ImageCanvas( filenamecb=self.imagefilename, **kwargs )
		self.card = None
		self.idx = 0

	def imagefilename( self, data ):
		self.idx += 1
		return "{0}dpi/composite/{1:03}.png".format( self.image.dpi, self.idx-1 )

	def beginCard(self, card):
		self.image.beginCard(card)
		self.texts = []
		self.card = card
	
	def endCard(self):
		# draw image
		outfn = self.image.endCard()
		self.pdf.beginCard(self.card)
		# don't use the PDFCanvas' renderer output, as that'll trigger the resource manager!
		# just use the actual canvas directly
		self.pdf.canvas.drawImage(outfn, 0, 0, self.pdf.cardw, self.pdf.cardh)
		# draw texts
		for t in self.texts:
			self.pdf.renderText(*t)
		self.pdf.endCard()

	def drawRect(self, fill=(0, 0, 0, 0), radius=0, x=0, y=0, width=0, height=0, mask=None):
		self.image.drawRect(fill, radius, x, y, width, height, mask)

	def drawImage(self, filename, x=0, y=0, width=None, height=None, mask=None):
		self.image.drawImage(filename, x, y, width, height, mask)

	def renderText(self, text, style=None, x=0, y=0, width=None, height=None):
		# save for later
		self.texts.append((text, style, x, y, width, height))
	
	def getFilename(self):
		return self.pdf.getFilename()

	def addStyle(self, data):
		self.pdf.addStyle(data)

	def finish(self):
		return self.pdf.finish()

	def setSize(self, cardw, cardh):
		self.pdf.setSize(cardw, cardh)
		self.image.setSize(cardw, cardh)


from canvas import Canvas
from pdfcanvas import PDFCanvas
from imagecanvas import ImageCanvas

class CompositingCanvas(Canvas):

	def __init__(self, **kwargs):
		self.pdf = PDFCanvas(**kwargs)
		self.image = ImageCanvas( filenamecb=self.imagefilename, **kwargs )
		self.card = None
		self.idx = 0

	def imagefilename(self, imageCanvas, fmt, data):
		self.idx += 1
		return "{0}dpi/composite/{1:03}.png".format( imageCanvas.dpi, self.idx-1)

	def beginCard(self, card):
		self.image.beginCard(card)
		self.texts = []
		self.card = card
	
	def endCard(self):
		# draw image
		outfn = self.image.endCard()
		self.pdf.beginCard(self.card)
		self.pdf.canvas.drawImage(outfn, 0, 0, self.pdf.cardw, self.pdf.cardh)
		# draw texts
		for t in self.texts:
			self.pdf.renderText(*t)
		self.pdf.endCard()

	def drawImage(self, filename, x, y, width, height):
		self.image.drawImage(filename, x, y, width, height)

	def renderText(self, text, stylename, x, y, width, height):
		# save for later
		self.texts.append((text, stylename, x, y, width, height))
	
	def getfilename(self):
		return self.pdf.getfilename()

	def addStyle(self, data):
		self.pdf.addStyle(data)

	def finish(self):
		return self.pdf.finish()

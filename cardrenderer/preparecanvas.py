from imageresource import Resources
from canvas import Canvas

class PrepareCanvas(Canvas):

	def __init__(self, res):
		self.images = []
		self.res = res or Resources("res")

	def drawImage(self, filename, x=0, y=0, width=None, height=None):
		self.res.markneeded(filename, width, height)

	def renderText(self, text, style=None, x=0, y=0, width=None, height=None):
		pass

from imageresource import Resources
from canvas import Canvas

class PrepareCanvas(Canvas):

	def __init__(self, res):
		self.images = []
		self.res = res or Resources("res")

	def drawImage(self, filename, x, y, width, height):
		self.res.markneeded(filename, width, height)

	def renderText(self, text, stylename, x, y, width, height):
		pass

from imageresource import Resources
from canvas import Canvas

class PrepareCanvas(Canvas):

	def __init__(self, res):
		self.images = []
		self.res = res or Resources("res")

	def drawImage(self, filename, x=0, y=0, width=None, height=None, mask=None):
		if type(filename) is str or type(filename) is unicode:
			self.res.markneeded(filename, width, height)
		if mask:
			self.res.markneeded(mask, width, height)

	def renderText(self, text, style=None, x=0, y=0, width=None, height=None):
		pass

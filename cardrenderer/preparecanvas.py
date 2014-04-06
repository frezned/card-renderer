from imageresource import Resources
from canvas import Canvas

class PrepareCanvas(Canvas):

	def __init__(self, res):
		self.images = []
		self.res = res or Resources("res")

	def drawRect(self, fill=(0, 0, 0, 0), radius=0, x=0, y=0, width=0, height=0, mask=None):
		if mask:
			self.res.markneeded(mask, width, height)

	def drawImage(self, filename, x=0, y=0, width=None, height=None, mask=None):
		if type(filename) is str or type(filename) is unicode:
			self.res.markneeded(filename, width, height)
		if mask:
			self.res.markneeded(mask, width, height)


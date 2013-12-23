from imageresource import Resources

class PrepareCanvas:

	def __init__(self, res):
		self.images = []
		self.res = res or Resources("res")

	def beginCard(self):
		pass

	def endCard(self):
		pass

	def addStyle(self):
		pass

	def drawImage(self, filename, x, y, width, height):
		self.res.markneeded(filename, width, height)

	def renderText(self, text, stylename, x, y, width, height):
		pass

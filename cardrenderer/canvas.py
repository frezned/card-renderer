
class Canvas(object):

	def beginCard(self, card):
		pass

	def endCard(self):
		pass

	def addStyle(self, data):
		pass

	def drawImage(self, filename, x=0, y=0, width=None, height=None, mask=None):
		pass

	def renderText(self, text, style=None, x=0, y=0, width=None, height=None):
		pass

	def getFilename(self):
		pass

	def finish(self):
		pass

	def setSize(self, cardw, cardh):
		pass

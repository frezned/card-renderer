
class Canvas(object):

    def beginCard(self, card):
        pass

    def endCard(self):
        pass

    def addStyle(self, data):
        pass

    def drawRect(self, fill=(0, 0, 0, 0), stroke=None, radius=0, x=0, y=0, width=0, height=0, mask=None):
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

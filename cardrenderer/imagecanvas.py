import tempfile, os

from PIL import Image, ImageDraw, ImageFont
from canvas import Canvas

inch = 25.4

def mkdir(n):
	if not os.path.exists(n): os.mkdir(n)

class ImageCanvas(Canvas):
    
	def __init__(self, res, cardw, cardh, outfmt="card.png", filenamecb=None, **kwargs):
		self.card = None
		self.cardw = cardw
		self.cardh = cardh
		self.image = None
		if kwargs:
			self.dpi = kwargs['dpi'] or 300
		else:
			self.dpi = 300
		self.scale = self.dpi / inch
		self.size = (int(cardw*self.scale), int(cardh*self.scale))
		self.finalsize = self.size #(825, 1125)
		self.outfmt = outfmt
		self.filenamecb = filenamecb or self.format
		self.styles = {}
		self.imgheight = self.size[1]
		self.res = res
		self.cmyk = outfmt.endswith(".tif")
		self.renderedcards = []

	def format(self, data):
		return self.outfmt.format( data )
			
	def getfilename(self):
		return self.outfmt

	def drawImage(self, filename, x=0, y=0, width=None, height=None):
		width = width or self.cardw
		height = height or self.height
		filename = self.res.getfilename(filename, self.dpi)
		if os.path.exists(filename):
			source = Image.open(filename).resize((int(width*self.scale), int(height*self.scale)))
			y = self.imgheight-(height*self.scale)-(y*self.scale)
			pos = (int(x*self.scale), int(y))
			try:
				self.image.paste(source, pos, source)
			except ValueError:
				self.image.paste(source, pos)

	def addStyle(self, data):
		s = {}
		s['name'] = data.get('name', "")
		s['size'] = int(data.get('size', 10)*self.scale*0.38)
		fontfile = data.get('font', "Candara.ttf")
		if fontfile.endswith(".ttf") or fontfile.endswith(".otf"):
			s['font'] = ImageFont.truetype(fontfile, s['size'])
		else:
			raise Exception("Text rendering on image output currently only supports .ttf files.")
		s['alignment'] = data.get('align', 'left')
		self.styles[s['name']] = s
		print "Added style (*{scale})".format(s=s, scale=self.scale)

	def renderText(self, text, style=None, x=0, y=0, width=None, height=None):
		width = width or self.cardw
		height = height or self.height
		lines = text.splitlines()
		i = 0
		styledata = self.styles[style]
		font = styledata['font']
		draw = ImageDraw.Draw(self.image)
		y = self.imgheight - y*self.scale
		for l in lines:
			tx, ty = font.getsize(l)
			xoffset = 0
			if styledata['alignment'] == 'center':
				xoffset = (width*self.scale-tx)*0.5
			voffset = ty*0.5*len(lines) - ty*(i-0.5)
			draw.text((int(x*self.scale + xoffset), int(y - voffset)), l, font=font, fill=(0,0,0))
			i += 1

	def beginCard(self, card):
		self.card = card
		self.image = Image.new(self.cmyk and "CMYK" or "RGBA", self.size)

	def endCard(self):
		fndata = dict(self.card)
		fndata['cardidx'] = len(self.renderedcards)
		outf = self.filenamecb( fndata )
        #  create directory if it doesn't exist
		mkdir( os.path.split( outf )[0] )
		
		finalimage = Image.new(self.cmyk and "CMYK" or "RGBA", self.finalsize)
		finalimage.paste((0,0,0))
		def getpad(idx):
			return int(0.5*(self.finalsize[idx] - self.size[idx]))
		finalimage.paste(self.image, (getpad(0), getpad(1)))
		finalimage.save(outf, format=self.cmyk and "TIFF" or "PNG")
		self.renderedcards.append(outf)
		return outf

	def finish(self):
		return self.renderedcards


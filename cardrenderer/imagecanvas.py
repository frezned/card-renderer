import tempfile, os

from PIL import Image, ImageDraw, ImageFont

class ImageCanvas:

	def __init__(self, res, cardw, cardh, outfmt, filenamecb):
		self.card = None
		self.image = None
		self.scale = 750.0 / cardw
		self.size = (int(cardw*self.scale), int(cardh*self.scale))
		self.finalsize = self.size #(825, 1125)
		self.outfmt = outfmt
		self.filenamecb = filenamecb
		self.styles = {}
		self.imgheight = self.size[1]
		self.dpi = 300
		self.res = res
		self.renderedcards = []

	def drawImage(self, filename, x, y, width, height):
		filename = self.res.getfilename(filename, self.dpi)
		if os.path.exists(filename):
			source = Image.open(filename).resize((int(width*self.scale), int(height*self.scale)))
			y = self.imgheight-(height*self.scale)-(y*self.scale)
			self.image.paste(source, (int(x*self.scale), int(y)), source)

	def addStyle(self, data):
		s = {}
		s['name'] = data.get('name', "")
		s['size'] = int(data.get('size', 10)*self.scale)
		fontfile = data.get('font', "Candara.ttf")
		if fontfile.endswith(".ttf") or fontfile.endswith(".otf"):
			s['font'] = ImageFont.truetype(fontfile, s['size'])
		else:
			raise Exception("Text rendering on image output currently only supports .ttf files.")
		s['alignment'] = data.get('align', 'left')
		self.styles[s['name']] = s

	def renderText(self, text, stylename, x, y, width, height):
		lines = text.splitlines()
		i = 0
		style = self.styles[stylename]
		font = style['font']
		draw = ImageDraw.Draw(self.image)
		y = self.imgheight - y*self.scale
		for l in lines:
			tx, ty = font.getsize(l)
			xoffset = 0
			if style['alignment'] == 'center':
				xoffset = (width*self.scale-tx)*0.5
			voffset = ty*0.5*len(lines) - ty*(i-0.5)
			draw.text((int(x*self.scale + xoffset), int(y - voffset)), l, font=font, fill=(0,0,0))
			i += 1

	def beginCard(self, card):
		self.card = card
		self.image = Image.new("RGBA", self.size)

	def endCard(self):
		fndata = dict(self.card)
		fndata['cardidx'] = len(self.renderedcards)
		outf = self.filenamecb(self.outfmt, fndata)
		finalimage = Image.new("RGBA", self.finalsize)
		finalimage.paste((0,0,0))
		def getpad(idx):
			return int(0.5*(self.finalsize[idx] - self.size[idx]))
		finalimage.paste(self.image, (getpad(0), getpad(1)))
		finalimage.save(outf, format="PNG")
		self.renderedcards.append(outf)

	def finish(self):
		return self.renderedcards


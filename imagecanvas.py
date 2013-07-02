import tempfile, os

from PIL import Image, ImageDraw, ImageFont

SC = 3

class ImageCanvas:

	def __init__(self, cardw, cardh, outfmt, filenamecb):
		self.card = None
		self.image = None
		self.size = (int(cardw*SC), int(cardh*SC))
		self.outfmt = outfmt
		self.filenamecb = filenamecb
		self.styles = {}
		self.imgheight = self.size[1]

	def drawImage(self, filename, x, y, width, height):
		source = Image.open(filename).resize((int(width*SC), int(height*SC)))
		y = self.imgheight-(height*SC)-(y*SC)
		self.image.paste(source, (int(x*SC), int(y)))

	def addStyle(self, data):
		s = {}
		s['name'] = data.get('name', "")
		s['size'] = int(data.get('size', 10)*SC)
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
		y = self.imgheight - y*SC
		for l in lines:
			tx, ty = font.getsize(l)
			xoffset = 0
			if style['alignment'] == 'center':
				xoffset = (width*SC-tx)*0.5
			voffset = ty*0.5*len(lines) - ty*(i-0.5)
			draw.text((int(x*SC + xoffset), int(y - voffset)), l, font=font, fill=(0,0,0))
			i += 1

	def beginCard(self, card):
		self.card = card
		self.image = Image.new("RGBA", self.size)

	def endCard(self):
		outf = self.filenamecb(self.outfmt, self.card)
		self.image.save(outf)

	def finish(self):
		pass


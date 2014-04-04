import HTMLParser # for unescape
import error

class TemplateItem:

	def __init__(self, template, data):
		self.template = template
		self.name = data.get('name', "")
		self.width = data.get('width', 0) or template.cardw
		self.height = data.get('height', 0) or template.cardh
		def coordormid(key, ref):
			val = data.get(key, 0)
			if val == "mid":
				return ref
			else:
				return val
		self.x = coordormid('x', 0.5*(template.cardw-self.width))
		self.y = coordormid('y', 0.5*(template.cardh-self.height))
		if data.get('hcenter', False):
			self.x = (template.cardw-self.width) / 2
	
	def format(self, fmtstring, data):
		return self.template.builder.format(fmtstring, data)

	def prepare(self, data):
		pass

class GraphicTemplateItem(TemplateItem):
	
	def __init__(self, template, data):
		TemplateItem.__init__(self, template, data)
		self.filename = data.get('filename', "")

	def render(self, canvas, data):
		url = self.format(self.filename, data)
		if url:
			canvas.drawImage(url, self.x, self.y, self.width, self.height)
		else:
			print "ERROR: blank url", data.get("title", "??")

class TextTemplateItem(TemplateItem):

	def __init__(self, template, data):
		TemplateItem.__init__(self, template, data)
		self.textformat = data.get('format', "{" + self.name + "}")
		self.style = data.get('style', self.name)

	def render(self, canvas, data):
		string = self.format(self.textformat, data)
		string = HTMLParser.HTMLParser().unescape(string)
		canvas.renderText(string, self.style, self.x, self.y, self.width, self.height)

class FunctionTemplateItem(TemplateItem):

	def __init__(self, template, data):
		TemplateItem.__init__(self, template, data)
		self.callback = data.get('callback', None)

	def render(self, canvas, data):
		if self.callback:
			self.callback(self, canvas, data)

class Template:

	def __init__(self, builder, **data):
		self.builder = builder
		self.cardw = data.get('cardw', builder.cardw)
		self.cardh = data.get('cardh', builder.cardh)
		self.items = []
		for e in data.get('elements', []):
			if type(e) == str:
				self.element(e)
			else:
				self.element(**e)
		self.cards = []

	@error.deprecated("Template.text", "Template.image", "Template.function")
	def element(self, *args, **kwargs):
		if len(args) == 1 and type(args[0]) == str and len(kwargs)==0:
			other = self.builder.templates[args[0]]
			for i in other.items:
				self.items.append(i)
		elif 'callback' in kwargs:
			self.items.append(FunctionTemplateItem(self, kwargs))
		elif 'filename' in kwargs:
			self.items.append(GraphicTemplateItem(self, kwargs))
		else:
			self.items.append(TextTemplateItem(self, kwargs))

	def text(self, format, **kwargs):
		kwargs['format'] = format
		self.items.append(TextTemplateItem(self, kwargs))

	def image(self, filename, **kwargs):
		kwargs['filename'] = filename
		self.items.append(GraphicTemplateItem(self, kwargs))

	def function(self, callback, **kwargs):
		kwargs['callback'] = callback
		self.items.append(FunctionTemplateItem(self, kwargs))

	def render(self, canvas, data):
		for i in self.items:
			i.render(canvas, data)
	
	def prepare(self, data):
		for i in self.items:
			i.prepare(data)

	def card(self, **card):
		self.cards.append(card)

	def use(self, urls, csv=False):
		if type(urls) == str:
			for c in loaddata(urls, csv):
				self.card(**c)
		else:
			for u in urls:
				self.use(u, csv)

	def sort(self):
		self.cards.sort(key=lambda x: x.get('title', x.get('name', None)) or 'zzzzzzzzzzzzzz')

import requests
import os
import sys
import json
import datetime
import optparse
import tempfile
import collections
from string import Formatter

import progressbar

from pdfcanvas import PDFCanvas
from compositingcanvas import CompositingCanvas
from imagecanvas import ImageCanvas
from preparecanvas import PrepareCanvas
from imageresource import Resources
from template import Template

inch = 25.4

CARD = (63, 88)
SIZES = {}
SIZES["A4"] = (210, 297)
SIZES["A4-P"] = (210, 297)
SIZES["A4-L"] = (297, 210)
SIZES["LETTER"] = (11*inch, 8.5*inch)
SIZES["LETTER-P"] = (8.5*inch, 11*inch)
SIZES["LETTER-L"] = (11*inch, 8.5*inch)
SIZES["CARD"] = ((63+6), (88+6))
FRAME = (63, 88)

class CardRenderer:

    def __init__(self, cardw=CARD[0], cardh=CARD[1]):
        self.styles = {}
        self.states = {}
        self.templates = []
        self.readfiles = set()
        self.outputs = []
        self.name = ""
        self.cardw = cardw
        self.cardh = cardh
        self.data = dict(
                name="",
                date=datetime.datetime.now().strftime("%d-%b-%Y")
                )
        self.styles['note'] = dict(align='center', size=9)
        self.resources = Resources("res")

    def format(self, fmtstring, data={}):
        #merged_data = {}
        #merged_data.update(self.data)
        #merged_data.update(data)
        #dd = collections.defaultdict(lambda: '???', merged_data)
        return Formatter().vformat(fmtstring, [], data)

    def render_card(self, template, card):
        self.canvas.setSize(template.cardw, template.cardh)
        self.canvas.beginCard(card)
        template.render(self.canvas, card)
        self.canvas.endCard()

    def parse_templates(self, data):
        for sd in data.get('styles', []):
            self.style(**sd)

        for td in data.get('templates', []):
            self.template(**td)

    def style(self, name=None, **descriptor):
        if name is None:
            namefmt = "{font}:{size}"
            font = os.path.splitext(descriptor.get("font", "unknown"))[0]
            size = descriptor.get("size", 10)
            name = "{}:{}".format(font, size)
            idx = 1
            while name in self.styles:
                idx += 1
                name = "{}:{}_{}".format(font, size, idx)
        descriptor["name"] = name
        self.styles[name] = descriptor
        return name

    def template(self, **kwargs):
        t = Template(self, **kwargs)
        self.templates.append(t)
        return t

    def all_cards_progress(self, function, check=None):
        i = 0
        cards = []
        for t in self.templates:
            for c in t.cards:
                cards.append((t, c))
        if check:
            cards = filter(check, cards)
        if cards:
            widgets = [progressbar.Percentage(), ' ', progressbar.Bar(marker='=', left='[', right=']')]
            bar = progressbar.ProgressBar(widgets=widgets, maxval=len(cards))
            bar.start()
            for c in cards:
                function(*c)
                i += 1
                bar.update(i)
            bar.finish()

    def prepare_cards(self):
        # ensure the destination folders exist
        # prepare the cards
        print "Preparing card art..."
        preparecanvas = PrepareCanvas(self.resources)
        def prepare(t, c):
            t.render(preparecanvas, c)
        self.all_cards_progress(prepare)
        self.page = False

    def load_states(self):
        fn = self.outputs[0]['filename'] + "_state.txt"
        if os.path.exists(fn):
            try:
                with open(fn, "r") as f:
                    self.states = json.load(f)
            except ValueError:
                self.states = {}
        else:
            self.states = {}

    def check_card_state(self, c):
        if c['id'] in self.states:
            return c.hash() != c['id']
        else:
            return True

    def save_states(self):
        cards = {}
        for t in self.templates:
            for c in t.cards:
                cards[c['id']] = c.hash()
        fn = self.outputs[0]['filename'] + "_state.txt"
        with open(fn, "w") as f:
            json.dump(cards, f)

    def render(self, pagesize, outfile, note='', guides=True, background=False, dpi=300, margin=0, filter=None, filtertemplate=None, imageextension=None, composite=False, **kwargs):
        if outfile.endswith(".pdf"):
            filename = self.format(outfile).replace(" ", "")
            if not (type(margin) is list or type(margin) is tuple):
                margin = (margin, margin)
            args = dict(
                    res=self.resources,
                    cardw=self.cardw, cardh=self.cardh, 
                    outfile=filename,
                    pagesize=pagesize, margin=margin,
                    background=background, 
                    notefmt=self.format(note),
                    dpi=dpi,
                    compat=kwargs.get("compat", False)
                    )
            kwargs.update(args)
            if composite:
                self.canvas = CompositingCanvas(**kwargs)
            else:
                self.canvas = PDFCanvas(**kwargs)
        else:
            self.canvas = ImageCanvas(self.resources, self.cardw, self.cardh, outfile, self.format)
        for s in self.styles:
            self.canvas.addStyle(self.styles[s])
        self.notefmt = note
        self.guides = guides
        self.background = background
        self.resources.prepare(dpi, imageextension)
        print "Rendering to {out}...".format(out=self.canvas.getFilename())
        def cardfilter(c):
            if self.check_card_state(c):
                if filtertemplate:
                    filt = self.format(filtertemplate, c)
                    if filter:
                        return filt in filter
                    else:
                        return filt
                else:
                    return True
            else:
                return False
        def render(t, c):
            if cardfilter(c):
                for i in range(int(c.get('copies', 1))):
                    self.render_card(t, c)
        self.all_cards_progress(render)
        return self.canvas.finish()

    def readfile(self, filename):
        if filename not in self.readfiles:
            self.readfiles.add(filename)
            data = loaddata(filename)
            self.parse_data(**data)
            self.parse_use(data.get('use', None))
            self.parse_output(data)
            self.parse_templates(data)
            self.parse_decks(data)

    def parse_data(self, cardwidth=None, cardheight=None, **kwargs):
        if cardwidth:
            self.cardw = cardwidth
        if cardheight:
            self.cardh = cardheight
        self.data.update(kwargs)

    def parse_use(self, filename=None):
        if filename:
            if type(filename) == str:
                self.readfile(filename)
            else:
                for u in filename:
                    self.readfile(u)

    def parse_output(self, data):
        for o in data.get('output', []):
            self.output(**o)

    def output(self, filename, **kwargs):
        kwargs['filename'] = filename
        self.outputs.append(kwargs)

    def parse_decks(self, data):
        for d in data.get('decks', []):
            template = [x for x in self.templates 
                    if x.name == d['template']][0]
            for c in d.get('cards', []):
                template.card(**c)
            if 'use' in d:
                template.use(d['use'])
            if 'use-csv' in d:
                template.use(d['use-csv'], True)
            template.sort()
        for c in data.get('cards', []):
            template = [x for x in self.templates if x.key == c['type']][0]
            template.card(**c)
            template.sort()

    def run(self, targets=None):
        self.load_states()

        self.prepare_cards()
        if not targets:
            outputs = self.outputs
        else:
            if type(targets) == str:
                targets = [targets]
            outputs = [o for o in self.outputs if o['name'] in targets]

        outfiles = []
        for o in outputs:
            size = o.get('size', "A4")
            if type(size) == str:
                size = SIZES[size]
            outfiles += self.render(
                    pagesize=size,
                    outfile = o['filename'],
                    **o
                )

        self.save_states()

        return outfiles

def loaddata(datafile, force_csv=False):
    if datafile.startswith("http://") or datafile.startswith("https://"):
        print "Downloading", datafile
        f = requests.get(datafile, stream=True).raw
    else:
        print "Reading", datafile
        f = open(datafile)
    if force_csv or datafile.endswith(".csv"):
        # csv is always card definitions
        import unicodecsv
        reader = unicodecsv.DictReader(f)
        data = []
        for row in reader:
            data.append({k: v.replace('|', '\n') for k, v in row.iteritems()})
    else:
        # assume it's yaml
        import yaml
        data = yaml.load(f)
    f.close()
    return data
    

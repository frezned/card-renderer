#!/usr/bin/python

import cardrenderer
import optparse

if __name__ == "__main__":
	parser = optparse.OptionParser()
	(options, args) = parser.parse_args()
	if len(args):
		maker = cardrenderer.CardRenderer()
		maker.readfile(args[0])
		maker.run(args[1:])
	else:
		print "Usage: cardrender.py datafile.yaml [target] [target2] ..."

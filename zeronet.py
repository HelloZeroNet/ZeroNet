#!/usr/bin/env python

try:
	from src import main
	main.start()
except Exception, err: # Prevent closing
	import traceback
	traceback.print_exc()
	raw_input("-- Error happened, press enter to close --")

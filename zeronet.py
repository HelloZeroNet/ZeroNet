#!/usr/bin/env python

def main():
	print "- Starting ZeroNet..."
	import sys, os
	main = None
	try:
		sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src")) # Imports relative to src
		import main
		main.start()
		if main.update_after_shutdown: # Updater
			import update, sys, os, gc
			# Try cleanup openssl
			try:
				if "lib.opensslVerify" in sys.modules:
					sys.modules["lib.opensslVerify"].opensslVerify.closeLibrary()
			except Exception, err:
				print "Error closing openssl", err

			# Update
			update.update()

			# Close log files
			logger = sys.modules["main"].logging.getLogger()

			for handler in logger.handlers[:]:
				handler.flush()
				handler.close()
				logger.removeHandler(handler)

	except Exception, err: # Prevent closing
		import traceback
		traceback.print_exc()
		traceback.print_exc(file=open("log/error.log", "a"))

	if main and main.update_after_shutdown: # Updater
		# Restart
		gc.collect() # Garbage collect
		print "Restarting..."
		args = sys.argv[:]
		args.insert(0, sys.executable) 
		if sys.platform == 'win32':
			args = ['"%s"' % arg for arg in args]
		os.execv(sys.executable, args)
		print "Bye."

if __name__ == '__main__':
	main()


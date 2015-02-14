#!/usr/bin/env python
import sys
import zeronet

def main():
	sys.argv += ["--open_browser", "default_browser"]
	zeronet.main()

if __name__ == '__main__':
	main()

#!/usr/bin/env python2.7


# Included modules
import sys

# ZeroNet Modules
import zeronet


def main():
    sys.argv = [sys.argv[0]]+["--open_browser", "default_browser"]+sys.argv[1:]
    zeronet.main()

if __name__ == '__main__':
    main()

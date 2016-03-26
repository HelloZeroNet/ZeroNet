#!/usr/bin/env python2


# Included modules
import sys

# ZeroNet Modules
import zeronet


def main():
    sys.argv += ["--open_browser", "default_browser"]
    zeronet.main()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3


# Included modules
import sys

# ZeroNet Modules
import zeronet


def main():
    if "--open_browser" not in sys.argv:
        sys.argv = [sys.argv[0]] + ["--open_browser", "default_browser"] + sys.argv[1:]
    zeronet.start()

if __name__ == '__main__':
    main()

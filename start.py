#!/usr/bin/env python
from multiprocessing import Process
import sys
import webbrowser
import zeronet

def main():
    browser_name = sys.argv.pop() if len(sys.argv) >= 2 else None
    server = Process(target=zeronet.main)
    server.start()
    browser = webbrowser.get(browser_name)
    url = browser.open("http://127.0.0.1:43110", new=2)
    server.join()

if __name__ == '__main__':
    main()

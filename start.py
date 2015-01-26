#!/usr/bin/env python
from multiprocessing import Process
import webbrowser
import zeronet

server = Process(target=zeronet.main)
server.start()
url = webbrowser.open("http://127.0.0.1:43110", new=2)
server.join()

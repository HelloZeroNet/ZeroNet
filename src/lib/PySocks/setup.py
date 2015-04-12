#!/usr/bin/env python
from distutils.core import setup

VERSION = "1.5.3"

setup(
    name = "PySocks",
    version = VERSION,
    description = "A Python SOCKS client module. See https://github.com/Anorov/PySocks for more information.",
    url = "https://github.com/Anorov/PySocks",
    license = "BSD",
    author = "Anorov",
    author_email = "anorov.vorona@gmail.com",
    keywords = ["socks", "proxy"],
    py_modules=["socks", "sockshandler"]
)


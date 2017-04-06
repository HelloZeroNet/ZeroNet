#
# This file is part of pyasn1 software.
#
# Copyright (c) 2005-2017, Ilya Etingof <etingof@gmail.com>
# License: http://pyasn1.sf.net/license.html
#
from pyasn1.type import base, tag


class EndOfOctets(base.AbstractSimpleAsn1Item):
    defaultValue = 0
    tagSet = tag.initTagSet(
        tag.Tag(tag.tagClassUniversal, tag.tagFormatSimple, 0x00)
    )

    _instance = None

    def __new__(cls, *args):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args)

        return cls._instance


endOfOctets = EndOfOctets()

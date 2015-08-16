# pylint:disable=C0111
import os

import maxminddb.reader

try:
    import maxminddb.extension
except ImportError:
    maxminddb.extension = None

from maxminddb.const import (MODE_AUTO, MODE_MMAP, MODE_MMAP_EXT, MODE_FILE,
                             MODE_MEMORY)
from maxminddb.decoder import InvalidDatabaseError


def open_database(database, mode=MODE_AUTO):
    """Open a Maxmind DB database

    Arguments:
        database -- A path to a valid MaxMind DB file such as a GeoIP2
                    database file.
        mode -- mode to open the database with. Valid mode are:
            * MODE_MMAP_EXT - use the C extension with memory map.
            * MODE_MMAP - read from memory map. Pure Python.
            * MODE_FILE - read database as standard file. Pure Python.
            * MODE_MEMORY - load database into memory. Pure Python.
            * MODE_AUTO - tries MODE_MMAP_EXT, MODE_MMAP, MODE_FILE in that
                          order. Default mode.
    """
    if (mode == MODE_AUTO and maxminddb.extension and
            hasattr(maxminddb.extension, 'Reader')) or mode == MODE_MMAP_EXT:
        return maxminddb.extension.Reader(database)
    elif mode in (MODE_AUTO, MODE_MMAP, MODE_FILE, MODE_MEMORY):
        return maxminddb.reader.Reader(database, mode)
    raise ValueError('Unsupported open mode: {0}'.format(mode))


def Reader(database):  # pylint: disable=invalid-name
    """This exists for backwards compatibility. Use open_database instead"""
    return open_database(database)

__title__ = 'maxminddb'
__version__ = '1.2.0'
__author__ = 'Gregory Oschwald'
__license__ = 'Apache License, Version 2.0'
__copyright__ = 'Copyright 2014 Maxmind, Inc.'

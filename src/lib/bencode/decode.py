import itertools
import collections

from . import string_type

try:
    range = xrange
except NameError:
    pass

def decode(data):
    '''
    Bdecodes data into Python built-in types.
    '''

    return consume(LookaheadIterator(data))

class LookaheadIterator(collections.Iterator):
    '''
    An iterator that lets you peek at the next item.
    '''

    def __init__(self, iterator):
        self.iterator, self.next_iterator = itertools.tee(iter(iterator))

        # Be one step ahead
        self._advance()

    def _advance(self):
        self.next_item = next(self.next_iterator, None)

    def __next__(self):
        self._advance()

        return next(self.iterator)

    # Python 2 compatibility
    next = __next__

def consume(stream):
    item = stream.next_item

    if item is None:
        raise ValueError('Encoding empty data is undefined')
    elif item == 'i':
        return consume_int(stream)
    elif item == 'l':
        return consume_list(stream)
    elif item == 'd':
        return consume_dict(stream)
    elif item is not None and item[0].isdigit():
        return consume_str(stream)
    else:
        raise ValueError('Invalid bencode object type: ', item)

def consume_number(stream):
    result = ''

    while True:
        chunk = stream.next_item

        if not chunk.isdigit():
            return result
        elif result.startswith('0'):
            raise ValueError('Invalid number')

        next(stream)
        result += chunk

def consume_int(stream):
    if next(stream) != 'i':
        raise ValueError()

    negative = stream.next_item == '-'

    if negative:
        next(stream)

    result = int(consume_number(stream))

    if negative:
        result *= -1

        if result == 0:
            raise ValueError('Negative zero is not allowed')

    if next(stream) != 'e':
        raise ValueError('Unterminated integer')

    return result

def consume_str(stream):
    length = int(consume_number(stream))

    if next(stream) != ':':
        raise ValueError('Malformed string')

    result = ''

    for i in range(length):
        try:
            result += next(stream)
        except StopIteration:
            raise ValueError('Invalid string length')

    return result

def consume_list(stream):
    if next(stream) != 'l':
        raise ValueError()

    l = []

    while stream.next_item != 'e':
        l.append(consume(stream))

    if next(stream) != 'e':
        raise ValueError('Unterminated list')

    return l

def consume_dict(stream):
    if next(stream) != 'd':
        raise ValueError()

    d = {}

    while stream.next_item != 'e':
        key = consume(stream)

        if not isinstance(key, string_type):
            raise ValueError('Dictionary keys must be strings')

        value = consume(stream)

        d[key] = value

    if next(stream) != 'e':
        raise ValueError('Unterminated dictionary')

    return d

from . import string_type

def encode(obj):
    '''
    Bencodes the object. The object must be an instance of: str, int, list, or dict.
    '''

    if isinstance(obj, string_type):
        return '{0}:{1}'.format(len(obj), obj)
    elif isinstance(obj, int):
        return 'i{0}e'.format(obj)
    elif isinstance(obj, list):
        values = ''.join([encode(o) for o in obj])

        return 'l{0}e'.format(values)
    elif isinstance(obj, dict):
        items = sorted(obj.items())
        values = ''.join([encode(str(key)) + encode(value) for key, value in items])

        return 'd{0}e'.format(values)
    else:
        raise TypeError('Unsupported type: {0}. Must be one of: str, int, list, dict.'.format(type(obj)))

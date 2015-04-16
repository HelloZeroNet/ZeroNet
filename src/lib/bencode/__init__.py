try:
    string_type = basestring
except NameError:
    string_type = str

from .encode import encode
from .decode import decode

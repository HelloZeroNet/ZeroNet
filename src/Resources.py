try:
    from importlib.resources import * # Py >=3.7
except ImportError: # cannot use ModuleNotFoundError (not in Py 3.4)
    from importlib_resources import *

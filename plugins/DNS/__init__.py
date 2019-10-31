from pkg_resources import DistributionNotFound, VersionConflict
import pkg_resources
import sys
import os


directory = os.path.dirname(__file__)

try:
    pkg_resources.require(open(directory + '/requirements.txt'))
except (DistributionNotFound, VersionConflict):
    sys.path.append(directory + '/requirements.zip')


from . import ConfigPlugin
from . import SiteManagerPlugin

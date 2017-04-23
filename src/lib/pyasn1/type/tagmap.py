#
# This file is part of pyasn1 software.
#
# Copyright (c) 2005-2017, Ilya Etingof <etingof@gmail.com>
# License: http://pyasn1.sf.net/license.html
#
from pyasn1 import error

__all__ = ['TagMap']


class TagMap(object):
    """Map *TagSet* objects to ASN.1 types

    Create an object mapping *TagSet* object to ASN.1 type.

    *TagMap* objects are immutable and duck-type read-only Python
    :class:`dict` objects holding *TagSet* objects as keys and ASN.1
     type objects as values.

    Parameters
    ----------
    presentTypes: :py:class:`dict`
        Map of :class:`~pyasn1.type.tag.TagSet` to ASN.1 objects considered
        as being unconditionally present in the *TagMap*.

    skipTypes: :py:class:`dict`
        A collection of :class:`~pyasn1.type.tag.TagSet` objects considered
        as absent in the *TagMap* even when *defaultType* is present.

    defaultType: ASN.1 type object
        An ASN.1 type object callee *TagMap* returns for any *TagSet* key not present
        in *presentTypes* (unless given key is present in *skipTypes*).
    """
    def __init__(self, presentTypes=None, skipTypes=None, defaultType=None):
        self.__presentTypes = presentTypes or {}
        self.__skipTypes = skipTypes or {}
        self.__defaultType = defaultType

    def __contains__(self, tagSet):
        return (tagSet in self.__presentTypes or
                self.__defaultType is not None and tagSet not in self.__skipTypes)

    def __getitem__(self, tagSet):
        try:
            return self.__presentTypes[tagSet]
        except KeyError:
            if self.__defaultType is None:
                raise KeyError()
            elif tagSet in self.__skipTypes:
                raise error.PyAsn1Error('Key in negative map')
            else:
                return self.__defaultType

    def __iter__(self):
        return iter(self.__presentTypes)

    def __repr__(self):
        s = self.__class__.__name__ + '('
        if self.__presentTypes:
            s += 'presentTypes=%r, ' % (self.__presentTypes,)
        if self.__skipTypes:
            s += 'skipTypes=%r, ' % (self.__skipTypes,)
        if self.__defaultType is not None:
            s += 'defaultType=%r' % (self.__defaultType,)
        return s + ')'

    def __str__(self):
        s = self.__class__.__name__ + ': '
        if self.__presentTypes:
            s += 'presentTypes: %s, ' % ', '.join([x.prettyPrintType() for x in self.__presentTypes.values()])
        if self.__skipTypes:
            s += 'skipTypes: %s, ' % ', '.join([x.prettyPrintType() for x in self.__skipTypes.values()])
        if self.__defaultType is not None:
            s += 'defaultType: %s, ' % self.__defaultType.prettyPrintType()
        return s

    @property
    def presentTypes(self):
        """Return *TagSet* to ASN.1 type map present in callee *TagMap*"""
        return self.__presentTypes

    @property
    def skipTypes(self):
        """Return *TagSet* collection unconditionally absent in callee *TagMap*"""
        return self.__skipTypes

    @property
    def defaultType(self):
        """Return default ASN.1 type being returned for any missing *TagSet*"""
        return self.__defaultType

    # Backward compatibility

    def getPosMap(self):
        return self.presentTypes

    def getNegMap(self):
        return self.skipTypes

    def getDef(self):
        return self.defaultType

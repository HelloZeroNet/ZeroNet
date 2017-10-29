#
# This file is part of pyasn1 software.
#
# Copyright (c) 2005-2017, Ilya Etingof <etingof@gmail.com>
# License: http://pyasn1.sf.net/license.html
#
import sys
from pyasn1.type import tagmap
from pyasn1 import error

__all__ = ['NamedType', 'OptionalNamedType', 'DefaultedNamedType', 'NamedTypes']


class NamedType(object):
    """Create named field object for a constructed ASN.1 type.

    The |NamedType| object represents a single name and ASN.1 type of a constructed ASN.1 type.

    |NamedType| objects are immutable and duck-type Python :class:`tuple` objects
    holding *name* and *asn1Object* components.

    Parameters
    ----------
    name: :py:class:`str`
        Field name

    asn1Object:
        ASN.1 type object
    """
    isOptional = False
    isDefaulted = False

    def __init__(self, name, asn1Object):
        self.__name = name
        self.__type = asn1Object
        self.__nameAndType = name, asn1Object

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.__name, self.__type)

    def __eq__(self, other):
        return self.__nameAndType == other

    def __ne__(self, other):
        return self.__nameAndType != other

    def __lt__(self, other):
        return self.__nameAndType < other

    def __le__(self, other):
        return self.__nameAndType <= other

    def __gt__(self, other):
        return self.__nameAndType > other

    def __ge__(self, other):
        return self.__nameAndType >= other

    def __hash__(self):
        return hash(self.__nameAndType)

    def __getitem__(self, idx):
        return self.__nameAndType[idx]

    def __iter__(self):
        return iter(self.__nameAndType)

    @property
    def name(self):
        return self.__name
    
    @property
    def asn1Object(self):
        return self.__type

    # Backward compatibility

    def getName(self):
        return self.name

    def getType(self):
        return self.asn1Object


class OptionalNamedType(NamedType):
    __doc__ = NamedType.__doc__

    isOptional = True


class DefaultedNamedType(NamedType):
    __doc__ = NamedType.__doc__

    isDefaulted = True


class NamedTypes(object):
    """Create a collection of named fields for a constructed ASN.1 type.

    The NamedTypes object represents a collection of named fields of a constructed ASN.1 type.

    *NamedTypes* objects are immutable and duck-type Python :class:`dict` objects
    holding *name* as keys and ASN.1 type object as values.

    Parameters
    ----------
    *namedTypes: :class:`~pyasn1.type.namedtype.NamedType`
    """
    def __init__(self, *namedTypes):
        self.__namedTypes = namedTypes
        self.__namedTypesLen = len(self.__namedTypes)
        self.__minTagSet = None
        self.__tagToPosMapImpl = None
        self.__nameToPosMapImpl = None
        self.__ambigiousTypesImpl = None
        self.__tagMap = {}
        self.__hasOptionalOrDefault = None
        self.__requiredComponents = None

    def __repr__(self):
        return '%s(%s)' % (
            self.__class__.__name__, ', '.join([repr(x) for x in self.__namedTypes])
        )

    def __eq__(self, other):
        return self.__namedTypes == other

    def __ne__(self, other):
        return self.__namedTypes != other

    def __lt__(self, other):
        return self.__namedTypes < other

    def __le__(self, other):
        return self.__namedTypes <= other

    def __gt__(self, other):
        return self.__namedTypes > other

    def __ge__(self, other):
        return self.__namedTypes >= other

    def __hash__(self):
        return hash(self.__namedTypes)

    def __getitem__(self, idx):
        try:
            return self.__namedTypes[idx]

        except TypeError:
            return self.__namedTypes[self.__nameToPosMap[idx]]

    def __contains__(self, key):
        return key in self.__nameToPosMap

    def __iter__(self):
        return (x[0] for x in self.__namedTypes)

    if sys.version_info[0] <= 2:
        def __nonzero__(self):
            return self.__namedTypesLen > 0
    else:
        def __bool__(self):
            return self.__namedTypesLen > 0

    def __len__(self):
        return self.__namedTypesLen

    # Python dict protocol

    def values(self):
        return (namedType.asn1Object for namedType in self.__namedTypes)

    def keys(self):
        return (namedType.name for namedType in self.__namedTypes)

    def items(self):
        return ((namedType.name, namedType.asn1Object) for namedType in self.__namedTypes)

    def clone(self):
        return self.__class__(*self.__namedTypes)

    @property
    def __tagToPosMap(self):
        if self.__tagToPosMapImpl is None:
            self.__tagToPosMapImpl = {}
            for idx, namedType in enumerate(self.__namedTypes):
                tagMap = namedType.asn1Object.tagMap
                if not tagMap:
                    continue
                for _tagSet in tagMap.presentTypes:
                    if _tagSet in self.__tagToPosMapImpl:
                        raise error.PyAsn1Error('Duplicate type %s in %s' % (_tagSet, namedType))
                    self.__tagToPosMapImpl[_tagSet] = idx

        return self.__tagToPosMapImpl

    @property
    def __nameToPosMap(self):
        if self.__nameToPosMapImpl is None:
            self.__nameToPosMapImpl = {}
            for idx, namedType in enumerate(self.__namedTypes):
                if namedType.name in self.__nameToPosMapImpl:
                    raise error.PyAsn1Error('Duplicate name %s in %s' % (namedType.name, namedType))
                self.__nameToPosMapImpl[namedType.name] = idx

        return self.__nameToPosMapImpl

    @property
    def __ambigiousTypes(self):
        if self.__ambigiousTypesImpl is None:
            self.__ambigiousTypesImpl = {}
            ambigiousTypes = ()
            for idx, namedType in reversed(tuple(enumerate(self.__namedTypes))):
                if namedType.isOptional or namedType.isDefaulted:
                    ambigiousTypes = (namedType,) + ambigiousTypes
                else:
                    ambigiousTypes = (namedType,)
                self.__ambigiousTypesImpl[idx] = NamedTypes(*ambigiousTypes)
        return self.__ambigiousTypesImpl

    def getTypeByPosition(self, idx):
        """Return ASN.1 type object by its position in fields set.

        Parameters
        ----------
        idx: :py:class:`int`
            Field index

        Returns
        -------
        :
            ASN.1 type

        Raises
        ------
        : :class:`~pyasn1.error.PyAsn1Error`
            If given position is out of fields range
        """
        try:
            return self.__namedTypes[idx].asn1Object

        except IndexError:
            raise error.PyAsn1Error('Type position out of range')

    def getPositionByType(self, tagSet):
        """Return field position by its ASN.1 type.

        Parameters
        ----------
        tagSet: :class:`~pysnmp.type.tag.TagSet`
            ASN.1 tag set distinguishing one ASN.1 type from others.

        Returns
        -------
        : :py:class:`int`
            ASN.1 type position in fields set

        Raises
        ------
        : :class:`~pyasn1.error.PyAsn1Error`
            If *tagSet* is not present or ASN.1 types are not unique within callee *NamedTypes*
        """
        try:
            return self.__tagToPosMap[tagSet]

        except KeyError:
            raise error.PyAsn1Error('Type %s not found' % (tagSet,))

    def getNameByPosition(self, idx):
        """Return field name by its position in fields set.

        Parameters
        ----------
        idx: :py:class:`idx`
            Field index

        Returns
        -------
        : :py:class:`str`
            Field name

        Raises
        ------
        : :class:`~pyasn1.error.PyAsn1Error`
            If given field name is not present in callee *NamedTypes*
        """
        try:
            return self.__namedTypes[idx].name

        except IndexError:
            raise error.PyAsn1Error('Type position out of range')

    def getPositionByName(self, name):
        """Return field position by filed name.

        Parameters
        ----------
        name: :py:class:`str`
            Field name

        Returns
        -------
        : :py:class:`int`
            Field position in fields set

        Raises
        ------
        : :class:`~pyasn1.error.PyAsn1Error`
            If *name* is not present or not unique within callee *NamedTypes*
        """
        try:
            return self.__nameToPosMap[name]

        except KeyError:
            raise error.PyAsn1Error('Name %s not found' % (name,))

    def getTagMapNearPosition(self, idx):
        """Return ASN.1 types that are allowed at or past given field position.

        Some ASN.1 serialization allow for skipping optional and defaulted fields.
        Some constructed ASN.1 types allow reordering of the fields. When recovering
        such objects it may be important to know which types can possibly be
        present at any given position in the field sets.

        Parameters
        ----------
        idx: :py:class:`int`
            Field index

        Returns
        -------
        : :class:`~pyasn1.type.tagmap.TagMap`
            Map if ASN.1 types allowed at given field position

        Raises
        ------
        : :class:`~pyasn1.error.PyAsn1Error`
            If given position is out of fields range
        """
        try:
            return self.__ambigiousTypes[idx].getTagMap()

        except KeyError:
            raise error.PyAsn1Error('Type position out of range')

    def getPositionNearType(self, tagSet, idx):
        """Return the closest field position where given ASN.1 type is allowed.

        Some ASN.1 serialization allow for skipping optional and defaulted fields.
        Some constructed ASN.1 types allow reordering of the fields. When recovering
        such objects it may be important to know at which field position, in field set,
        given *tagSet* is allowed at or past *idx* position.

        Parameters
        ----------
        tagSet: :class:`~pyasn1.type.tag.TagSet`
           ASN.1 type which field position to look up

        idx: :py:class:`int`
            Field position at or past which to perform ASN.1 type look up

        Returns
        -------
        : :py:class:`int`
            Field position in fields set

        Raises
        ------
        : :class:`~pyasn1.error.PyAsn1Error`
            If *tagSet* is not present or not unique within callee *NamedTypes*
            or *idx* is out of fields range
        """
        try:
            return idx + self.__ambigiousTypes[idx].getPositionByType(tagSet)

        except KeyError:
            raise error.PyAsn1Error('Type position out of range')

    @property
    def minTagSet(self):
        """Return the minimal TagSet among ASN.1 type in callee *NamedTypes*.

        Some ASN.1 types/serialization protocols require ASN.1 types to be
        arranged based on their numerical tag value. The *minTagSet* property
        returns that.

        Returns
        -------
        : :class:`~pyasn1.type.tagset.TagSet`
            Minimal TagSet among ASN.1 types in callee *NamedTypes*
        """
        if self.__minTagSet is None:
            for namedType in self.__namedTypes:
                asn1Object = namedType.asn1Object
                try:
                    tagSet = asn1Object.getMinTagSet()

                except AttributeError:
                    tagSet = asn1Object.tagSet
                if self.__minTagSet is None or tagSet < self.__minTagSet:
                    self.__minTagSet = tagSet
        return self.__minTagSet

    def getTagMap(self, unique=False):
        """Create a *TagMap* object from tags and types recursively.

        Create a new :class:`~pyasn1.type.tagmap.TagMap` object by
        combining tags from *TagMap* objects of children types and
        associating them with their immediate child type.

        Example
        -------

        .. code-block:: python

            OuterType ::= CHOICE {
                innerType INTEGER
            }

        Calling *.getTagMap()* on *OuterType* will yield a map like this:

        .. code-block:: python

            Integer.tagSet -> Choice

        Parameters
        ----------
        unique: :py:class:`bool`
            If `True`, duplicate *TagSet* objects occurring while building
            new *TagMap* would cause error.

        Returns
        -------
        : :class:`~pyasn1.type.tagmap.TagMap`
            New *TagMap* holding *TagSet* object gathered from childen types.
        """
        if unique not in self.__tagMap:
            presentTypes = {}
            skipTypes = {}
            defaultType = None
            for namedType in self.__namedTypes:
                tagMap = namedType.asn1Object.tagMap
                for tagSet in tagMap:
                    if unique and tagSet in presentTypes:
                        raise error.PyAsn1Error('Non-unique tagSet %s' % (tagSet,))
                    presentTypes[tagSet] = namedType.asn1Object
                skipTypes.update(tagMap.skipTypes)

                if defaultType is None:
                    defaultType = tagMap.defaultType
                elif tagMap.defaultType is not None:
                    raise error.PyAsn1Error('Duplicate default ASN.1 type at %s' % (self,))

            self.__tagMap[unique] = tagmap.TagMap(presentTypes, skipTypes, defaultType)

        return self.__tagMap[unique]

    @property
    def hasOptionalOrDefault(self):
        if self.__hasOptionalOrDefault is None:
            self.__hasOptionalOrDefault = bool([True for namedType in self.__namedTypes if namedType.isDefaulted or namedType.isOptional])
        return self.__hasOptionalOrDefault

    @property
    def namedTypes(self):
        return iter(self.__namedTypes)

    @property
    def requiredComponents(self):
        if self.__requiredComponents is None:
            self.__requiredComponents = frozenset(
                [idx for idx, nt in enumerate(self.__namedTypes) if not nt.isOptional and not nt.isDefaulted]
            )
        return self.__requiredComponents

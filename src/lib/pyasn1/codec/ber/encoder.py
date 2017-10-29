#
# This file is part of pyasn1 software.
#
# Copyright (c) 2005-2017, Ilya Etingof <etingof@gmail.com>
# License: http://pyasn1.sf.net/license.html
#
from pyasn1.type import base, tag, univ, char, useful
from pyasn1.codec.ber import eoo
from pyasn1.compat.octets import int2oct, oct2int, ints2octs, null, str2octs
from pyasn1.compat.integer import to_bytes
from pyasn1 import debug, error

__all__ = ['encode']


class AbstractItemEncoder(object):
    supportIndefLenMode = 1

    # noinspection PyMethodMayBeStatic
    def encodeTag(self, singleTag, isConstructed):
        tagClass, tagFormat, tagId = singleTag
        encodedTag = tagClass | tagFormat
        if isConstructed:
            encodedTag |= tag.tagFormatConstructed
        if tagId < 31:
            return (encodedTag | tagId,)
        else:
            substrate = (tagId & 0x7f,)
            tagId >>= 7
            while tagId:
                substrate = (0x80 | (tagId & 0x7f),) + substrate
                tagId >>= 7
            return (encodedTag | 0x1F,) + substrate

    def encodeLength(self, length, defMode):
        if not defMode and self.supportIndefLenMode:
            return (0x80,)
        if length < 0x80:
            return (length,)
        else:
            substrate = ()
            while length:
                substrate = (length & 0xff,) + substrate
                length >>= 8
            substrateLen = len(substrate)
            if substrateLen > 126:
                raise error.PyAsn1Error('Length octets overflow (%d)' % substrateLen)
            return (0x80 | substrateLen,) + substrate

    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        raise error.PyAsn1Error('Not implemented')

    def _encodeEndOfOctets(self, encodeFun, defMode):
        if defMode or not self.supportIndefLenMode:
            return null
        else:
            return encodeFun(eoo.endOfOctets, defMode)

    def encode(self, encodeFun, value, defMode, maxChunkSize):
        substrate, isConstructed, isOctets = self.encodeValue(
            encodeFun, value, defMode, maxChunkSize
        )
        tagSet = value.tagSet
        # tagged value?
        if tagSet:
            if not isConstructed:  # primitive form implies definite mode
                defMode = True
            header = self.encodeTag(tagSet[-1], isConstructed)
            header += self.encodeLength(len(substrate), defMode)

            if isOctets:
                substrate = ints2octs(header) + substrate
            else:
                substrate = ints2octs(header + substrate)

            eoo =  self._encodeEndOfOctets(encodeFun, defMode)
            if eoo:
                substrate += eoo

        return substrate


class EndOfOctetsEncoder(AbstractItemEncoder):
    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        return null, False, True


class ExplicitlyTaggedItemEncoder(AbstractItemEncoder):
    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        if isinstance(value, base.AbstractConstructedAsn1Item):
            value = value.clone(tagSet=value.tagSet[:-1], cloneValueFlag=1)
        else:
            value = value.clone(tagSet=value.tagSet[:-1])
        return encodeFun(value, defMode, maxChunkSize), True, True


explicitlyTaggedItemEncoder = ExplicitlyTaggedItemEncoder()


class BooleanEncoder(AbstractItemEncoder):
    supportIndefLenMode = False

    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        return value and (1,) or (0,), False, False


class IntegerEncoder(AbstractItemEncoder):
    supportIndefLenMode = False
    supportCompactZero = False

    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        if value == 0:
            # de-facto way to encode zero
            if self.supportCompactZero:
                return (), False, False
            else:
                return (0,), False, False

        return to_bytes(int(value), signed=True), False, True


class BitStringEncoder(AbstractItemEncoder):
    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        valueLength = len(value)
        if valueLength % 8:
            alignedValue = value << (8 - valueLength % 8)
        else:
            alignedValue = value

        if not maxChunkSize or len(alignedValue) <= maxChunkSize * 8:
            substrate = alignedValue.asOctets()
            return int2oct(len(substrate) * 8 - valueLength) + substrate, False, True

        stop = 0
        substrate = null
        while stop < valueLength:
            start = stop
            stop = min(start + maxChunkSize * 8, valueLength)
            substrate += encodeFun(alignedValue[start:stop], defMode, maxChunkSize)

        return substrate, True, True


class OctetStringEncoder(AbstractItemEncoder):
    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        if not maxChunkSize or len(value) <= maxChunkSize:
            return value.asOctets(), False, True
        else:
            pos = 0
            substrate = null
            while True:
                v = value.clone(value[pos:pos + maxChunkSize])
                if not v:
                    break
                substrate += encodeFun(v, defMode, maxChunkSize)
                pos += maxChunkSize

            return substrate, True, True


class NullEncoder(AbstractItemEncoder):
    supportIndefLenMode = False

    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        return null, False, True


class ObjectIdentifierEncoder(AbstractItemEncoder):
    supportIndefLenMode = False

    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        oid = value.asTuple()

        # Build the first pair
        try:
            first = oid[0]
            second = oid[1]

        except IndexError:
            raise error.PyAsn1Error('Short OID %s' % (value,))

        if 0 <= second <= 39:
            if first == 1:
                oid = (second + 40,) + oid[2:]
            elif first == 0:
                oid = (second,) + oid[2:]
            elif first == 2:
                oid = (second + 80,) + oid[2:]
            else:
                raise error.PyAsn1Error('Impossible first/second arcs at %s' % (value,))
        elif first == 2:
            oid = (second + 80,) + oid[2:]
        else:
            raise error.PyAsn1Error('Impossible first/second arcs at %s' % (value,))

        octets = ()

        # Cycle through subIds
        for subOid in oid:
            if 0 <= subOid <= 127:
                # Optimize for the common case
                octets += (subOid,)
            elif subOid > 127:
                # Pack large Sub-Object IDs
                res = (subOid & 0x7f,)
                subOid >>= 7
                while subOid:
                    res = (0x80 | (subOid & 0x7f),) + res
                    subOid >>= 7
                # Add packed Sub-Object ID to resulted Object ID
                octets += res
            else:
                raise error.PyAsn1Error('Negative OID arc %s at %s' % (subOid, value))

        return octets, False, False


class RealEncoder(AbstractItemEncoder):
    supportIndefLenMode = 0
    binEncBase = 2  # set to None to choose encoding base automatically

    @staticmethod
    def _dropFloatingPoint(m, encbase, e):
        ms, es = 1, 1
        if m < 0:
            ms = -1  # mantissa sign
        if e < 0:
            es = -1  # exponenta sign 
        m *= ms
        if encbase == 8:
            m *= 2 ** (abs(e) % 3 * es)
            e = abs(e) // 3 * es
        elif encbase == 16:
            m *= 2 ** (abs(e) % 4 * es)
            e = abs(e) // 4 * es

        while True:
            if int(m) != m:
                m *= encbase
                e -= 1
                continue
            break
        return ms, int(m), encbase, e

    def _chooseEncBase(self, value):
        m, b, e = value
        encBase = [2, 8, 16]
        if value.binEncBase in encBase:
            return self._dropFloatingPoint(m, value.binEncBase, e)
        elif self.binEncBase in encBase:
            return self._dropFloatingPoint(m, self.binEncBase, e)
        # auto choosing base 2/8/16 
        mantissa = [m, m, m]
        exponenta = [e, e, e]
        sign = 1
        encbase = 2
        e = float('inf')
        for i in range(3):
            (sign,
             mantissa[i],
             encBase[i],
             exponenta[i]) = self._dropFloatingPoint(mantissa[i], encBase[i], exponenta[i])
            if abs(exponenta[i]) < abs(e) or (abs(exponenta[i]) == abs(e) and mantissa[i] < m):
                e = exponenta[i]
                m = int(mantissa[i])
                encbase = encBase[i]
        return sign, m, encbase, e

    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        if value.isPlusInfinity():
            return (0x40,), False, False
        if value.isMinusInfinity():
            return (0x41,), False, False
        m, b, e = value
        if not m:
            return null, False, True
        if b == 10:
            return str2octs('\x03%dE%s%d' % (m, e == 0 and '+' or '', e)), False, True
        elif b == 2:
            fo = 0x80  # binary encoding
            ms, m, encbase, e = self._chooseEncBase(value)
            if ms < 0:  # mantissa sign
                fo |= 0x40  # sign bit
            # exponenta & mantissa normalization
            if encbase == 2:
                while m & 0x1 == 0:
                    m >>= 1
                    e += 1
            elif encbase == 8:
                while m & 0x7 == 0:
                    m >>= 3
                    e += 1
                fo |= 0x10
            else:  # encbase = 16
                while m & 0xf == 0:
                    m >>= 4
                    e += 1
                fo |= 0x20
            sf = 0  # scale factor
            while m & 0x1 == 0:
                m >>= 1
                sf += 1
            if sf > 3:
                raise error.PyAsn1Error('Scale factor overflow')  # bug if raised
            fo |= sf << 2
            eo = null
            if e == 0 or e == -1:
                eo = int2oct(e & 0xff)
            else:
                while e not in (0, -1):
                    eo = int2oct(e & 0xff) + eo
                    e >>= 8
                if e == 0 and eo and oct2int(eo[0]) & 0x80:
                    eo = int2oct(0) + eo
                if e == -1 and eo and not (oct2int(eo[0]) & 0x80):
                    eo = int2oct(0xff) + eo
            n = len(eo)
            if n > 0xff:
                raise error.PyAsn1Error('Real exponent overflow')
            if n == 1:
                pass
            elif n == 2:
                fo |= 1
            elif n == 3:
                fo |= 2
            else:
                fo |= 3
                eo = int2oct(n & 0xff) + eo
            po = null
            while m:
                po = int2oct(m & 0xff) + po
                m >>= 8
            substrate = int2oct(fo) + eo + po
            return substrate, False, True
        else:
            raise error.PyAsn1Error('Prohibited Real base %s' % b)


class SequenceEncoder(AbstractItemEncoder):
    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        value.verifySizeSpec()
        namedTypes = value.getComponentType()
        substrate = null
        idx = len(value)
        while idx > 0:
            idx -= 1
            if namedTypes:
                if namedTypes[idx].isOptional and not value[idx].isValue:
                    continue
                if namedTypes[idx].isDefaulted and value[idx] == namedTypes[idx].asn1Object:
                    continue
            substrate = encodeFun(value[idx], defMode, maxChunkSize) + substrate
        return substrate, True, True


class SequenceOfEncoder(AbstractItemEncoder):
    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        value.verifySizeSpec()
        substrate = null
        idx = len(value)
        while idx > 0:
            idx -= 1
            substrate = encodeFun(value[idx], defMode, maxChunkSize) + substrate
        return substrate, True, True


class ChoiceEncoder(AbstractItemEncoder):
    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        return encodeFun(value.getComponent(), defMode, maxChunkSize), True, True


class AnyEncoder(OctetStringEncoder):
    def encodeValue(self, encodeFun, value, defMode, maxChunkSize):
        return value.asOctets(), defMode == False, True


tagMap = {
    eoo.endOfOctets.tagSet: EndOfOctetsEncoder(),
    univ.Boolean.tagSet: BooleanEncoder(),
    univ.Integer.tagSet: IntegerEncoder(),
    univ.BitString.tagSet: BitStringEncoder(),
    univ.OctetString.tagSet: OctetStringEncoder(),
    univ.Null.tagSet: NullEncoder(),
    univ.ObjectIdentifier.tagSet: ObjectIdentifierEncoder(),
    univ.Enumerated.tagSet: IntegerEncoder(),
    univ.Real.tagSet: RealEncoder(),
    # Sequence & Set have same tags as SequenceOf & SetOf
    univ.SequenceOf.tagSet: SequenceOfEncoder(),
    univ.SetOf.tagSet: SequenceOfEncoder(),
    univ.Choice.tagSet: ChoiceEncoder(),
    # character string types
    char.UTF8String.tagSet: OctetStringEncoder(),
    char.NumericString.tagSet: OctetStringEncoder(),
    char.PrintableString.tagSet: OctetStringEncoder(),
    char.TeletexString.tagSet: OctetStringEncoder(),
    char.VideotexString.tagSet: OctetStringEncoder(),
    char.IA5String.tagSet: OctetStringEncoder(),
    char.GraphicString.tagSet: OctetStringEncoder(),
    char.VisibleString.tagSet: OctetStringEncoder(),
    char.GeneralString.tagSet: OctetStringEncoder(),
    char.UniversalString.tagSet: OctetStringEncoder(),
    char.BMPString.tagSet: OctetStringEncoder(),
    # useful types
    useful.ObjectDescriptor.tagSet: OctetStringEncoder(),
    useful.GeneralizedTime.tagSet: OctetStringEncoder(),
    useful.UTCTime.tagSet: OctetStringEncoder()
}

# Put in ambiguous & non-ambiguous types for faster codec lookup
typeMap = {
    univ.Boolean.typeId: BooleanEncoder(),
    univ.Integer.typeId: IntegerEncoder(),
    univ.BitString.typeId: BitStringEncoder(),
    univ.OctetString.typeId: OctetStringEncoder(),
    univ.Null.typeId: NullEncoder(),
    univ.ObjectIdentifier.typeId: ObjectIdentifierEncoder(),
    univ.Enumerated.typeId: IntegerEncoder(),
    univ.Real.typeId: RealEncoder(),
    # Sequence & Set have same tags as SequenceOf & SetOf
    univ.Set.typeId: SequenceEncoder(),
    univ.SetOf.typeId: SequenceOfEncoder(),
    univ.Sequence.typeId: SequenceEncoder(),
    univ.SequenceOf.typeId: SequenceOfEncoder(),
    univ.Choice.typeId: ChoiceEncoder(),
    univ.Any.typeId: AnyEncoder(),
    # character string types
    char.UTF8String.typeId: OctetStringEncoder(),
    char.NumericString.typeId: OctetStringEncoder(),
    char.PrintableString.typeId: OctetStringEncoder(),
    char.TeletexString.typeId: OctetStringEncoder(),
    char.VideotexString.typeId: OctetStringEncoder(),
    char.IA5String.typeId: OctetStringEncoder(),
    char.GraphicString.typeId: OctetStringEncoder(),
    char.VisibleString.typeId: OctetStringEncoder(),
    char.GeneralString.typeId: OctetStringEncoder(),
    char.UniversalString.typeId: OctetStringEncoder(),
    char.BMPString.typeId: OctetStringEncoder(),
    # useful types
    useful.ObjectDescriptor.typeId: OctetStringEncoder(),
    useful.GeneralizedTime.typeId: OctetStringEncoder(),
    useful.UTCTime.typeId: OctetStringEncoder()
}


class Encoder(object):
    supportIndefLength = True

    # noinspection PyDefaultArgument
    def __init__(self, tagMap, typeMap={}):
        self.__tagMap = tagMap
        self.__typeMap = typeMap

    def __call__(self, value, defMode=True, maxChunkSize=0):
        if not defMode and not self.supportIndefLength:
            raise error.PyAsn1Error('Indefinite length encoding not supported by this codec')
        debug.logger & debug.flagEncoder and debug.logger(
            'encoder called in %sdef mode, chunk size %s for type %s, value:\n%s' % (
                not defMode and 'in' or '', maxChunkSize, value.prettyPrintType(), value.prettyPrint()))
        tagSet = value.tagSet
        if len(tagSet) > 1:
            concreteEncoder = explicitlyTaggedItemEncoder
        else:
            try:
                concreteEncoder = self.__typeMap[value.typeId]
            except KeyError:
                # use base type for codec lookup to recover untagged types
                baseTagSet = tag.TagSet(value.tagSet.baseTag, value.tagSet.baseTag)
                try:
                    concreteEncoder = self.__tagMap[baseTagSet]
                except KeyError:
                    raise error.PyAsn1Error('No encoder for %s' % (value,))
        debug.logger & debug.flagEncoder and debug.logger(
            'using value codec %s chosen by %s' % (concreteEncoder.__class__.__name__, tagSet))
        substrate = concreteEncoder.encode(
            self, value, defMode, maxChunkSize
        )
        debug.logger & debug.flagEncoder and debug.logger(
            'built %s octets of substrate: %s\nencoder completed' % (len(substrate), debug.hexdump(substrate)))
        return substrate

#: Turns ASN.1 object into BER octet stream.
#:
#: Takes any ASN.1 object (e.g. :py:class:`~pyasn1.type.base.PyAsn1Item` derivative)
#: walks all its components recursively and produces a BER octet stream.
#:
#: Parameters
#: ----------
#  value: any pyasn1 object (e.g. :py:class:`~pyasn1.type.base.PyAsn1Item` derivative)
#:     A pyasn1 object to encode
#:
#: defMode: :py:class:`bool`
#:     If `False`, produces indefinite length encoding
#:
#: maxChunkSize: :py:class:`int`
#:     Maximum chunk size in chunked encoding mode (0 denotes unlimited chunk size)
#:
#: Returns
#: -------
#: : :py:class:`bytes` (Python 3) or :py:class:`str` (Python 2)
#:     Given ASN.1 object encoded into BER octetstream
#:
#: Raises
#: ------
#: : :py:class:`pyasn1.error.PyAsn1Error`
#:     On encoding errors
encode = Encoder(tagMap, typeMap)

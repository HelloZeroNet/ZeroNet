def loads(data):
    if not isinstance(data, bytes):
        raise TypeError("Expected 'bytes' object, got {}".format(type(data)))

    offset = 0


    def parseInteger():
        nonlocal offset

        offset += 1
        had_digit = False
        abs_value = 0

        sign = 1
        if data[offset] == ord("-"):
            sign = -1
            offset += 1
        while offset < len(data):
            if data[offset] == ord("e"):
                # End of string
                offset += 1
                if not had_digit:
                    raise ValueError("Integer without value")
                break
            if ord("0") <= data[offset] <= ord("9"):
                abs_value = abs_value * 10 + int(chr(data[offset]))
                had_digit = True
                offset += 1
            else:
                raise ValueError("Invalid integer")
        else:
            raise ValueError("Unexpected EOF, expected integer")

        if not had_digit:
            raise ValueError("Empty integer")

        return sign * abs_value


    def parseString():
        nonlocal offset

        length = int(chr(data[offset]))
        offset += 1

        while offset < len(data):
            if data[offset] == ord(":"):
                offset += 1
                break
            if ord("0") <= data[offset] <= ord("9"):
                length = length * 10 + int(chr(data[offset]))
                offset += 1
            else:
                raise ValueError("Invalid string length")
        else:
            raise ValueError("Unexpected EOF, expected string contents")

        if offset + length > len(data):
            raise ValueError("Unexpected EOF, expected string contents")
        offset += length

        return data[offset - length:offset]


    def parseList():
        nonlocal offset

        offset += 1
        values = []

        while offset < len(data):
            if data[offset] == ord("e"):
                # End of list
                offset += 1
                return values
            else:
                values.append(parse())

        raise ValueError("Unexpected EOF, expected list contents")


    def parseDict():
        nonlocal offset

        offset += 1
        items = {}

        while offset < len(data):
            if data[offset] == ord("e"):
                # End of list
                offset += 1
                return items
            else:
                key, value = parse(), parse()
                if not isinstance(key, bytes):
                    raise ValueError("A dict key must be a byte string")
                if key in items:
                    raise ValueError("Duplicate dict key: {}".format(key))
                items[key] = value

        raise ValueError("Unexpected EOF, expected dict contents")


    def parse():
        nonlocal offset

        if data[offset] == ord("i"):
            return parseInteger()
        elif data[offset] == ord("l"):
            return parseList()
        elif data[offset] == ord("d"):
            return parseDict()
        elif ord("0") <= data[offset] <= ord("9"):
            return parseString()

        raise ValueError("Unknown type specifier: '{}'".format(chr(data[offset])))

    result = parse()

    if offset != len(data):
        raise ValueError("Expected EOF, got {} bytes left".format(len(data) - offset))

    return result


def dumps(data):
    result = bytearray()


    def convert(data):
        nonlocal result

        if isinstance(data, str):
            raise ValueError("bencode only supports bytes, not str. Use encode")

        if isinstance(data, bytes):
            result += str(len(data)).encode() + b":" + data
        elif isinstance(data, int):
            result += b"i" + str(data).encode() + b"e"
        elif isinstance(data, list):
            result += b"l"
            for val in data:
                convert(val)
            result += b"e"
        elif isinstance(data, dict):
            result += b"d"
            for key in sorted(data.keys()):
                if not isinstance(key, bytes):
                    raise ValueError("Dict key can only be bytes, not {}".format(type(key)))
                convert(key)
                convert(data[key])
            result += b"e"
        else:
            raise ValueError("bencode only supports bytes, int, list and dict")


    convert(data)

    return bytes(result)

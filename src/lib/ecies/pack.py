from struct import unpack, pack


def parseEciesData(data):
    # IV
    iv = data[:16]
    data = data[16:]
    # Curve
    curve = unpack("!H", data[:2])[0]
    data = data[2:]
    # X
    x_len = unpack("!H", data[:2])[0]
    data = data[2:]
    publickey_x = int.from_bytes(data[:x_len], byteorder="big")
    data = data[x_len:]
    # Y
    y_len = unpack("!H", data[:2])[0]
    data = data[2:]
    publickey_y = int.from_bytes(data[:y_len], byteorder="big")
    data = data[y_len:]
    # Ciphertext
    ciphertext = data[:-32]
    # MAC
    mac = data[-32:]

    return {
        "iv": iv,
        "curve": curve,
        "publickey": (publickey_x, publickey_y),
        "ciphertext": ciphertext,
        "mac": mac
    }



def encodeEciesData(data):
    return (
        # IV
        data["iv"] +
        # Curve
        pack("!H", data["curve"]) +
        # X
        pack("!H", 32) +
        data["publickey"][0].to_bytes(32, byteorder="big") +
        # Y
        pack("!H", 32) +
        data["publickey"][1].to_bytes(32, byteorder="big") +
        # Ciphertext
        data["ciphertext"] +
        # MAC
        data["mac"]
    )
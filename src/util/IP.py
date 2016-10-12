import string

def is_private_address(ip):
    """
    :return True if this ip address is on a private address range:
    """
    if isinstance(ip, tuple):
        ip = ip[0]
    split = ip.split(".")
    if len(split) != 4:
        return False
    for part in split:
        for c in part:
            if c not in string.digits:
                return False
    prefix = split[0]
    return prefix in ['127', '10']

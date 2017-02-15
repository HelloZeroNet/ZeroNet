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
    try:
        for part in split:
            if int(part) < 0:
                return False
            if int(part) > 255:
                return False
            
    except:
        return False
    prefix = split[0]
    return prefix in ['127', '10']

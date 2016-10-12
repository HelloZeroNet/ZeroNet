

def is_private_address(ip):
    """
    :return True if this ip address is on a private address range:
    """
    if isinstance(ip, tuple):
        ip = ip[0]
    prefix = ip.split(".")[0]
    return prefix in ['127', '10']

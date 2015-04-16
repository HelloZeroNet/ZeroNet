import main as main
import transaction as tx

# Shared secrets and uncovering pay keys


def shared_secret_sender(scan_pubkey, ephem_privkey):
    shared_point = main.multiply(scan_pubkey, ephem_privkey)
    shared_secret = main.sha256(main.encode_pubkey(shared_point, 'bin_compressed'))
    return shared_secret


def shared_secret_receiver(ephem_pubkey, scan_privkey):
    shared_point = main.multiply(ephem_pubkey, scan_privkey)
    shared_secret = main.sha256(main.encode_pubkey(shared_point, 'bin_compressed'))
    return shared_secret


def uncover_pay_pubkey_sender(scan_pubkey, spend_pubkey, ephem_privkey):
    shared_secret = shared_secret_sender(scan_pubkey, ephem_privkey)
    return main.add_pubkeys(spend_pubkey, main.privtopub(shared_secret))


def uncover_pay_pubkey_receiver(scan_privkey, spend_pubkey, ephem_pubkey):
    shared_secret = shared_secret_receiver(ephem_pubkey, scan_privkey)
    return main.add_pubkeys(spend_pubkey, main.privtopub(shared_secret))


def uncover_pay_privkey(scan_privkey, spend_privkey, ephem_pubkey):
    shared_secret = shared_secret_receiver(ephem_pubkey, scan_privkey)
    return main.add_privkeys(spend_privkey, shared_secret)

# Address encoding

# Functions for basic stealth addresses,
# i.e. one scan key, one spend key, no prefix


def pubkeys_to_basic_stealth_address(scan_pubkey, spend_pubkey, magic_byte=42):
    # magic_byte = 42 for mainnet, 43 for testnet.
    hex_scankey = main.encode_pubkey(scan_pubkey, 'hex_compressed')
    hex_spendkey = main.encode_pubkey(spend_pubkey, 'hex_compressed')
    hex_data = '00{0:066x}01{1:066x}0100'.format(int(hex_scankey, 16), int(hex_spendkey, 16))
    addr = main.hex_to_b58check(hex_data, magic_byte)
    return addr


def basic_stealth_address_to_pubkeys(stealth_address):
    hex_data = main.b58check_to_hex(stealth_address)
    if len(hex_data) != 140:
        raise Exception('Stealth address is not of basic type (one scan key, one spend key, no prefix)')

    scan_pubkey = hex_data[2:68]
    spend_pubkey = hex_data[70:136]
    return scan_pubkey, spend_pubkey

# Sending stealth payments


def mk_stealth_metadata_script(ephem_pubkey, nonce):
    op_return = '6a'
    msg_size = '26'
    version = '06'
    return op_return + msg_size + version + '{0:08x}'.format(nonce) + main.encode_pubkey(ephem_pubkey, 'hex_compressed')


def mk_stealth_tx_outputs(stealth_addr, value, ephem_privkey, nonce, network='btc'):

    scan_pubkey, spend_pubkey = basic_stealth_address_to_pubkeys(stealth_addr)

    if network == 'btc':
        btc_magic_byte = 42
        if stealth_addr != pubkeys_to_basic_stealth_address(scan_pubkey, spend_pubkey, btc_magic_byte):
            raise Exception('Invalid btc mainnet stealth address: ' + stealth_addr)
        magic_byte_addr = 0

    elif network == 'testnet':
        testnet_magic_byte = 43
        if stealth_addr != pubkeys_to_basic_stealth_address(scan_pubkey, spend_pubkey, testnet_magic_byte):
            raise Exception('Invalid testnet stealth address: ' + stealth_addr)
        magic_byte_addr = 111

    ephem_pubkey = main.privkey_to_pubkey(ephem_privkey)
    output0 = {'script': mk_stealth_metadata_script(ephem_pubkey, nonce),
               'value': 0}

    pay_pubkey = uncover_pay_pubkey_sender(scan_pubkey, spend_pubkey, ephem_privkey)
    pay_addr = main.pubkey_to_address(pay_pubkey, magic_byte_addr)
    output1 = {'address': pay_addr,
               'value': value}

    return [output0, output1]

# Receiving stealth payments


def ephem_pubkey_from_tx_script(stealth_tx_script):
    if len(stealth_tx_script) != 80:
        raise Exception('Wrong format for stealth tx output')
    return stealth_tx_script[14:]

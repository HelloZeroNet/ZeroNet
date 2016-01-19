'''
Based on the specification at http://bittorrent.org/beps/bep_0015.html
'''
import random
import struct
import time
import socket
from collections import defaultdict


__version__ = '0.0.1'

CONNECT = 0
ANNOUNCE = 1
SCRAPE = 2
ERROR = 3


def norm_info_hash(info_hash):
    if len(info_hash) == 40:
        info_hash = info_hash.decode('hex')
    if len(info_hash) != 20:
        raise UdpTrackerClientException(
            'info_hash length is not 20: {}'.format(len(info_hash)))
    return info_hash


def info_hash_to_str(info_hash):
    return binascii.hexlify(info_hash)


class UdpTrackerClientException(Exception):
    pass


class UdpTrackerClient:

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.peer_port = 6881
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.conn_id = 0x41727101980
        self.transactions = {}
        self.peer_id = self._generate_peer_id()
        self.timeout = 9

    def connect(self):
        return self._send(CONNECT)

    def announce(self, **kwargs):
        if not kwargs:
            raise UdpTrackerClientException('arguments missing')
        args = {
            'peer_id': self.peer_id,
            'downloaded': 0,
            'left': 0,
            'uploaded': 0,
            'event': 0,
            'key': 0,
            'num_want': 10,
            'ip_address': 0,
            'port': self.peer_port,
        }
        args.update(kwargs)

        fields = 'info_hash peer_id downloaded left uploaded event ' \
            'ip_address key num_want port'

        # Check and raise if missing fields
        self._check_fields(args, fields)

        # Humans tend to use hex representations of the hash. Wasteful humans.
        args['info_hash'] = norm_info_hash(args['info_hash'])

        values = [args[a] for a in fields.split()]
        payload = struct.pack('!20s20sQQQLLLLH', *values)
        return self._send(ANNOUNCE, payload)

    def scrape(self, info_hash_list):
        if len(info_hash_list) > 74:
            raise UdpTrackerClientException('Max info_hashes is 74')

        payload = ''
        for info_hash in info_hash_list:
            info_hash = norm_info_hash(info_hash)
            payload += info_hash

        trans = self._send(SCRAPE, payload)
        trans['sent_hashes'] = info_hash_list
        return trans

    def poll_once(self):
        self.sock.settimeout(self.timeout)
        try:
            response = self.sock.recv(10240)
        except socket.timeout:
            return

        header = response[:8]
        payload = response[8:]
        action, trans_id = struct.unpack('!LL', header)
        try:
            trans = self.transactions[trans_id]
        except KeyError:
            self.error('transaction_id not found')
            return
        trans['response'] = self._process_response(action, payload, trans)
        trans['completed'] = True
        del self.transactions[trans_id]
        return trans

    def error(self, message):
        print('error: {}'.format(message))

    def _send(self, action, payload=None):
        if not payload:
            payload = ''
        trans_id, header = self._request_header(action)
        self.transactions[trans_id] = trans = {
            'action': action,
            'time': time.time(),
            'payload': payload,
            'completed': False,
        }
        self.sock.connect((self.host, self.port))
        self.sock.send(header + payload)
        return trans

    def _request_header(self, action):
        trans_id = random.randint(0, (1 << 32) - 1)
        return trans_id, struct.pack('!QLL', self.conn_id, action, trans_id)

    def _process_response(self, action, payload, trans):
        if action == CONNECT:
            return self._process_connect(payload, trans)
        elif action == ANNOUNCE:
            return self._process_announce(payload, trans)
        elif action == SCRAPE:
            return self._process_scrape(payload, trans)
        elif action == ERROR:
            return self._proecss_error(payload, trans)
        else:
            raise UdpTrackerClientException(
                'Unknown action response: {}'.format(action))

    def _process_connect(self, payload, trans):
        self.conn_id = struct.unpack('!Q', payload)[0]
        return self.conn_id

    def _process_announce(self, payload, trans):
        response = {}

        info_struct = '!LLL'
        info_size = struct.calcsize(info_struct)
        info = payload[:info_size]
        interval, leechers, seeders = struct.unpack(info_struct, info)

        peer_data = payload[info_size:]
        peer_struct = '!LH'
        peer_size = struct.calcsize(peer_struct)
        peer_count = len(peer_data) / peer_size
        peers = []

        for peer_offset in xrange(peer_count):
            off = peer_size * peer_offset
            peer = peer_data[off:off + peer_size]
            addr, port = struct.unpack(peer_struct, peer)
            peers.append({
                'addr': socket.inet_ntoa(struct.pack('!L', addr)),
                'port': port,
            })

        return {
            'interval': interval,
            'leechers': leechers,
            'seeders': seeders,
            'peers': peers,
        }

    def _process_scrape(self, payload, trans):
        info_struct = '!LLL'
        info_size = struct.calcsize(info_struct)
        info_count = len(payload) / info_size
        hashes = trans['sent_hashes']
        response = {}
        for info_offset in xrange(info_count):
            off = info_size * info_offset
            info = payload[off:off + info_size]
            seeders, completed, leechers = struct.unpack(info_struct, info)
            response[hashes[info_offset]] = {
                'seeders': seeders,
                'completed': completed,
                'leechers': leechers,
            }
        return response

    def _process_error(self, payload, trans):
        '''
        I haven't seen this action type be sent from a tracker, but I've left
        it here for the possibility.
        '''
        self.error(payload)
        return payload

    def _generate_peer_id(self):
        '''http://www.bittorrent.org/beps/bep_0020.html'''
        peer_id = '-PU' + __version__.replace('.', '-') + '-'
        remaining = 20 - len(peer_id)
        numbers = [str(random.randint(0, 9)) for _ in xrange(remaining)]
        peer_id += ''.join(numbers)
        assert(len(peer_id) == 20)
        return peer_id

    def _check_fields(self, args, fields):
        for f in fields:
            try:
                args.get(f)
            except KeyError:
                raise UdpTrackerClientException('field missing: {}'.format(f))


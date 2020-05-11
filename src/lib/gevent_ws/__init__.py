from gevent.pywsgi import WSGIHandler, _InvalidClientInput
from gevent.queue import Queue
import gevent
import hashlib
import base64
import struct
import socket
import time
import sys


SEND_PACKET_SIZE = 1300
OPCODE_TEXT = 1
OPCODE_BINARY = 2
OPCODE_CLOSE = 8
OPCODE_PING = 9
OPCODE_PONG = 10
STATUS_OK = 1000
STATUS_PROTOCOL_ERROR = 1002
STATUS_DATA_ERROR = 1007
STATUS_POLICY_VIOLATION = 1008
STATUS_TOO_LONG = 1009


class WebSocket:
    def __init__(self, socket):
        self.socket = socket
        self.closed = False
        self.status = None
        self._receive_error = None
        self._queue = Queue()
        self.max_length = 10 * 1024 * 1024
        gevent.spawn(self._listen)


    def set_max_message_length(self, length):
        self.max_length = length


    def _listen(self):
        try:
            while True:
                fin = False
                message = bytearray()
                is_first_message = True
                start_opcode = None
                while not fin:
                    payload, opcode, fin = self._get_frame(max_length=self.max_length - len(message))
                    # Make sure continuation frames have correct information
                    if not is_first_message and opcode != 0:
                        self._error(STATUS_PROTOCOL_ERROR)
                    if is_first_message:
                        if opcode not in (OPCODE_TEXT, OPCODE_BINARY):
                            self._error(STATUS_PROTOCOL_ERROR)
                        # Save opcode
                        start_opcode = opcode
                    message += payload
                    is_first_message = False
                message = bytes(message)
                if start_opcode == OPCODE_TEXT:  # UTF-8 text
                    try:
                        message = message.decode()
                    except UnicodeDecodeError:
                        self._error(STATUS_DATA_ERROR)
                self._queue.put(message)
        except Exception as e:
            self.closed = True
            self._receive_error = e
            self._queue.put(None)  # To make sure the error is read


    def receive(self):
        if not self._queue.empty():
            return self.receive_nowait()
        if isinstance(self._receive_error, EOFError):
            return None
        if self._receive_error:
            raise self._receive_error
        self._queue.peek()
        return self.receive_nowait()


    def receive_nowait(self):
        ret = self._queue.get_nowait()
        if self._receive_error and not isinstance(self._receive_error, EOFError):
            raise self._receive_error
        return ret


    def send(self, data):
        if self.closed:
            raise EOFError()
        if isinstance(data, str):
            self._send_frame(OPCODE_TEXT, data.encode())
        elif isinstance(data, bytes):
            self._send_frame(OPCODE_BINARY, data)
        else:
            raise TypeError("Expected str or bytes, got " + repr(type(data)))


    # Reads a frame from the socket. Pings, pongs and close packets are handled
    # automatically
    def _get_frame(self, max_length):
        while True:
            payload, opcode, fin = self._read_frame(max_length=max_length)
            if opcode == OPCODE_PING:
                self._send_frame(OPCODE_PONG, payload)
            elif opcode == OPCODE_PONG:
                pass
            elif opcode == OPCODE_CLOSE:
                if len(payload) >= 2:
                    self.status = struct.unpack("!H", payload[:2])[0]
                was_closed = self.closed
                self.closed = True
                if not was_closed:
                    # Send a close frame in response
                    self.close(STATUS_OK)
                raise EOFError()
            else:
                return payload, opcode, fin


    # Low-level function, use _get_frame instead
    def _read_frame(self, max_length):
        header = self._recv_exactly(2)

        if not (header[1] & 0x80):
            self._error(STATUS_POLICY_VIOLATION)

        opcode = header[0] & 0xf
        fin = bool(header[0] & 0x80)

        payload_length = header[1] & 0x7f
        if payload_length == 126:
            payload_length = struct.unpack("!H", self._recv_exactly(2))[0]
        elif payload_length == 127:
            payload_length = struct.unpack("!Q", self._recv_exactly(8))[0]

        # Control frames are handled in a special way
        if opcode in (OPCODE_PING, OPCODE_PONG):
            max_length = 125

        if payload_length > max_length:
            self._error(STATUS_TOO_LONG)

        mask = self._recv_exactly(4)
        payload = self._recv_exactly(payload_length)
        payload = self._unmask(payload, mask)

        return payload, opcode, fin


    def _recv_exactly(self, length):
        buf = bytearray()
        while len(buf) < length:
            block = self.socket.recv(min(4096, length - len(buf)))
            if block == b"":
                raise EOFError()
            buf += block
        return bytes(buf)


    def _unmask(self, payload, mask):
        def gen(c):
            return bytes([x ^ c for x in range(256)])


        payload = bytearray(payload)
        payload[0::4] = payload[0::4].translate(gen(mask[0]))
        payload[1::4] = payload[1::4].translate(gen(mask[1]))
        payload[2::4] = payload[2::4].translate(gen(mask[2]))
        payload[3::4] = payload[3::4].translate(gen(mask[3]))
        return bytes(payload)


    def _send_frame(self, opcode, data):
        for i in range(0, len(data), SEND_PACKET_SIZE):
            part = data[i:i + SEND_PACKET_SIZE]
            fin = int(i == (len(data) - 1) // SEND_PACKET_SIZE * SEND_PACKET_SIZE)
            header = bytes(
                [
                    (opcode if i == 0 else 0) | (fin << 7),
                    min(len(part), 126)
                ]
            )
            if len(part) >= 126:
                header += struct.pack("!H", len(part))
            self.socket.sendall(header + part)


    def _error(self, status):
        self.close(status)
        raise EOFError()


    def close(self, status=STATUS_OK):
        self.closed = True
        try:
            self._send_frame(OPCODE_CLOSE, struct.pack("!H", status))
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.socket.close()


class WebSocketHandler(WSGIHandler):
    def handle_one_response(self):
        self.time_start = time.time()
        self.status = None
        self.headers_sent = False

        self.result = None
        self.response_use_chunked = False
        self.response_length = 0


        http_connection = [s.strip().lower() for s in self.environ.get("HTTP_CONNECTION", "").split(",")]
        if "upgrade" not in http_connection or self.environ.get("HTTP_UPGRADE", "").lower() != "websocket":
            # Not my problem
            return super(WebSocketHandler, self).handle_one_response()

        if "HTTP_SEC_WEBSOCKET_KEY" not in self.environ:
            self.start_response("400 Bad Request", [])
            return

        # Generate Sec-Websocket-Accept header
        accept = self.environ["HTTP_SEC_WEBSOCKET_KEY"].encode()
        accept += b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept = base64.b64encode(hashlib.sha1(accept).digest()).decode()

        # Accept
        self.start_response("101 Switching Protocols", [
            ("Upgrade", "websocket"),
            ("Connection", "Upgrade"),
            ("Sec-Websocket-Accept", accept)
        ])(b"")

        self.environ["wsgi.websocket"] = WebSocket(self.socket)

        # Can't call super because it sets invalid flags like "status"
        try:
            try:
                self.run_application()
            finally:
                try:
                    self.wsgi_input._discard()
                except (socket.error, IOError):
                    pass
        except _InvalidClientInput:
            self._send_error_response_if_possible(400)
        except socket.error as ex:
            if ex.args[0] in self.ignored_socket_errors:
                self.close_connection = True
            else:
                self.handle_error(*sys.exc_info())
        except:  # pylint:disable=bare-except
            self.handle_error(*sys.exc_info())
        finally:
            self.time_finish = time.time()
            self.log_request()
            self.close_connection = True


    def process_result(self):
        if "wsgi.websocket" in self.environ:
            if self.result is None:
                return
            # Flushing result is required for werkzeug compatibility
            for elem in self.result:
                pass
        else:
            super(WebSocketHandler, self).process_result()


    @property
    def version(self):
        if not self.environ:
            return None

        return self.environ.get('HTTP_SEC_WEBSOCKET_VERSION')

import logging
import traceback

import socket
import stem
from stem import Signal
from stem.control import Controller
from stem.socket import ControlPort

from Plugin import PluginManager
from Config import config
from Debug import Debug

if config.tor != "disable":
    from gevent import monkey
    monkey.patch_time()
    monkey.patch_socket(dns=False)
    monkey.patch_thread()
    print "Stem Port Plugin: modules are patched."
else:
    print "Stem Port Plugin: Tor mode disabled. Module patching skipped."


class PatchedControlPort(ControlPort):
    def _make_socket(self):
        try:
            if "socket_noproxy" in dir(socket):  # Socket proxy-patched, use non-proxy one
                control_socket = socket.socket_noproxy(socket.AF_INET, socket.SOCK_STREAM)
            else:
                control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # TODO: repeated code - consider making a separate method

            control_socket.connect((self._control_addr, self._control_port))
            return control_socket
        except socket.error as exc:
            raise stem.SocketError(exc)

def from_port(address = '127.0.0.1', port = 'default'):
    import stem.connection

    if not stem.util.connection.is_valid_ipv4_address(address):
        raise ValueError('Invalid IP address: %s' % address)
    elif port != 'default' and not stem.util.connection.is_valid_port(port):
        raise ValueError('Invalid port: %s' % port)

    if port == 'default':
        raise ValueError('Must specify a port')
    else:
        control_port = PatchedControlPort(address, port)

    return Controller(control_port)


@PluginManager.registerTo("TorManager")
class TorManagerPlugin(object):

    def connectController(self):
        self.log.info("Authenticate using Stem... %s:%s" % (self.ip, self.port))

        try:
            with self.lock:
                if config.tor_password:
                    controller = from_port(port=self.port, password=config.tor_password)
                else:
                    controller = from_port(port=self.port)
                controller.authenticate()
                self.controller = controller
                self.status = u"Connected (via Stem)"
        except Exception, err:
            print("\n")
            traceback.print_exc()
            print("\n")

            self.controller = None
            self.status = u"Error (%s)" % err
            self.log.error("Tor stem connect error: %s" % Debug.formatException(err))

        return self.controller


    def disconnect(self):
        self.controller.close()
        self.controller = None


    def resetCircuits(self):
        try:
            self.controller.signal(Signal.NEWNYM)
        except Exception, err:
            self.status = u"Stem reset circuits error (%s)" % err
            self.log.error("Stem reset circuits error: %s" % err)


    def makeOnionAndKey(self):
        try:
            service = self.controller.create_ephemeral_hidden_service(
                {self.fileserver_port: self.fileserver_port},
                await_publication = False
            )
            if service.private_key_type != "RSA1024":
                raise Exception("ZeroNet doesn't support crypto " + service.private_key_type)

            self.log.debug("Stem created %s.onion (async descriptor publication)" % service.service_id)

            return (service.service_id, service.private_key)

        except Exception, err:
            self.status = u"AddOnion error (Stem: %s)" % err
            self.log.error("Failed to create hidden service with Stem: " + err)
            return False


    def delOnion(self, address):
        try:
            self.controller.remove_ephemeral_hidden_service(address)
            return True
        except Exception, err:
            self.status = u"DelOnion error (Stem: %s)" % err
            self.log.error("Stem failed to delete %s.onion: %s" % (address, err))
            self.disconnect() # Why?
            return False


    def request(self, cmd):
        with self.lock:
            if not self.enabled:
                return False
            else:
                self.log.error("[WARNING] StemPort self.request should not be called")
                return ""

    def send(self, cmd, conn=None):
        self.log.error("[WARNING] StemPort self.send should not be called")
        return ""

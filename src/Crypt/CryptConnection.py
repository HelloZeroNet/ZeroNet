import sys
import logging
import os
import ssl
import hashlib

from Config import config
from util import SslPatch
from util import helper


class CryptConnectionManager:
    def __init__(self):
        # OpenSSL params
        if sys.platform.startswith("win"):
            self.openssl_bin = "src\\lib\\opensslVerify\\openssl.exe"
        else:
            self.openssl_bin = "openssl"
        self.openssl_env = {"OPENSSL_CONF": "src/lib/opensslVerify/openssl.cnf"}

        self.crypt_supported = []  # Supported cryptos

    # Select crypt that supported by both sides
    # Return: Name of the crypto
    def selectCrypt(self, client_supported):
        for crypt in self.crypt_supported:
            if crypt in client_supported:
                return crypt
        return False

    # Wrap socket for crypt
    # Return: wrapped socket
    def wrapSocket(self, sock, crypt, server=False, cert_pin=None):
        if crypt == "tls-rsa":
            ciphers = "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:AES128-GCM-SHA256:AES128-SHA256:HIGH:"
            ciphers += "!aNULL:!eNULL:!EXPORT:!DSS:!DES:!RC4:!3DES:!MD5:!PSK"
            if server:
                sock_wrapped = ssl.wrap_socket(
                    sock, server_side=server, keyfile='%s/key-rsa.pem' % config.data_dir,
                    certfile='%s/cert-rsa.pem' % config.data_dir, ciphers=ciphers)
            else:
                sock_wrapped = ssl.wrap_socket(sock, ciphers=ciphers)
            if cert_pin:
                cert_hash = hashlib.sha256(sock_wrapped.getpeercert(True)).hexdigest()
                assert cert_hash == cert_pin, "Socket certificate does not match (%s != %s)" % (cert_hash, cert_pin)
            return sock_wrapped
        else:
            return sock

    def removeCerts(self):
        if config.keep_ssl_cert:
            return False
        for file_name in ["cert-rsa.pem", "key-rsa.pem"]:
            file_path = "%s/%s" % (config.data_dir, file_name)
            if os.path.isfile(file_path):
                os.unlink(file_path)

    # Load and create cert files is necessary
    def loadCerts(self):
        if config.disable_encryption:
            return False

        if self.createSslRsaCert():
            self.crypt_supported.append("tls-rsa")

    # Try to create RSA server cert + sign for connection encryption
    # Return: True on success
    def createSslRsaCert(self):
        if os.path.isfile("%s/cert-rsa.pem" % config.data_dir) and os.path.isfile("%s/key-rsa.pem" % config.data_dir):
            return True  # Files already exits

        import subprocess
        cmd = "%s req -x509 -newkey rsa:2048 -sha256 -batch -keyout %s -out %s -nodes -config %s" % helper.shellquote(
            self.openssl_bin,
            config.data_dir+"/key-rsa.pem",
            config.data_dir+"/cert-rsa.pem",
            self.openssl_env["OPENSSL_CONF"]
        )
        proc = subprocess.Popen(
            cmd.encode(sys.getfilesystemencoding()),
            shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=self.openssl_env
        )
        back = proc.stdout.read().strip()
        proc.wait()
        logging.debug("Generating RSA cert and key PEM files...%s" % back)

        if os.path.isfile("%s/cert-rsa.pem" % config.data_dir) and os.path.isfile("%s/key-rsa.pem" % config.data_dir):
            return True
        else:
            logging.error("RSA ECC SSL cert generation failed, cert or key files not exist.")
            return False

    # Not used yet: Missing on some platform
    """def createSslEccCert(self):
        return False
        import subprocess

        # Create ECC privatekey
        proc = subprocess.Popen(
            "%s ecparam -name prime256v1 -genkey -out %s/key-ecc.pem" % (self.openssl_bin, config.data_dir),
            shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=self.openssl_env
        )
        back = proc.stdout.read().strip()
        proc.wait()
        self.log.debug("Generating ECC privatekey PEM file...%s" % back)

        # Create ECC cert
        proc = subprocess.Popen(
            "%s req -new -key %s -x509 -nodes -out %s -config %s" % helper.shellquote(
                self.openssl_bin,
                config.data_dir+"/key-ecc.pem",
                config.data_dir+"/cert-ecc.pem",
                self.openssl_env["OPENSSL_CONF"]
            ),
            shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, env=self.openssl_env
        )
        back = proc.stdout.read().strip()
        proc.wait()
        self.log.debug("Generating ECC cert PEM file...%s" % back)

        if os.path.isfile("%s/cert-ecc.pem" % config.data_dir) and os.path.isfile("%s/key-ecc.pem" % config.data_dir):
            return True
        else:
            self.logging.error("ECC SSL cert generation failed, cert or key files not exits.")
            return False
    """

manager = CryptConnectionManager()

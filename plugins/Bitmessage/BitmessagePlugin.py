from Plugin import PluginManager

import BMIO
from BMAPI import BMAPI

@PluginManager.registerTo("UiWebsocket")
class UiWebsocketPlugin(object):
    def actionSendBitmessage(self, to, text, publickey=0):
        if type(publickey) is int:  # Encrypt using user's publickey
            publickey = self.user.getBitmessage(self.site.address, publickey)
        if type(to) is int:  # Encrypt using user's publickey
            to2 = self.user.getBitmessage(self.site.address, to)
        else:
            to2 = to
        BMAPI().check_connection()
        ackData = BMIO.sendMessage(publickey, to2, "ZeroNet message", text)
        self.response(to, ackData)


@PluginManager.registerTo("User")
class UserPlugin(object):
    def getBitmessage(self, address, param_index=0):
        assert param_index >= 0 and param_index <= 1000
        site_data = self.getSiteData(address)

        if site_data.get("cert"):  # Different privatekey for different cert provider
            index = param_index + self.getAddressAuthIndex(site_data["cert"])
        else:
            index = param_index

        if "bitmessage_%s" % index not in site_data:
            site_data["bitmessage_%s" % index] = "BM-2cVuNdpRNKaPmPCroMxrzS14RXbXZhxPrx"
            self.log.debug("New bitmessage address generated for %s:%s" % (address, index))
        return site_data["bitmessage_%s" % index]


@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("Bitmessage plugin")
        group.add_argument('--bitmessage_username', help='Username for Bitmessage API', default=None, metavar="username")
        group.add_argument('--bitmessage_password', help='Password for Bitmessage API', default=None, metavar="password")
        group.add_argument('--bitmessage_host', help='Host for Bitmessage API', default="127.0.0.1", metavar="host")
        group.add_argument('--bitmessage_port', help='Port for Bitmessage API', default="8445", metavar="port")

        return super(ConfigPlugin, self).createArguments()

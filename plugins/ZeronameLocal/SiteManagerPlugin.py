import logging, json, os, re, sys, time, requests
import gevent
from Plugin import PluginManager
from Config import config
from Debug import Debug

allow_reload = False # No reload supported

log = logging.getLogger("ZeronameLocalPlugin")


@PluginManager.registerTo("SiteManager")
class SiteManagerPlugin(object):

    def load(self, *args, **kwargs):
        super(SiteManagerPlugin, self).load(*args, **kwargs)
        self.url = "http://%(host)s:%(port)s" % {"host": config.namecoin_host, "port": config.namecoin_rpcport}
        self.cache = dict()

    # Checks if it's a valid address
    def isAddress(self, address):
        print("ISADDRESS")
        return self.isBitDomain(address) or super(SiteManagerPlugin, self).isAddress(address)

    # Return: True if the address is domain
    def isDomain(self, address):
        print("ISDOMAIN : ", address)
        return self.isBitDomain(address) or super(SiteManagerPlugin, self).isDomain(address)

    # Return: True if the address is .bit domain
    def isBitDomain(self, address):
        print("ISBITDOMAIN : ", address)
        return re.match(r"(.*?)([A-Za-z0-9_-]+\.bit)$", address)

    # Return: Site object or None if not found
    def get(self, address):
        print("GET : ", address)
        if self.isBitDomain(address):  # Its looks like a domain
            address_resolved = self.resolveDomain(address)
            if address_resolved:  # Domain found
                site = self.sites.get(address_resolved)
                if site:
                    site_domain = site.settings.get("domain")
                    if site_domain != address:
                        site.settings["domain"] = address
            else:  # Domain not found
                site = self.sites.get(address)

        else:  # Access by site address
            site = super(SiteManagerPlugin, self).get(address)
        return site

    # Return or create site and start download site files
    # Return: Site or None if dns resolve failed
    def need(self, address, *args, **kwargs):
        print("NEED : ", address)
        if self.isBitDomain(address):  # Its looks like a domain
            address_resolved = self.resolveDomain(address)
            if address_resolved:
                address = address_resolved
            else:
                return None

        return super(SiteManagerPlugin, self).need(address, *args, **kwargs)

    # Resolve domain
    # Return: The address or None
    def resolveDomain(self, domain):
        print("RESOLVEDOMAIN : ", domain)
        domain = domain.lower()

        #remove .bit on end
        if domain[-4:] == ".bit":
            domain = domain[0:-4]

        domain_array = domain.split(".")

        if len(domain_array) > 2:
            raise Error("Too many subdomains! Can only handle one level (eg. staging.mixtape.bit)")

        subdomain = ""
        if len(domain_array) == 1:
            domain = domain_array[0]
        else:
            subdomain = domain_array[0]
            domain = domain_array[1]

        print(domain)

        if domain in self.cache:
            delta = time.time() - self.cache[domain]["time"]
            if delta < 3600:
                # Must have been less than 1hour
                return self.cache[domain]["addresses_resolved"][subdomain]

        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": "zeronet",
            "method": "name_show",
            "params": ["d/"+domain]
        })

        try:
            #domain_object = self.rpc.name_show("d/"+domain)
            response = requests.post(self.url, auth=(config.namecoin_rpcuser, config.namecoin_rpcpassword), data=payload)
            print(response)
            domain_object = response.json()["result"]
        except Exception as err:
            #domain doesn't exist
            print("FAILED TO RESOLVE NAME : ", err)
            return None

        print(domain_object)
        if "zeronet" in domain_object["value"]:
            # Has a subdomain?
            zeronet_domains = json.loads(domain_object["value"])["zeronet"]

            self.cache[domain] = {"addresses_resolved": zeronet_domains, "time": time.time()}

            print(self.cache[domain])

            return self.cache[domain]["addresses_resolved"][subdomain]

@PluginManager.registerTo("ConfigPlugin")
class ConfigPlugin(object):
    def createArguments(self):
        group = self.parser.add_argument_group("Zeroname Local plugin")
        group.add_argument('--namecoin_host', help="Host to namecoin node (eg. 127.0.0.1)")
        group.add_argument('--namecoin_rpcport', help="Port to connect (eg. 8336)")
        group.add_argument('--namecoin_rpcuser', help="RPC user to connect to the namecoin node (eg. nofish)")
        group.add_argument('--namecoin_rpcpassword', help="RPC password to connect to namecoin node")

        return super(ConfigPlugin, self).createArguments()

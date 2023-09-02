import logging
import urllib.request
import urllib.parse
import re
import time

from Debug import Debug
from util import UpnpPunch


class PeerPortchecker(object):
    checker_functions = {
        "ipv4": ["checkIpfingerprints", "checkCanyouseeme"],
        "ipv6": ["checkMyaddr", "checkIpv6scanner"]
    }
    def __init__(self, file_server):
        self.log = logging.getLogger("PeerPortchecker")
        self.upnp_port_opened = False
        self.file_server = file_server

    def requestUrl(self, url, post_data=None):
        if type(post_data) is dict:
            post_data = urllib.parse.urlencode(post_data).encode("utf8")
        req = urllib.request.Request(url, post_data)
        req.add_header("Referer", url)
        req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11")
        req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        return urllib.request.urlopen(req, timeout=20.0)

    def portOpen(self, port):
        self.log.info("Trying to open port using UpnpPunch...")

        try:
            UpnpPunch.ask_to_open_port(port, 'ZeroNet', retries=3, protos=["TCP"])
            self.upnp_port_opened = True
        except Exception as err:
            self.log.warning("UpnpPunch run error: %s" % Debug.formatException(err))
            return False

        return True

    def portClose(self, port):
        return UpnpPunch.ask_to_close_port(port, protos=["TCP"])

    def portCheck(self, port, ip_type="ipv4"):
        checker_functions = self.checker_functions[ip_type]

        for func_name in checker_functions:
            func = getattr(self, func_name)
            s = time.time()
            try:
                res = func(port)
                if res:
                    self.log.info(
                        "Checked port %s (%s) using %s result: %s in %.3fs" %
                        (port, ip_type, func_name, res, time.time() - s)
                    )
                    time.sleep(0.1)
                    if res["opened"] and not self.file_server.had_external_incoming:
                        res["opened"] = False
                        self.log.warning("Port %s:%s looks opened, but no incoming connection" % (res["ip"], port))
                    break
            except Exception as err:
                self.log.warning(
                    "%s check error: %s in %.3fs" %
                    (func_name, Debug.formatException(err), time.time() - s)
                )
                res = {"ip": None, "opened": False}

        return res

    def checkCanyouseeme(self, port):
        data = urllib.request.urlopen("https://www.canyouseeme.org/", b"ip=1.1.1.1&port=%s" % str(port).encode("ascii"), timeout=20.0).read().decode("utf8")

        message = re.match(r'.*<p style="padding-left:15px">(.*?)</p>', data, re.DOTALL).group(1)
        message = re.sub(r"<.*?>", "", message.replace("<br>", " ").replace("&nbsp;", " "))  # Strip http tags

        match = re.match(r".*service on (.*?) on", message)
        if match:
            ip = match.group(1)
        else:
            raise Exception("Invalid response: %s" % message)

        if "Success" in message:
            return {"ip": ip, "opened": True}
        elif "Error" in message:
            return {"ip": ip, "opened": False}
        else:
            raise Exception("Invalid response: %s" % message)

    def checkIpfingerprints(self, port):
        data = self.requestUrl("https://www.ipfingerprints.com/portscan.php").read().decode("utf8")
        ip = re.match(r'.*name="remoteHost".*?value="(.*?)"', data, re.DOTALL).group(1)

        post_data = {
            "remoteHost": ip, "start_port": port, "end_port": port,
            "normalScan": "Yes", "scan_type": "connect2", "ping_type": "none"
        }
        message = self.requestUrl("https://www.ipfingerprints.com/scripts/getPortsInfo.php", post_data).read().decode("utf8")

        if "open" in message:
            return {"ip": ip, "opened": True}
        elif "filtered" in message or "closed" in message:
            return {"ip": ip, "opened": False}
        else:
            raise Exception("Invalid response: %s" % message)

    def checkMyaddr(self, port):
        url = "http://ipv6.my-addr.com/online-ipv6-port-scan.php"

        data = self.requestUrl(url).read().decode("utf8")

        ip = re.match(r'.*Your IP address is:[ ]*([0-9\.:a-z]+)', data.replace("&nbsp;", ""), re.DOTALL).group(1)

        post_data = {"addr": ip, "ports_selected": "", "ports_list": port}
        data = self.requestUrl(url, post_data).read().decode("utf8")

        message = re.match(r".*<table class='table_font_16'>(.*?)</table>", data, re.DOTALL).group(1)

        if "ok.png" in message:
            return {"ip": ip, "opened": True}
        elif "fail.png" in message:
            return {"ip": ip, "opened": False}
        else:
            raise Exception("Invalid response: %s" % message)

    def checkIpv6scanner(self, port):
        url = "http://www.ipv6scanner.com/cgi-bin/main.py"

        data = self.requestUrl(url).read().decode("utf8")

        ip = re.match(r'.*Your IP address is[ ]*([0-9\.:a-z]+)', data.replace("&nbsp;", ""), re.DOTALL).group(1)

        post_data = {"host": ip, "scanType": "1", "port": port, "protocol": "tcp", "authorized": "yes"}
        data = self.requestUrl(url, post_data).read().decode("utf8")

        message = re.match(r".*<table id='scantable'>(.*?)</table>", data, re.DOTALL).group(1)
        message_text = re.sub("<.*?>", " ", message.replace("<br>", " ").replace("&nbsp;", " ").strip())  # Strip http tags

        if "OPEN" in message_text:
            return {"ip": ip, "opened": True}
        elif "CLOSED" in message_text or "FILTERED" in message_text:
            return {"ip": ip, "opened": False}
        else:
            raise Exception("Invalid response: %s" % message_text)

    def checkPortchecker(self, port):  # Not working: Forbidden
        data = self.requestUrl("https://portchecker.co").read().decode("utf8")
        csrf = re.match(r'.*name="_csrf" value="(.*?)"', data, re.DOTALL).group(1)

        data = self.requestUrl("https://portchecker.co", {"port": port, "_csrf": csrf}).read().decode("utf8")
        message = re.match(r'.*<div id="results-wrapper">(.*?)</div>', data, re.DOTALL).group(1)
        message = re.sub(r"<.*?>", "", message.replace("<br>", " ").replace("&nbsp;", " ").strip())  # Strip http tags

        match = re.match(r".*targetIP.*?value=\"(.*?)\"", data, re.DOTALL)
        if match:
            ip = match.group(1)
        else:
            raise Exception("Invalid response: %s" % message)

        if "open" in message:
            return {"ip": ip, "opened": True}
        elif "closed" in message:
            return {"ip": ip, "opened": False}
        else:
            raise Exception("Invalid response: %s" % message)

    def checkSubnetonline(self, port):  # Not working: Invalid response
        url = "https://www.subnetonline.com/pages/ipv6-network-tools/online-ipv6-port-scanner.php"

        data = self.requestUrl(url).read().decode("utf8")

        ip = re.match(r'.*Your IP is.*?name="host".*?value="(.*?)"', data, re.DOTALL).group(1)
        token = re.match(r'.*name="token".*?value="(.*?)"', data, re.DOTALL).group(1)

        post_data = {"host": ip, "port": port, "allow": "on", "token": token, "submit": "Scanning.."}
        data = self.requestUrl(url, post_data).read().decode("utf8")

        print(post_data, data)

        message = re.match(r".*<div class='formfield'>(.*?)</div>", data, re.DOTALL).group(1)
        message = re.sub(r"<.*?>", "", message.replace("<br>", " ").replace("&nbsp;", " ").strip())  # Strip http tags

        if "online" in message:
            return {"ip": ip, "opened": True}
        elif "closed" in message:
            return {"ip": ip, "opened": False}
        else:
            raise Exception("Invalid response: %s" % message)

import re
import urllib.request
import http.client
import logging
from urllib.parse import urlparse
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError

from gevent import socket
import gevent

# Relevant UPnP spec:
# http://www.upnp.org/specs/gw/UPnP-gw-WANIPConnection-v1-Service.pdf

# General TODOs:
# Handle 0 or >1 IGDs

logger = logging.getLogger("Upnp")

class UpnpError(Exception):
    pass


class IGDError(UpnpError):
    """
    Signifies a problem with the IGD.
    """
    pass


REMOVE_WHITESPACE = re.compile(r'>\s*<')


def perform_m_search(local_ip):
    """
    Broadcast a UDP SSDP M-SEARCH packet and return response.
    """
    search_target = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"

    ssdp_request = ''.join(
        ['M-SEARCH * HTTP/1.1\r\n',
         'HOST: 239.255.255.250:1900\r\n',
         'MAN: "ssdp:discover"\r\n',
         'MX: 2\r\n',
         'ST: {0}\r\n'.format(search_target),
         '\r\n']
    ).encode("utf8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.bind((local_ip, 0))

    sock.sendto(ssdp_request, ('239.255.255.250', 1900))
    if local_ip == "127.0.0.1":
        sock.settimeout(1)
    else:
        sock.settimeout(5)

    try:
        return sock.recv(2048).decode("utf8")
    except socket.error:
        raise UpnpError("No reply from IGD using {} as IP".format(local_ip))
    finally:
        sock.close()


def _retrieve_location_from_ssdp(response):
    """
    Parse raw HTTP response to retrieve the UPnP location header
    and return a ParseResult object.
    """
    parsed_headers = re.findall(r'(?P<name>.*?): (?P<value>.*?)\r\n', response)
    header_locations = [header[1]
                        for header in parsed_headers
                        if header[0].lower() == 'location']

    if len(header_locations) < 1:
        raise IGDError('IGD response does not contain a "location" header.')

    return urlparse(header_locations[0])


def _retrieve_igd_profile(url):
    """
    Retrieve the device's UPnP profile.
    """
    try:
        return urllib.request.urlopen(url.geturl(), timeout=5).read().decode('utf-8')
    except socket.error:
        raise IGDError('IGD profile query timed out')


def _get_first_child_data(node):
    """
    Get the text value of the first child text node of a node.
    """
    return node.childNodes[0].data


def _parse_igd_profile(profile_xml):
    """
    Traverse the profile xml DOM looking for either
    WANIPConnection or WANPPPConnection and return
    the 'controlURL' and the service xml schema.
    """
    try:
        dom = parseString(profile_xml)
    except ExpatError as e:
        raise IGDError(
            'Unable to parse IGD reply: {0} \n\n\n {1}'.format(profile_xml, e))

    service_types = dom.getElementsByTagName('serviceType')
    for service in service_types:
        if _get_first_child_data(service).find('WANIPConnection') > 0 or \
           _get_first_child_data(service).find('WANPPPConnection') > 0:
            try:
                control_url = _get_first_child_data(
                    service.parentNode.getElementsByTagName('controlURL')[0])
                upnp_schema = _get_first_child_data(service).split(':')[-2]
                return control_url, upnp_schema
            except IndexError:
                # Pass the error because any error here should raise the
                # that's specified outside the for loop.
                pass
    raise IGDError(
        'Could not find a control url or UPNP schema in IGD response.')


# add description
def _get_local_ips():
    def method1():
        try:
            # get local ip using UDP and a  broadcast address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Not using <broadcast> because gevents getaddrinfo doesn't like that
            # using port 1 as per hobbldygoop's comment about port 0 not working on osx:
            # https://github.com/sirMackk/ZeroNet/commit/fdcd15cf8df0008a2070647d4d28ffedb503fba2#commitcomment-9863928
            s.connect(('239.255.255.250', 1))
            return [s.getsockname()[0]]
        except:
            pass

    def method2():
        # Get ip by using UDP and a normal address (google dns ip)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 0))
            return [s.getsockname()[0]]
        except:
            pass

    def method3():
        # Get ip by '' hostname . Not supported on all platforms.
        try:
            return socket.gethostbyname_ex('')[2]
        except:
            pass

    threads = [
        gevent.spawn(method1),
        gevent.spawn(method2),
        gevent.spawn(method3)
    ]

    gevent.joinall(threads, timeout=5)

    local_ips = []
    for thread in threads:
        if thread.value:
            local_ips += thread.value

    # Delete duplicates
    local_ips = list(set(local_ips))


    # Probably we looking for an ip starting with 192
    local_ips = sorted(local_ips, key=lambda a: a.startswith("192"), reverse=True)

    return local_ips


def _create_open_message(local_ip,
                         port,
                         description="UPnPPunch",
                         protocol="TCP",
                         upnp_schema='WANIPConnection'):
    """
    Build a SOAP AddPortMapping message.
    """

    soap_message = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <s:Body>
        <u:AddPortMapping xmlns:u="urn:schemas-upnp-org:service:{upnp_schema}:1">
            <NewRemoteHost></NewRemoteHost>
            <NewExternalPort>{port}</NewExternalPort>
            <NewProtocol>{protocol}</NewProtocol>
            <NewInternalPort>{port}</NewInternalPort>
            <NewInternalClient>{host_ip}</NewInternalClient>
            <NewEnabled>1</NewEnabled>
            <NewPortMappingDescription>{description}</NewPortMappingDescription>
            <NewLeaseDuration>0</NewLeaseDuration>
        </u:AddPortMapping>
    </s:Body>
</s:Envelope>""".format(port=port,
                        protocol=protocol,
                        host_ip=local_ip,
                        description=description,
                        upnp_schema=upnp_schema)
    return (REMOVE_WHITESPACE.sub('><', soap_message), 'AddPortMapping')


def _create_close_message(local_ip,
                          port,
                          description=None,
                          protocol='TCP',
                          upnp_schema='WANIPConnection'):
    soap_message = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <s:Body>
        <u:DeletePortMapping xmlns:u="urn:schemas-upnp-org:service:{upnp_schema}:1">
            <NewRemoteHost></NewRemoteHost>
            <NewExternalPort>{port}</NewExternalPort>
            <NewProtocol>{protocol}</NewProtocol>
        </u:DeletePortMapping>
    </s:Body>
</s:Envelope>""".format(port=port,
                        protocol=protocol,
                        upnp_schema=upnp_schema)
    return (REMOVE_WHITESPACE.sub('><', soap_message), 'DeletePortMapping')


def _parse_for_errors(soap_response):
    logger.debug(soap_response.status)
    if soap_response.status >= 400:
        response_data = soap_response.read()
        logger.debug(response_data)
        try:
            err_dom = parseString(response_data)
            err_code = _get_first_child_data(err_dom.getElementsByTagName(
                'errorCode')[0])
            err_msg = _get_first_child_data(
                err_dom.getElementsByTagName('errorDescription')[0]
            )
        except Exception as err:
            raise IGDError(
                'Unable to parse SOAP error: {0}. Got: "{1}"'.format(
                    err, response_data))
        raise IGDError(
            'SOAP request error: {0} - {1}'.format(err_code, err_msg)
        )
    return soap_response


def _send_soap_request(location, upnp_schema, control_path, soap_fn,
                       soap_message):
    """
    Send out SOAP request to UPnP device and return a response.
    """
    headers = {
        'SOAPAction': (
            '"urn:schemas-upnp-org:service:{schema}:'
            '1#{fn_name}"'.format(schema=upnp_schema, fn_name=soap_fn)
        ),
        'Content-Type': 'text/xml'
    }
    logger.debug("Sending UPnP request to {0}:{1}...".format(
        location.hostname, location.port))
    conn = http.client.HTTPConnection(location.hostname, location.port)
    conn.request('POST', control_path, soap_message, headers)

    response = conn.getresponse()
    conn.close()

    return _parse_for_errors(response)


def _collect_idg_data(ip_addr):
    idg_data = {}
    idg_response = perform_m_search(ip_addr)
    idg_data['location'] = _retrieve_location_from_ssdp(idg_response)
    idg_data['control_path'], idg_data['upnp_schema'] = _parse_igd_profile(
        _retrieve_igd_profile(idg_data['location']))
    return idg_data


def _send_requests(messages, location, upnp_schema, control_path):
    responses = [_send_soap_request(location, upnp_schema, control_path,
                                    message_tup[1], message_tup[0])
                 for message_tup in messages]

    if all(rsp.status == 200 for rsp in responses):
        return
    raise UpnpError('Sending requests using UPnP failed.')


def _orchestrate_soap_request(ip, port, msg_fn, desc=None, protos=("TCP", "UDP")):
    logger.debug("Trying using local ip: %s" % ip)
    idg_data = _collect_idg_data(ip)

    soap_messages = [
        msg_fn(ip, port, desc, proto, idg_data['upnp_schema'])
        for proto in protos
    ]

    _send_requests(soap_messages, **idg_data)


def _communicate_with_igd(port=15441,
                          desc="UpnpPunch",
                          retries=3,
                          fn=_create_open_message,
                          protos=("TCP", "UDP")):
    """
    Manage sending a message generated by 'fn'.
    """

    local_ips = _get_local_ips()
    success = False

    def job(local_ip):
        for retry in range(retries):
            try:
                _orchestrate_soap_request(local_ip, port, fn, desc, protos)
                return True
            except Exception as e:
                logger.debug('Upnp request using "{0}" failed: {1}'.format(local_ip, e))
                gevent.sleep(1)
        return False

    threads = []

    for local_ip in local_ips:
        job_thread = gevent.spawn(job, local_ip)
        threads.append(job_thread)
        gevent.sleep(0.1)
        if any([thread.value for thread in threads]):
            success = True
            break

    # Wait another 10sec for competition or any positive result
    for _ in range(10):
        all_done = all([thread.value is not None for thread in threads])
        any_succeed = any([thread.value for thread in threads])
        if all_done or any_succeed:
            break
        gevent.sleep(1)

    if any([thread.value for thread in threads]):
        success = True

    if not success:
        raise UpnpError(
            'Failed to communicate with igd using port {0} on local machine after {1} tries.'.format(
                port, retries))

    return success


def ask_to_open_port(port=15441, desc="UpnpPunch", retries=3, protos=("TCP", "UDP")):
    logger.debug("Trying to open port %d." % port)
    return _communicate_with_igd(port=port,
                          desc=desc,
                          retries=retries,
                          fn=_create_open_message,
                          protos=protos)


def ask_to_close_port(port=15441, desc="UpnpPunch", retries=3, protos=("TCP", "UDP")):
    logger.debug("Trying to close port %d." % port)
    # retries=1 because multiple successes cause 500 response and failure
    return _communicate_with_igd(port=port,
                          desc=desc,
                          retries=retries,
                          fn=_create_close_message,
                          protos=protos)


if __name__ == "__main__":
    from gevent import monkey
    monkey.patch_all()
    logging.basicConfig(level=logging.DEBUG)
    import time

    s = time.time()
    print("Opening port...")
    print("Success:", ask_to_open_port(15443, "ZeroNet", protos=["TCP"]))
    print("Done in", time.time() - s)


    print("Closing port...")
    print("Success:", ask_to_close_port(15443, "ZeroNet", protos=["TCP"]))
    print("Done in", time.time() - s)


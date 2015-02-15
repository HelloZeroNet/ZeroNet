import socket
import re
import urllib2
import httplib
from urlparse import urlparse
from xml.dom.minidom import parseString

# Relevant UPnP spec: http://www.upnp.org/specs/gw/UPnP-gw-WANIPConnection-v1-Service.pdf

# General TODOs:
# Handle 0 or >1 IGDs
# Format the SOAP AddPortEntry message correctly (remove spaces/whitespace)
# Find robust way to find own ip


def _m_search_ssdp():
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
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(ssdp_request, ('239.255.255.250', 1900))

    # TODO: add timeout
    return sock.recv(1024)


def _retrieve_location_from_ssdp(response):
    """
    Parse raw HTTP response to retrieve the UPnP location header
    and return a ParseResult object.
    """
    parsed = re.findall(r'(?P<name>.*?): (?P<value>.*?)\r\n', response)
    location_header = filter(lambda x: x[0].lower() == 'location', parsed)

    if not len(location_header):
        # no location header returned :(
        return False

    return urlparse(location_header[0][1])


def _retrieve_igd_profile(url):
    """
    Retrieve the device's UPnP profile.
    """
    # TODO: add exception handling
    return urllib2.urlopen(url.geturl()).read()


def __get_node_value(node):
    """ 
    Get the text value of the first child text node of a node.
    """
    return node.childeNodes[0].data


def _parse_igd_profile(profile_xml):
    """
    Traverse the profile xml DOM looking for either
    WANIPConnection or WANPPPConnection and return
    the value found as well as the 'controlURL'.
    """
    # TODO: return upnp schema as well
    dom = parseString(profile_xml)

    service_types = dom.getElementsByTagName('serviceType')
    for service in service_types:
        if __get_node_value(service).find('WANIPConnection') > 0 or \
           __get_node_value(service).find('WANPPPConnection') > 0:
            control_url = service.parentNode.getElementsByTagName(
                'controlURL'
            )[0].childNodes[0].data

    return control_url, upnp_schema


def _create_soap_message(port, description="UPnPPunch", protocol="TCP",
                         upnp_schema='WANIPConnection'):
    """
    Build a SOAP AddPortMapping message.
    """
    # TODO: get current ip
    current_ip = '192.168.0.2'

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
                        host_ip=current_ip,
                        description=description,
                        upnp_schema=upnp_schema)

    return soap_message


def _send_soap_request(location, upnp_schema, control_url, soap_message):
    """
    Send out SOAP request to UPnP device and return a response.
    """
    headers = {
        'SOAPAction': (
            '"urn:schemas-upnp-org:service:{schema}:'
            '1#AddPortMapping"'.format(schema=upnp_schema)
        ),
        'Content-Type': 'text/xml'
    }
    conn = httplib.HTTPConnection(location.hostname, location.port)
    conn.request('POST', control_url, soap_message, headers)

    response_body = conn.getresponse().read()

    return response_body


def open_port(port=15441):
    """
    Attempt to forward a port using UPnP.
    """
    location = _retrieve_location_from_ssdp(_m_search_ssdp())
    control_url, upnp_schema = _parse_igd_profile(
        _retrieve_igd_profile(location)
    )

    for protocol in ["TCP", "UDP"]:
        message = _create_soap_message(port, protocol, upnp_schema)
        # TODO: gevent this
        _send_soap_request(location, upnp_schema, control_url, message)
        # TODO: handle error code in response

import gevent
from gevent import socket

import re, urllib2, httplib, logging
from urlparse import urlparse
from xml.dom.minidom import parseString

# Relevant UPnP spec: http://www.upnp.org/specs/gw/UPnP-gw-WANIPConnection-v1-Service.pdf

# General TODOs:
# Handle 0 or >1 IGDs

remove_whitespace = re.compile(r'>\s*<')


def _m_search_ssdp(local_ip):
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

	sock.bind((local_ip, 10000))

	sock.sendto(ssdp_request, ('239.255.255.250', 1900))
	sock.settimeout(5)

	try:
		return sock.recv(2048)
	except socket.error, err:
		# no reply from IGD, possibly no IGD on LAN
		logging.debug("UDP SSDP M-SEARCH send error using ip %s: %s" % (local_ip, err))
		return False


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
	return urllib2.urlopen(url.geturl()).read()


def _node_val(node):
	""" 
	Get the text value of the first child text node of a node.
	"""
	return node.childNodes[0].data


def _parse_igd_profile(profile_xml):
	"""
	Traverse the profile xml DOM looking for either
	WANIPConnection or WANPPPConnection and return
	the value found as well as the 'controlURL'.
	"""
	dom = parseString(profile_xml)

	service_types = dom.getElementsByTagName('serviceType')
	for service in service_types:
		if _node_val(service).find('WANIPConnection') > 0 or \
		   _node_val(service).find('WANPPPConnection') > 0:
			control_url = service.parentNode.getElementsByTagName(
				'controlURL'
			)[0].childNodes[0].data
			upnp_schema = _node_val(service).split(':')[-2]
			return control_url, upnp_schema

	return False


def _get_local_ip():
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
	# not using <broadcast> because gevents getaddrinfo doesn't like that
	# using port 1 as per hobbldygoop's comment about port 0 not working on osx:
	# https://github.com/sirMackk/ZeroNet/commit/fdcd15cf8df0008a2070647d4d28ffedb503fba2#commitcomment-9863928
	s.connect(('239.255.255.250', 1))
	return s.getsockname()[0]


def _create_soap_message(local_ip, port, description="UPnPPunch", protocol="TCP",
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
	return remove_whitespace.sub('><', soap_message)


def _parse_for_errors(soap_response):
	if soap_response.status == 500:
		err_dom = parseString(soap_response.read())
		err_code = _node_val(err_dom.getElementsByTagName('errorCode')[0])
		err_msg = _node_val(
			err_dom.getElementsByTagName('errorDescription')[0]
		)
		logging.error('SOAP request error: {0} - {1}'.format(err_code, err_msg))
		raise Exception(
			'SOAP request error: {0} - {1}'.format(err_code, err_msg)
		)

		return False
	else:
		return True


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

	response = conn.getresponse()
	conn.close()

	return _parse_for_errors(response)


def open_port(port=15441, desc="UpnpPunch"):
	"""
	Attempt to forward a port using UPnP.
	"""

	local_ips = [_get_local_ip()]
	try:
		local_ips += socket.gethostbyname_ex('')[2] # Get ip by '' hostname not supported on all platform
	except:
		pass

	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(('8.8.8.8', 0)) # Using google dns route
		local_ips.append(s.getsockname()[0])
	except:
		pass

	local_ips = list(set(local_ips)) # Delete duplicates
	logging.debug("Found local ips: %s" % local_ips)
	local_ips = local_ips*3 # Retry every ip 3 times

	for local_ip in local_ips:
		logging.debug("Trying using local ip: %s" % local_ip)
		idg_response = _m_search_ssdp(local_ip)

		if not idg_response:
			logging.debug("No IGD response")
			continue

		location = _retrieve_location_from_ssdp(idg_response)

		if not location:
			logging.debug("No location")
			continue

		parsed = _parse_igd_profile(
			_retrieve_igd_profile(location)
		)

		if not parsed:
			logging.debug("IGD parse error using location %s" % repr(location))
			continue

		control_url, upnp_schema = parsed

		soap_messages = [_create_soap_message(local_ip, port, desc, proto, upnp_schema)
						 for proto in ['TCP', 'UDP']]

		requests = [gevent.spawn(
			_send_soap_request, location, upnp_schema, control_url, message
		) for message in soap_messages]

		gevent.joinall(requests, timeout=3)

		if all([request.value for request in requests]):
			return True
	return False

if __name__ == "__main__":
	from gevent import monkey
	monkey.patch_socket()

	logging.getLogger().setLevel(logging.DEBUG) 
	print open_port(15441, "ZeroNet")

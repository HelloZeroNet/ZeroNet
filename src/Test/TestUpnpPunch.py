import socket
from urlparse import urlparse

import pytest
import mock

from util import UpnpPunch as upnp


@pytest.fixture
def mock_socket():
    mock_socket = mock.MagicMock()
    mock_socket.recv = mock.MagicMock(return_value='Hello')
    mock_socket.bind = mock.MagicMock()
    mock_socket.send_to = mock.MagicMock()

    return mock_socket


@pytest.fixture
def url_obj():
    return urlparse('http://192.168.1.1/ctrlPoint.xml')


@pytest.fixture(params=['WANPPPConnection', 'WANIPConnection'])
def igd_profile(request):
    return """<root><serviceList><service>
  <serviceType>urn:schemas-upnp-org:service:{}:1</serviceType>
  <serviceId>urn:upnp-org:serviceId:wanpppc:pppoa</serviceId>
  <controlURL>/upnp/control/wanpppcpppoa</controlURL>
  <eventSubURL>/upnp/event/wanpppcpppoa</eventSubURL>
  <SCPDURL>/WANPPPConnection.xml</SCPDURL>
</service></serviceList></root>""".format(request.param)


@pytest.fixture
def httplib_response():
    class FakeResponse(object):
        def __init__(self, status=200, body='OK'):
            self.status = status
            self.body = body

        def read(self):
            return self.body
    return FakeResponse


class TestUpnpPunch(object):
    def test_perform_m_search(self, mock_socket):
        local_ip = '127.0.0.1'

        with mock.patch('util.UpnpPunch.socket.socket',
                        return_value=mock_socket):
            result = upnp.perform_m_search(local_ip)
            assert result == 'Hello'
            assert local_ip == mock_socket.bind.call_args_list[0][0][0][0]
            assert ('239.255.255.250',
                    1900) == mock_socket.sendto.call_args_list[0][0][1]

    def test_perform_m_search_socket_error(self, mock_socket):
        mock_socket.recv.side_effect = socket.error('Timeout error')

        with mock.patch('util.UpnpPunch.socket.socket',
                        return_value=mock_socket):
            with pytest.raises(upnp.UpnpError):
                upnp.perform_m_search('127.0.0.1')

    def test_retrieve_location_from_ssdp(self, url_obj):
        ctrl_location = url_obj.geturl()
        parsed_location = urlparse(ctrl_location)
        rsp = ('auth: gibberish\r\nlocation: {0}\r\n'
               'Content-Type: text/html\r\n\r\n').format(ctrl_location)
        result = upnp._retrieve_location_from_ssdp(rsp)
        assert result == parsed_location

    def test_retrieve_location_from_ssdp_no_header(self):
        rsp = 'auth: gibberish\r\nContent-Type: application/json\r\n\r\n'
        with pytest.raises(upnp.IGDError):
            upnp._retrieve_location_from_ssdp(rsp)

    def test_retrieve_igd_profile(self, url_obj):
        with mock.patch('urllib2.urlopen') as mock_urlopen:
            upnp._retrieve_igd_profile(url_obj)
            mock_urlopen.assert_called_with(url_obj.geturl(), timeout=5)

    def test_retrieve_igd_profile_timeout(self, url_obj):
        with mock.patch('urllib2.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = socket.error('Timeout error')
            with pytest.raises(upnp.IGDError):
                upnp._retrieve_igd_profile(url_obj)

    def test_parse_igd_profile_service_type(self, igd_profile):
        control_path, upnp_schema = upnp._parse_igd_profile(igd_profile)
        assert control_path == '/upnp/control/wanpppcpppoa'
        assert upnp_schema in ('WANPPPConnection', 'WANIPConnection',)

    def test_parse_igd_profile_no_ctrlurl(self, igd_profile):
        igd_profile = igd_profile.replace('controlURL', 'nope')
        with pytest.raises(upnp.IGDError):
            control_path, upnp_schema = upnp._parse_igd_profile(igd_profile)

    def test_parse_igd_profile_no_schema(self, igd_profile):
        igd_profile = igd_profile.replace('Connection', 'nope')
        with pytest.raises(upnp.IGDError):
            control_path, upnp_schema = upnp._parse_igd_profile(igd_profile)

    def test_create_open_message_parsable(self):
        from xml.parsers.expat import ExpatError
        msg, _ = upnp._create_open_message('127.0.0.1', 8888)
        try:
            upnp.parseString(msg)
        except ExpatError as e:
            pytest.fail('Incorrect XML message: {}'.format(e))

    def test_create_open_message_contains_right_stuff(self):
        settings = {'description': 'test desc',
                    'protocol': 'test proto',
                    'upnp_schema': 'test schema'}
        msg, fn_name = upnp._create_open_message('127.0.0.1', 8888, **settings)
        assert fn_name == 'AddPortMapping'
        assert '127.0.0.1' in msg
        assert '8888' in msg
        assert settings['description'] in msg
        assert settings['protocol'] in msg
        assert settings['upnp_schema'] in msg

    def test_parse_for_errors_bad_rsp(self, httplib_response):
        rsp = httplib_response(status=500)
        with pytest.raises(upnp.IGDError) as exc:
            upnp._parse_for_errors(rsp)
        assert 'Unable to parse' in exc.value.message

    def test_parse_for_errors_error(self, httplib_response):
        soap_error = ('<document>'
                      '<errorCode>500</errorCode>'
                      '<errorDescription>Bad request</errorDescription>'
                      '</document>')
        rsp = httplib_response(status=500, body=soap_error)
        with pytest.raises(upnp.IGDError) as exc:
            upnp._parse_for_errors(rsp)
        assert 'SOAP request error' in exc.value.message

    def test_parse_for_errors_good_rsp(self, httplib_response):
        rsp = httplib_response(status=200)
        assert rsp == upnp._parse_for_errors(rsp)

    def test_send_requests_success(self):
        with mock.patch(
                'util.UpnpPunch._send_soap_request') as mock_send_request:
            mock_send_request.return_value = mock.MagicMock(status=200)
            upnp._send_requests(['msg'], None, None, None)

        assert mock_send_request.called

    def test_send_requests_failed(self):
        with mock.patch(
                'util.UpnpPunch._send_soap_request') as mock_send_request:
            mock_send_request.return_value = mock.MagicMock(status=500)
            with pytest.raises(upnp.UpnpError):
                upnp._send_requests(['msg'], None, None, None)

        assert mock_send_request.called

    def test_collect_idg_data(self):
        pass

    @mock.patch('util.UpnpPunch._get_local_ips')
    @mock.patch('util.UpnpPunch._collect_idg_data')
    @mock.patch('util.UpnpPunch._send_requests')
    def test_ask_to_open_port_success(self, mock_send_requests,
                                      mock_collect_idg, mock_local_ips):
        mock_collect_idg.return_value = {'upnp_schema': 'schema-yo'}
        mock_local_ips.return_value = ['192.168.0.12']

        result = upnp.ask_to_open_port(retries=5)

        soap_msg = mock_send_requests.call_args[0][0][0][0]

        assert result is None

        assert mock_collect_idg.called
        assert '192.168.0.12' in soap_msg
        assert '15441' in soap_msg
        assert 'schema-yo' in soap_msg

    @mock.patch('util.UpnpPunch._get_local_ips')
    @mock.patch('util.UpnpPunch._collect_idg_data')
    @mock.patch('util.UpnpPunch._send_requests')
    def test_ask_to_open_port_failure(self, mock_send_requests,
                                      mock_collect_idg, mock_local_ips):
        mock_local_ips.return_value = ['192.168.0.12']
        mock_collect_idg.return_value = {'upnp_schema': 'schema-yo'}
        mock_send_requests.side_effect = upnp.UpnpError()

        with pytest.raises(upnp.UpnpError):
            upnp.ask_to_open_port()

    @mock.patch('util.UpnpPunch._collect_idg_data')
    @mock.patch('util.UpnpPunch._send_requests')
    def test_orchestrate_soap_request(self, mock_send_requests,
                                      mock_collect_idg):
        soap_mock = mock.MagicMock()
        args = ['127.0.0.1', 31337, soap_mock, 'upnp-test', {'upnp_schema':
                                                             'schema-yo'}]
        mock_collect_idg.return_value = args[-1]

        upnp._orchestrate_soap_request(*args[:-1])

        assert mock_collect_idg.called
        soap_mock.assert_called_with(
            *args[:2] + ['upnp-test', 'UDP', 'schema-yo'])
        assert mock_send_requests.called

    @mock.patch('util.UpnpPunch._collect_idg_data')
    @mock.patch('util.UpnpPunch._send_requests')
    def test_orchestrate_soap_request_without_desc(self, mock_send_requests,
                                                   mock_collect_idg):
        soap_mock = mock.MagicMock()
        args = ['127.0.0.1', 31337, soap_mock, {'upnp_schema': 'schema-yo'}]
        mock_collect_idg.return_value = args[-1]

        upnp._orchestrate_soap_request(*args[:-1])

        assert mock_collect_idg.called
        soap_mock.assert_called_with(*args[:2] + [None, 'UDP', 'schema-yo'])
        assert mock_send_requests.called

    def test_create_close_message_parsable(self):
        from xml.parsers.expat import ExpatError
        msg, _ = upnp._create_close_message('127.0.0.1', 8888)
        try:
            upnp.parseString(msg)
        except ExpatError as e:
            pytest.fail('Incorrect XML message: {}'.format(e))

    def test_create_close_message_contains_right_stuff(self):
        settings = {'protocol': 'test proto',
                    'upnp_schema': 'test schema'}
        msg, fn_name = upnp._create_close_message('127.0.0.1', 8888, **
                                                  settings)
        assert fn_name == 'DeletePortMapping'
        assert '8888' in msg
        assert settings['protocol'] in msg
        assert settings['upnp_schema'] in msg

    @mock.patch('util.UpnpPunch._get_local_ips')
    @mock.patch('util.UpnpPunch._orchestrate_soap_request')
    def test_communicate_with_igd_success(self, mock_orchestrate,
                                          mock_get_local_ips):
        mock_get_local_ips.return_value = ['192.168.0.12']
        upnp._communicate_with_igd()
        assert mock_get_local_ips.called
        assert mock_orchestrate.called

    @mock.patch('util.UpnpPunch._get_local_ips')
    @mock.patch('util.UpnpPunch._orchestrate_soap_request')
    def test_communicate_with_igd_succeed_despite_single_failure(
            self, mock_orchestrate, mock_get_local_ips):
        mock_get_local_ips.return_value = ['192.168.0.12']
        mock_orchestrate.side_effect = [upnp.UpnpError, None]
        upnp._communicate_with_igd(retries=2)
        assert mock_get_local_ips.called
        assert mock_orchestrate.called

    @mock.patch('util.UpnpPunch._get_local_ips')
    @mock.patch('util.UpnpPunch._orchestrate_soap_request')
    def test_communicate_with_igd_total_failure(self, mock_orchestrate,
                                                mock_get_local_ips):
        mock_get_local_ips.return_value = ['192.168.0.12']
        mock_orchestrate.side_effect = [upnp.UpnpError, upnp.IGDError]
        with pytest.raises(upnp.UpnpError):
            upnp._communicate_with_igd(retries=2)
        assert mock_get_local_ips.called
        assert mock_orchestrate.called

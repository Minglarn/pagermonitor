import os
import json
import socket
import unittest
from unittest.mock import patch

from udp_forwarder import (
    init_udp_forwarder, is_enabled, get_status, forward_pocsag
)


class TestUdpForwarder(unittest.TestCase):
    def setUp(self):
        # Clear UDP environment variables before each test
        for var in ('UDP_FORWARD_HOST', 'UDP_FORWARD_PORT', 'UDP_FORWARD_ENABLED'):
            if var in os.environ:
                del os.environ[var]
        init_udp_forwarder()

    def tearDown(self):
        for var in ('UDP_FORWARD_HOST', 'UDP_FORWARD_PORT', 'UDP_FORWARD_ENABLED'):
            if var in os.environ:
                del os.environ[var]
        init_udp_forwarder()

    def test_default_state_is_disabled(self):
        self.assertFalse(is_enabled())
        status = get_status()
        self.assertFalse(status['enabled'])
        self.assertEqual(status['host'], '')
        self.assertEqual(status['port'], 0)

    def test_init_with_valid_env_variables(self):
        os.environ['UDP_FORWARD_HOST'] = '127.0.0.1'
        os.environ['UDP_FORWARD_PORT'] = '5599'
        os.environ['UDP_FORWARD_ENABLED'] = 'true'
        init_udp_forwarder()

        self.assertTrue(is_enabled())
        status = get_status()
        self.assertTrue(status['enabled'])
        self.assertEqual(status['host'], '127.0.0.1')
        self.assertEqual(status['port'], 5599)

    def test_explicitly_disabled_overrides_host_and_port(self):
        os.environ['UDP_FORWARD_HOST'] = '127.0.0.1'
        os.environ['UDP_FORWARD_PORT'] = '5599'
        os.environ['UDP_FORWARD_ENABLED'] = 'false'
        init_udp_forwarder()

        self.assertFalse(is_enabled())

    def test_auto_enabled_when_host_and_port_provided(self):
        os.environ['UDP_FORWARD_HOST'] = '192.168.1.150'
        os.environ['UDP_FORWARD_PORT'] = '8888'
        init_udp_forwarder()

        self.assertTrue(is_enabled())
        self.assertEqual(get_status()['host'], '192.168.1.150')
        self.assertEqual(get_status()['port'], 8888)

    def test_invalid_port_disables_forwarder(self):
        os.environ['UDP_FORWARD_HOST'] = '127.0.0.1'
        os.environ['UDP_FORWARD_PORT'] = 'not-a-port'
        init_udp_forwarder()

        self.assertFalse(is_enabled())

    def test_forward_pocsag_sends_full_json_datagram(self):
        # Create a local UDP server socket on loopback
        receiver_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver_sock.bind(('127.0.0.1', 0))
        receiver_sock.settimeout(2.0)
        _, assigned_port = receiver_sock.getsockname()

        try:
            os.environ['UDP_FORWARD_HOST'] = '127.0.0.1'
            os.environ['UDP_FORWARD_PORT'] = str(assigned_port)
            os.environ['UDP_FORWARD_ENABLED'] = 'true'
            init_udp_forwarder()

            pocsag_payload = {
                'type': 'message',
                'id': 42,
                'timestamp': '2026-10-27T21:00:00',
                'address': '1234567',
                'message': 'LARM: Stor brand på Åkergatan 12',
                'alias': 'Räddningstjänsten',
                'protocol': 'POCSAG',
                'bitrate': '1200',
                'function': 3,
                'frequency': '169.8M',
                'is_alert': True,
                'alert_word': 'BRAND',
                'alert_color': '#f85149',
                'sdr_name': 'RTL-SDR 1',
                'is_duplicate': False,
                'repeat_count': 1,
                'raw': 'POCSAG1200: Address: 1234567 Function: 3 Alpha: LARM: Stor brand på Åkergatan 12'
            }

            res = forward_pocsag(pocsag_payload)
            self.assertTrue(res)

            data, addr = receiver_sock.recvfrom(4096)
            decoded_text = data.decode('utf-8')
            received_json = json.loads(decoded_text)

            self.assertEqual(received_json['id'], 42)
            self.assertEqual(received_json['address'], '1234567')
            self.assertEqual(received_json['message'], 'LARM: Stor brand på Åkergatan 12')
            self.assertEqual(received_json['alias'], 'Räddningstjänsten')
            self.assertEqual(received_json['protocol'], 'POCSAG')
            self.assertEqual(received_json['bitrate'], '1200')
            self.assertEqual(received_json['function'], 3)
            self.assertEqual(received_json['frequency'], '169.8M')
            self.assertTrue(received_json['is_alert'])
            self.assertEqual(received_json['alert_word'], 'BRAND')
            self.assertEqual(received_json['raw'], pocsag_payload['raw'])

            # Verify counter
            status = get_status()
            self.assertGreaterEqual(status['packets_sent'], 1)
            self.assertIsNotNone(status['last_sent_time'])
        finally:
            receiver_sock.close()

    def test_non_pocsag_protocols_are_filtered_out(self):
        receiver_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver_sock.bind(('127.0.0.1', 0))
        receiver_sock.settimeout(0.5)
        _, assigned_port = receiver_sock.getsockname()

        try:
            os.environ['UDP_FORWARD_HOST'] = '127.0.0.1'
            os.environ['UDP_FORWARD_PORT'] = str(assigned_port)
            os.environ['UDP_FORWARD_ENABLED'] = 'true'
            init_udp_forwarder()

            # Test VDL2
            vdl2_payload = {
                'type': 'message',
                'address': 'SE-ROX',
                'message': 'VDL2 Flight data',
                'protocol': 'VDL2',
                'bitrate': '31500'
            }
            self.assertFalse(forward_pocsag(vdl2_payload))

            # Test ACARS
            acars_payload = {
                'type': 'message',
                'address': 'SK1234',
                'message': 'ACARS Position report',
                'protocol': 'ACARS',
                'bitrate': 'VHF-ACARS'
            }
            self.assertFalse(forward_pocsag(acars_payload))

            # Test AFSK
            afsk_payload = {
                'type': 'message',
                'address': 'AFSK',
                'message': 'APRS packet',
                'protocol': 'AFSK',
                'bitrate': '1200'
            }
            self.assertFalse(forward_pocsag(afsk_payload))

            # Test TETRA
            tetra_payload = {
                'type': 'message',
                'address': 'RAKEL-101',
                'message': 'TETRA data',
                'protocol': 'TETRA',
                'bitrate': 'TETRA-NET'
            }
            self.assertFalse(forward_pocsag(tetra_payload))

            # Ensure nothing arrived on the socket
            with self.assertRaises(socket.timeout):
                receiver_sock.recvfrom(4096)
        finally:
            receiver_sock.close()

    def test_forward_when_disabled_returns_false(self):
        pocsag_payload = {
            'protocol': 'POCSAG',
            'address': '1234567',
            'message': 'Test'
        }
        self.assertFalse(forward_pocsag(pocsag_payload))

    def test_empty_or_invalid_payload_returns_false(self):
        os.environ['UDP_FORWARD_HOST'] = '127.0.0.1'
        os.environ['UDP_FORWARD_PORT'] = '5599'
        os.environ['UDP_FORWARD_ENABLED'] = 'true'
        init_udp_forwarder()

        self.assertFalse(forward_pocsag(None))
        self.assertFalse(forward_pocsag({}))
        self.assertFalse(forward_pocsag("not-a-dict"))

    def test_forward_pocsag_to_multiple_hosts_and_ports(self):
        sock1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock1.bind(('127.0.0.1', 0))
        sock1.settimeout(2.0)
        _, port1 = sock1.getsockname()

        sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock2.bind(('127.0.0.1', 0))
        sock2.settimeout(2.0)
        _, port2 = sock2.getsockname()

        try:
            # First target uses inline :port1, second target uses default UDP_FORWARD_PORT=port2
            os.environ['UDP_FORWARD_HOST'] = f'127.0.0.1:{port1}, 127.0.0.1'
            os.environ['UDP_FORWARD_PORT'] = str(port2)
            os.environ['UDP_FORWARD_ENABLED'] = 'true'
            init_udp_forwarder()

            status = get_status()
            self.assertTrue(status['enabled'])
            self.assertEqual(len(status['targets']), 2)
            self.assertEqual(status['targets'][0], {'host': '127.0.0.1', 'port': port1})
            self.assertEqual(status['targets'][1], {'host': '127.0.0.1', 'port': port2})

            pocsag_payload = {
                'type': 'message',
                'id': 99,
                'address': '7654321',
                'message': 'LARM: Multihost UDP test',
                'protocol': 'POCSAG',
                'bitrate': '1200'
            }

            res = forward_pocsag(pocsag_payload)
            self.assertTrue(res)

            data1, _ = sock1.recvfrom(4096)
            data2, _ = sock2.recvfrom(4096)

            json1 = json.loads(data1.decode('utf-8'))
            json2 = json.loads(data2.decode('utf-8'))

            self.assertEqual(json1['id'], 99)
            self.assertEqual(json2['id'], 99)
            self.assertEqual(json1['message'], 'LARM: Multihost UDP test')
            self.assertEqual(json2['message'], 'LARM: Multihost UDP test')
        finally:
            sock1.close()
            sock2.close()


if __name__ == '__main__':
    unittest.main()

import unittest

from pydantic import ValidationError

from app.schemas.device import DeviceCreate


def payload(host: str) -> dict:
    return {"name": "Portaria", "host": host, "username": "admin", "password": "secret"}


class DeviceCreateTests(unittest.TestCase):
    def test_accepts_a_ddns_hostname(self) -> None:
        device = DeviceCreate(**payload("portaria.ddns.net"))

        self.assertEqual(device.host, "portaria.ddns.net")

    def test_accepts_an_ip_address(self) -> None:
        self.assertEqual(DeviceCreate(**payload("192.168.1.10")).host, "192.168.1.10")

    def test_defaults_to_the_isapi_port(self) -> None:
        self.assertEqual(DeviceCreate(**payload("192.168.1.10")).port, 80)

    def test_rejects_a_malformed_host(self) -> None:
        for host in ("nao valido", "-inicio.net", "fim-.net", "a..b"):
            with self.subTest(host=host), self.assertRaises(ValidationError):
                DeviceCreate(**payload(host))

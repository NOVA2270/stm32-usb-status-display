"""Offline regression tests: no physical HID or COM devices are accessed."""
import contextlib
import datetime
import io
import unittest
from unittest.mock import Mock, patch

import maxwell_battery as app


class BatteryTests(unittest.TestCase):
    def test_battery_marker_and_invalid_percentage(self):
        marker = b"\xd6\x0c\x00\x00"
        for value in (0, 26, 100):
            self.assertEqual(app.parse_battery(b"\x07" + marker + bytes([value])), value)
        for response in (b"", marker, marker + b"\xff", b"unrelated"):
            self.assertIsNone(app.parse_battery(response))

    def test_disconnected_device_does_not_keep_old_value(self):
        state = {"logitech": (88, 1), "audeze": (77, 0)}
        reading = app.BatteryReading("Audeze Maxwell", 26, "Maxwell", 0x4B19, "", b"")
        app.update_packet_state([reading], state)
        self.assertEqual(state, {"logitech": (-1, -1), "audeze": (26, -1)})
        app.update_packet_state([], state)
        self.assertEqual(state, {"logitech": (-1, -1), "audeze": (-1, -1)})

    def test_only_known_maxwell_interfaces_are_used(self):
        good = dict(product_id=0x4B19, usage_page=0xFF13, usage=1)
        unknown = dict(product_id=0xFFFF, product_string="Maxwell 2", usage_page=0xFF13, usage=1)
        wrong_interface = dict(product_id=0x4B19, usage_page=1, usage=2)
        with patch.object(app, "hid") as fake:
            fake.enumerate.return_value = [good, unknown, wrong_interface]
            self.assertEqual(app._preferred_interfaces(app.enumerate_maxwell()), [good])

    def test_audio_parameter_write_is_excluded(self):
        write_prefix = bytes.fromhex("06 09 80 05 5a 05 00 00 09 25")
        self.assertFalse(any(packet.startswith(write_prefix) for packet in
                             app.INITIALIZATION_REQUESTS + app.STATUS_REQUESTS))

    @patch.object(app.time, "sleep")
    def test_maxwell_rejects_partial_io(self, _sleep):
        device = Mock()
        device.write.return_value = 1
        with self.assertRaises(OSError):
            app._exchange(device, app.STATUS_REQUESTS[0])
        device.get_input_report.assert_not_called()
        device.write.return_value = 62
        device.get_input_report.return_value = b"\x07"
        with self.assertRaises(OSError):
            app._exchange(device, app.STATUS_REQUESTS[0])

    def test_hidpp_rejects_short_matching_response(self):
        request = app._hidpp_request(1, 2, 1)
        device = Mock()
        device.read.side_effect = [[], list(request[:4])]
        device.write.return_value = 20
        with self.assertRaises(OSError):
            app._hidpp_exchange(device, request)

    def test_hidpp_discards_unrelated_response(self):
        request = app._hidpp_request(1, 2, 1)
        expected = request[:4] + bytes([44, 0, 0]) + bytes(13)
        device = Mock()
        device.read.side_effect = [[], bytes(20), expected]
        device.write.return_value = 20
        self.assertEqual(app._hidpp_exchange(device, request), expected)

    def test_hidpp_drain_has_a_limit(self):
        device = Mock()
        device.read.return_value = [1] * 20
        with self.assertRaises(TimeoutError):
            app._hidpp_exchange(device, app._hidpp_request(1, 2, 1))
        device.write.assert_not_called()
        self.assertLessEqual(device.read.call_count, 64)

    def test_weather_rejects_server_error_and_handles_celsius(self):
        with patch.object(app.urllib.request, "urlopen") as opener:
            response = opener.return_value.__enter__.return_value
            for raw, expected in [("+22°C\n", "+22"), ("-7°C", "-7"),
                                  ("<html>Error 503</html>", "--"), ("+999°C", "--")]:
                response.read.return_value = raw.encode()
                self.assertEqual(app.get_weather_temperature("Moscow"), expected)

    def test_packet_matches_six_field_firmware_protocol(self):
        packet = app.build_stm32_packet(
            {"logitech": (44, 0), "audeze": (26, -1)}, "+22",
            datetime.datetime(2026, 9, 10, 18, 17))
        self.assertEqual(packet, "L44 LC0 A26 AC-1 T18:17 W+22\n")
        self.assertLessEqual(len(packet.encode("ascii")), 63)

    def test_packet_rejects_injection_and_invalid_battery(self):
        state = {"logitech": (44, 0), "audeze": (26, -1)}
        with self.assertRaises(ValueError):
            app.build_stm32_packet(state, "22\nL99")
        state["logitech"] = (101, 0)
        with self.assertRaises(ValueError):
            app.build_stm32_packet(state)

    def test_demo_runs_without_hid_serial_or_network(self):
        with patch.object(app, "hid", None), patch.object(app, "serial", None), \
                patch.object(app, "get_weather_temperature", side_effect=AssertionError("network")), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(app.main(["--demo"]), 0)
            self.assertIn("L44 LC0 A26 AC-1 T", output.getvalue())

    def test_invalid_poll_intervals(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for interval in ("nan", "inf", "0", "-1", "29"):
                self.assertEqual(app.main(["--demo", "--watch", interval]), 2)

    @unittest.skipIf(app.serial is None, "pyserial is not installed")
    def test_serial_loopback(self):
        packet = app.build_stm32_packet({"logitech": (100, 1), "audeze": (-1, -1)}, "-15")
        with app.serial.serial_for_url("loop://", timeout=1) as port:
            encoded = packet.encode("ascii")
            self.assertEqual(port.write(encoded), len(encoded))
            self.assertEqual(port.readline(), encoded)

    @unittest.skipIf(app.serial is None, "pyserial is not installed")
    def test_demo_once_sends_and_closes_port(self):
        port = Mock(is_open=True)
        port.write.side_effect = lambda data: len(data)
        with patch.object(app.serial, "serial_for_url", return_value=port), \
                patch.object(app.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(app.main(["--demo", "--port", "COM_TEST", "--once"]), 0)
        self.assertTrue(port.write.call_args.args[0].startswith(b"L44 LC0 A26 AC-1 T"))
        port.close.assert_called_once()

    @unittest.skipIf(app.serial is None, "pyserial is not installed")
    def test_com_write_failure_returns_error(self):
        port = Mock(is_open=True)
        port.write.return_value = 0
        with patch.object(app.serial, "serial_for_url", return_value=port), \
                patch.object(app.time, "sleep"), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(app.main(["--demo", "--port", "COM_TEST", "--once"]), 1)
        port.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

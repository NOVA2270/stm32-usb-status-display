#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Maxwell protocol adapted from HeadsetControl (Sapd and contributors).
# See LICENSE and ../THIRD_PARTY_NOTICES.md.
"""Показывает заряд Audeze Maxwell и Logitech G PRO X Superlight 2.

Зависимости: python -m pip install hidapi pyserial
Примеры:
  python maxwell_battery.py
  python maxwell_battery.py --watch 30
  python maxwell_battery.py --port COM5 --watch 60
  python maxwell_battery.py --json
  python maxwell_battery.py --list
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

try:
    import hid  # type: ignore
except ImportError:
    hid = None

try:
    import serial  # type: ignore
except ImportError:
    serial = None


MAXWELL_VENDOR_ID = 0x3329
MAXWELL_PRODUCT_IDS = {0x4B18, 0x4B19, 0x4B1A}  # Xbox/PS dongle, wired headset
MAXWELL_USAGE_PAGE = 0xFF13
MAXWELL_USAGE_ID = 0x01
MAXWELL_REPORT_SIZE = 62
MAXWELL_INPUT_REPORT_ID = 0x07
MAXWELL_PACKET_DELAY = 0.060

LOGITECH_VENDOR_ID = 0x046D
LOGITECH_PRODUCT_IDS = {
    0xC54D,  # G PRO X Superlight 2 LIGHTSPEED receiver
    0xC09B,  # G PRO X Superlight 2 connected by USB cable
}
LOGITECH_WIRED_PRODUCT_IDS = {0xC09B}
LOGITECH_USAGE_PAGE = 0xFF00
LOGITECH_WRITE_USAGE = 0x02
LOGITECH_REPORT_ID = 0x11
LOGITECH_REPORT_SIZE = 20
LOGITECH_SOFTWARE_ID = 0x0D
LOGITECH_UNIFIED_BATTERY = 0x1004
LOGITECH_RESPONSE_TIMEOUT = 1.5

MIN_WATCH_INTERVAL = 30.0


def _packet(*values: int) -> bytes:
    if len(values) > MAXWELL_REPORT_SIZE:
        raise ValueError("HID packet is too long")
    return bytes(values) + bytes(MAXWELL_REPORT_SIZE - len(values))


# Последовательности чтения перенесены из реализации Audeze Maxwell в
# HeadsetControl. Намеренно исключена команда
#   06 09 80 05 5A 05 00 00 09 25 00 7A
# из исходной инициализации: это запись параметра 0x25, а для утилиты, которая
# только показывает батарею, изменение настроек гарнитуры недопустимо.
INITIALIZATION_REQUESTS = (
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x20),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x25),
    _packet(0x06, 0x07, 0x80, 0x05, 0x5A, 0x03, 0x00, 0x07, 0x1C),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x28),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x83, 0x2C, 0x01),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x83, 0x2C, 0x07),
    _packet(0x06, 0x07, 0x00, 0x05, 0x5A, 0x03, 0x00, 0x07, 0x1C),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x2D),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x2C),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x83, 0x2C, 0x0B),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x24),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x2F),
    _packet(0x06, 0x07, 0x80, 0x05, 0x5A, 0x03, 0x00, 0xD6, 0x0C),
)

STATUS_REQUESTS = (
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x22),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x83, 0x2C, 0x0B),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x24),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x01, 0x09, 0x2C),
    _packet(0x06, 0x08, 0x80, 0x05, 0x5A, 0x04, 0x00, 0x83, 0x2C, 0x07),
)


@dataclass(frozen=True)
class BatteryReading:
    name: str
    percent: int
    product: str
    product_id: int
    path: str
    raw_response: bytes
    charging: bool | None = None


def _path_text(path: Any) -> str:
    if isinstance(path, bytes):
        return path.decode("utf-8", errors="backslashreplace")
    return str(path)


def enumerate_maxwell() -> list[dict[str, Any]]:
    devices = hid.enumerate(MAXWELL_VENDOR_ID, 0)  # type: ignore[union-attr]
    candidates = []
    for item in devices:
        pid = int(item.get("product_id") or 0)
        if pid in MAXWELL_PRODUCT_IDS:
            candidates.append(item)
    return candidates


def _preferred_interfaces(devices: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    devices = list(devices)
    exact = [
        d for d in devices
        if d.get("usage_page") == MAXWELL_USAGE_PAGE and d.get("usage") == MAXWELL_USAGE_ID
    ]
    return exact


def _exchange(device: Any, request: bytes) -> bytes:
    time.sleep(MAXWELL_PACKET_DELAY)
    written = device.write(request)
    if written != len(request):
        raise OSError("HID write was incomplete")
    if not hasattr(device, "get_input_report"):
        raise RuntimeError(
            "Установленная библиотека hidapi не поддерживает get_input_report; "
            "обновите её: python -m pip install -U hidapi"
        )
    response = bytes(device.get_input_report(MAXWELL_INPUT_REPORT_ID, MAXWELL_REPORT_SIZE))
    if len(response) != MAXWELL_REPORT_SIZE:
        raise OSError(f"ожидалось {MAXWELL_REPORT_SIZE} байт, получено {len(response)}")
    return response


def parse_battery(response: Sequence[int]) -> int | None:
    data = bytes(response)
    marker = b"\xD6\x0C\x00\x00"
    position = data.find(marker)
    if position < 0 or position + len(marker) >= len(data):
        return None
    percent = data[position + len(marker)]
    return percent if 0 <= percent <= 100 else None


def query_maxwell_battery(debug: bool = False) -> BatteryReading:
    candidates = _preferred_interfaces(enumerate_maxwell())
    if not candidates:
        raise RuntimeError(
            "Audeze Maxwell не найден. Подключите USB-донгл и включите гарнитуру."
        )

    errors: list[str] = []
    for info in candidates:
        device = hid.device()  # type: ignore[union-attr]
        path = info["path"]
        path_text = _path_text(path)
        try:
            device.open_path(path)
            for request in INITIALIZATION_REQUESTS:
                _exchange(device, request)

            battery_response = b""
            for index, request in enumerate(STATUS_REQUESTS):
                response = _exchange(device, request)
                if index == 0:
                    battery_response = response

            percent = parse_battery(battery_response)
            if percent is None:
                suffix = f"; ответ: {battery_response.hex(' ')}" if debug else ""
                raise RuntimeError("гарнитура не вернула уровень батареи" + suffix)

            return BatteryReading(
                name="Audeze Maxwell",
                percent=percent,
                product=str(info.get("product_string") or "Audeze Maxwell"),
                product_id=int(info.get("product_id") or 0),
                path=path_text,
                raw_response=battery_response,
                # USB connection alone does not prove that the battery is charging.
                charging=None,
            )
        except Exception as exc:
            errors.append(f"{path_text}: {exc}")
        finally:
            try:
                device.close()
            except Exception:
                pass

    details = "\n  ".join(errors)
    raise RuntimeError(
        "Maxwell найден, но прочитать заряд не удалось. Закройте Audeze HQ и повторите."
        + (f"\n  {details}" if details else "")
    )


def enumerate_logitech_mouse() -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for product_id in LOGITECH_PRODUCT_IDS:
        devices.extend(hid.enumerate(LOGITECH_VENDOR_ID, product_id))  # type: ignore[union-attr]
    candidates = [
        item for item in devices
        if item.get("usage_page") == LOGITECH_USAGE_PAGE
        and item.get("usage") == LOGITECH_WRITE_USAGE
    ]
    return sorted(
        candidates,
        key=lambda item: int(item.get("product_id") or 0) not in LOGITECH_WIRED_PRODUCT_IDS,
    )


def _hidpp_request(
    device_index: int, feature_index: int, function: int, *parameters: int
) -> bytes:
    if len(parameters) > 16:
        raise ValueError("Слишком много параметров HID++")
    function_and_software_id = (function << 4) | LOGITECH_SOFTWARE_ID
    prefix = bytes(
        [LOGITECH_REPORT_ID, device_index, feature_index, function_and_software_id]
    )
    return prefix + bytes(parameters) + bytes(16 - len(parameters))


def _hidpp_exchange(device: Any, request: bytes) -> bytes:
    # Убираем накопившиеся push-события, не изменяя настройки мыши.
    for _ in range(64):
        if not device.read(LOGITECH_REPORT_SIZE, 1):
            break
    else:
        raise TimeoutError("поток HID++ событий не прекращается; повторите опрос")

    if device.write(request) != LOGITECH_REPORT_SIZE:
        raise OSError("не удалось отправить HID++ запрос")

    expected = request[:4]
    deadline = time.monotonic() + LOGITECH_RESPONSE_TIMEOUT
    while time.monotonic() < deadline:
        response = bytes(device.read(LOGITECH_REPORT_SIZE, 100))
        if not response:
            continue
        if len(response) >= 4 and response[:4] == expected:
            if len(response) != LOGITECH_REPORT_SIZE:
                raise OSError("неполный HID++ ответ")
            return response
        # HID++ 2.0 error: FF, original feature index, function/software ID, code.
        if (
            len(response) >= 6
            and response[0] == LOGITECH_REPORT_ID
            and response[1] == request[1]
            and response[2] == 0xFF
            and response[3:5] == request[2:4]
        ):
            raise RuntimeError(f"HID++ вернул ошибку 0x{response[5]:02X}")
    raise TimeoutError("мышь не ответила; подвигайте её и повторите")


def query_logitech_battery() -> BatteryReading:
    candidates = enumerate_logitech_mouse()
    if not candidates:
        raise RuntimeError("Logitech G PRO X Superlight 2 не найдена")

    errors: list[str] = []
    for info in candidates:
        device = hid.device()  # type: ignore[union-attr]
        path = info["path"]
        path_text = _path_text(path)
        try:
            device.open_path(path)
            product_id = int(info.get("product_id") or 0)
            device_index = 0xFF if product_id in LOGITECH_WIRED_PRODUCT_IDS else 0x01

            # Root.getFeature(0x1004) возвращает динамический индекс Unified Battery.
            lookup = _hidpp_request(
                device_index,
                0x00,
                0,
                (LOGITECH_UNIFIED_BATTERY >> 8) & 0xFF,
                LOGITECH_UNIFIED_BATTERY & 0xFF,
                0x00,
            )
            feature_response = _hidpp_exchange(device, lookup)
            feature_index = feature_response[4]
            if feature_index == 0:
                raise RuntimeError("мышь не поддерживает HID++ Unified Battery")

            # UnifiedBattery.getBatteryInfo(), fn=1. Это только чтение.
            battery_response = _hidpp_exchange(
                device,
                _hidpp_request(device_index, feature_index, 1, 0x00, 0x00, 0x00),
            )
            percent = battery_response[4]
            status_code = battery_response[6]
            if percent > 100:
                raise RuntimeError(f"некорректный заряд: {percent}")

            if status_code == 4:
                raise RuntimeError("мышь сообщила об ошибке батареи")
            return BatteryReading(
                name="Logitech G PRO X Superlight 2",
                percent=percent,
                product=str(info.get("product_string") or "LIGHTSPEED Receiver"),
                product_id=product_id,
                path=path_text,
                raw_response=battery_response,
                charging=(status_code in (1, 2)) if status_code in (0, 1, 2, 3) else None,
            )
        except Exception as exc:
            errors.append(f"{path_text}: {exc}")
        finally:
            try:
                device.close()
            except Exception:
                pass

    raise RuntimeError("Не удалось прочитать заряд мыши:\n  " + "\n  ".join(errors))


def print_devices() -> None:
    devices = enumerate_maxwell() + enumerate_logitech_mouse()
    if not devices:
        print("Поддерживаемые HID-интерфейсы не найдены.")
        return
    for item in devices:
        print(
            f"VID:PID={item.get('vendor_id', 0):04X}:{item.get('product_id', 0):04X} "
            f"usage={item.get('usage_page', 0):04X}:{item.get('usage', 0):04X} "
            f"interface={item.get('interface_number', '?')} "
            f"product={item.get('product_string')!r}\n  {_path_text(item.get('path'))}"
        )


def reading_to_dict(reading: BatteryReading, debug: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
            "device": reading.product,
            "name": reading.name,
            "product_id": f"0x{reading.product_id:04x}",
            "battery_percent": reading.percent,
    }
    if reading.charging is not None:
        result["charging"] = reading.charging
    if debug:
        result["path"] = reading.path
        result["raw_response"] = reading.raw_response.hex(" ")
    return result


def emit(readings: list[BatteryReading], errors: list[str], as_json: bool, debug: bool) -> None:
    if as_json:
        print(json.dumps(
            {
                "devices": [reading_to_dict(reading, debug) for reading in readings],
                "errors": errors,
            },
            ensure_ascii=False,
        ))
        return

    for reading in readings:
        suffix = " (заряжается)" if reading.charging else ""
        print(f"{reading.name}: {reading.percent}%{suffix}")
        if debug:
            print(f"  HID: {reading.product} (PID 0x{reading.product_id:04X})")
            print(f"  Путь: {reading.path}")
            print(f"  Ответ: {reading.raw_response.hex(' ')}")
    for error in errors:
        print(f"Ошибка: {error}", file=sys.stderr)


def get_weather_temperature(location: str) -> str:
    """Возвращает целую температуру, пригодную для ASCII-пакета STM32."""
    try:
        encoded_location = urllib.parse.quote(location, safe="")
        url = f"https://wttr.in/{encoded_location}?format=%t&m"
        request = urllib.request.Request(url, headers={"User-Agent": "battery-monitor/1.0"})
        with urllib.request.urlopen(request, timeout=3) as response:
            text = response.read(128).decode("utf-8", errors="replace")
        match = re.fullmatch(r"\s*([+-]?[0-9]{1,3})(?:\s*°?\s*C)?\s*", text)
        return match.group(1) if match and -100 <= int(match.group(1)) <= 100 else "--"
    except Exception:
        return "--"


def update_packet_state(
    readings: list[BatteryReading], state: dict[str, tuple[int, int]]
) -> None:
    # A failed poll must not keep the previous device's battery level on screen.
    state.update(logitech=(-1, -1), audeze=(-1, -1))
    for reading in readings:
        if not 0 <= reading.percent <= 100:
            continue
        charging_status = -1 if reading.charging is None else int(reading.charging)
        if reading.name == "Logitech G PRO X Superlight 2":
            state["logitech"] = (reading.percent, charging_status)
        elif reading.name == "Audeze Maxwell":
            state["audeze"] = (reading.percent, charging_status)


def build_stm32_packet(
    state: dict[str, tuple[int, int]], weather_text: str = "--",
    now: datetime.datetime | None = None,
) -> str:
    logitech_percent, logitech_charge_status = state["logitech"]
    audeze_percent, audeze_charge_status = state["audeze"]
    for percent, charging in (state["logitech"], state["audeze"]):
        if not -1 <= percent <= 100 or charging not in (-1, 0, 1):
            raise ValueError("Battery value outside the protocol range")
    if weather_text != "--" and not re.fullmatch(r"[+-]?[0-9]{1,3}", weather_text):
        raise ValueError("Temperature must be an ASCII integer or --")
    time_text = (now or datetime.datetime.now()).strftime("%H:%M")
    packet = (
        f"L{logitech_percent} LC{logitech_charge_status} "
        f"A{audeze_percent} AC{audeze_charge_status} "
        f"T{time_text} W{weather_text}\n"
    )
    if len(packet.encode("ascii")) > 63:
        raise ValueError("Packet exceeds the firmware line buffer")
    return packet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Показать заряд Maxwell и Superlight 2")
    parser.add_argument("--watch", type=float, metavar="SECONDS", help="опрашивать с указанным интервалом")
    parser.add_argument("--json", action="store_true", help="выводить JSON")
    parser.add_argument("--list", action="store_true", help="показать найденные HID-интерфейсы")
    parser.add_argument("--debug", action="store_true", help="показать HID-путь и сырой ответ")
    parser.add_argument("--port", metavar="COM_PORT", help="отправлять ASCII-пакеты на STM32, например COM5")
    parser.add_argument("--baud", type=int, default=115200, help="скорость COM-порта (по умолчанию 115200)")
    parser.add_argument("--weather-location", default="Moscow", help="город для температуры wttr.in")
    parser.add_argument("--no-weather", action="store_true", help="не обращаться к погодному сервису")
    parser.add_argument("--demo", action="store_true", help="пример данных без опроса HID и интернета")
    parser.add_argument("--once", action="store_true", help="один опрос и выход, в том числе с --port")
    parser.add_argument("--list-ports", action="store_true", help="показать доступные COM-порты")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_ports:
        if serial is None:
            print("Установите pyserial для просмотра портов", file=sys.stderr)
            return 2
        from serial.tools import list_ports
        for port in list_ports.comports():
            print(f"{port.device}: {port.description}")
        return 0
    if hid is None and (not args.demo or args.list):
        print("Не найден модуль hid. Установите: python -m pip install hidapi", file=sys.stderr)
        return 2
    if args.port and serial is None:
        print("Не найден модуль serial. Установите: python -m pip install pyserial", file=sys.stderr)
        return 2
    if args.list:
        print_devices()
        return 0
    if args.baud <= 0:
        print("Скорость порта должна быть положительной", file=sys.stderr)
        return 2
    if args.watch is not None and (not math.isfinite(args.watch) or args.watch < MIN_WATCH_INTERVAL):
        print(
            f"Интервал --watch должен быть не меньше {MIN_WATCH_INTERVAL:g} секунд, "
            "чтобы не опрашивать Maxwell слишком часто.",
            file=sys.stderr,
        )
        return 2

    packet_state = {
        "logitech": (-1, -1),
        "audeze": (-1, -1),
    }
    serial_connection: Any = None
    poll_interval = args.watch if args.watch is not None else (60.0 if args.port else None)
    if args.once:
        poll_interval = None
    weather_text = "--"
    weather_updated: float | None = None

    try:
        while True:
            readings: list[BatteryReading] = []
            errors: list[str] = []
            if args.demo:
                readings = [
                    BatteryReading("Logitech G PRO X Superlight 2", 44, "Demo mouse", 0xC54D, "", b"", False),
                    BatteryReading("Audeze Maxwell", 26, "Demo headset", 0x4B19, "", b""),
                ]
                if not args.json:
                    print("DEMO: пример данных / sample data")
            for query in (() if args.demo else (query_maxwell_battery, query_logitech_battery)):
                try:
                    readings.append(query(args.debug) if query is query_maxwell_battery else query())
                except Exception as exc:
                    errors.append(str(exc))
            emit(readings, errors, args.json, args.debug)
            update_packet_state(readings, packet_state)
            send_failed = False
            if args.port or args.demo:
                if args.demo:
                    weather_text = "+22"
                elif not args.no_weather and (
                    weather_updated is None or time.monotonic() - weather_updated >= 300
                ):
                    weather_text = get_weather_temperature(args.weather_location)
                    weather_updated = time.monotonic()
                packet = build_stm32_packet(packet_state, weather_text)
                if args.demo and not args.port:
                    print(packet.rstrip(), file=sys.stderr if args.json else sys.stdout)

            if args.port:
                try:
                    if serial_connection is None or not serial_connection.is_open:
                        serial_connection = serial.serial_for_url(
                            args.port,
                            args.baud,
                            timeout=1,
                            write_timeout=2,
                        )
                        # После открытия CDC-порта плата может кратковременно
                        # переинициализироваться; первый пакет отправляем после паузы.
                        time.sleep(1.5)
                    encoded = packet.encode("ascii")
                    if serial_connection.write(encoded) != len(encoded):
                        raise OSError("COM write was incomplete")
                    serial_connection.flush()
                    if args.debug:
                        print(f"{args.port} <- {packet.rstrip()}", file=sys.stderr)
                except Exception as exc:
                    send_failed = True
                    print(f"Ошибка COM-порта {args.port}: {exc}", file=sys.stderr)
                    if serial_connection is not None:
                        try:
                            serial_connection.close()
                        except Exception:
                            pass
                    serial_connection = None

            if poll_interval is None:
                return 0 if readings and not send_failed else 1
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        return 130
    finally:
        if serial_connection is not None:
            try:
                serial_connection.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

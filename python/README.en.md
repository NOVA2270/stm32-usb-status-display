# PC client: batteries → USB → OLED

[Русский](README.md) · **English**

`maxwell_battery.py` polls an Audeze Maxwell and a Logitech G PRO X Superlight 2 through HID and sends readings to the STM32F401 firmware over a virtual COM port. A separate `headsetcontrol.exe` is not required.

## Installation

Windows, Python 3.10 or later. Tested with Python 3.12.14. Run commands from the repository root:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r python/requirements.txt
```

Dependencies: `hidapi` (imported as `hid`) and `pyserial`. Do not install the separate package named `hid`.

## First run

An example without hardware or internet access:

```powershell
.venv\Scripts\python.exe python/maxwell_battery.py --demo
```

List the board's COM port and supported HID interfaces:

```powershell
.venv\Scripts\python.exe python/maxwell_battery.py --list-ports
.venv\Scripts\python.exe python/maxwell_battery.py --list
```

Send real readings once per minute. Replace `COM5` with your board's port:

```powershell
.venv\Scripts\python.exe python/maxwell_battery.py --port COM5 --watch 60
```

Stop with `Ctrl+C`. Close other applications using that COM port. If Maxwell does not respond, close Audeze HQ and retry; try moving a sleeping mouse.

## Options

| Arguments | Behavior |
|---|---|
| No arguments | Poll devices once and print readings |
| `--port COM5` | Send to the board every 60 seconds |
| `--watch 30` | Repeated polling; minimum interval is 30 seconds |
| `--port COM5 --once` | Send once and exit |
| `--demo --port COM5 --once` | Send sample values 44% / 26% / +22°C to the board |
| `--weather-location Moscow` | Location for wttr.in; defaults to Moscow |
| `--no-weather` | Skip the weather service and send `W--` |
| `--json` | Print polling results as JSON |
| `--debug` | Include communication diagnostics |

Time comes from the PC. Temperature is requested in °C only when sending to a port, at most once every five minutes. A failed request produces `--`. Demo mode uses fictional readings and never polls HID or the internet; it writes to a COM port only when `--port` is explicitly supplied.

## Protocol and devices

```text
L44 LC0 A26 AC-1 T18:17 W+22\n
```

Here `\n` represents one newline character. The fields match the [firmware parser](../Core/Src/main.c). The script validates ranges and line length before sending. A failed device poll resets its battery and charging state to `-1` instead of keeping stale data. Maxwell charging status is unknown: a USB connection alone does not prove charging.

HID filters: Maxwell VID `3329`, PID `4B18/4B19/4B1A`, usage `FF13:0001`; Logitech VID `046D`, PID `C54D/C09B`, usage `FF00:0002`. Other models, including Maxwell 2, are not polled. Each connection variant requires validation on the corresponding hardware.

Maxwell sequences are based on [HeadsetControl](https://github.com/Sapd/HeadsetControl/blob/master/lib/devices/audeze_maxwell.hpp). The parameter `0x25` write associated with the audio-balance issue is excluded; see [PR #577](https://github.com/Sapd/HeadsetControl/pull/577). See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and [LICENSE](LICENSE) for attribution and licensing.

## Validation

```powershell
.venv\Scripts\python.exe -m unittest discover -s python -v
.venv\Scripts\python.exe python/maxwell_battery.py --demo --port loop:// --once --debug
```

Tests use simulated HID responses and a virtual [pyserial loop:// port](https://pyserial.readthedocs.io/en/latest/url_handlers.html#loop), without accessing physical devices. They cover disconnected devices, malformed responses, write failures, packet format and offline demo mode.

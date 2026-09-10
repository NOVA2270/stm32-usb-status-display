# Проверка сборки / Build validation

**2026-09-10 — Arm Compiler 6.22, Keil µVision**

## Русский

Сборка завершилась с **0 ошибок, 0 предупреждений**, включая компоновку и создание HEX.

Размер из отчёта компоновки:

```text
Program Size: Code=27540 RO-data=2480 RW-data=256 ZI-data=10456
```

Проверка сборки выполнена на Windows. Аппаратные испытания в эту проверку не входили.

## English

Build completed with **0 errors and 0 warnings**, including linking and HEX generation.

The linker-reported size is shown above. The build was verified on Windows; hardware testing was outside the scope of this check.

## Python — 2026-09-11

Windows, Python 3.12.14, hidapi 0.15.0, pyserial 3.5.

**16 тестов пройдены**: протокол STM32, потеря устройства, повреждённые HID-ответы, ограничение чтения событий, ошибки COM-порта и режим без оборудования. Пройдена передача через виртуальный порт `loop://`.

**16 tests passed**: STM32 packet format, device loss, malformed HID responses, bounded event draining, COM errors and offline demo mode. Virtual `loop://` transmission passed.

```powershell
python -m unittest discover -s python -v
python python/maxwell_battery.py --demo --port loop:// --once --debug
```

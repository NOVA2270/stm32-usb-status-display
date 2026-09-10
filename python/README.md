# Клиент ПК: батареи → USB → OLED

**Русский** · [English](README.en.md)

`maxwell_battery.py` опрашивает Audeze Maxwell и Logitech G PRO X Superlight 2 через HID и передаёт данные в прошивку STM32F401 по виртуальному COM-порту. Отдельный `headsetcontrol.exe` не требуется.

## Установка

Windows, Python 3.10 или новее. Проверено на Python 3.12.14. Команды выполняются из корня репозитория:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r python/requirements.txt
```

Зависимости: `hidapi` (импортируется как `hid`) и `pyserial`. Пакет с названием `hid` устанавливать не нужно.

## Первый запуск

Пример без оборудования и без интернета:

```powershell
.venv\Scripts\python.exe python/maxwell_battery.py --demo
```

Найти COM-порт платы и поддерживаемые HID-интерфейсы:

```powershell
.venv\Scripts\python.exe python/maxwell_battery.py --list-ports
.venv\Scripts\python.exe python/maxwell_battery.py --list
```

Передавать реальные показания раз в минуту. Заменить `COM5` на порт своей платы:

```powershell
.venv\Scripts\python.exe python/maxwell_battery.py --port COM5 --watch 60
```

Остановка — `Ctrl+C`. Закройте другие программы, занявшие этот COM-порт. Если Maxwell не отвечает, закройте Audeze HQ и повторите; для спящей мыши попробуйте движение.

## Режимы

| Аргументы | Поведение |
|---|---|
| Без аргументов | Один опрос устройств, вывод в консоль |
| `--port COM5` | Отправка на плату каждые 60 секунд |
| `--watch 30` | Повторный опрос; минимальный интервал 30 секунд |
| `--port COM5 --once` | Одна отправка и выход |
| `--demo --port COM5 --once` | Отправить пример 44% / 26% / +22°C на плату |
| `--weather-location Moscow` | Город для wttr.in; по умолчанию Москва |
| `--no-weather` | Не обращаться к погодному сервису, отправлять `W--` |
| `--json` | Результаты опроса в JSON |
| `--debug` | Подробности обмена для диагностики |

Время берётся с ПК. Температура запрашивается в °C только при отправке на плату и обновляется не чаще раза в пять минут. Ошибка запроса даёт `--`. Режим `--demo` всегда использует вымышленные показания и не опрашивает устройства или интернет; запись в COM-порт выполняется только при явном `--port`.

## Протокол и устройства

```text
L44 LC0 A26 AC-1 T18:17 W+22\n
```

Здесь `\n` обозначает один символ конца строки. Поля соответствуют парсеру в [прошивке](../Core/Src/main.c). Скрипт проверяет диапазоны и размер строки перед отправкой. При неудачном опросе заряд соответствующего устройства становится `-1`, состояние зарядки — `-1`, вместо сохранения старого значения. Для Maxwell состояние зарядки неизвестно: подключение USB само по себе не означает зарядку.

Фильтры HID: Maxwell VID `3329`, PID `4B18/4B19/4B1A`, usage `FF13:0001`; Logitech VID `046D`, PID `C54D/C09B`, usage `FF00:0002`. Другие модели, включая Maxwell 2, не опрашиваются. Совместимость каждого варианта подключения требует проверки на соответствующем оборудовании.

Последовательности Maxwell основаны на [HeadsetControl](https://github.com/Sapd/HeadsetControl/blob/master/lib/devices/audeze_maxwell.hpp). Команда записи параметра `0x25`, связанная с проблемой баланса звука, исключена; см. [PR #577](https://github.com/Sapd/HeadsetControl/pull/577). Уведомления и лицензия — в [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) и [LICENSE](LICENSE).

## Проверка

```powershell
.venv\Scripts\python.exe -m unittest discover -s python -v
.venv\Scripts\python.exe python/maxwell_battery.py --demo --port loop:// --once --debug
```

Тесты используют имитацию HID и виртуальный порт [pyserial loop://](https://pyserial.readthedocs.io/en/latest/url_handlers.html#loop). Они не обращаются к физическим устройствам. Проверены потеря устройства, повреждённые ответы, ошибки отправки, формат строки и автономный демонстрационный режим.

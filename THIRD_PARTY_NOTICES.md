# Компоненты / Third-party components

## Русский

STM32 HAL, CMSIS/device headers и сгенерированный каркас приложения содержат исходные уведомления STMicroelectronics/Arm и других авторов. Лицензии компонентов находятся в соответствующих каталогах и заголовках исходников.

Драйвер SSD1306 и шрифты в `Core` содержат уведомления Tilen Majerle / Alexander Lutsai и GPL v3 или более поздней версии. Эти уведомления оставлены без изменений. ST USB Device Library содержит собственный `LICENSE.txt`.

Лицензии отдельных компонентов действуют в отношении соответствующих файлов.

## English

STM32 HAL, CMSIS/device headers and the generated application framework contain their original STMicroelectronics/Arm and other authors' notices. Component licenses are provided in their respective directories and source headers.

The SSD1306 driver and fonts in `Core` carry notices for Tilen Majerle / Alexander Lutsai and GPL v3 or later. These notices are retained unchanged. The ST USB Device Library has its own `LICENSE.txt`.

Individual component licenses apply to their corresponding files.

## Python / HeadsetControl

Последовательности запросов и разбор батареи Maxwell в `python/maxwell_battery.py` адаптированы из [HeadsetControl, Sapd and contributors](https://github.com/Sapd/HeadsetControl/blob/master/lib/devices/audeze_maxwell.hpp), GPL-3.0. Python-клиент распространяется по GPL-3.0; текст лицензии находится в [python/LICENSE](python/LICENSE). Адаптация использует Python HID API, исключает запись параметра `0x25` и добавляет сбор данных Logitech, погоды и передачу по COM.

The Maxwell request sequences and battery parsing in `python/maxwell_battery.py` are adapted from [HeadsetControl, Sapd and contributors](https://github.com/Sapd/HeadsetControl/blob/master/lib/devices/audeze_maxwell.hpp), GPL-3.0. The Python client is distributed under GPL-3.0; see [python/LICENSE](python/LICENSE). The adaptation uses Python HID APIs, omits the parameter `0x25` write, and adds Logitech/weather data collection and COM transmission.

Dependencies are installed separately: [hidapi Python bindings](https://github.com/trezor/cython-hidapi) and [pyserial](https://github.com/pyserial/pyserial). Their respective licenses apply.

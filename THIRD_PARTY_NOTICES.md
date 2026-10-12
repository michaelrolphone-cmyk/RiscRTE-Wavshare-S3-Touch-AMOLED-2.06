# Third-party notices

## Espressif codec control sequences — Apache-2.0

The ES8311 and ES7210 control sequences in `drivers/codec_es83xx/driver.c` are adapted from Espressif's esp_codec_dev implementations and the Waveshare ES8311 reference. They have been rewritten to use RiscRTE capability transports and session lifecycles.

Copyright (c) 2015-2022 Espressif Systems (Shanghai) CO LTD (ES8311).
Copyright (c) 2023 Espressif Systems (Shanghai) CO LTD (ES7210).

Licensed under the Apache License, Version 2.0. The standard license text is in `licenses/Apache-2.0.txt` and is also included with compiled provider artifacts. Source blob identities and adaptation details are recorded in `docs/AUDIO.md`.

## SensorLib — MIT License

The QMI8658 protocol is derived from SensorLib distributed in Waveshare's ESP32-S3-Touch-AMOLED-2.06 example bundle b099739ad0e33b34e5fbaae77f02bd84805d79a3. The implementation uses RiscRTE capability and lifecycle interfaces instead of Arduino classes.

Copyright (c) 2022 Lewis He

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

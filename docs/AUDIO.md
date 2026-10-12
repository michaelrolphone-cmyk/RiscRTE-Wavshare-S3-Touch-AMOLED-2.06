# ES8311 / ES7210 audio

The device provider owns both codecs and their shared standard-I2S clocks. It publishes generic `audio.pcm@1`; reusable RiscRTE-Drivers adapters publish the existing `audio.input@1` and `audio.output@1` application interfaces. Neither the app nor those adapters knows the chips, pin numbers or I2C addresses.

The native raw transport is `platform.i2s.standard`, with copied 16-bit stereo buffers and an explicit MCLK. The board description selects controller, wires, codec addresses and amplifier polarity. The driver opens the shared duplex transport once, adds input/output leases independently and leaves the remaining direction running when the other closes. Rates are 8000, 16000, 22050, 32000, 44100 and 48000 Hz; simultaneous streams must use the same rate.

Output starts muted at 0 dB analog gain. Public gain applies linear attenuation to copied samples; it never maps unity to the codec's +32 dB register maximum. Input configures the two microphones and drops stale startup samples through bounded normal reads. The separate echo-reference channel and software echo cancellation are not implemented.

Tests exercise the actual driver, both generic adapters and every codec startup/shutdown register failure, including errors after a GPIO write, partial output, short input, mismatched rates, duplex ordering and retained native cleanup. The seven physical provider ELFs and two generic audio adapters compile with GCC 8.4 and pass the deployed ELF validator locally. Hardware playback/capture and acoustic quality remain untested.

Source references: Waveshare ESP32-S3-Touch-AMOLED-2.06 b099739ad0e33b34e5fbaae77f02bd84805d79a3, examples/arduino/08_ES8311; Espressif esp-adf components/esp_codec_dev/device/es8311/es8311.c blob b563bae92e4bf69b73d55692348edd97b1d239eb and es7210/es7210.c blob 866ca93539d68a683ab796942281029b7b700330. These files are Apache-2.0 licensed, Copyright 2015-2022 and 2023 Espressif Systems (Shanghai) CO LTD respectively. The implementation rewrites their control sequences against RiscRTE capabilities. A copy of the Apache-2.0 license accompanies this source.

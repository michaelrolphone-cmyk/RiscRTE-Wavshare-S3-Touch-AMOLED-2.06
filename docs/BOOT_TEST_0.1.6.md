# Waveshare 0.1.6 instrumented Home test

Waveshare ESP32-S3 Touch AMOLED 2.06 only. Erase the lower 8 MB, then write the full BIN at address 0x0. No hardware validation is claimed.

This preserves shared Home 0.15.0. Before Home starts its dependent power/touch providers, the native vendor display requests ALLPON for 0.8 seconds, returns to normal, shows red for 1.2 seconds using fillScreen, then green for 1.2 seconds using the same row API as Home. Report which colors appear and whether Home appears afterward.

SPI acquire/start/end return codes now use ESP_ERROR_CHECK; a failure logs and aborts rather than reporting a successful invisible frame. PANEL_PAD records GPIO output latch, enable, mux, matrix, RTC-pad and global hold registers at vendor startup, Home brightness calls and first Home row. PANEL_BRIGHTNESS reports actual values. Transaction fields, reset sequence and PMIC policy are unchanged.

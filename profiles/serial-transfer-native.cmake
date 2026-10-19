# Selected Waveshare dedicated serial transfer factory profile.
include("${CMAKE_CURRENT_LIST_DIR}/provisioning-native.cmake")
list(APPEND RISC_NATIVE_DEFINITIONS RISC_NATIVE_SERIAL_TRANSFER_MODE=1)

# Qualification-only derivative. Keep Wave's external volume and all released features.
include("${CMAKE_CURRENT_LIST_DIR}/shared-home-capacity.cmake")
list(APPEND RISC_NATIVE_DEFINITIONS
    RISC_NATIVE_SETTINGS_LOCAL_ONLY=0
    RISC_NATIVE_SETTINGS_LOCAL_FRESH=0)

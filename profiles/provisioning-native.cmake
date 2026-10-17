# New factory-only provisioning composition over retained0.1.55 native policy.
include("${CMAKE_CURRENT_LIST_DIR}/native-idf61.cmake")
list(APPEND RISC_NATIVE_DEFINITIONS
    RISC_NATIVE_PACKAGE_VOLUME=1
    RISC_NATIVE_PROVISION_REQUEST=1
    RISC_PLATFORM_CAPACITY=32)

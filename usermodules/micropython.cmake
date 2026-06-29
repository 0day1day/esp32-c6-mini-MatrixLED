# User C module registration for the ESP32 MicroPython firmware build.
# Passed via: make ... USER_C_MODULES=/work/usermodules/micropython.cmake
#
# Links the deauth_sniffer module into the `usermod` target. esp_wifi APIs are
# resolved at link time from the IDF components already pulled in by the port.

target_sources(usermod INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/deauth_sniffer.c
)

target_include_directories(usermod INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

# Make esp_wifi component symbols available to the user module.
idf_component_get_property(wifi_lib esp_wifi COMPONENT_LIB)
target_link_libraries(usermod INTERFACE ${wifi_lib})

set(IDF_TARGET esp32c6)

# Same defaults as ESP32_GENERIC_C6 but WITHOUT boards/sdkconfig.ble.
# Bluetooth / NimBLE is not used by this project; omitting it avoids the
# modbluetooth_nimble build incompatibility and shrinks the firmware.
set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.riscv
    boards/sdkconfig.c6
    ${MICROPY_BOARD_DIR}/sdkconfig.board
)

// Matrix LED: generic ESP32-C6 (4MiB+ flash), no Bluetooth.

#define MICROPY_HW_BOARD_NAME               "Matrix LED C6"
#define MICROPY_HW_MCU_NAME                 "ESP32C6"

#define MICROPY_HW_ENABLE_UART_REPL         (1)

// Disable the Bluetooth / NimBLE module entirely (this project does not use
// BLE). Overriding the port default (1) here stops modbluetooth_nimble.c and
// mpnimbleport.c from being compiled, avoiding the NimBLE header dependency.
#define MICROPY_PY_BLUETOOTH                (0)
#define MICROPY_BLUETOOTH_NIMBLE            (0)

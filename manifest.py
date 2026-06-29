# MicroPython frozen manifest for ESP32-C6.
# Used by the CI build to bake the project code into firmware.bin.
# Freezing puts bytecode in flash -> near-zero RAM usage.
#
# Note: the CI generates led_matrix_project/embedded_assets.py (with the CSS)
# before running the build, so the firmware is self-contained.

include("$(PORT_DIR)/boards/ESP32_GENERIC_C6/manifest.py")

# Core modules (frozen as top-level modules)
freeze("led_matrix_project", (
    "main.py",
    "webserver.py",
    "display.py",
    "effects.py",
    "max7219.py",
    "sensor_aht20_bmp280.py",
))

# Embedded resources (CSS) generated at build time
freeze("led_matrix_project", "embedded_assets.py")

# Fonts package
freeze("led_matrix_project", ("fonts/__init__.py", "fonts/default.py"))

# ESP32-C6 Mini · Matrix LED

A **32×8 LED matrix** controller (4× MAX7219) running on an **ESP32-C6** with
MicroPython. Built-in web dashboard, ~15 visual effects, digital/binary clock,
rack monitor (AHT20 + BMP280), **OTA updates**, **captive Wi-Fi portal**,
**one-click web flasher** and a **Wi-Fi deauth attack detector (DEFCON)**.

---

## ✨ Features

- **Effects**: Matrix rain, Game of Life, digital/binary clock, fire, waves, spectrum, stars, plasma, equalizer, maze runner.
- **Text**: scroll, typewriter, hacker (matrix-style reveal).
- **Sprites**: upload JSON animations (Pac-Man, Snake, Heart, Hack the Planet).
- **Rack monitor**: live temperature, humidity and pressure.
- **Display**: brightness, contrast, flip X/Y, invert colors.
- **OTA**: update any `.py` from the browser with auto-backup + syntax validation.
- **Captive Wi-Fi portal**: first-boot setup with network scanning (`MatrixLED-Setup` AP).
- **Web dashboard**: professional control center with live matrix preview and status pills.
- **One-click web flasher**: flash the firmware from the browser via WebSerial (ESP Web Tools).
- **Wi-Fi attack detector**: blinks a DEFCON alert on the matrix when deauth floods are detected.

---

## 🛡️ Wi-Fi Attack Detector (DEFCON)

Detects **deauth / disassociation attacks** (Marauder, Bruce, and similar tools)
using two modes, auto-selected:

| Mode | How it works | Available in |
|------|--------------|--------------|
| **Frames** (native C sniffer) | Count real deauth/disassoc frames in the air via monitor mode — catches attacks on **any** nearby network | Compiled firmware binary |
| **Connection** (fallback) | Detects the *symptom* of a deauth flood — the device's own connection churns | Always (dev / OTA mode) |

The matrix blinks **`DC1` → `DC5`** (lower = more urgent). At DEFCON 1 it
flashes an aggressive warning fill. A few normal background deauths stay at
DEFCON 4–5; a real flood drops to DEFCON 1 in seconds.

> The native frame sniffer (`usermodules/deauth_sniffer.c`) uses the ESP-IDF
> promiscuous callback and only bumps a C counter (never touches the Python VM).
> `wifimon.py` polls it every 2 s and maps the rate to DEFCON levels.

---

## 🧰 Bill of Materials (BOM)

| Qty | Component | Notes |
|-----|-----------|-------|
| 1 | **ESP32-C6** (mini / dev board) | MicroPython v1.27+ |
| 1 | **MAX7219 8×8 LED matrix** (FC-16 module) ×4 cascaded | Form a 32×8 panel |
| 1 | **AHT20 + BMP280** sensor (I2C combo) | Temp / humidity / pressure |
| — | Wire / breadboard / jumpers | Keep I2C leads short (<20 cm) |
| — | 4.7kΩ I2C pull-ups (optional) | If the module lacks them |

> The device works without the sensor — the code detects it and skips the rack monitor.

---

## 🔌 Pinout

### ESP32-C6 → LED Matrix (SPI1)

| ESP32-C6 | Function | MAX7219 module |
|----------|----------|----------------|
| **GPIO 14** | MOSI / DIN | **DIN** |
| **GPIO 15** | SCK / CLK | **CLK** |
| **GPIO 18** | CS / LOAD | **CS** |
| **5V (VIN)** | LED power | **VCC** |
| **GND** | Common ground | **GND** |

### ESP32-C6 → AHT20+BMP280 (I2C0)

| ESP32-C6 | Function | Sensor |
|----------|----------|--------|
| **GPIO 22** | SCL | **SCL** |
| **GPIO 21** | SDA | **SDA** |
| **3.3V** | Power | **VCC** ⚠️ never 5V |
| **GND** | Common ground | **GND** |

> The 4 MAX7219 modules chain (DIN→DOUT). Only the first receives DIN/CLK/CS.

---

## ⚡ Wiring Diagram

```mermaid
flowchart LR
    classDef esp fill:#1c2128,stroke:#22c55e,color:#e6e8ec
    classDef mx fill:#2a1f12,stroke:#f59e0b,color:#ffe7c2
    classDef sens fill:#121f2a,stroke:#38bdf8,color:#cdeeff

    ESP["🖥️ ESP32-C6"]:::esp
    MX["💡 Matrix 32×8<br/>MAX7219 ×4"]:::mx
    SEN["🌡️ AHT20 + BMP280"]:::sens

    ESP -- "GPIO14 → DIN" --> MX
    ESP -- "GPIO15 → CLK" --> MX
    ESP -- "GPIO18 → CS" --> MX
    ESP -- "5V → VCC" --> MX
    ESP -- "GND → GND" --> MX

    ESP -- "GPIO22 → SCL" --> SEN
    ESP -- "GPIO21 → SDA" --> SEN
    ESP -- "3.3V → VCC" --> SEN
    ESP -- "GND → GND" --> SEN
```

---

## 🚀 Getting Started

### Option A — One-click web flasher (easiest)
1. Open the **[web flasher](https://0day1day.github.io/esp32-c6-mini-MatrixLED/)** in Chrome or Edge.
2. Connect the ESP32-C6 via USB and click **Install**.
3. After flashing, join the **`MatrixLED-Setup`** Wi-Fi and open **192.168.4.1**.
4. Pick your network, enter your password → the device reboots and joins it.
5. Open the IP shown on the serial console (e.g. `http://192.168.0.137`).

> Requires a Chromium browser with WebSerial. The firmware is served from the
> [latest release](https://github.com/0day1day/esp32-c6-mini-MatrixLED/releases/latest).

### Option B — Manual upload (development)
1. Flash MicroPython on the ESP32-C6 ([esptool-js](https://espressif.github.io/esptool-js/) or `esptool.py`).
2. Install tools and upload:
   ```bash
   pip install -r requirements.txt
   ./upload.sh                       # auto-detects the serial port
   ```
3. Configure Wi-Fi:
   ```bash
   cp led_matrix_project/config.example.txt led_matrix_project/config.txt
   # edit config.txt with your SSID / PASSWORD
   ./upload.sh
   ```
   Without `config.txt`, the device boots into the `MatrixLED-Setup` AP portal.

---

## 🌐 Captive Wi-Fi Portal

On first boot (or whenever the configured network is unavailable) the device
starts an open Access Point named **`MatrixLED-Setup`**:

1. Connect to `MatrixLED-Setup`.
2. Browse to **192.168.4.1** (most phones auto-prompt the captive portal).
3. Scan networks → pick yours → enter the password (optionally set a UI password).
4. **Save & reboot** — the credentials are written to `config.txt` and the device joins your network.

---

## 🔁 OTA Updates

From the web dashboard → **OTA Updates** card:
1. Select a `.py` file → **Upload Python**.
2. The file is **syntax-validated** before writing (rejected code never overwrites the original).
3. An **automatic backup** is created (`backups/file.py.bak_DATE`).
4. Click **Restart device** to apply (settings in `settings.json` are preserved across reboots).

Security: syntax validation, 500 KB limit, path-traversal protection, max 5 backups per file.

---

## 🏗️ Firmware Build (CI/CD)

A GitHub Actions workflow (`.github/workflows/firmware.yml`) builds a complete
firmware binary with all code **frozen** (zero-RAM bytecode) plus the native
**deauth sniffer** C module:

- **On every push**: `py_compile` + `ruff` syntax check of all modules.
- **On version tags** (`v3.x`): builds `firmware.bin` for `ESP32_GENERIC_C6`
  (frozen modules + `deauth_sniffer.c`), then publishes a **GitHub Release**.

```bash
git tag v3.1
git push origin v3.1      # → CI builds firmware.bin and creates the release
```

The frozen build bakes `static/style.css` into an `embedded_assets` module so
the firmware is fully self-contained.

---

## 🔧 Configuration (`config.txt`)

```ini
SSID=your_wifi
PASSWORD=your_password
WEB_PASSWORD=             # optional: protects the dashboard (HTTP Basic Auth)
```

If absent, the device launches the captive setup portal instead.

---

## 🩺 Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Sensor returns `null` | I2C failure (`ENODEV`) | Power the sensor at **3.3V** (not 5V), add 4.7kΩ pull-ups, keep cables short (I2C already runs at 50 kHz) |
| No IP / unreachable | Wi-Fi not configured | Connect to `MatrixLED-Setup` AP and reconfigure at 192.168.4.1 |
| DEFCON stays at 5 | C sniffer not present | Frame-level detection only works in the compiled firmware binary; dev mode uses the connection fallback |
| Device won't boot after OTA | Bad uploaded code | Restore a backup via REPL: `mpremote cp backups/file.py.bak_DATE :/file.py` |

I2C scan for diagnostics (REPL):
```python
from machine import I2C, Pin
print(I2C(0, scl=Pin(22), sda=Pin(21)).scan())  # [56, 118] = [0x38, 0x76]
```

---

## 📁 Project Structure

```
├── led_matrix_project/
│   ├── main.py                  # Boot: Wi-Fi, HTTP routes, effect loop, DEFCON guard
│   ├── webserver.py             # HTTP server + dashboard UI + setup portal
│   ├── display.py              # Matrix wrapper (flip / invert / contrast)
│   ├── max7219.py              # MAX7219 low-level driver (mcauser)
│   ├── effects.py              # All visual effects + DefconEffect
│   ├── wifimon.py              # DEFCON detector (frames or connection fallback)
│   ├── sensor_aht20_bmp280.py  # AHT20 + BMP280 I2C driver
│   ├── config.txt              # SSID / PASSWORD (gitignored)
│   ├── config.example.txt      # Config template
│   ├── settings.json           # Persistent state (auto-generated)
│   ├── fonts/                  # Bitmap fonts
│   ├── drawings/               # Example sprite JSON
│   ├── static/style.css        # Dashboard styles
│   └── backups/                # OTA backups (auto-generated)
├── usermodules/
│   ├── deauth_sniffer.c        # Native C Wi-Fi deauth frame counter
│   └── micropython.cmake       # Registers the C module in the firmware build
├── manifest.py                 # MicroPython frozen-manifest for the CI build
├── docs/
│   ├── index.html              # ESP Web Tools one-click flasher page
│   └── manifest.json           # Flash manifest (points to release firmware.bin)
├── .github/workflows/
│   └── firmware.yml            # CI: lint + frozen firmware build + release
├── upload.sh                   # Auto-detecting serial upload script
├── requirements.txt
└── README.md
```

---

## ❤️ Credits & License

- MAX7219 driver: [mcauser/micropython-max7219](https://github.com/mcauser/micropython-max7219) (MIT)
- Web flasher: [ESP Web Tools](https://esphome.github.io/esp-web-tools/)
- 0x7EA · idiotsandwich.club · v3.0

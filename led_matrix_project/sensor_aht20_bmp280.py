"""
AHT20 + BMP280 Sensor Module Driver
Temperature, Humidity, and Pressure Sensor
I2C Communication
"""
from machine import I2C, Pin

# Sensor addresses
AHT20_ADDR = 0x38
BMP280_ADDR = 0x76  # Can also be 0x77

class AHT20_BMP280:
    def __init__(self, i2c=None, scl=22, sda=21):
        """
        Initialize sensor module.
        Default pins: SCL=22, SDA=21 (common ESP32 I2C pins)
        """
        if i2c is None:
            # Reduced frequency for better stability with combined module
            self.i2c = I2C(0, scl=Pin(scl), sda=Pin(sda), freq=50000)  # 50kHz instead of 100kHz
        else:
            self.i2c = i2c
        
        self.aht20_initialized = False
        self.bmp280_initialized = False
        self.bmp280_addr = BMP280_ADDR  # Use instance variable instead of global
        self.aht20_error_count = 0  # Track consecutive errors
        self.aht20_max_errors = 3  # Max errors before disabling
        
        self._init_aht20()
        self._init_bmp280()
    
    def _init_aht20(self):
        """Initialize AHT20 temperature and humidity sensor."""
        try:
            # Check if sensor is present
            devices = self.i2c.scan()
            print(f"I2C devices found: {[hex(d) for d in devices]}")
            if AHT20_ADDR not in devices:
                print(f"AHT20 not found at 0x{AHT20_ADDR:02X}")
                return False
            
            import time
            # Soft reset
            self.i2c.writeto(AHT20_ADDR, bytes([0xBA]))
            time.sleep_ms(50)  # Increased delay after reset
            
            # Initialize
            self.i2c.writeto(AHT20_ADDR, bytes([0xBE, 0x08, 0x00]))
            time.sleep_ms(50)  # Increased delay
            
            # Check calibration status
            time.sleep_ms(10)
            data = bytearray(1)
            self.i2c.readfrom_into(AHT20_ADDR, data)
            if data[0] & 0x08 == 0:
                # Not calibrated, trigger calibration
                self.i2c.writeto(AHT20_ADDR, bytes([0xBE, 0x08, 0x00]))
                time.sleep_ms(200)  # Increased wait for calibration to complete
            
            self.aht20_initialized = True
            self.aht20_error_count = 0  # Reset error count on successful init
            print("AHT20 initialized")
            time.sleep_ms(200)  # Increased wait after initialization before first read
            return True
        except OSError as e:
            if e.args[0] == 19:  # ENODEV
                print(f"AHT20 init error (ENODEV) - check I2C connections")
            else:
                print(f"AHT20 init error: {e}")
            return False
        except Exception as e:
            print(f"AHT20 init error: {e}")
            return False
    
    def _init_bmp280(self):
        """Initialize BMP280 pressure sensor."""
        try:
            # Check if sensor is present
            devices = self.i2c.scan()
            print(f"I2C devices found: {[hex(d) for d in devices]}")
            if self.bmp280_addr not in devices:
                # Try alternative address
                if 0x77 in devices:
                    self.bmp280_addr = 0x77
                    print(f"BMP280 found at 0x{self.bmp280_addr:02X}")
                else:
                    print(f"BMP280 not found at 0x{self.bmp280_addr:02X} or 0x77")
                    return False
            else:
                print(f"BMP280 found at 0x{self.bmp280_addr:02X}")
            
            # Read calibration data
            import time
            time.sleep_ms(100)  # Wait before reading calibration
            if not self._read_bmp280_calibration():
                print("BMP280 calibration read failed")
                return False
            
            # Configure sensor (normal mode, 16x oversampling)
            # ctrl_meas: temp_x2, press_x16, normal mode
            time.sleep_ms(100)  # Increased wait before configuring
            try:
                self.i2c.writeto_mem(self.bmp280_addr, 0xF4, bytes([0b01010111]))
                time.sleep_ms(100)
                # config: standby 250ms, filter off
                self.i2c.writeto_mem(self.bmp280_addr, 0xF5, bytes([0b00000000]))
                time.sleep_ms(300)  # Increased wait for sensor to stabilize
            except OSError as e:
                if e.args[0] == 19:  # ENODEV
                    print(f"BMP280 config error (ENODEV)")
                    return False
                raise
            
            self.bmp280_initialized = True
            print("BMP280 initialized")
            return True
        except OSError as e:
            if e.args[0] == 19:  # ENODEV
                print(f"BMP280 init error (ENODEV) - check I2C connections")
            else:
                print(f"BMP280 init error: {e}")
            return False
        except Exception as e:
            print(f"BMP280 init error: {e}")
            return False
    
    def _read_bmp280_calibration(self):
        """Read BMP280 calibration data."""
        try:
            import time
            time.sleep_ms(50)  # Increased delay before reading
            cal = bytearray(24)
            # Try reading calibration data with retry
            try:
                self.i2c.readfrom_mem_into(self.bmp280_addr, 0x88, cal)
            except OSError as e:
                if e.args[0] == 19:  # ENODEV
                    time.sleep_ms(100)  # Wait and retry once
                    self.i2c.readfrom_mem_into(self.bmp280_addr, 0x88, cal)
                else:
                    raise
            
            # Parse calibration (signed 16-bit values)
            self.dig_T1 = cal[0] | (cal[1] << 8)
            self.dig_T2 = self._s16(cal[2] | (cal[3] << 8))
            self.dig_T3 = self._s16(cal[4] | (cal[5] << 8))
            
            self.dig_P1 = cal[6] | (cal[7] << 8)
            self.dig_P2 = self._s16(cal[8] | (cal[9] << 8))
            self.dig_P3 = self._s16(cal[10] | (cal[11] << 8))
            self.dig_P4 = self._s16(cal[12] | (cal[13] << 8))
            self.dig_P5 = self._s16(cal[14] | (cal[15] << 8))
            self.dig_P6 = self._s16(cal[16] | (cal[17] << 8))
            self.dig_P7 = self._s16(cal[18] | (cal[19] << 8))
            self.dig_P8 = self._s16(cal[20] | (cal[21] << 8))
            self.dig_P9 = self._s16(cal[22] | (cal[23] << 8))
            
            return True
        except OSError as e:
            if e.args[0] == 19:  # ENODEV
                print(f"BMP280 calibration read error (ENODEV) - check I2C connections")
            else:
                print(f"BMP280 calibration read error: {e}")
            return False
        except Exception as e:
            print(f"BMP280 calibration read error: {e}")
            return False
    
    def _s16(self, value):
        """Convert unsigned 16-bit to signed."""
        return value if value < 32768 else value - 65536
    
    def read_aht20(self):
        """Read temperature and humidity from AHT20."""
        if not self.aht20_initialized:
            return None, None
        
        # If too many consecutive errors, skip reading
        if self.aht20_error_count >= self.aht20_max_errors:
            return None, None
        
        try:
            import time
            # Small delay before triggering
            time.sleep_ms(10)
            # Trigger measurement
            self.i2c.writeto(AHT20_ADDR, bytes([0xAC, 0x33, 0x00]))
            time.sleep_ms(150)  # Increased wait time for measurement
            
            # Read 6 bytes
            data = bytearray(6)
            self.i2c.readfrom_into(AHT20_ADDR, data)
            
            # Check status
            if data[0] & 0x80:
                # Still busy, wait a bit more
                time.sleep_ms(50)
                self.i2c.readfrom_into(AHT20_ADDR, data)
                if data[0] & 0x80:
                    self.aht20_error_count += 1
                    return None, None  # Still busy after retry
            
            # Parse humidity (20 bits)
            humidity_raw = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4))
            humidity = (humidity_raw * 100.0) / (2**20)
            
            # Parse temperature (20 bits)
            temp_raw = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5])
            temperature = (temp_raw * 200.0) / (2**20) - 50.0
            
            # Validate readings
            if humidity < 0 or humidity > 100 or temperature < -40 or temperature > 85:
                self.aht20_error_count += 1
                return None, None
            
            # Success - reset error count
            self.aht20_error_count = 0
            return temperature, humidity
        except OSError as e:
            # ENODEV error - device not responding
            if e.args[0] == 19:  # ENODEV
                self.aht20_error_count += 1
                # Only disable after max errors reached
                if self.aht20_error_count == 1:
                    print(f"AHT20 read error (ENODEV)")
                elif self.aht20_error_count >= self.aht20_max_errors:
                    if self.aht20_error_count == self.aht20_max_errors:
                        print(f"AHT20 disabled after {self.aht20_max_errors} consecutive errors")
                    self.aht20_initialized = False
                return None, None
            self.aht20_error_count += 1
            return None, None
        except Exception as e:
            self.aht20_error_count += 1
            return None, None
    
    def read_bmp280(self):
        """Read temperature and pressure from BMP280."""
        if not self.bmp280_initialized:
            return None, None
        
        try:
            import time
            # Small delay before reading
            time.sleep_ms(10)
            # Read pressure and temperature
            data = bytearray(6)
            self.i2c.readfrom_mem_into(self.bmp280_addr, 0xF7, data)
            
            press_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
            temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
            
            # Compensate temperature
            var1 = (((temp_raw >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
            var2 = (((((temp_raw >> 4) - self.dig_T1) * ((temp_raw >> 4) - self.dig_T1)) >> 12) * self.dig_T3) >> 14
            t_fine = var1 + var2
            temperature = ((t_fine * 5 + 128) >> 8) / 100.0
            
            # Compensate pressure
            var1 = (t_fine >> 1) - 64000
            var2 = (((var1 >> 2) * (var1 >> 2)) >> 11) * self.dig_P6
            var2 = var2 + ((var1 * self.dig_P5) << 1)
            var2 = (var2 >> 2) + (self.dig_P4 << 16)
            var1 = (((self.dig_P3 * ((var1 >> 2) * (var1 >> 2)) >> 13) >> 3) + ((self.dig_P2 * var1) >> 1)) >> 18
            var1 = ((32768 + var1) * self.dig_P1) >> 15
            
            if var1 == 0:
                return None, None
            
            pressure = 1048576 - press_raw
            pressure = ((pressure - (var2 >> 12)) * 3125)
            if pressure < 0x80000000:
                pressure = (pressure << 1) // var1
            else:
                pressure = (pressure // var1) * 2
            
            var1 = (self.dig_P9 * (((pressure >> 3) * (pressure >> 3)) >> 13)) >> 12
            var2 = ((pressure >> 2) * self.dig_P8) >> 13
            pressure = pressure + ((var1 + var2 + self.dig_P7) >> 4)
            pressure = pressure / 100.0  # Convert to hPa
            
            return temperature, pressure
        except OSError as e:
            # ENODEV error - device not responding
            if e.args[0] == 19:  # ENODEV
                # Don't print every time to avoid spam
                return None, None
            return None, None
        except Exception as e:
            return None, None
    
    def read_all(self):
        """Read all sensor data."""
        temp_aht, hum = self.read_aht20()
        temp_bmp, press = self.read_bmp280()
        
        # Use AHT20 temperature if available, otherwise BMP280
        temperature = temp_aht if temp_aht is not None else temp_bmp
        
        # If AHT20 was disabled due to errors, try to reinitialize once
        if not self.aht20_initialized and self.aht20_error_count >= self.aht20_max_errors:
            # Reset error count after some time to allow retry
            # This happens naturally when sensor instance is recreated
            pass
        
        return {
            'temperature': temperature,
            'humidity': hum,
            'pressure': press,
            'temp_aht20': temp_aht,
            'temp_bmp280': temp_bmp
        }

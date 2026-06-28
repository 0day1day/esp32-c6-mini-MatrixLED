from machine import SPI, Pin
from max7219 import Matrix8x8

class Display:
    """
    Wrapper around mcauser/micropython-max7219 library.
    Maintains backwards compatibility with existing effects.
    """
    def __init__(self, mosi=14, clk=15, cs=18, matrices=4):
        self.WIDTH = matrices * 8
        self.HEIGHT = 8
        self.NUM_MATRICES = matrices
        
        # Initialize SPI and MAX7219
        # Reduced baudrate from 10MHz to 5MHz to minimize electrical noise
        spi = SPI(1, baudrate=5_000_000, polarity=0, phase=0,
                  sck=Pin(clk), mosi=Pin(mosi))
        self._cs = Pin(cs, Pin.OUT)
        self._matrix = Matrix8x8(spi, self._cs, matrices)
        self._brightness = 4  # Default brightness (0-15), reduced from 2 to avoid electrical noise
        self._flip_x = False
        self._flip_y = False
        self._contrast = 1.0  # Contrast multiplier (0.0-2.0)
        self._invert_colors = False  # Invert colors: background green, content black
        self._matrix.brightness(self._brightness)
    
    def clear(self):
        """Clear the display buffer."""
        if self._invert_colors:
            # In invert mode, fill with all pixels ON (green background)
            self._matrix.fill(1)
        else:
            # Normal mode, fill with all pixels OFF (black background)
            self._matrix.fill(0)
    
    def set_pixel(self, x, y, val=1):
        """Set a pixel with optional flip, contrast, and color inversion."""
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            # Apply flip
            final_x = self.WIDTH - 1 - x if self._flip_x else x
            final_y = self.HEIGHT - 1 - y if self._flip_y else y
            
            # Apply contrast (for future use with grayscale)
            final_val = int(val * self._contrast) if val > 0 else 0
            final_val = min(1, final_val)  # Binary display, so max is 1
            
            # Apply color inversion: if invert mode, flip the value
            if self._invert_colors:
                final_val = 1 - final_val  # 1 becomes 0 (black), 0 becomes 1 (green)
            
            self._matrix.pixel(final_x, final_y, final_val)
    
    def draw_sprite(self, sprite_data, x_offset, y_offset, flip_x=False, flip_y=False):
        """Draw a sprite with optional flipping."""
        sprite_height = len(sprite_data)
        sprite_width = len(sprite_data[0]) if sprite_height > 0 else 0
        
        for y, row in enumerate(sprite_data):
            for x, pixel in enumerate(row):
                if pixel:
                    draw_x = sprite_width - 1 - x if flip_x else x
                    draw_y = sprite_height - 1 - y if flip_y else y
                    final_x = x_offset + draw_x
                    final_y = y_offset + draw_y
                    if 0 <= final_x < self.WIDTH and 0 <= final_y < self.HEIGHT:
                        self.set_pixel(final_x, final_y)
    
    def render(self):
        """Send buffer to display."""
        self._matrix.show()
    
    # === Graphics primitives ===
    # These respect flip/invert/contrast consistently (routed through set_pixel).

    def line(self, x1, y1, x2, y2, col=1):
        """Draw a line (Bresenham)."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        x, y = x1, y1
        while True:
            self.set_pixel(x, y, col)
            if x == x2 and y == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def rect(self, x, y, w, h, col=1):
        """Draw a rectangle outline."""
        if w <= 0 or h <= 0:
            return
        self.hline(x, y, w, col)
        self.hline(x, y + h - 1, w, col)
        self.vline(x, y, h, col)
        self.vline(x + w - 1, y, h, col)

    def fill_rect(self, x, y, w, h, col=1):
        """Draw a filled rectangle."""
        for ry in range(y, y + h):
            self.hline(x, ry, w, col)

    def hline(self, x, y, w, col=1):
        """Draw horizontal line."""
        for px in range(x, x + w):
            self.set_pixel(px, y, col)

    def vline(self, x, y, h, col=1):
        """Draw vertical line."""
        for py in range(y, y + h):
            self.set_pixel(x, py, col)
    
    def brightness(self, value):
        """Set display brightness (0-15).
        Automatically limits brightness when invert_colors is active to prevent electrical noise."""
        value = max(0, min(15, int(value)))
        self._brightness = value
        
        # If invert mode is active, limit brightness to prevent electrical noise
        # (all LEDs ON consumes much more current)
        if self._invert_colors:
            # Store original brightness for restoration later
            if not hasattr(self, '_original_brightness'):
                self._original_brightness = value
            # Limit to safe level when inverted (max 2 out of 15)
            safe_brightness = min(2, value)
            self._matrix.brightness(safe_brightness)
        else:
            self._matrix.brightness(value)
    
    def set_flip(self, flip_x=False, flip_y=False):
        """Set display flip modes."""
        self._flip_x = flip_x
        self._flip_y = flip_y
    
    def set_contrast(self, contrast):
        """Set contrast multiplier (0.0-2.0)."""
        self._contrast = max(0.0, min(2.0, float(contrast)))
    
    def set_invert_colors(self, invert):
        """Set color inversion mode (background green, content black).
        Automatically reduces brightness when active to prevent electrical noise."""
        invert = bool(invert)
        was_inverted = self._invert_colors
        self._invert_colors = invert
        
        # When enabling invert mode, reduce brightness to prevent electrical noise
        # (all LEDs ON consumes much more current)
        if invert and not was_inverted:
            # Store original brightness and reduce to safer level
            if not hasattr(self, '_original_brightness'):
                self._original_brightness = self._brightness
            # Reduce brightness to 2 (from 0-15 scale) when inverted
            self._brightness = min(2, self._brightness)
            self._matrix.brightness(self._brightness)
        elif not invert and was_inverted:
            # Restore original brightness when disabling invert
            if hasattr(self, '_original_brightness'):
                self._brightness = self._original_brightness
                delattr(self, '_original_brightness')
            self._matrix.brightness(self._brightness)
    
    def reset_display_settings(self):
        """Reset all display settings to defaults."""
        self._brightness = 4
        self._flip_x = False
        self._flip_y = False
        self._contrast = 1.0
        self._invert_colors = False
        # Clear stored original brightness if it exists
        if hasattr(self, '_original_brightness'):
            delattr(self, '_original_brightness')
        self._matrix.brightness(self._brightness)
    
    def get_brightness(self):
        """Get current brightness."""
        return self._brightness
    
    def get_flip(self):
        """Get current flip settings."""
        return (self._flip_x, self._flip_y)
    
    def get_contrast(self):
        """Get current contrast."""
        return self._contrast
    
    def get_invert_colors(self):
        """Get current invert colors setting."""
        return self._invert_colors
    
    def get_buffer(self):
        """Get current display buffer as 2D array - reads buffer exactly as displayed physically."""
        buffer = self._matrix.buffer
        pixels = []
        # Buffer format: MONO_HLSB - 8 rows * NUM_MATRICES bytes
        # Each byte represents 8 horizontal pixels
        # MONO_HLSB: Horizontal, LSB first (leftmost pixel is LSB/bit 0)
        # Buffer layout: [row0_matrix0, row0_matrix1, ..., row0_matrixN, row1_matrix0, ...]
        # The buffer already has flip/invert transformations applied from set_pixel
        # Read buffer directly to match physical display
        for y in range(self.HEIGHT):
            row = []
            for x in range(self.WIDTH):
                # Calculate which matrix (0 to NUM_MATRICES-1)
                matrix_idx = x // 8
                # Bit position within byte: x % 8
                # MONO_HLSB: bit 0 (LSB) is leftmost pixel in byte
                bit_pos = x % 8
                # Byte index: row * NUM_MATRICES + matrix_index
                byte_idx = y * self.NUM_MATRICES + matrix_idx
                if byte_idx < len(buffer):
                    # Read bit: In MONO_HLSB, LSB (bit 0) should be leftmost
                    # But MAX7219 may interpret bits differently, try MSB first
                    # Try reading MSB first (bit 7) for leftmost pixel
                    pixel_val = (buffer[byte_idx] >> (7 - bit_pos)) & 1
                    row.append(pixel_val)
                else:
                    row.append(0)
            pixels.append(row)
        return pixels
    
    def fill(self, col=0):
        """Fill entire display."""
        self._matrix.fill(col)

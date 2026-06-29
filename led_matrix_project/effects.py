import random
import json
import time

_PI = 3.14159


def _fast_sin(x, pi=_PI):
    """Bhaskara sine approximation - shared by wave/plasma effects."""
    x = x % (2 * pi)
    if x < pi:
        return 4 * x * (pi - x) / (pi * pi)
    x = x - pi
    return -4 * x * (pi - x) / (pi * pi)


def _parse_manual_datetime(dt_str):
    """Parse 'YYYY-MM-DDTHH:MM[:SS]' into a time.localtime-style tuple.
    Returns None on failure. Indices [3]=hours, [4]=minutes, [5]=seconds."""
    try:
        parts = dt_str.split('T')
        if len(parts) != 2:
            return None
        dp = parts[0].split('-')
        tp = parts[1].split(':')
        year = int(dp[0])
        month = int(dp[1])
        day = int(dp[2])
        hour = int(tp[0])
        minute = int(tp[1]) if len(tp) > 1 else 0
        second = int(tp[2]) if len(tp) > 2 else 0
        try:
            base = time.mktime((year, month, day, hour, minute, second, 0, 0))
            return time.localtime(base)
        except Exception:
            return (year, month, day, hour, minute, second, 0, 0)
    except Exception:
        return None


def _current_localtime(tz_offset, manual_dt=None):
    """Resolve the current localtime tuple (hours at index 3)."""
    if manual_dt:
        lt = _parse_manual_datetime(manual_dt)
        if lt is not None:
            return lt
    return time.localtime(time.time() + int(tz_offset * 3600))


class Effect:
    def __init__(self, display):
        self.display = display
        self.frame = 0
        self.speed = 1.0
        self._speed_accum = 0.0

    def set_speed(self, speed):
        self.speed = max(0.1, float(speed))

    def should_update(self):
        self._speed_accum += self.speed
        updates = 0
        while self._speed_accum >= 1.0:
            self._speed_accum -= 1.0
            updates += 1
        return updates > 0

    def update(self):
        raise NotImplementedError

    def render(self):
        self.display.render()


class MatrixRain(Effect):
    def __init__(self, display):
        super().__init__(display)
        self.columns = []
        self.chars = [
            [1, 0, 1, 0, 1, 0, 1, 0],
            [1, 1, 0, 0, 1, 1, 0, 0],
            [1, 0, 0, 1, 0, 0, 1, 0],
            [0, 1, 0, 1, 0, 1, 0, 1],
        ]
        for x in range(display.WIDTH):
            self.columns.append({
                'y': random.randint(-30, -5),
                'speed': random.uniform(0.8, 2.5),
                'length': random.randint(5, 12),
                'active': random.random() < 0.25,
                'char_idx': random.randint(0, len(self.chars) - 1),
                'head_y': 0
            })

    def update(self):
        if not self.should_update():
            return

        self.display.clear()
        for x, col in enumerate(self.columns):
            if not col['active']:
                if random.random() < (0.015 + 0.01 * self.speed):
                    col['active'] = True
                    col['y'] = -random.randint(8, 25)
                    col['speed'] = random.uniform(0.8, 2.2) * self.speed
                    col['length'] = random.randint(6, 14)
                    col['char_idx'] = random.randint(0, len(self.chars) - 1)
                continue

            col['y'] += col['speed']
            col['head_y'] = int(col['y'])

            for i in range(col['length']):
                y = int(col['y'] - i)
                if 0 <= y < self.display.HEIGHT:
                    brightness = max(0, 1.0 - (i / col['length']) * 0.7)
                    if i == 0:
                        self.display.set_pixel(x, y)
                    elif i < col['length'] - 1:
                        char_pattern = self.chars[col['char_idx']]
                        if char_pattern[i % len(char_pattern)] and brightness > 0.3:
                            self.display.set_pixel(x, y)
                    else:
                        if random.random() < brightness:
                            self.display.set_pixel(x, y)

            if col['y'] > self.display.HEIGHT + col['length']:
                col['y'] = -random.randint(10, 30)
                col['speed'] = random.uniform(0.8, 2.2) * self.speed
                col['length'] = random.randint(6, 14)
                col['char_idx'] = random.randint(0, len(self.chars) - 1)
                if random.random() < 0.4:
                    col['active'] = False


class GameOfLife(Effect):
    def __init__(self, display):
        super().__init__(display)
        # Double-buffered grids to avoid per-frame allocation
        w, h = display.WIDTH, display.HEIGHT
        self._buf_a = [[random.choice([0, 1]) for _ in range(h)] for _ in range(w)]
        self._buf_b = [[0] * h for _ in range(w)]
        self.grid = self._buf_a
        self._stagnant = 0

    def update(self):
        if not self.should_update():
            return

        w = self.display.WIDTH
        h = self.display.HEIGHT
        grid = self.grid
        new = self._buf_b
        changed = False

        for x in range(w):
            gx = grid[x]
            nx_l = grid[(x - 1) % w]
            nx_r = grid[(x + 1) % w]
            new_row = new[x]
            for y in range(h):
                y_u = (y - 1) % h
                y_d = (y + 1) % h
                neighbors = (nx_l[y_u] + nx_l[y] + nx_l[y_d] +
                             gx[y_u] + gx[y_d] +
                             nx_r[y_u] + nx_r[y] + nx_r[y_d])
                alive = gx[y]
                if alive:
                    new_row[y] = 1 if neighbors in (2, 3) else 0
                else:
                    new_row[y] = 1 if neighbors == 3 else 0
                if new_row[y] != alive:
                    changed = True

        # Swap buffers
        self.grid = new
        self._buf_a, self._buf_b = self._buf_b, self._buf_a

        self.display.clear()
        for x in range(w):
            grid_x = self.grid[x]
            for y in range(h):
                if grid_x[y]:
                    self.display.set_pixel(x, y)

        # Re-seed if the board stagnates
        if not changed:
            self._stagnant += 1
            if self._stagnant > 20:
                self._reseed()
        else:
            self._stagnant = 0

    def _reseed(self):
        w, h = self.display.WIDTH, self.display.HEIGHT
        for x in range(w):
            for y in range(h):
                self.grid[x][y] = random.choice([0, 1])
        self._stagnant = 0


class Marquee(Effect):
    def __init__(self, display, text, font, mode='scroll'):
        super().__init__(display)
        self.text = text
        self.font = font
        self.offset = display.WIDTH
        self.mode = mode
        self.typewriter_pos = 0
        self.typewriter_delay = 0
        self.hacker_chars = []
        self.hacker_frame = 0

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        if self.mode == 'typewriter':
            self._update_typewriter()
        elif self.mode == 'hacker':
            self._update_hacker()
        else:
            self._update_scroll()

    def _update_scroll(self):
        x = int(self.offset)
        for char in self.text:
            if char in self.font:
                for col_byte in self.font[char]:
                    if 0 <= x < self.display.WIDTH:
                        for y in range(8):
                            if col_byte & (1 << y):
                                self.display.set_pixel(x, y)
                    x += 1
                x += 1

        self.offset -= 1 * self.speed
        if self.offset < -len(self.text) * 6:
            self.offset = self.display.WIDTH

    def _update_typewriter(self):
        if not hasattr(self, 'typewriter_scroll'):
            self.typewriter_scroll = 0

        self.typewriter_delay += 1
        if self.typewriter_delay >= max(2, int(8 / self.speed)):
            self.typewriter_delay = 0
            if self.typewriter_pos < len(self.text):
                self.typewriter_pos += 1

        written_width = 1
        for char in self.text[:self.typewriter_pos]:
            if char in self.font:
                written_width += len(self.font[char]) + 1

        cursor_x = written_width

        if cursor_x >= self.display.WIDTH - 2:
            self.typewriter_scroll = cursor_x - (self.display.WIDTH - 3)
        elif self.typewriter_scroll > 0 and cursor_x < self.display.WIDTH - 5:
            self.typewriter_scroll = max(0, self.typewriter_scroll - 0.3 * self.speed)

        x = 1 - int(self.typewriter_scroll)
        for char in self.text[:self.typewriter_pos]:
            if char in self.font:
                for col_byte in self.font[char]:
                    if 0 <= x < self.display.WIDTH:
                        for y in range(8):
                            if col_byte & (1 << y):
                                self.display.set_pixel(x, y)
                    x += 1
                x += 1

        cursor_display_x = cursor_x - int(self.typewriter_scroll)
        if self.typewriter_pos < len(self.text) and (self.typewriter_delay // 4) % 2 == 0:
            if 0 <= cursor_display_x < self.display.WIDTH:
                for cy in range(7):
                    self.display.set_pixel(cursor_display_x, cy)

        if self.typewriter_pos >= len(self.text):
            self.typewriter_delay += 1
            if self.typewriter_delay > 100:
                self.typewriter_pos = 0
                self.typewriter_delay = 0
                self.typewriter_scroll = 0

    def _update_hacker(self):
        self.hacker_frame += 1

        if not hasattr(self, 'hacker_phase') or not hasattr(self, 'hacker_text_len') or self.hacker_text_len != len(self.text):
            self.hacker_text_len = len(self.text)
            self.revealed = [False] * self.hacker_text_len
            self.reveal_idx = 0
            self.hacker_chars = list('0' * self.hacker_text_len)
            self.hacker_scroll = self.display.WIDTH
            self.hacker_phase = 0
            self.hacker_text_width = 0
            self.hacker_char_positions = [0]
            for c in self.text:
                char_width = len(self.font.get(c, (0, 0, 0, 0, 0, 0))) + 1
                self.hacker_text_width += char_width
                self.hacker_char_positions.append(self.hacker_text_width)

        if self.hacker_phase == 0:
            self.hacker_scroll -= self.speed
            if self.hacker_scroll <= 0:
                self.hacker_scroll = 0
                self.hacker_phase = 1

        elif self.hacker_phase == 1:
            if self.hacker_frame % 6 == 0 and self.reveal_idx < self.hacker_text_len:
                self.revealed[self.reveal_idx] = True
                self.reveal_idx += 1

                if self.reveal_idx > 0:
                    revealed_end_x = self.hacker_char_positions[self.reveal_idx]
                    revealed_screen_x = revealed_end_x + self.hacker_scroll
                    if revealed_screen_x >= self.display.WIDTH - 1:
                        self.hacker_scroll = (self.display.WIDTH - 2) - revealed_end_x
                        if self.hacker_scroll > 0:
                            self.hacker_scroll = 0

            if self.reveal_idx >= self.hacker_text_len:
                if self.hacker_text_width > self.display.WIDTH:
                    max_scroll = -(self.hacker_text_width - self.display.WIDTH + 5)
                    if self.hacker_scroll > max_scroll:
                        self.hacker_phase = 2
                    else:
                        self.hacker_phase = 3
                else:
                    self.hacker_phase = 3
                self.hacker_frame = 0

        elif self.hacker_phase == 2:
            max_scroll = -(self.hacker_text_width - self.display.WIDTH + 5)
            self.hacker_scroll -= 0.5 * self.speed
            if self.hacker_scroll <= max_scroll:
                self.hacker_scroll = max_scroll
                self.hacker_phase = 3
                self.hacker_frame = 0

        elif self.hacker_phase == 3:
            if self.hacker_frame > 80:
                for i in range(self.hacker_text_len):
                    self.revealed[i] = False
                self.reveal_idx = 0
                self.hacker_frame = 0
                self.hacker_scroll = self.display.WIDTH
                self.hacker_phase = 0

        if self.hacker_frame % 2 == 0:
            glyphs = '0123456789ABCDEF@#$%'
            for i in range(self.hacker_text_len):
                if not self.revealed[i]:
                    self.hacker_chars[i] = glyphs[random.getrandbits(4) % 20]

        x = int(self.hacker_scroll)
        for i in range(self.hacker_text_len):
            char = self.text[i] if self.revealed[i] else self.hacker_chars[i]
            glyph = self.font.get(char)
            if glyph:
                for col_byte in glyph:
                    if 0 <= x < self.display.WIDTH:
                        for y in range(8):
                            if col_byte & (1 << y):
                                self.display.set_pixel(x, y)
                    x += 1
                x += 1


class DigitalClock(Effect):
    def __init__(self, display, font, timezone_offset=0):
        super().__init__(display)
        self.font = font
        self.timezone_offset = timezone_offset
        self.last_second = -1
        self.show_colon = True

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        local_t = _current_localtime(self.timezone_offset, getattr(self, '_manual_datetime', None))
        year = local_t[0]
        month = local_t[1]
        day = local_t[2]
        hours = local_t[3]
        minutes = local_t[4]
        seconds = local_t[5]

        show_date = (seconds % 10) < 3

        if show_date:
            if seconds % 3 == 2:
                display_str = "{:04d}".format(year)
            else:
                display_str = "{:02d}.{:02d}".format(day, month)
        else:
            display_str = "{:02d}:{:02d}".format(hours, minutes)
            self.show_colon = seconds % 2 == 0

        char_width = 5
        if show_date and seconds % 3 != 2:
            total_width = 4 * char_width + 1
        elif show_date:
            total_width = 4 * char_width
        else:
            total_width = 4 * char_width + 1

        x = max(0, (self.display.WIDTH - total_width) // 2)

        for char in display_str:
            if char == ':':
                if self.show_colon:
                    self.display.set_pixel(x, 2)
                    self.display.set_pixel(x, 5)
                x += 1
            elif char == '.':
                self.display.set_pixel(x, 5)
                self.display.set_pixel(x, 6)
                x += 1
            elif char in self.font:
                for col_byte in self.font[char]:
                    for y in range(8):
                        if col_byte & (1 << y):
                            self.display.set_pixel(x, y)
                    x += 1
                if x < self.display.WIDTH - 1:
                    x += 1


class FireEffect(Effect):
    def __init__(self, display):
        super().__init__(display)
        self.heat = [[0] * display.HEIGHT for _ in range(display.WIDTH)]

    def update(self):
        if not self.should_update():
            return

        self.display.clear()
        h = self.display.HEIGHT
        w = self.display.WIDTH

        for x in range(w):
            self.heat[x][h - 1] = random.randint(160, 255)

        for x in range(w):
            heat_x = self.heat[x]
            left = self.heat[(x - 1) % w]
            right = self.heat[(x + 1) % w]
            for y in range(h - 1, 0, -1):
                cooling = random.randint(0, int((255 - heat_x[y]) / 10))
                heat_x[y] = max(0, heat_x[y] - cooling)
                avg_heat = (heat_x[y] + left[y] + right[y]) // 3
                heat_x[y - 1] = max(0, min(255, avg_heat - random.randint(0, 20)))

        for x in range(w):
            heat_x = self.heat[x]
            for y in range(h):
                heat_val = heat_x[y]
                if heat_val > 180:
                    self.display.set_pixel(x, y)
                elif heat_val > 100 and y < h - 2:
                    if random.random() < 0.3:
                        self.display.set_pixel(x, y)


class WaveEffect(Effect):
    def __init__(self, display):
        super().__init__(display)
        self.phase = 0.0
        self.wave_types = ('sine', 'square', 'sawtooth')
        self.wave_type_idx = 0
        self.wave_amplitude = 3
        self.wave_frequency = 0.1

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        self.phase += self.wave_frequency * self.speed
        if self.phase > 100:
            self.phase = 0
            self.wave_type_idx = (self.wave_type_idx + 1) % len(self.wave_types)

        wave_type = self.wave_types[self.wave_type_idx]
        center_y = self.display.HEIGHT // 2

        for x in range(self.display.WIDTH):
            if wave_type == 'sine':
                y_offset = int(self.wave_amplitude * _fast_sin((x * 0.2) + self.phase))
            elif wave_type == 'square':
                val = ((x * 0.2) + self.phase) % (2 * _PI)
                y_offset = self.wave_amplitude if val < _PI else -self.wave_amplitude
            else:
                val = ((x * 0.2) + self.phase) % (2 * _PI)
                y_offset = int(self.wave_amplitude * (val / _PI - 1))

            y = center_y + y_offset
            if 0 <= y < self.display.HEIGHT:
                self.display.set_pixel(x, y)
                if 0 <= y + 1 < self.display.HEIGHT:
                    self.display.set_pixel(x, y + 1)


class SpectrumEffect(Effect):
    def __init__(self, display):
        super().__init__(display)
        self.bars = [0] * 8
        self.bar_targets = [0] * 8
        self.bar_speeds = [0.5] * 8

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        if self.frame % 5 == 0:
            for i in range(len(self.bars)):
                if random.random() < 0.3:
                    self.bar_targets[i] = random.randint(0, self.display.HEIGHT)
                    self.bar_speeds[i] = random.uniform(0.3, 1.5) * self.speed

        bar_width = self.display.WIDTH // len(self.bars)
        for i in range(len(self.bars)):
            target = self.bar_targets[i]
            current = self.bars[i]

            if abs(target - current) < 0.5:
                self.bars[i] = target
            else:
                if target > current:
                    self.bars[i] = min(target, current + self.bar_speeds[i])
                else:
                    self.bars[i] = max(target, current - self.bar_speeds[i])

            bar_height = int(self.bars[i])
            x_start = i * bar_width
            x_end = min((i + 1) * bar_width, self.display.WIDTH)

            for x in range(x_start, x_end):
                for y in range(self.display.HEIGHT - bar_height, self.display.HEIGHT):
                    if y >= 0:
                        self.display.set_pixel(x, y)

        self.frame += 1


class StarsEffect(Effect):
    def __init__(self, display):
        super().__init__(display)
        self.stars = []
        self.max_stars = 15
        self.shooting_stars = []

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        if len(self.stars) < self.max_stars and random.random() < 0.1:
            self.stars.append({
                'x': random.randint(0, self.display.WIDTH - 1),
                'y': random.randint(0, self.display.HEIGHT - 1),
                'brightness': random.randint(1, 3),
                'twinkle': random.randint(0, 10)
            })

        stars_to_remove = []
        for star in self.stars:
            star['twinkle'] += 1
            if star['twinkle'] > 20:
                star['twinkle'] = 0
            if star['twinkle'] % 4 < 2:
                self.display.set_pixel(star['x'], star['y'])
            if random.random() < 0.01:
                stars_to_remove.append(star)

        for star in stars_to_remove:
            self.stars.remove(star)

        if random.random() < 0.05 and len(self.shooting_stars) < 2:
            self.shooting_stars.append({
                'x': self.display.WIDTH,
                'y': random.randint(0, self.display.HEIGHT - 1),
                'speed': random.uniform(2, 4) * self.speed,
                'length': random.randint(3, 6)
            })

        shooting_to_remove = []
        for star in self.shooting_stars:
            star['x'] -= star['speed']
            for i in range(star['length']):
                x = int(star['x']) + i
                if 0 <= x < self.display.WIDTH:
                    self.display.set_pixel(x, star['y'])
            if star['x'] < -star['length']:
                shooting_to_remove.append(star)

        for star in shooting_to_remove:
            self.shooting_stars.remove(star)


class BinaryClockEffect(Effect):
    def __init__(self, display, font, timezone_offset=0):
        super().__init__(display)
        self.font = font
        self.timezone_offset = timezone_offset
        self.show_binary = True
        self.binary_toggle = 0

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        local_t = _current_localtime(self.timezone_offset, getattr(self, '_manual_datetime', None))
        hours = local_t[3]
        minutes = local_t[4]
        seconds = local_t[5]

        self.binary_toggle += 1
        if self.binary_toggle > 37:
            self.show_binary = not self.show_binary
            self.binary_toggle = 0

        if self.show_binary:
            numbers = [hours // 10, hours % 10, minutes // 10, minutes % 10]
            total_binary_width = 4 * 8 + 3
            x = max(0, (self.display.WIDTH - total_binary_width) // 2)

            for i, num in enumerate(numbers):
                for bit in range(8):
                    if num & (1 << (7 - bit)):
                        self.display.set_pixel(x, bit)
                    x += 1
                if i < 3:
                    x += 1
        else:
            display_str = "{:02d}:{:02d}".format(hours, minutes)
            char_width = 5
            total_width = 4 * char_width + 1
            x = max(0, (self.display.WIDTH - total_width) // 2)

            for char in display_str:
                if char == ':':
                    if seconds % 2 == 0:
                        self.display.set_pixel(x, 2)
                        self.display.set_pixel(x, 5)
                    x += 1
                elif char in self.font:
                    for col_byte in self.font[char]:
                        for y in range(8):
                            if col_byte & (1 << y):
                                self.display.set_pixel(x, y)
                        x += 1
                    if x < self.display.WIDTH - 1:
                        x += 1


class NewsTickerEffect(Effect):
    def __init__(self, display, text, font):
        super().__init__(display)
        self.text = text if text else "BREAKING NEWS"
        self.font = font
        self.offset = display.WIDTH
        self.pause_counter = 0
        self.pause_at_end = 100

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        text_width = sum(len(self.font.get(c, (0, 0, 0, 0, 0, 0))) + 1 for c in self.text)

        if self.offset <= -text_width:
            self.pause_counter += 1
            if self.pause_counter > self.pause_at_end:
                self.offset = self.display.WIDTH
                self.pause_counter = 0
        else:
            x = int(self.offset)
            for char in self.text:
                if char in self.font:
                    for col_byte in self.font[char]:
                        if 0 <= x < self.display.WIDTH:
                            for y in range(8):
                                if col_byte & (1 << y):
                                    self.display.set_pixel(x, y)
                        x += 1
                    x += 1

            self.offset -= 0.5 * self.speed


class PlasmaEffect(Effect):
    def __init__(self, display):
        super().__init__(display)
        self.time = 0.0
        # Pre-calculated sine lookup table
        self.sin_table = tuple(_fast_sin((i / 32.0) * 2 * _PI) for i in range(32))

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        self.time += 0.1 * self.speed
        st = self.sin_table

        for x in range(self.display.WIDTH):
            sx = st[x % 32]
            for y in range(self.display.HEIGHT):
                value = (sx +
                         st[y % 8] +
                         st[(x + y) % 32] +
                         _fast_sin(self.time + x * 0.1) +
                         _fast_sin(self.time * 0.7 + y * 0.2))
                if value > 0:
                    self.display.set_pixel(x, y)


class EqualizerEffect(Effect):
    def __init__(self, display):
        super().__init__(display)
        self.bars = [0] * 8
        self.bar_targets = [0] * 8
        self.bar_speeds = [0.3] * 8

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        if self.frame % 3 == 0:
            for i in range(len(self.bars)):
                if random.random() < 0.4:
                    self.bar_targets[i] = random.randint(1, self.display.HEIGHT)
                    self.bar_speeds[i] = random.uniform(0.2, 1.0) * self.speed

        bar_width = 4
        for i in range(len(self.bars)):
            target = self.bar_targets[i]
            current = self.bars[i]

            if abs(target - current) < 0.3:
                self.bars[i] = target
            else:
                if target > current:
                    self.bars[i] = min(target, current + self.bar_speeds[i])
                else:
                    self.bars[i] = max(0, current - self.bar_speeds[i] * 1.5)

            bar_height = int(self.bars[i])
            x_start = i * bar_width
            x_end = min(x_start + bar_width, self.display.WIDTH)

            for x in range(x_start, x_end):
                for y in range(self.display.HEIGHT - bar_height, self.display.HEIGHT):
                    if y >= 0:
                        self.display.set_pixel(x, y)

        self.frame += 1


class MazeRunnerEffect(Effect):
    def __init__(self, display):
        super().__init__(display)
        self.maze = None
        self.player_pos = None
        self.target_pos = None
        self.player_path = []
        self.max_path_length = 30
        self.maze_view_x = 0

    def _generate_maze(self):
        width, height = 32, 8
        maze = [[1] * width for _ in range(height)]

        for y in range(1, height - 1, 2):
            for x in range(1, width - 1):
                maze[y][x] = 0

        for x in range(1, width - 1, 3):
            for y in range(1, height - 1):
                maze[y][x] = 0

        for y in range(2, height - 1, 2):
            for x in range(3, width - 1, 3):
                if random.random() < 0.6:
                    maze[y][x] = 0

        maze[1][1] = 0
        maze[height - 2][width - 2] = 0

        for x in range(1, min(5, width - 1)):
            maze[1][x] = 0

        for y in range(height - 2, max(height - 6, 1), -1):
            maze[y][width - 2] = 0

        return maze

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        if self.maze is None:
            self.maze = self._generate_maze()
            self.player_pos = [1, 1]
            self.target_pos = [len(self.maze[0]) - 2, len(self.maze) - 2]
            self.player_path = [tuple(self.player_pos)]
            self.maze_view_x = 0

        if self.frame % 4 == 0:
            px, py = self.player_pos
            tx, ty = self.target_pos

            possible_moves = []
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = px + dx, py + dy
                if 0 <= nx < len(self.maze[0]) and 0 <= ny < len(self.maze):
                    if self.maze[ny][nx] == 0:
                        new_dist = abs(tx - nx) + abs(ty - ny)
                        possible_moves.append(((dx, dy), new_dist))

            if possible_moves:
                possible_moves.sort(key=lambda m: m[1])
                if random.random() < 0.8:
                    dx, dy = possible_moves[0][0]
                else:
                    dx, dy = random.choice(possible_moves)[0]

                self.player_pos[0] += dx
                self.player_pos[1] += dy
                self.player_path.append(tuple(self.player_pos))

                if len(self.player_path) > self.max_path_length:
                    self.player_path.pop(0)

                if tuple(self.player_pos) == tuple(self.target_pos):
                    self.maze = None
                    self.player_pos = None
                    self.maze_view_x = 0

        target_view_x = max(0, self.player_pos[0] - self.display.WIDTH // 2)
        target_view_x = min(target_view_x, len(self.maze[0]) - self.display.WIDTH)

        if abs(target_view_x - self.maze_view_x) > 0.5:
            if target_view_x > self.maze_view_x:
                self.maze_view_x += 0.5
            else:
                self.maze_view_x -= 0.5
        else:
            self.maze_view_x = target_view_x

        maze_start_x = int(self.maze_view_x)

        for y in range(len(self.maze)):
            for x in range(self.display.WIDTH):
                maze_x = maze_start_x + x
                if 0 <= maze_x < len(self.maze[0]):
                    if self.maze[y][maze_x] == 1:
                        self.display.set_pixel(x, y)

        for (path_x, path_y) in self.player_path[-5:]:
            px_rel = path_x - maze_start_x
            if 0 <= px_rel < self.display.WIDTH:
                if self.frame % 3 < 2:
                    self.display.set_pixel(px_rel, path_y)

        px_rel = self.player_pos[0] - maze_start_x
        if 0 <= px_rel < self.display.WIDTH:
            self.display.set_pixel(px_rel, self.player_pos[1])
            if px_rel > 0:
                self.display.set_pixel(px_rel - 1, self.player_pos[1])

        tx_rel = self.target_pos[0] - maze_start_x
        if 0 <= tx_rel < self.display.WIDTH:
            if self.frame % 8 < 6:
                self.display.set_pixel(tx_rel, self.target_pos[1])
                if tx_rel > 0:
                    self.display.set_pixel(tx_rel - 1, self.target_pos[1])

        self.frame += 1


class SpriteAnimation(Effect):
    def __init__(self, display, sprite_file):
        super().__init__(display)
        with open(sprite_file, 'r') as f:
            data = json.load(f)
        self.frames = data['frames']
        self.x = float(data.get('x', 0))
        self.y = float(data.get('y', 0))
        self.dx = float(data.get('dx', 1))
        self.dy = float(data.get('dy', 0))
        self.frame_idx = 0
        self.frame_delay = max(1, int(data.get('delay', 3) / self.speed))
        self.counter = 0
        self.name = sprite_file.lower()
        self.original_delay = data.get('delay', 3)
        # Animation type: explicit 'type' field, else inferred from filename
        self.anim_type = data.get('type') or self._infer_type(sprite_file)
        self._init_special()

    def _infer_type(self, fname):
        lower = fname.lower()
        for t in ('snake', 'pacman', 'hack', 'heart'):
            if t in lower:
                return t
        return 'sprite'

    def _init_special(self):
        if self.anim_type == 'snake':
            self._reset_snake()
        elif self.anim_type == 'hack':
            self.hack_offset = self.display.WIDTH
            self.hack_frame = 0
            self.blink_on = True

    def set_speed(self, speed):
        super().set_speed(speed)
        self.frame_delay = max(1, int(self.original_delay / speed))

    def update(self):
        if not self.should_update():
            return

        self.display.clear()

        if self.anim_type == 'snake':
            self._update_snake()
        elif self.anim_type == 'hack':
            self._update_hack()
        elif self.anim_type == 'pacman':
            self._update_pacman()
        else:
            self._update_sprite()

        self.counter += 1
        if self.counter >= self.frame_delay:
            self.counter = 0
            self.frame_idx = (self.frame_idx + 1) % len(self.frames)

    def _update_pacman(self):
        current_frame = self.frames[self.frame_idx]
        flip_x = self.dx < 0
        self.display.draw_sprite(current_frame, int(self.x), int(self.y), flip_x=flip_x, flip_y=False)

        self.x += self.dx * self.speed
        self.y += self.dy * self.speed

        sprite_width = len(self.frames[0][0]) if self.frames else 14
        if self.dx < 0 and self.x < -sprite_width:
            self.x = self.display.WIDTH
        elif self.dx > 0 and self.x > self.display.WIDTH:
            self.x = -sprite_width

    def _update_hack(self):
        from fonts.default import FONT_5X7
        text = "HACK THE PLANET!"

        self.hack_frame += 1
        if self.hack_frame % 15 == 0:
            self.blink_on = not self.blink_on
        if self.hack_frame % 2 == 0:
            self.hack_offset -= 1
            text_width = len(text) * 6
            if self.hack_offset < -text_width:
                self.hack_offset = self.display.WIDTH

        if self.blink_on or self.hack_frame % 30 < 25:
            x = self.hack_offset
            for char in text:
                if char in FONT_5X7:
                    for col_byte in FONT_5X7[char]:
                        if 0 <= x < self.display.WIDTH:
                            for y in range(8):
                                if col_byte & (1 << y):
                                    self.display.set_pixel(x, y)
                        x += 1
                    x += 1

    def _update_snake(self):
        self.snake_timer += 1

        if self.game_over:
            self.crash_timer += 1
            if self.crash_timer % 6 < 3:
                for sx, sy in self.snake_body:
                    self.display.set_pixel(sx, sy)
            if self.crash_timer > 30:
                self._reset_snake()
        else:
            if self.snake_timer % 4 == 0:
                self._snake_ai()

            if self.snake_timer % 3 == 0:
                head = self.snake_body[0]
                new_head = (head[0] + self.snake_dir[0], head[1] + self.snake_dir[1])

                if (new_head[0] < 0 or new_head[0] >= self.display.WIDTH or
                        new_head[1] < 0 or new_head[1] >= self.display.HEIGHT):
                    self.game_over = True
                elif new_head in self.snake_body[:-1]:
                    self.game_over = True
                else:
                    self.snake_body.insert(0, new_head)
                    if new_head == self.food:
                        self._spawn_food()
                    else:
                        self.snake_body.pop()

            for (sx, sy) in self.snake_body:
                self.display.set_pixel(sx, sy)

            if self.snake_timer % 5 < 4:
                self.display.set_pixel(self.food[0], self.food[1])

    def _update_sprite(self):
        current_frame = self.frames[self.frame_idx]
        flip_x = False
        if 'pacman' in self.name and self.dx < 0:
            flip_x = True
        self.display.draw_sprite(current_frame, int(self.x), int(self.y), flip_x=flip_x, flip_y=False)

        self.x += self.dx * self.speed
        self.y += self.dy * self.speed

        sprite_width = len(self.frames[0][0]) if self.frames and self.frames[0] else 9
        sprite_height = len(self.frames[0]) if self.frames else 8
        if self.x >= self.display.WIDTH or self.x < -sprite_width:
            self.dx = -self.dx
        if self.y >= self.display.HEIGHT or self.y < -sprite_height:
            self.dy = -self.dy

    def _reset_snake(self):
        start_x = self.display.WIDTH // 2
        self.snake_body = [(start_x, 4), (start_x - 1, 4), (start_x - 2, 4)]
        self.snake_dir = (1, 0)
        self._spawn_food()
        self.snake_timer = 0
        self.crash_timer = 0
        self.game_over = False

    def _spawn_food(self):
        for _ in range(100):
            fx = random.randint(1, self.display.WIDTH - 2)
            fy = random.randint(1, self.display.HEIGHT - 2)
            if (fx, fy) not in self.snake_body:
                self.food = (fx, fy)
                return
        self.food = (1, 1)

    def _snake_ai(self):
        head = self.snake_body[0]
        fx, fy = self.food
        dx, dy = self.snake_dir

        moves = []
        if dx != 1:
            moves.append((-1, 0))
        if dx != -1:
            moves.append((1, 0))
        if dy != 1:
            moves.append((0, -1))
        if dy != -1:
            moves.append((0, 1))

        safe_moves = []
        for mdx, mdy in moves:
            new_pos = (head[0] + mdx, head[1] + mdy)
            if new_pos[0] < 0 or new_pos[0] >= self.display.WIDTH:
                continue
            if new_pos[1] < 0 or new_pos[1] >= self.display.HEIGHT:
                continue
            if new_pos in self.snake_body[:-1]:
                continue
            safe_moves.append((mdx, mdy))

        if not safe_moves:
            return

        best_move = safe_moves[0]
        best_dist = 999
        for mdx, mdy in safe_moves:
            new_pos = (head[0] + mdx, head[1] + mdy)
            dist = abs(new_pos[0] - fx) + abs(new_pos[1] - fy)
            if dist < best_dist:
                best_dist = dist
                best_move = (mdx, mdy)

        if random.randint(0, 9) == 0 and len(safe_moves) > 1:
            best_move = random.choice(safe_moves)

        self.snake_dir = best_move


class DefconEffect(Effect):
    """WiFi attack alert. Blinks 'DC<level>'; at DEFCON 1 flashes a warning fill."""
    def __init__(self, display, font, level=2):
        super().__init__(display)
        self.font = font
        self.level = max(1, min(5, level))
        self.blink = 0

    def set_level(self, level):
        self.level = max(1, min(5, level))

    def update(self):
        # Runs every frame regardless of speed (alert must be responsive)
        self.display.clear()
        self.blink += 1
        period = max(3, self.level * 3)  # lower level = faster blink
        on_phase = (self.blink // period) % 2 == 0
        if on_phase:
            self._draw_label()
        elif self.level <= 1:
            self._draw_warning()

    def _draw_label(self):
        s = 'DC%d' % self.level
        char_width = 5
        total = len(s) * char_width + (len(s) - 1)
        x = max(0, (self.display.WIDTH - total) // 2)
        for ch in s:
            if ch in self.font:
                for col_byte in self.font[ch]:
                    for y in range(8):
                        if col_byte & (1 << y):
                            self.display.set_pixel(x, y)
                    x += 1
            x += 1

    def _draw_warning(self):
        # Full-screen hatched warning fill
        for y in range(self.display.HEIGHT):
            for x in range(self.display.WIDTH):
                if (x + y) % 2 == 0:
                    self.display.set_pixel(x, y)


import network
import time
import os
import ntptime
import machine
import json
import gc
import sys
from display import Display
from effects import (MatrixRain, GameOfLife, Marquee, SpriteAnimation, DigitalClock,
                     FireEffect, WaveEffect, SpectrumEffect, StarsEffect, BinaryClockEffect,
                     NewsTickerEffect, PlasmaEffect, EqualizerEffect, MazeRunnerEffect)
from webserver import WebServer, create_html
from fonts.default import FONT_5X7

FRAME_INTERVAL_MS = 80
TZ_NAMES = {0: 'UTC', 1: 'CET', 2: 'EET', -5: 'EST', -6: 'CST', -8: 'PST', 9: 'JST', 8: 'CST'}


def load_config():
    """Load config.txt (KEY=value lines). Never raises; returns dict."""
    config = {}
    try:
        with open('config.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                config[key.strip()] = val.strip()
    except OSError as e:
        print('config.txt not readable: %s' % e)
    return config


def connect_wifi(ssid, password):
    """Connect to WiFi. Falls back to Access Point if it fails.
    Returns (ip, is_ap_mode)."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.disconnect()
    except Exception:
        pass

    if ssid:
        print('Connecting to WiFi [%s]...' % ssid)
        wlan.connect(ssid, password)
        timeout = 20
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print('Connected: %s' % ip)
        try:
            ntptime.settime()
            print('Time set via NTP')
        except Exception as e:
            print('NTP failed: %s' % e)
        return ip, False

    # Fallback: start an Access Point so the device stays reachable
    print('WiFi failed, starting AP fallback')
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap.config(essid='MatrixLED-Setup')
    except Exception:
        pass
    ip = ap.ifconfig()[0]
    print('AP mode active: %s' % ip)
    return ip, True


def list_drawings():
    try:
        return [f for f in os.listdir('drawings') if f.endswith('.json')]
    except Exception:
        return []


def list_python_files():
    try:
        return [f for f in os.listdir('.') if f.endswith('.py')]
    except Exception:
        return []


def list_backups():
    try:
        return [f for f in os.listdir('backups') if '.bak_' in f]
    except Exception:
        return []


config = load_config()
display = Display()
global_speed = 1.0
clock_timezone = 0.0
manual_datetime = None


def load_settings():
    global clock_timezone, manual_datetime
    manual_datetime = None
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
            clock_timezone = settings.get('timezone', 0.0)
            manual_datetime = settings.get('manual_datetime', None)
            display.brightness(settings.get('brightness', 4))
            display.set_flip(settings.get('flip_x', False), settings.get('flip_y', False))
            display.set_contrast(settings.get('contrast', 1.0))
            display.set_invert_colors(settings.get('invert_colors', False))
            return settings
    except Exception as e:
        print('settings.json load skipped: %s' % e)
        return {}


def save_settings():
    try:
        settings = {
            'timezone': clock_timezone,
            'manual_datetime': manual_datetime,
            'brightness': display.get_brightness(),
            'flip_x': display.get_flip()[0],
            'flip_y': display.get_flip()[1],
            'contrast': display.get_contrast(),
            'invert_colors': display.get_invert_colors()
        }
        with open('settings.json', 'w') as f:
            json.dump(settings, f)
    except Exception as e:
        print('save_settings failed: %s' % e)


load_settings()
current_effect = MatrixRain(display)
effect_name = 'matrix'

ip, ap_mode = connect_wifi(config.get('SSID', ''), config.get('PASSWORD', ''))
if not ip:
    print('Running offline mode')

server = WebServer(password=config.get('WEB_PASSWORD', None) or None)


@server.route('/')
def index(params):
    flip_x, flip_y = display.get_flip()
    download_icon = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="8" y1="2" x2="8" y2="12"/><polyline points="4 8, 8 12, 12 8"/><line x1="2" y1="14" x2="14" y2="14"/></svg>'
    delete_icon = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/></svg>'

    gc.collect()
    drawings = list_drawings()
    animations = ''.join([
        '<button class="btn btn-primary btn-sm" onclick="playAnim(\'%s\')" title="%s">%s</button>' % (
            f, f.replace('.json', '').replace('_', ' '), f.replace('.json', '').replace('_', ' '))
        for f in drawings])
    files = ''.join([
        '<div class="file-item"><span class="file-name">%s</span>'
        '<div class="file-actions">'
        '<button class="btn btn-ghost btn-sm btn-icon" onclick="downloadFile(\'%s\')" title="Download">%s</button>'
        '<button class="btn btn-destructive btn-sm btn-icon" onclick="deleteFile(\'%s\')" title="Delete">%s</button>'
        '</div></div>' % (f, f, download_icon, f, delete_icon)
        for f in drawings])

    flash = None
    if params.get('u') == '1':
        flash = {'msg': 'File uploaded successfully', 'error': False}

    html = create_html(
        effect_name, animations, files,
        tz_value=clock_timezone, manual_dt=manual_datetime,
        brightness=display.get_brightness(), contrast=display.get_contrast(),
        flip_x=flip_x, flip_y=flip_y, invert_colors=display.get_invert_colors(),
        flash=flash, ip=ip, ap_mode=ap_mode)
    return html


def _safe_filename(name):
    """Reject path traversal and return cleaned filename, or None."""
    if not name or '/' in name or '\\' in name or '..' in name:
        return None
    return name


@server.route('/delete', methods=('POST',))
def delete_file(params):
    filename = _safe_filename(params.get('file', ''))
    if not filename or not filename.endswith('.json'):
        return '<script>window.location="/"</script>'
    try:
        drawings = list_drawings()
        candidates = [filename, filename.replace('+', ' '), filename.replace('%20', ' ')]
        target = None
        for variant in candidates:
            if variant in drawings:
                target = variant
                break
        if target is None:
            lower = filename.lower()
            for drawing in drawings:
                if drawing.lower() == lower:
                    target = drawing
                    break
        if target:
            os.remove('drawings/' + target)
            print('Deleted: %s' % target)
        else:
            print('Delete failed: %s not found' % filename)
    except Exception as e:
        print('Delete error: %s' % e)
    return '<script>window.location="/"</script>'


@server.route('/speed', methods=('POST',))
def set_speed(params):
    global global_speed
    try:
        speed = float(params.get('val', 1.0))
        global_speed = max(0.1, min(10.0, speed))
        if hasattr(current_effect, 'set_speed'):
            current_effect.set_speed(global_speed)
        return '%.1f' % global_speed
    except Exception as e:
        print('Speed error: %s' % e)
    return '1.0'


def _apply_clock_tz(params):
    global clock_timezone
    tz = params.get('tz')
    if tz is not None:
        try:
            clock_timezone = float(tz)
            save_settings()
        except Exception as e:
            print('TZ parse error: %s' % e)


@server.route('/effect', methods=('POST',))
def set_effect(params):
    global current_effect, effect_name
    name = params.get('name', 'matrix')

    if name == 'matrix':
        current_effect = MatrixRain(display)
        effect_name = 'matrix'
    elif name == 'life':
        current_effect = GameOfLife(display)
        effect_name = 'game of life'
    elif name == 'clock':
        _apply_clock_tz(params)
        current_effect = DigitalClock(display, FONT_5X7, clock_timezone)
        if manual_datetime:
            current_effect._manual_datetime = manual_datetime
        effect_name = 'clock (%s)' % TZ_NAMES.get(clock_timezone, 'TZ:%s' % clock_timezone)
    elif name == 'fire':
        current_effect = FireEffect(display)
        effect_name = 'fire'
    elif name == 'wave':
        current_effect = WaveEffect(display)
        effect_name = 'wave'
    elif name == 'spectrum':
        current_effect = SpectrumEffect(display)
        effect_name = 'spectrum'
    elif name == 'stars':
        current_effect = StarsEffect(display)
        effect_name = 'stars'
    elif name == 'binary':
        _apply_clock_tz(params)
        current_effect = BinaryClockEffect(display, FONT_5X7, clock_timezone)
        if manual_datetime:
            current_effect._manual_datetime = manual_datetime
        effect_name = 'binary clock (%s)' % TZ_NAMES.get(clock_timezone, 'TZ:%s' % clock_timezone)
    elif name == 'plasma':
        current_effect = PlasmaEffect(display)
        effect_name = 'plasma'
    elif name == 'equalizer':
        current_effect = EqualizerEffect(display)
        effect_name = 'equalizer'
    elif name == 'maze':
        current_effect = MazeRunnerEffect(display)
        effect_name = 'maze runner'

    if hasattr(current_effect, 'set_speed'):
        current_effect.set_speed(global_speed)
    return '<script>window.location="/"</script>'


@server.route('/marquee', methods=('POST',))
def set_marquee(params):
    global current_effect, effect_name
    text = params.get('text', 'HELLO')
    mode = params.get('mode', 'scroll')
    current_effect = Marquee(display, text, FONT_5X7, mode=mode)
    effect_name = 'marquee (%s): %s' % (mode, text)
    if hasattr(current_effect, 'set_speed'):
        current_effect.set_speed(global_speed)
    return '<script>window.location="/"</script>'


@server.route('/ticker', methods=('POST',))
def set_ticker(params):
    global current_effect, effect_name
    text = params.get('text', 'BREAKING NEWS')
    current_effect = NewsTickerEffect(display, text, FONT_5X7)
    effect_name = 'news ticker: %s' % text
    if hasattr(current_effect, 'set_speed'):
        current_effect.set_speed(global_speed)
    return '<script>window.location="/"</script>'


@server.route('/animation', methods=('POST',))
def play_animation(params):
    global current_effect, effect_name
    filename = _safe_filename(params.get('file', ''))
    if filename:
        try:
            current_effect = SpriteAnimation(display, 'drawings/%s' % filename)
            effect_name = 'animation: %s' % filename
            if hasattr(current_effect, 'set_speed'):
                current_effect.set_speed(global_speed)
        except Exception as e:
            print('Animation error: %s' % e)
    return '<script>window.location="/"</script>'


@server.route('/download')
def download_file(params):
    filename = _safe_filename(params.get('file', ''))
    if not filename or not filename.endswith('.json'):
        return ('text/plain', None, 'Invalid filename')
    try:
        with open('drawings/%s' % filename, 'r') as f:
            content = f.read()
        return ('application/json', 'attachment; filename="%s"' % filename, content)
    except Exception as e:
        print('Download error: %s' % e)
        return ('text/plain', None, 'File not found')


# Global sensor instance (reused to avoid reinitialization)
rack_sensor = None


@server.route('/rack')
def get_rack_status(params):
    global rack_sensor
    try:
        if rack_sensor is None:
            from sensor_aht20_bmp280 import AHT20_BMP280
            rack_sensor = AHT20_BMP280()
            time.sleep_ms(500)
        data = rack_sensor.read_all()
        return json.dumps({
            'temperature': data.get('temperature'),
            'humidity': data.get('humidity'),
            'pressure': data.get('pressure')
        })
    except ImportError as e:
        print('Import error: %s' % e)
        return '{"error":"Sensor module not available"}'
    except Exception as e:
        sys.print_exception(e)
        # Only reset on non-read errors
        if 'ENODEV' not in str(e):
            rack_sensor = None
        return '{"error":"%s"}' % str(e)


@server.route('/set_time', methods=('POST',))
def set_manual_time(params):
    global manual_datetime
    datetime_str = params.get('datetime', '')
    if datetime_str:
        try:
            parts = datetime_str.split('T')
            if len(parts) == 2:
                dp = parts[0].split('-')
                tp = parts[1].split(':')
                year = int(dp[0])
                month = int(dp[1])
                day = int(dp[2])
                hour = int(tp[0])
                minute = int(tp[1]) if len(tp) > 1 else 0
                second = int(tp[2]) if len(tp) > 2 else 0
                rtc = machine.RTC()
                rtc.datetime((year, month, day, 0, hour, minute, second, 0))
                manual_datetime = datetime_str
                save_settings()
                print('Manual time set: %04d-%02d-%02d %02d:%02d:%02d' % (year, month, day, hour, minute, second))
        except Exception as e:
            print('Set time error: %s' % e)
    return '<script>window.location="/"</script>'


@server.route('/preview')
def get_preview(params):
    try:
        current_effect.update()
        current_effect.render()
        pixels = display.get_buffer()
        scale = 4
        svg_width = display.WIDTH * scale
        svg_height = display.HEIGHT * scale
        # Build rect list then join (faster than repeated concatenation)
        rects = []
        for y in range(display.HEIGHT):
            row = pixels[y]
            for x in range(display.WIDTH):
                if row[x]:
                    rects.append('<rect x="%d" y="%d" width="1" height="1" fill="#22c55e"/>' % (x, y))
        svg = '<svg width="%d" height="%d" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" style="background:#09090b">' % (
            svg_width, svg_height, display.WIDTH, display.HEIGHT)
        svg += ''.join(rects)
        svg += '</svg>'
        return ('image/svg+xml', None, svg)
    except Exception as e:
        return ('text/plain', None, 'Error: %s' % e)


@server.route('/display', methods=('POST',))
def set_display(params):
    try:
        if params.get('reset') == 'true':
            display.reset_display_settings()
            save_settings()
            return '<script>window.location="/"</script>'

        brightness = params.get('brightness')
        if brightness is not None:
            display.brightness(int(brightness))

        flip_x = params.get('flip_x')
        if flip_x is not None:
            display.set_flip(flip_x.lower() == 'true', display.get_flip()[1])

        flip_y = params.get('flip_y')
        if flip_y is not None:
            display.set_flip(display.get_flip()[0], flip_y.lower() == 'true')

        contrast = params.get('contrast')
        if contrast is not None:
            display.set_contrast(float(contrast))

        invert_colors = params.get('invert_colors')
        if invert_colors is not None:
            display.set_invert_colors(invert_colors.lower() == 'true')

        save_settings()
    except Exception as e:
        print('Display settings error: %s' % e)
    return '<script>window.location="/"</script>'


@server.route('/ota/files')
def ota_list_files(params):
    try:
        files_info = []
        for fname in list_python_files():
            try:
                stat = os.stat(fname)
                files_info.append({'name': fname, 'size': stat[6]})
            except Exception:
                files_info.append({'name': fname, 'size': 0})
        return json.dumps(files_info)
    except Exception as e:
        return '{"error":"%s"}' % str(e)


@server.route('/ota/backups')
def ota_list_backups(params):
    try:
        backups_info = []
        for fname in list_backups():
            try:
                stat = os.stat('backups/%s' % fname)
                backups_info.append({'name': fname, 'size': stat[6]})
            except Exception:
                backups_info.append({'name': fname, 'size': 0})
        return json.dumps(backups_info)
    except Exception as e:
        return '{"error":"%s"}' % str(e)


@server.route('/ota/restore', methods=('POST',))
def ota_restore_backup(params):
    backup_file = _safe_filename(params.get('file', ''))
    if not backup_file or '.bak_' not in backup_file:
        return '<script>alert("Invalid backup file");window.location="/"</script>'
    try:
        original_file = backup_file.split('.bak_')[0]
        if original_file in os.listdir('.'):
            t = time.localtime()
            ts = '%d%02d%02d_%02d%02d%02d' % (t[0], t[1], t[2], t[3], t[4], t[5])
            temp_backup = '%s.bak_%s' % (original_file, ts)
            with open(original_file, 'rb') as src:
                with open('backups/%s' % temp_backup, 'wb') as dst:
                    dst.write(src.read())
        with open('backups/%s' % backup_file, 'rb') as src:
            with open(original_file, 'wb') as dst:
                dst.write(src.read())
        print('Restored: %s from %s' % (original_file, backup_file))
        server.pending_reset = True
        return '<html><head><meta http-equiv="refresh" content="10;url=/"></head><body style="font-family:sans-serif;text-align:center;padding:40px"><h2>Restored! Restarting...</h2></body></html>'
    except Exception as e:
        print('Restore error: %s' % e)
        return '<script>alert("Restore failed");window.location="/"</script>'


@server.route('/ota/download')
def ota_download_file(params):
    filename = _safe_filename(params.get('file', ''))
    backup = params.get('backup', 'false') == 'true'
    if not filename:
        return ('text/plain', None, 'Invalid filename')
    try:
        filepath = 'backups/%s' % filename if backup else filename
        with open(filepath, 'r') as f:
            content = f.read()
        return ('text/plain', 'attachment; filename="%s"' % filename, content)
    except Exception as e:
        return ('text/plain', None, 'File not found')


@server.route('/ota/delete_backup', methods=('POST',))
def ota_delete_backup(params):
    filename = _safe_filename(params.get('file', ''))
    if filename and '.bak_' in filename:
        try:
            os.remove('backups/%s' % filename)
            print('Deleted backup: %s' % filename)
        except Exception as e:
            print('Delete backup error: %s' % e)
    return '<script>window.location="/"</script>'


@server.route('/ota/restart', methods=('POST',))
def ota_restart(params):
    # Response is flushed by handle_client; reboot happens afterwards.
    server.pending_reset = True
    return '<html><head><meta http-equiv="refresh" content="10;url=/"></head><body style="font-family:sans-serif;text-align:center;padding:40px"><h2>Restarting ESP32...</h2><p>Reconnecting in 10 seconds...</p></body></html>'


if ip:
    server.start()
    print('Server running at http://%s%s' % (ip, ' (AP mode)' if ap_mode else ''))


def _log(msg):
    """Append a message to error.log (capped to ~8KB to avoid filling flash)."""
    try:
        line = '[%d] %s\n' % (time.time(), msg)
        try:
            size = os.stat('error.log')[6]
        except OSError:
            size = 0
        mode = 'a' if size < 8192 else 'w'
        with open('error.log', mode) as f:
            f.write(line)
    except Exception:
        pass


@server.route('/health')
def health(params):
    """Diagnostic endpoint: free memory, effect, uptime."""
    try:
        t = time.ticks_ms()
        return json.dumps({
            'free_mem': gc.mem_free(),
            'alloc_mem': gc.mem_alloc(),
            'effect': effect_name,
            'uptime_s': t // 1000,
            'ip': ip,
            'ap_mode': ap_mode
        })
    except Exception as e:
        return '{"error":"%s"}' % str(e)


loop_count = 0
last_update = time.ticks_ms()
while True:
    try:
        if ip:
            server.handle_client()

        now = time.ticks_ms()
        if time.ticks_diff(now, last_update) >= FRAME_INTERVAL_MS:
            try:
                current_effect.update()
                current_effect.render()
            except Exception as e:
                print('Effect error: %s' % e)
                _log('Effect error [%s]: %s' % (effect_name, e))
            last_update = now
            loop_count += 1
            # Periodic GC + memory heartbeat (every ~8s)
            if loop_count % 100 == 0:
                gc.collect()
                _log('heartbeat free=%d effect=%s' % (gc.mem_free(), effect_name))
            else:
                gc.collect()
    except Exception as e:
        print('Loop error: %s' % e)
        _log('LOOP error: %s' % e)
        time.sleep_ms(50)


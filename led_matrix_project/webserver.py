import socket
import gc
import os
import time

try:
    from embedded_assets import CSS as EMBEDDED_CSS
except Exception:
    EMBEDDED_CSS = ''

MAX_REQUEST_SIZE = 600 * 1024  # Hard limit: uploads up to 500KB + overhead
RECV_CHUNK = 1024

_HTTP_STATUS = {
    200: 'OK', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
    404: 'Not Found', 405: 'Method Not Allowed', 413: 'Payload Too Large',
    500: 'Internal Server Error',
}

# SVG icons built once at module load (avoids rebuilding every page render)
ICONS = {
    'rain': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="4" y1="2" x2="4" y2="14"/><line x1="8" y1="1" x2="8" y2="14"/><line x1="12" y1="3" x2="12" y2="14"/></svg>',
    'life': '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><circle cx="3" cy="3" r="1"/><circle cx="8" cy="3" r="1"/><circle cx="13" cy="3" r="1"/><circle cx="3" cy="8" r="1"/><circle cx="8" cy="8" r="1"/><circle cx="13" cy="8" r="1"/><circle cx="3" cy="13" r="1"/><circle cx="8" cy="13" r="1"/><circle cx="13" cy="13" r="1"/></svg>',
    'clock': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><line x1="8" y1="8" x2="8" y2="5"/><line x1="8" y1="8" x2="10" y2="8"/></svg>',
    'fire': '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 14 L6 12 L7 10 L5 8 L8 6 L11 8 L9 10 L10 12 Z"/></svg>',
    'wave': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 8 Q4 4, 6 8 T10 8 T14 8"/></svg>',
    'spectrum': '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="12" width="2" height="4"/><rect x="4" y="8" width="2" height="8"/><rect x="7" y="4" width="2" height="12"/><rect x="10" y="6" width="2" height="10"/><rect x="13" y="10" width="2" height="6"/></svg>',
    'stars': '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 2 L9 6 L13 6 L10 8 L11 12 L8 10 L5 12 L6 8 L3 6 L7 6 Z"/></svg>',
    'binary': '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" font-size="10" font-family="monospace"><text x="2" y="6">0</text><text x="6" y="6">1</text><text x="10" y="6">0</text><text x="14" y="6">1</text></svg>',
    'plasma': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 8 Q4 4, 6 8 T10 8"/><path d="M2 12 Q4 8, 6 12 T10 12"/></svg>',
    'equalizer': '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="10" width="2" height="6"/><rect x="4" y="6" width="2" height="10"/><rect x="7" y="4" width="2" height="12"/><rect x="10" y="8" width="2" height="8"/><rect x="13" y="12" width="2" height="4"/></svg>',
    'maze': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1"><rect x="2" y="2" width="12" height="12"/><line x1="6" y1="2" x2="6" y2="8"/><line x1="10" y1="8" x2="10" y2="14"/></svg>',
    'scroll': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="2" y1="8" x2="14" y2="8"/><polyline points="10 4, 14 8, 10 12"/></svg>',
    'type': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="4" y1="3" x2="12" y2="3"/><line x1="4" y1="8" x2="12" y2="8"/><line x1="4" y1="13" x2="8" y2="13"/><line x1="10" y1="10" x2="10" y2="14"/></svg>',
    'hack': '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" font-size="8" font-family="monospace"><text x="2" y="6">#</text><text x="6" y="6">$</text><text x="10" y="6">%</text></svg>',
    'upload': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="8" y1="2" x2="8" y2="12"/><polyline points="4 6, 8 2, 12 6"/><line x1="2" y1="14" x2="14" y2="14"/></svg>',
    'download': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="8" y1="2" x2="8" y2="12"/><polyline points="4 8, 8 12, 12 8"/><line x1="2" y1="14" x2="14" y2="14"/></svg>',
    'delete': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/></svg>',
    'speed': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="5"/><path d="M8 3 L8 8 L11 11"/></svg>',
    'settings': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="2"/><path d="M8 2 L8 4 M8 12 L8 14 M2 8 L4 8 M12 8 L14 8 M4.34 4.34 L5.76 5.76 M10.24 10.24 L11.66 11.66 M4.34 11.66 L5.76 10.24 M10.24 5.76 L11.66 4.34"/></svg>',
    'rack': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="12" height="10"/><line x1="2" y1="6" x2="14" y2="6"/><line x1="2" y1="9" x2="14" y2="9"/><circle cx="5" cy="4.5" r="0.5" fill="currentColor"/><circle cx="5" cy="7.5" r="0.5" fill="currentColor"/><circle cx="5" cy="10.5" r="0.5" fill="currentColor"/></svg>',
    'temp': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 2 L8 6 M6 6 L10 6 M8 6 L8 10 M6 10 L10 10 M8 10 L8 12 M7 12 L9 12"/></svg>',
    'humidity': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 2 Q4 6, 8 10 Q12 6, 8 2"/><path d="M8 4 Q6 7, 8 9 Q10 7, 8 4"/></svg>',
    'pressure': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="5"/><line x1="8" y1="3" x2="8" y2="8"/><line x1="8" y1="8" x2="10" y2="10"/></svg>',
    'ota': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 2 L8 10 M5 7 L8 10 L11 7"/><line x1="3" y1="14" x2="13" y2="14"/></svg>',
    'restart': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 8 A6 6 0 0 1 14 8"/><polyline points="11 4, 14 8, 11 12"/></svg>',
    'backup': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="10" height="10"/><path d="M6 3 L6 1 L10 1 L10 3"/></svg>',
    'logo': '<svg width="16" height="16" viewBox="0 0 16 16" fill="#04210f"><rect x="2" y="2" width="3" height="3"/><rect x="6" y="2" width="3" height="3" opacity=".6"/><rect x="10" y="2" width="3" height="3"/><rect x="2" y="6" width="3" height="3" opacity=".6"/><rect x="6" y="6" width="3" height="3"/><rect x="10" y="6" width="3" height="3" opacity=".6"/><rect x="2" y="10" width="3" height="3"/><rect x="6" y="10" width="3" height="3" opacity=".6"/><rect x="10" y="10" width="3" height="3"/></svg>',
    'text': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M3 4 L13 4 M3 8 L11 8 M3 12 L9 12"/></svg>',
    'gauge': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M3 11 A5 5 0 0 1 13 11"/><line x1="8" y1="11" x2="10.5" y2="7.5"/></svg>',
    'flip': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M3 5 L3 11 M5 3 L11 3 M5 13 L11 13 M13 5 L13 11"/><line x1="8" y1="2" x2="8" y2="14" stroke-dasharray="2 2"/></svg>',
    'sun': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="8" cy="8" r="3"/><path d="M8 2 L8 3.5 M8 12.5 L8 14 M2 8 L3.5 8 M12.5 8 L14 8 M3.8 3.8 L4.8 4.8 M11.2 11.2 L12.2 12.2 M3.8 12.2 L4.8 11.2 M11.2 4.8 L12.2 3.8"/></svg>',
    'shield': '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M8 1 L14 3 L14 8 Q14 13 8 15 Q2 13 2 8 L2 3 Z"/><path d="M5.5 8 L7 9.5 L10.5 6"/></svg>',
}

_CONTENT_TYPES = {
    '.css': 'text/css', '.js': 'application/javascript', '.json': 'application/json',
    '.html': 'text/html', '.svg': 'image/svg+xml', '.png': 'image/png', '.txt': 'text/plain',
}


class WebServer:
    def __init__(self, port=80, password=None):
        self.port = port
        self.password = password  # None or empty disables auth
        self.handlers = {}  # path -> (set(methods), func)
        self.sock = None
        self.pending_reset = False

    def route(self, path, methods=('GET',)):
        allowed = set(methods)

        def decorator(func):
            self.handlers[path] = (allowed, func)
            return func

        return decorator

    def start(self):
        addr = socket.getaddrinfo('0.0.0.0', self.port)[0][-1]
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(addr)
        self.sock.listen(2)
        self.sock.settimeout(0.1)

    # ---- HTTP helpers ----

    def _send(self, conn, status, content_type, body, content_disposition=None, extra=None):
        reason = _HTTP_STATUS.get(status, 'Unknown')
        if isinstance(body, str):
            body = body.encode('utf-8')
        head = 'HTTP/1.1 %d %s\r\n' % (status, reason)
        head += 'Content-Type: %s\r\n' % content_type
        head += 'Content-Length: %d\r\n' % len(body)
        if content_disposition:
            head += 'Content-Disposition: %s\r\n' % content_disposition
        if extra:
            head += extra
        head += 'Connection: close\r\n\r\n'
        conn.sendall(head.encode('utf-8') + body)

    def _authorized(self, headers_str):
        if not self.password:
            return True
        try:
            import ubinascii
            for line in headers_str.split('\r\n'):
                if line.lower().startswith('authorization:'):
                    val = line.split(':', 1)[1].strip()
                    bits = val.split(' ', 1)
                    if len(bits) == 2 and bits[0].lower() == 'basic':
                        decoded = ubinascii.a2b_base64(bits[1]).decode('utf-8', 'ignore')
                        pwd = decoded.split(':', 1)[1] if ':' in decoded else ''
                        return pwd == self.password
        except Exception as e:
            print('Auth error: %s' % e)
        return False

    def _content_length(self, request):
        head = request.split(b'\r\n\r\n', 1)[0].decode('utf-8', 'ignore')
        for line in head.split('\r\n'):
            if line.lower().startswith('content-length:'):
                try:
                    return int(line.split(':', 1)[1].strip())
                except Exception:
                    return None
        return None

    @staticmethod
    def _url_decode(v):
        out = []
        i = 0
        n = len(v)
        while i < n:
            c = v[i]
            if c == '%' and i + 2 < n:
                try:
                    out.append(chr(int(v[i + 1:i + 3], 16)))
                    i += 3
                    continue
                except Exception:
                    pass
            out.append(' ' if c == '+' else c)
            i += 1
        return ''.join(out)

    def _parse_query(self, query):
        params = {}
        for param in query.split('&'):
            if '=' in param:
                k, v = param.split('=', 1)
                params[k] = self._url_decode(v)
        return params

    def _read_request(self, conn):
        request = b''
        total = 0
        deadline = time.ticks_add(time.ticks_ms(), 3000)  # 3s hard budget per request
        while True:
            if time.ticks_diff(time.ticks_ms(), deadline) > 0:
                return request if request else None
            try:
                chunk = conn.recv(RECV_CHUNK)
            except OSError:
                break
            if not chunk:
                break
            request += chunk
            total += len(chunk)
            if total > MAX_REQUEST_SIZE:
                return None  # too large -> handled by caller
            sep = request.find(b'\r\n\r\n')
            if sep >= 0:
                cl = self._content_length(request)
                body_have = len(request) - (sep + 4)
                if cl is None or body_have >= cl:
                    break
        return request

    def _serve_static(self, conn, fname):
        # Prevent path traversal
        if not fname or '/' in fname or '..' in fname:
            self._send(conn, 403, 'text/plain', 'Forbidden')
            return
        if '.' not in fname:
            self._send(conn, 404, 'text/plain', 'Not Found')
            return
        ext = '.' + fname.rsplit('.', 1)[1].lower()
        ctype = _CONTENT_TYPES.get(ext, 'application/octet-stream')
        try:
            with open('static/' + fname, 'r') as f:
                self._send(conn, 200, ctype, f.read(),
                           extra='Cache-Control: public, max-age=3600\r\n')
        except OSError:
            # Frozen-firmware fallback: serve embedded CSS when no static file
            if fname == 'style.css' and EMBEDDED_CSS:
                self._send(conn, 200, ctype, EMBEDDED_CSS,
                           extra='Cache-Control: public, max-age=3600\r\n')
            else:
                self._send(conn, 404, 'text/plain', 'Not Found')

    # ---- Main request loop ----

    def handle_client(self):
        conn = None
        try:
            conn, _ = self.sock.accept()
            conn.settimeout(1.0)
            request = self._read_request(conn)
            if request is None:
                self._send(conn, 413, 'text/plain', 'Payload Too Large')
                return
            if not request:
                return

            if b'\r\n\r\n' in request:
                headers_part, body_part = request.split(b'\r\n\r\n', 1)
            else:
                headers_part, body_part = request, b''

            headers_str = headers_part.decode('utf-8', 'ignore')
            lines = headers_str.split('\r\n')
            if not lines or not lines[0]:
                self._send(conn, 400, 'text/plain', 'Bad Request')
                return

            parts = lines[0].split()
            if len(parts) < 2:
                self._send(conn, 400, 'text/plain', 'Bad Request')
                return
            method, raw_path = parts[0], parts[1]

            if not self._authorized(headers_str):
                self._send(conn, 401, 'text/html', '<h1>401 Unauthorized</h1>',
                           extra='WWW-Authenticate: Basic realm="MatrixLED"\r\n')
                return

            # Static files
            if raw_path.startswith('/static/'):
                self._serve_static(conn, raw_path[8:])
                return

            params = {}
            if '?' in raw_path:
                raw_path, query = raw_path.split('?', 1)
                params = self._parse_query(query)

            # Multipart upload (only to /upload)
            if method == 'POST' and raw_path == '/upload' and 'multipart/form-data' in headers_str:
                boundary = None
                for line in lines:
                    if 'boundary=' in line:
                        boundary = line.split('boundary=')[1].strip()
                        break
                if not boundary:
                    self._send(conn, 400, 'text/plain', 'No boundary')
                    return
                ok, err = self._handle_upload(body_part, boundary.encode())
                if ok:
                    response = '<script>window.location="/?u=1"</script>'
                else:
                    msg = (err or 'Upload failed').replace("'", "\\'").replace('"', '\\"')
                    response = '<script>alert("Upload failed: %s");window.location="/"</script>' % msg
                self._send(conn, 200, 'text/html', response)
                return

            handler = self.handlers.get(raw_path)
            if handler is None:
                self._send(conn, 404, 'text/html', '<h1>404 Not Found</h1>')
                return
            allowed_methods, func = handler
            if method not in allowed_methods:
                self._send(conn, 405, 'text/plain', 'Method Not Allowed',
                           extra='Allow: %s\r\n' % ', '.join(sorted(allowed_methods)))
                return

            content_type, content_disposition = 'text/html', None
            result = func(params)
            if isinstance(result, tuple) and len(result) == 3:
                content_type, content_disposition, result = result

            self._send(conn, 200, content_type, result, content_disposition=content_disposition)

            # Deferred reboot: response already flushed to the socket
            if self.pending_reset:
                time.sleep_ms(300)
                import machine
                machine.reset()
        except MemoryError:
            gc.collect()
        except OSError:
            pass
        except Exception as e:
            try:
                print('HTTP error: %s' % e)
                if conn:
                    self._send(conn, 500, 'text/plain', 'Server Error')
            except Exception:
                pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            gc.collect()

    # ---- Upload handling ----

    def _handle_upload(self, body_bytes, boundary):
        boundary_bytes = b'--' + boundary
        parts = body_bytes.split(boundary_bytes)
        ok = True
        error_message = None

        for part in parts:
            if b'filename="' not in part:
                continue
            try:
                if b'\r\n\r\n' not in part:
                    continue
                headers, content = part.split(b'\r\n\r\n', 1)
                headers_str = headers.decode('utf-8', 'ignore')
                filename = headers_str.split('filename="')[1].split('"')[0]

                # Strip multipart framing
                while content.endswith(b'\r\n'):
                    content = content[:-2]
                if content.endswith(b'--'):
                    content = content[:-2]
                while content.endswith(b'\r\n'):
                    content = content[:-2]

                # Animations (.json)
                if filename.endswith('.json'):
                    try:
                        os.listdir('drawings')
                    except OSError:
                        os.mkdir('drawings')
                    with open('drawings/' + filename, 'wb') as f:
                        f.write(content)
                    print('Uploaded animation: %s (%d bytes)' % (filename, len(content)))
                    continue

                # OTA updates (.py)
                if filename.endswith('.py'):
                    if '/' in filename or '..' in filename:
                        ok, error_message = False, 'Invalid filename'
                        continue
                    if len(content) > 512000:
                        ok, error_message = False, 'File too large (max 500KB)'
                        continue

                    gc.collect()
                    try:
                        source = content.decode('utf-8')
                        compile(source, filename, 'exec')
                        del source
                    except SyntaxError as e:
                        ok = False
                        error_message = 'Syntax error'
                        print('Upload rejected (syntax): %s: %s' % (filename, e))
                        continue
                    except MemoryError:
                        ok = False
                        error_message = 'Not enough memory to validate'
                        gc.collect()
                        continue
                    except Exception as e:
                        ok = False
                        error_message = 'Validation error'
                        print('Upload rejected (validation): %s' % e)
                        continue

                    try:
                        os.listdir('backups')
                    except OSError:
                        os.mkdir('backups')

                    gc.collect()
                    if filename in os.listdir('.'):
                        try:
                            t = time.localtime()
                            ts = '%d%02d%02d_%02d%02d%02d' % (t[0], t[1], t[2], t[3], t[4], t[5])
                            backup_name = '%s.bak_%s' % (filename, ts)
                            with open(filename, 'rb') as src:
                                with open('backups/' + backup_name, 'wb') as dst:
                                    while True:
                                        chunk = src.read(1024)
                                        if not chunk:
                                            break
                                        dst.write(chunk)
                            print('Backup created: %s' % backup_name)
                            self._cleanup_old_backups(filename)
                        except Exception as e:
                            print('Backup warning: %s' % e)

                    gc.collect()
                    with open(filename, 'wb') as f:
                        f.write(content)
                    print('OTA updated: %s (%d bytes)' % (filename, len(content)))
                    gc.collect()
                else:
                    ok, error_message = False, 'Only .py and .json allowed'
            except Exception as e:
                print('Upload error: %s' % e)
                ok = False
                error_message = str(e)

        return (ok, error_message)

    def _cleanup_old_backups(self, filename):
        try:
            backups = [f for f in os.listdir('backups') if f.startswith('%s.bak_' % filename)]
            if len(backups) > 5:
                backups.sort()
                for old in backups[:-5]:
                    os.remove('backups/' + old)
                    print('Deleted old backup: %s' % old)
        except Exception as e:
            print('Cleanup backups error: %s' % e)

    def _not_found(self, params):
        return '<h1>404 Not Found</h1>'


def _fx_button(name, label, icon):
    return '<button class="fx" data-name="%s" onclick="setEffect(\'%s\')" title="%s">%s<span>%s</span></button>' % (
        name, name, label, icon, label)


def create_config_html():
    """First-boot WiFi setup page (served in AP setup mode)."""
    return '''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Matrix LED · Setup</title>
<link rel="stylesheet" href="/static/style.css">
<style>
.setup{max-width:420px;margin:0 auto;padding:20px}
.setup h1{font-size:20px;margin-bottom:4px;text-align:center}
.setup .sub{text-align:center;color:var(--text-dim);font-size:12px;margin-bottom:22px;font-family:var(--mono)}
.setup label{font-size:11px;color:var(--text-dim);display:block;margin:14px 0 6px;font-weight:500;text-transform:uppercase;letter-spacing:.04em}
.setup .row{display:flex;gap:8px}
.setup .row .input{flex:1}
.setup .scan-btn{flex-shrink:0;width:auto;padding:0 12px}
.field-note{font-size:10px;color:var(--text-faint);margin-top:4px;font-family:var(--mono)}
.setup .btn{width:100%;margin-top:22px;height:42px;font-size:14px}
.spin{display:inline-block;width:14px;height:14px;border:2px solid var(--border-hi);border-top-color:var(--accent);border-radius:50%;animation:sp 1s linear infinite;vertical-align:-2px;margin-right:6px}
@keyframes sp{to{transform:rotate(360deg)}}
</style></head><body>
<div class="setup">
<div style="text-align:center;margin-bottom:6px"><span class="logo">__LOGO__</span></div>
<h1>Matrix LED</h1>
<div class="sub">First-time setup &middot; connect me to WiFi</div>

<label>WiFi network</label>
<div class="row">
<select id="ssid" class="input"><option value="">-- Select network --</option></select>
<button class="btn scan-btn" onclick="doScan()"><span id="scanLbl">Scan</span></button>
</div>
<input type="text" id="ssidManual" class="input" style="margin-top:8px;display:none" placeholder="...or type SSID manually">

<label>WiFi password</label>
<input type="password" id="pwd" class="input" placeholder="Password">
<div class="field-note" id="pwdNote"></div>

<label>UI password <span style="text-transform:none;color:var(--text-faint)">(optional, protects the dashboard)</span></label>
<input type="text" id="webpwd" class="input" placeholder="Leave empty for open access">

<button class="btn btn-primary" onclick="save()">Save &amp; reboot</button>
<div class="sub" style="margin-top:18px">The device will reboot and join your network.</div>
</div>
<script>
function doScan(){var l=document.getElementById('scanLbl');l.innerHTML='<span class="spin"></span>Scanning';fetch('/scan').then(function(r){return r.json()}).then(function(n){var s=document.getElementById('ssid');s.innerHTML='<option value="">-- Select network --</option>';n.sort(function(a,b){return b.rssi-a.rssi});n.forEach(function(x){var o=document.createElement('option');o.value=x.ssid;o.textContent=x.ssid+(x.secure?' \u25CF':'')+' ('+x.rssi+'dBm)';s.appendChild(o)});l.textContent='Rescan'}).catch(function(){l.textContent='Scan';alert('Scan failed - type SSID manually')})}
function save(){var sel=document.getElementById('ssid').value;var man=document.getElementById('ssidManual');var ssid=man.style.display!=='none'?man.value:sel;var pwd=document.getElementById('pwd').value;var wp=document.getElementById('webpwd').value;if(!ssid){alert('Pick or type a network');return}var u='/save_config?ssid='+encodeURIComponent(ssid)+'&password='+encodeURIComponent(pwd);if(wp)u+='&web_password='+encodeURIComponent(wp);fetch(u,{method:'POST'}).then(function(){document.body.innerHTML='<div style="text-align:center;padding:60px;color:#9098a4;font-family:monospace"><h2>Rebooting...</h2><p>Joining '+ssid+'</p></div>'}).catch(function(){alert('Save failed')})}
document.getElementById('ssid').addEventListener('change',function(){document.getElementById('pwdNote').textContent=this.value?'':'If unsure, leave blank for open networks';var m=document.getElementById('ssidManual');if(!this.value)m.style.display='block';else m.style.display='none'});
doScan();
</script>
</body></html>'''.replace('__LOGO__', ICONS['logo'])


def create_html(effect_name, animations, files, tz_value=0, manual_dt=None,
                brightness=4, contrast=1.0, flip_x=False, flip_y=False,
                invert_colors=False, flash=None, ip=None, ap_mode=False):
    ic = ICONS

    def sel(v):
        return ' selected' if tz_value == v else ''

    manual_dt_attr = ' value="%s"' % manual_dt if manual_dt else ''
    flip_x_chk = ' checked' if flip_x else ''
    flip_y_chk = ' checked' if flip_y else ''
    invert_chk = ' checked' if invert_colors else ''
    ip_text = ip if ip else '--'

    toast = ''
    if flash:
        cls = 'toast error' if flash.get('error') else 'toast'
        toast = '<div class="%s" id="toast">%s</div>' % (cls, flash.get('msg', ''))

    fx = [_fx_button(n, l, ic[k]) for n, l, k in [
        ('matrix', 'Rain', 'rain'), ('life', 'Life', 'life'), ('clock', 'Clock', 'clock'),
        ('fire', 'Fire', 'fire'), ('wave', 'Wave', 'wave'), ('spectrum', 'Spec', 'spectrum'),
        ('stars', 'Stars', 'stars'), ('binary', 'Binary', 'binary'), ('plasma', 'Plasma', 'plasma'),
        ('equalizer', 'EQ', 'equalizer'), ('maze', 'Maze', 'maze')]]
    fx_html = ''.join(fx)

    P = []
    P.append('<!DOCTYPE html><html lang="en"><head>'
             '<meta charset="UTF-8">'
             '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
             '<meta name="theme-color" content="#07080a">'
             '<title>Matrix LED</title>'
             '<link rel="stylesheet" href="/static/style.css">'
             '</head><body>')

    # Top bar
    P.append('<header class="topbar">'
             '<div class="brand"><span class="logo">%s</span>'
             '<span>MATRIX LED<br><span class="tag">Control Center</span></span></div>'
             '<div class="pills">'
             '<span class="pill live"><span class="dot"></span>LIVE</span>'
             '<span class="pill" id="upPill">--</span>'
             '<span class="pill" id="memPill">--</span>'
             '<span class="pill">%s</span>'
             '</div></header>' % (ic['logo'], ip_text))

    P.append('<main class="grid">')

    # Hero (preview + current effect)
    P.append('<section class="card hero span4">'
             '<div class="screen"><img id="displayPreview" src="/preview" onerror="this.style.opacity=0"></div>'
             '<div class="hero-meta">'
             '<span class="badge">%s</span>'
             '<span class="hint">32&times;8 live</span>'
             '</div></section>' % effect_name)

    # Speed
    P.append('<section class="card span8">'
             '<div class="card-head">%s Speed <span class="val" id="speedValue">1.0x</span></div>'
             '<input type="range" min="0.1" max="10.0" step="0.1" value="1.0" id="speedSlider" onchange="setSpeed(this.value)">'
             '</section>' % ic['speed'])

    # Effects
    P.append('<section class="card">'
             '<div class="card-head">%s Effects</div>'
             '<div class="fx-grid">%s</div>'
             '</section>' % (ic['gauge'], fx_html))

    # Text
    P.append('<section class="card span6">'
             '<div class="card-head">%s Marquee</div>'
             '<input type="text" id="text" placeholder="Type a message..." class="input" style="margin-bottom:10px">'
             '<div class="g3">'
             '<button class="btn" onclick="setText(\'scroll\')">%s Scroll</button>'
             '<button class="btn" onclick="setText(\'typewriter\')">%s Type</button>'
             '<button class="btn" onclick="setText(\'hacker\')">%s Hack</button>'
             '</div><div class="g2" style="margin-top:8px">'
             '<button class="btn btn-ghost btn-sm" onclick="toCase(\'upper\')">UPPERCASE</button>'
             '<button class="btn btn-ghost btn-sm" onclick="toCase(\'lower\')">lowercase</button>'
             '</div></section>' % (ic['text'], ic['scroll'], ic['type'], ic['hack']))

    # Rack monitor
    P.append('<section class="card span6">'
             '<div class="card-head">%s Rack Monitor</div>'
             '<div class="rack-grid">'
             '<div class="reading">%s<div class="num" id="rackTemp">--</div><div class="unit">&#176;C temp</div></div>'
             '<div class="reading">%s<div class="num" id="rackHum">--</div><div class="unit">%% rh</div></div>'
             '<div class="reading">%s<div class="num" id="rackPress">--</div><div class="unit">hPa</div></div>'
              '</div></section>' % (ic['rack'], ic['temp'], ic['humidity'], ic['pressure']))

    # DEFCON threat panel
    P.append('<section class="card threat">'
             '<div class="card-head">%s Threat Monitor <span class="threat-modes" id="threatMode">--</span></div>'
             '<div class="threat-head"><span class="defcon-badge lv5" id="defconBadge">DC 5</span>'
             '<span style="font-size:11px;color:var(--text-dim)" id="defconLabel">All clear</span></div>'
             '<div id="threatDetails"><div class="mac-note">Monitoring Wi-Fi for deauth attacks...</div></div>'
             '</section>' % ic['shield'])

    # Timezone / time
    P.append('<section class="card span6">'
             '<div class="card-head">%s Time</div>'
             '<select id="timezone" class="input" style="margin-bottom:10px" onchange="setTimezone()">'
             '<option value="0"%s>UTC &middot; London</option>'
             '<option value="1"%s>CET &middot; Madrid</option>'
             '<option value="2"%s>EET &middot; Athens</option>'
             '<option value="-5"%s>EST &middot; New York</option>'
             '<option value="-6"%s>CST &middot; Chicago</option>'
             '<option value="-8"%s>PST &middot; LA</option>'
             '<option value="9"%s>JST &middot; Tokyo</option>'
             '<option value="8"%s>CST &middot; Beijing</option>'
             '</select>'
             '<div style="display:flex;gap:8px">'
             '<input type="datetime-local" id="manualDateTime" class="input"%s>'
             '<button class="btn btn-sm" onclick="setManualTime()">Set</button>'
             '</div></section>' % (ic['clock'], sel(0), sel(1), sel(2), sel(-5), sel(-6),
                                   sel(-8), sel(9), sel(8), manual_dt_attr))

    # Display settings
    P.append('<section class="card span6">'
             '<div class="card-head">%s Display</div>'
             '<label class="lbl">Brightness <span id="brightnessValue">%d</span>/15</label>'
             '<input type="range" min="0" max="15" step="1" value="%d" id="brightnessSlider" onchange="setBrightness(this.value)">'
             '<label class="lbl">Contrast <span id="contrastValue">%s</span></label>'
             '<input type="range" min="0.5" max="2.0" step="0.1" value="%s" id="contrastSlider" onchange="setContrast(this.value)">'
             '<div class="g3" style="margin-top:10px">'
             '<label class="toggle"><input type="checkbox" id="flipXChk" onchange="toggleFlip(\'x\')"%s><span class="track"></span>Flip X</label>'
             '<label class="toggle"><input type="checkbox" id="flipYChk" onchange="toggleFlip(\'y\')"%s><span class="track"></span>Flip Y</label>'
             '<label class="toggle"><input type="checkbox" id="invertChk" onchange="toggleInvert()"%s><span class="track"></span>Invert</label>'
             '</div>'
             '<button class="btn btn-ghost btn-sm" style="margin-top:10px;width:100%%" onclick="resetDisplay()">Reset to defaults</button>'
             '</section>' % (ic['sun'], brightness, brightness, contrast, contrast,
                             flip_x_chk, flip_y_chk, invert_chk))

    # Animations
    P.append('<section class="card span6">'
             '<div class="card-head">%s Library</div>'
             '<div class="fx-grid" style="grid-template-columns:repeat(2,1fr)">%s</div>'
             '</section>' % (ic['stars'], animations))

    # Animation upload + file list
    P.append('<section class="card span6">'
             '<div class="card-head">%s Upload Sprite</div>'
             '<form action="/upload" method="post" enctype="multipart/form-data" style="margin-bottom:8px">'
             '<input type="file" name="file" accept=".json">'
             '<button type="submit" class="btn btn-sm" style="margin-top:6px">%s Upload JSON</button>'
             '</form>'
             '<div class="file-list">%s</div>'
             '</section>' % (ic['upload'], ic['upload'], files))

    # OTA
    P.append('<section class="card span6">'
             '<div class="card-head">%s OTA Updates</div>'
             '<form action="/upload" method="post" enctype="multipart/form-data" id="otaForm" style="margin-bottom:8px">'
             '<input type="file" name="file" accept=".py" id="pyFile">'
             '<button type="submit" class="btn btn-primary btn-sm" style="margin-top:6px">%s Upload .py</button>'
             '</form>'
             '<div class="hint" style="margin-bottom:8px">Remote code updates with auto-backup</div>'
             '<button class="btn btn-danger btn-sm" style="width:100%%" onclick="restartDevice()">%s Restart device</button>'
             '</section>' % (ic['ota'], ic['ota'], ic['restart']))

    P.append('</main>')

    P.append('<div class="footer">MATRIX LED <span>&middot;</span> 0x7EA <span>&middot;</span> v3.0 <span>&middot;</span> idiotsandwich.club</div>')
    P.append(toast)

    P.append('''<script>
function post(u){return fetch(u,{method:'POST'})}
function setEffect(n){post('/effect?name='+n).then(()=>location.reload())}
function setTimezone(){post('/effect?name=clock&tz='+document.getElementById('timezone').value).then(()=>location.reload())}
function setManualTime(){var dt=document.getElementById('manualDateTime').value;if(dt)post('/set_time?datetime='+encodeURIComponent(dt)).then(()=>location.reload())}
function setText(m){post('/marquee?text='+encodeURIComponent(document.getElementById('text').value)+'&mode='+m).then(()=>location.reload())}
function toCase(c){var t=document.getElementById('text');t.value=c==='upper'?t.value.toUpperCase():t.value.toLowerCase()}
function setSpeed(v){document.getElementById('speedValue').textContent=parseFloat(v).toFixed(1)+'x';post('/speed?val='+v)}
function setBrightness(v){document.getElementById('brightnessValue').textContent=v;post('/display?brightness='+v)}
function setContrast(v){document.getElementById('contrastValue').textContent=parseFloat(v).toFixed(1);post('/display?contrast='+v)}
function toggleFlip(a){var v=document.getElementById(a==='x'?'flipXChk':'flipYChk').checked;post('/display?flip_'+a+'='+v)}
function toggleInvert(){var v=document.getElementById('invertChk').checked;post('/display?invert_colors='+v)}
function resetDisplay(){if(confirm('Reset all display settings?')){post('/display?reset=true').then(()=>location.reload())}}
function playAnim(f){post('/animation?file='+f).then(()=>location.reload())}
function downloadFile(f){window.location.href='/download?file='+f}
var delFile=null;
function deleteFile(f){delFile=f;showModal('Delete sprite','Delete '+f+'?')}
function confirmDelete(){if(delFile)post('/delete?file='+encodeURIComponent(delFile)).then(()=>location.reload());hideModal()}
function showModal(t,c){var o=document.createElement('div');o.className='modal-overlay show';o.innerHTML='<div class="modal"><div class="modal-header">'+t+'</div><div class="modal-content">'+c+'</div><div class="modal-actions"><button class="btn btn-sm" onclick="hideModal()">Cancel</button><button class="btn btn-danger btn-sm" id="modalOk">Delete</button></div></div>';o.onclick=function(e){if(e.target===o)hideModal()};document.body.appendChild(o);document.getElementById('modalOk').onclick=confirmDelete}
function hideModal(){var o=document.querySelector('.modal-overlay');if(o){o.classList.remove('show');setTimeout(function(){o.remove()},150)}delFile=null}
function updatePreview(){var img=document.getElementById('displayPreview');if(img)img.src='/preview?'+Date.now()}
function updateRack(){fetch('/rack').then(function(r){return r.text()}).then(function(d){try{var j=JSON.parse(d);if(j.error){set('rackTemp','--');set('rackHum','--');set('rackPress','--')}else{set('rackTemp',j.temperature!=null?j.temperature.toFixed(1):'--');set('rackHum',j.humidity!=null?j.humidity.toFixed(1):'--');set('rackPress',j.pressure!=null?j.pressure.toFixed(0):'--')}}catch(e){}}).catch(function(){})}
function set(id,v){var e=document.getElementById(id);if(e)e.textContent=v}
function updateHealth(){fetch('/health').then(function(r){return r.json()}).then(function(h){var m=Math.round(h.free_mem/1024);var up=h.uptime_s;var mm=Math.floor(up/60),ss=up%60;set('memPill',m+'KB');set('upPill',mm+'m'+(ss<10?'0':'')+ss+'s')}).catch(function(){})}
document.getElementById('otaForm').onsubmit=function(e){var f=document.getElementById('pyFile').files[0];if(f&&!f.name.endsWith('.py')){alert('Select a .py file');e.preventDefault();return false}if(f&&f.size>512000){alert('File too large (max 500KB)');e.preventDefault();return false}if(f){var crit=['webserver.py','main.py'];if(crit.indexOf(f.name)>=0){if(!confirm('WARNING: '+f.name+' is critical! A bad upload bricks remote access. A backup is made. Continue?')){e.preventDefault();return false}}else if(!confirm('Upload '+f.name+'? A backup is created automatically.')){e.preventDefault();return false}}}
function restartDevice(){if(confirm('Restart ESP32? Reboots in ~10s.')){post('/ota/restart').then(function(){document.body.innerHTML='<div style="text-align:center;padding:80px;color:#9098a4;font-family:monospace"><h2>Rebooting...</h2></div>';setTimeout(function(){location.reload()},10000)})}}
function updateThreats(){fetch('/threats').then(function(r){return r.json()}).then(function(t){var b=document.getElementById('defconBadge');var l=document.getElementById('defconLabel');var m=document.getElementById('threatMode');var d=document.getElementById('threatDetails');if(!b)return;var lv=t.defcon||5;b.className='defcon-badge lv'+lv;b.textContent='DC '+lv;var labels=['','CRITICAL - under attack','HIGH - attack suspected','ELEVATED','GUARDED','All clear'];l.textContent=labels[lv]||'Unknown';m.textContent=t.mode||'none';if(t.mode!=='frames'){d.innerHTML='<div class="mac-note">Frame-level detection needs compiled firmware. Using connection monitor.</div>';return}var html='';if(t.target_bssid)html+='<div class="mac-row"><span class="mac-label">Target AP BSSID</span><span class="mac-val">'+t.target_bssid+'</span></div>';if(t.last_src)html+='<div class="mac-row"><span class="mac-label">Source (spoofed?)</span><span class="mac-val">'+t.last_src+'</span></div>';if(t.victim)html+='<div class="mac-row"><span class="mac-label">Victim</span><span class="mac-val">'+t.victim+'</span></div>';if(t.recent_sources&&t.recent_sources.length)html+='<div class="mac-row"><span class="mac-label">MACs seen ('+t.total_deauths+' frames)</span><span class="mac-val">'+t.recent_sources.join(' ')+'</span></div>';if(!html)html=t.under_attack?'<div class="mac-note">Attack in progress, capturing...</div>':'<div class="mac-note">No deauth frames detected.</div>';else if(t.under_attack)html+='<div class="mac-note">Source is usually the spoofed AP BSSID, not the real attacker.</div>';d.innerHTML=html}).catch(function(){})}
setInterval(updatePreview,600);setInterval(updateRack,5000);setInterval(updateHealth,4000);setInterval(updateThreats,3000);
updateRack();updateHealth();updateThreats();
setTimeout(function(){var t=document.getElementById('toast');if(t)t.remove()},3500);
(function(){var b=(document.querySelector('.badge')||{}).textContent||'';b=b.toLowerCase();var map={matrix:'matrix',life:'game of life',clock:'clock',fire:'fire',wave:'wave',spectrum:'spectrum',stars:'stars',binary:'binary clock',plasma:'plasma',equalizer:'equalizer',maze:'maze runner','marquee':'marquee','news':'news'};var keys=Object.keys(map);[].forEach.call(document.querySelectorAll('.fx'),function(el){var m=map[el.dataset.name];if(m&&b.indexOf(m)===0)el.classList.add('on')})})();
</script>''')

    P.append('</body></html>')
    return ''.join(P)

"""
Best-effort Telegram alert sender for the IDIOT monitor.

Sends a text message to a chat via the Telegram Bot API over HTTPS. Any
failure is silently swallowed so Wi-Fi monitoring is never interrupted.
"""
import socket


def send_alert(token, chat_id, text):
    if not token or not chat_id:
        return False
    try:
        import ssl
    except ImportError:
        return False

    host = 'api.telegram.org'
    s = None
    try:
        path = '/bot%s/sendMessage' % token
        body = 'chat_id=%s&text=%s' % (chat_id, _urlencode(text))
        body_b = body.encode('utf-8')
        addr = socket.getaddrinfo(host, 443)[0][-1]
        s = socket.socket()
        s.settimeout(8)
        s.connect(addr)
        try:
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=host)
        except Exception:
            s = ssl.wrap_socket(s, server_hostname=host)
        req = ('POST %s HTTP/1.1\r\n'
               'Host: %s\r\n'
               'Content-Type: application/x-www-form-urlencoded\r\n'
               'Content-Length: %d\r\n'
               'Connection: close\r\n\r\n') % (path, host, len(body_b))
        s.write(req.encode('utf-8'))
        s.write(body_b)
        resp = s.read(256)
        return b'"ok":true' in resp or b' 200 ' in resp[:30]
    except Exception:
        return False
    finally:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass


def _urlencode(s):
    out = []
    for c in s:
        o = ord(c)
        if (ord('A') <= o <= ord('Z')) or (ord('a') <= o <= ord('z')) or \
           (ord('0') <= o <= ord('9')) or c in '-_.~':
            out.append(c)
        else:
            for byte in c.encode('utf-8'):
                out.append('%%%02X' % byte)
    return ''.join(out)

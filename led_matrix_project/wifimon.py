"""
WiFi attack (deauth) detector with two detection modes:

  1) Frame-level (preferred, requires the deauth_sniffer C module baked into
     firmware): counts actual deauth/disassoc frames in the air via monitor
     mode. Catches attacks against ANY nearby network (Marauder, Bruce, ...).

  2) Connection-level (fallback, pure Python): detects the *symptom* of a
     deauth flood - the device's own connection churns. Always available.

The module auto-selects the best available mode. DEFCON 5 = peace, 1 = attack.
"""
import time

try:
    import deauth_sniffer
    _C_AVAILABLE = True
except ImportError:
    _C_AVAILABLE = False

_WINDOW_S = 60
_CHECK_MS = 2000


class WifiMonitor:
    def __init__(self, wlan=None, window_s=_WINDOW_S):
        self.wlan = wlan
        self.window_s = window_s
        self.events = []          # list of (timestamp_ms, count) within window
        self.last_check = time.ticks_ms()
        self.connected = self._is_connected()
        self.defcon = 5
        self.mode = 'connection'
        self._last_total = 0
        self._start_c_sniffer()

    def _is_connected(self):
        if self.wlan is None:
            return False
        try:
            return self.wlan.isconnected()
        except Exception:
            return self.connected

    def _start_c_sniffer(self):
        if not _C_AVAILABLE:
            return
        try:
            ok = deauth_sniffer.start()
            if ok == 0:
                self.mode = 'frames'
                print('DEFCON: frame-level deauth sniffer active')
            else:
                print('DEFCON: C sniffer start failed, using connection monitor')
        except Exception as e:
            print('DEFCON: C sniffer error: %s' % e)

    def update(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_check) < _CHECK_MS:
            return self.defcon
        self.last_check = now

        if self.mode == 'frames':
            try:
                total = deauth_sniffer.count()
                new = total - self._last_total if total >= self._last_total else 0
                self._last_total = total
                if new > 0:
                    self.events.append((now, new))
            except Exception:
                pass
        else:
            conn = self._is_connected()
            if self.connected and not conn:
                self.events.append((now, 1))
            self.connected = conn

        cutoff = time.ticks_add(now, -self.window_s * 1000)
        self.events = [(t, c) for (t, c) in self.events if time.ticks_diff(t, cutoff) > 0]

        n = 0
        for (t, c) in self.events:
            n += c

        if self.mode == 'frames':
            self.defcon = self._frame_defcon(n)
        else:
            self.defcon = self._conn_defcon(n)
        return self.defcon

    @staticmethod
    def _conn_defcon(n):
        if n <= 1:
            return 5
        if n <= 3:
            return 4
        if n <= 6:
            return 3
        if n <= 10:
            return 2
        return 1

    @staticmethod
    def _frame_defcon(n):
        if n <= 3:
            return 5
        if n <= 9:
            return 4
        if n <= 19:
            return 3
        if n <= 39:
            return 2
        return 1

    @property
    def under_attack(self):
        return self.defcon <= 2

    def threat_info(self):
        """Return a dict with DEFCON level, mode and attacker MAC details
        (only meaningful in frames mode)."""
        info = {'defcon': self.defcon, 'mode': self.mode,
                'under_attack': self.under_attack}
        if self.mode == 'frames' and _C_AVAILABLE:
            try:
                info['total_deauths'] = deauth_sniffer.count()
                src = deauth_sniffer.last_src()
                bssid = deauth_sniffer.last_bssid()
                dst = deauth_sniffer.last_dst()
                if src and len(src) == 6:
                    info['last_src'] = _format_mac(src)
                if bssid and len(bssid) == 6:
                    info['target_bssid'] = _format_mac(bssid)
                if dst and len(dst) == 6:
                    info['victim'] = _format_mac(dst)
                raw = deauth_sniffer.recent_sources()
                seen = set()
                macs = []
                for i in range(0, len(raw), 6):
                    chunk = raw[i:i + 6]
                    if len(chunk) == 6 and any(chunk):
                        m = _format_mac(chunk)
                        if m not in seen:
                            seen.add(m)
                            macs.append(m)
                if macs:
                    info['recent_sources'] = macs
            except Exception:
                pass
        return info


def _format_mac(b):
    return ':'.join('%02X' % c for c in b)

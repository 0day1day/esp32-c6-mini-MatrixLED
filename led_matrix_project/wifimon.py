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
        self._ssid_cache = {}          # bssid str -> ssid str (resolved via scan)
        self._last_scan = 0
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

    def resolve_bssid(self, mac):
        """Return cached SSID for a BSSID/MAC string, or None."""
        return self._ssid_cache.get(mac)

    def rescan_ssids(self, wlan):
        """Pause the sniffer, perform a Wi-Fi scan and cache BSSID->SSID
        for every nearby AP. Best-effort: failures are ignored."""
        if self.mode != 'frames' or wlan is None:
            return
        paused = False
        try:
            deauth_sniffer.stop()
            paused = True
        except Exception:
            pass
        try:
            nets = wlan.scan()
            for entry in nets:
                try:
                    ssid = entry[0]
                    bssid = entry[1]
                    s = ssid.decode('utf-8', 'ignore') if isinstance(ssid, (bytes, bytearray)) else ssid
                    m = _format_mac(bssid)
                    if m not in self._ssid_cache and s:
                        self._ssid_cache[m] = s
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            if paused:
                try:
                    deauth_sniffer.start()
                except Exception:
                    pass

    def threat_info(self):
        """Return a dict with DEFCON level, mode, attacker MAC details,
        attack type/subtype and resolved SSID names."""
        info = {'defcon': self.defcon, 'mode': self.mode,
                'under_attack': self.under_attack}
        if self.mode == 'frames' and _C_AVAILABLE:
            try:
                info['total_deauths'] = deauth_sniffer.count()
                src = deauth_sniffer.last_src()
                bssid = deauth_sniffer.last_bssid()
                dst = deauth_sniffer.last_dst()
                tbyte = deauth_sniffer.last_type()
                src_m = _format_mac(src) if src and len(src) == 6 else ''
                bssid_m = _format_mac(bssid) if bssid and len(bssid) == 6 else ''
                dst_m = _format_mac(dst) if dst and len(dst) == 6 else ''
                if src_m:
                    info['last_src'] = src_m
                    info['last_src_ssid'] = self.resolve_bssid(src_m)
                if bssid_m:
                    info['target_bssid'] = bssid_m
                    info['target_ssid'] = self.resolve_bssid(bssid_m)
                if dst_m:
                    info['victim'] = dst_m
                    info['victim_ssid'] = self.resolve_bssid(dst_m)
                # Attack type + subtype classification
                info['attack_type'] = 'Disassociation' if tbyte == 0xA0 else 'Deauth'
                if dst_m.upper() == 'FF:FF:FF:FF:FF:FF':
                    info['attack_subtype'] = 'Broadcast (kick all clients)'
                else:
                    info['attack_subtype'] = 'Targeted (single client)'
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
                    info['recent_sources_ssids'] = [self.resolve_bssid(m) for m in macs]
            except Exception:
                pass
        return info


def _format_mac(b):
    return ':'.join('%02X' % c for c in b)

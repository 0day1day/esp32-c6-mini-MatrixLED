/*
 * deauth_sniffer - native C user module for MicroPython (ESP32).
 *
 * Counts WiFi deauth/disassoc frames seen over the air via promiscuous mode
 * and extracts the management-frame addresses (victim DA, claimed source SA,
 * target AP BSSID). Used by wifimon.py to surface attack details.
 *
 * The callback runs on the IDF WiFi task, so it MUST NOT touch the Python VM.
 * It only mutates C state that Python polls later.
 */
#include "py/runtime.h"
#include "py/obj.h"
#include "esp_wifi.h"
#include "esp_err.h"

#define RING_LEN 8

static volatile uint32_t _deauth_count = 0;
static volatile uint8_t _started = 0;

/* Last seen frame addresses (6 bytes each). */
static volatile uint8_t _last_dst[6];   /* Address 1 - victim client (or broadcast) */
static volatile uint8_t _last_src[6];    /* Address 2 - claimed source (usually spoofed AP BSSID) */
static volatile uint8_t _last_bssid[6]; /* Address 3 - target AP BSSID (real, useful) */
static volatile uint8_t _have_last = 0;

/* Ring buffer of recent source MACs for deauth bursts. */
static volatile uint8_t _ring[RING_LEN * 6];
static volatile uint8_t _ring_idx = 0;

static int _is_zero(const uint8_t *m) {
    for (int i = 0; i < 6; i++) {
        if (m[i]) return 0;
    }
    return 1;
}

/* Promiscuous RX callback. Frame Control byte 0 & 0xFC: 0xC0 = deauth,
 * 0xA0 = disassociation. Management header is 24 bytes: Addr1=[4..9],
 * Addr2=[10..15], Addr3=[16..21]. */
static void _sniffer_cb(void *buf, wifi_promiscuous_pkt_type_t type) {
    if (type != WIFI_PKT_MGMT) {
        return;
    }
    const wifi_promiscuous_pkt_t *pkt = (const wifi_promiscuous_pkt_t *)buf;
    if (pkt->rx_ctrl.sig_len < 24) {
        return;
    }
    const uint8_t *f = pkt->payload;
    const uint8_t fc = f[0] & 0xFC;
    if (fc != 0xC0 && fc != 0xA0) {
        return;
    }
    _deauth_count++;

    /* Capture the three addresses. */
    for (int i = 0; i < 6; i++) {
        _last_dst[i] = f[4 + i];
        _last_src[i] = f[10 + i];
        _last_bssid[i] = f[16 + i];
        _ring[_ring_idx * 6 + i] = f[10 + i]; /* source MAC into ring */
    }
    _ring_idx = (_ring_idx + 1) % RING_LEN;
    _have_last = 1;
}

static mp_obj_t mod_start(void) {
    if (_started) {
        return mp_obj_new_int(0);
    }
    wifi_promiscuous_filter_t filt = {
        .filter_mask = WIFI_PROMIS_FILTER_MASK_MGMT,
    };
    esp_err_t e1 = esp_wifi_set_promiscuous_filter(&filt);
    esp_err_t e2 = esp_wifi_set_promiscuous_rx_cb(_sniffer_cb);
    esp_err_t e3 = esp_wifi_set_promiscuous(true);
    if (e1 == ESP_OK && e2 == ESP_OK && e3 == ESP_OK) {
        _started = 1;
        return mp_obj_new_int(0);
    }
    return mp_obj_new_int(-1);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_start_obj, mod_start);

static mp_obj_t mod_count(void) {
    return mp_obj_new_int_from_uint((uint32_t)_deauth_count);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_count_obj, mod_count);

static mp_obj_t mod_reset(void) {
    _deauth_count = 0;
    _have_last = 0;
    _ring_idx = 0;
    for (int i = 0; i < (RING_LEN * 6); i++) {
        _ring[i] = 0;
    }
    return mp_obj_new_int(0);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_reset_obj, mod_reset);

static mp_obj_t mod_stop(void) {
    esp_wifi_set_promiscuous(false);
    _started = 0;
    return mp_obj_new_int(0);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_stop_obj, mod_stop);

static mp_obj_t mod_available(void) {
    return mp_obj_new_int(1);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_available_obj, mod_available);

/* Return the most recent deauth source MAC (6 bytes) or empty bytes. */
static mp_obj_t mod_last_src(void) {
    if (!_have_last) {
        return mp_obj_new_bytes((const byte *)"", 0);
    }
    uint8_t out[6];
    for (int i = 0; i < 6; i++) {
        out[i] = _last_src[i];
    }
    return mp_obj_new_bytes(out, 6);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_last_src_obj, mod_last_src);

/* Return the most recent deauth target AP BSSID (6 bytes) or empty bytes. */
static mp_obj_t mod_last_bssid(void) {
    if (!_have_last) {
        return mp_obj_new_bytes((const byte *)"", 0);
    }
    uint8_t out[6];
    for (int i = 0; i < 6; i++) {
        out[i] = _last_bssid[i];
    }
    return mp_obj_new_bytes(out, 6);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_last_bssid_obj, mod_last_bssid);

/* Return the most recent deauth destination/victim MAC (6 bytes) or empty bytes. */
static mp_obj_t mod_last_dst(void) {
    if (!_have_last) {
        return mp_obj_new_bytes((const byte *)"", 0);
    }
    uint8_t out[6];
    for (int i = 0; i < 6; i++) {
        out[i] = _last_dst[i];
    }
    return mp_obj_new_bytes(out, 6);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_last_dst_obj, mod_last_dst);

/* Return the ring of recent source MACs (RING_LEN*6 bytes). */
static mp_obj_t mod_recent_sources(void) {
    uint8_t out[RING_LEN * 6];
    for (int i = 0; i < (RING_LEN * 6); i++) {
        out[i] = _ring[i];
    }
    return mp_obj_new_bytes(out, RING_LEN * 6);
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_recent_sources_obj, mod_recent_sources);

static const mp_rom_map_elem_t _module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_deauth_sniffer) },
    { MP_ROM_QSTR(MP_QSTR_start), MP_ROM_PTR(&mod_start_obj) },
    { MP_ROM_QSTR(MP_QSTR_count), MP_ROM_PTR(&mod_count_obj) },
    { MP_ROM_QSTR(MP_QSTR_reset), MP_ROM_PTR(&mod_reset_obj) },
    { MP_ROM_QSTR(MP_QSTR_stop), MP_ROM_PTR(&mod_stop_obj) },
    { MP_ROM_QSTR(MP_QSTR_available), MP_ROM_PTR(&mod_available_obj) },
    { MP_ROM_QSTR(MP_QSTR_last_src), MP_ROM_PTR(&mod_last_src_obj) },
    { MP_ROM_QSTR(MP_QSTR_last_bssid), MP_ROM_PTR(&mod_last_bssid_obj) },
    { MP_ROM_QSTR(MP_QSTR_last_dst), MP_ROM_PTR(&mod_last_dst_obj) },
    { MP_ROM_QSTR(MP_QSTR_recent_sources), MP_ROM_PTR(&mod_recent_sources_obj) },
};
static MP_DEFINE_CONST_DICT(_module_globals, _module_globals_table);

const mp_obj_module_t deauth_sniffer_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_deauth_sniffer, deauth_sniffer_user_cmodule);

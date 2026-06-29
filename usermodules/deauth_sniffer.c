/*
 * deauth_sniffer - native C user module for MicroPython (ESP32).
 *
 * Counts WiFi deauthentication / disassociation frames seen over the air
 * using the ESP-IDF promiscuous (monitor) mode. This catches attacks that
 * target ANY nearby network (Marauder, Bruce, etc.), not only the device's
 * own connection.
 *
 * Used by wifimon.py. The callback runs on the IDF WiFi task, so it MUST NOT
 * touch the Python VM / GIL. It only increments a C counter that Python polls.
 */
#include "py/runtime.h"
#include "py/obj.h"
#include "esp_wifi.h"
#include "esp_err.h"

static volatile uint32_t _deauth_count = 0;
static volatile uint8_t _started = 0;

/* Promiscuous RX callback. Frame Control byte 0: subtype(4)|type(2)|ver(2).
 * Management frames have type 00, so byte0 == subtype. 0xC0 = deauth,
 * 0xA0 = disassociation. Mask version bits (0xFC) before comparing. */
static void _sniffer_cb(void *buf, wifi_promiscuous_pkt_type_t type) {
    if (type != WIFI_PKT_MGMT) {
        return;
    }
    const wifi_promiscuous_pkt_t *pkt = (const wifi_promiscuous_pkt_t *)buf;
    const uint8_t fc = pkt->payload[0] & 0xFC;
    if (fc == 0xC0 || fc == 0xA0) {
        _deauth_count++;
    }
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

static const mp_rom_map_elem_t _module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_deauth_sniffer) },
    { MP_ROM_QSTR(MP_QSTR_start), MP_ROM_PTR(&mod_start_obj) },
    { MP_ROM_QSTR(MP_QSTR_count), MP_ROM_PTR(&mod_count_obj) },
    { MP_ROM_QSTR(MP_QSTR_reset), MP_ROM_PTR(&mod_reset_obj) },
    { MP_ROM_QSTR(MP_QSTR_stop), MP_ROM_PTR(&mod_stop_obj) },
    { MP_ROM_QSTR(MP_QSTR_available), MP_ROM_PTR(&mod_available_obj) },
};
static MP_DEFINE_CONST_DICT(_module_globals, _module_globals_table);

const mp_obj_module_t deauth_sniffer_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_deauth_sniffer, deauth_sniffer_user_cmodule);

"""Эмулятор VIA-клавиатуры: демо-режим и тесты без железа."""
from . import via
from .keycodes import BASIC

_DEFAULT_ROWS = [
    "ESC 1 2 3 4 5 6 7 8 9 0 MINS EQL BSPC GRV",
    "TAB Q W E R T Y U I O P LBRC RBRC BSLS DEL",
    "CAPS A S D F G H J K L SCLN QUOT NO ENT PGUP",
    "LSFT NO Z X C V B N M COMM DOT SLSH RSFT UP PGDN",
    "LCTL LGUI LALT NO NO NO SPC NO NO RALT NO RCTL LEFT DOWN RGHT",
    "NO NO NO NO NO NO NO NO NO NO NO NO NO NO NO",
]


class EmulatedKeyboard:
    def __init__(self, protocol=12, layers=4, macros=16, buffer_size=1024):
        self.protocol = protocol
        self.layers = layers
        self.macros = macros
        self.buffer = bytearray(buffer_size)
        self.values = {via.RGB_BRIGHTNESS: [180], via.RGB_EFFECT: [1],
                       via.RGB_SPEED: [128], via.RGB_COLOR: [170, 255]}
        self.saved = None
        base = [[BASIC["KC_" + n] for n in row.split()] for row in _DEFAULT_ROWS]
        self.keymap = [[row[:] for row in base]] + [
            [[0x01] * via.MATRIX_COLS for _ in range(via.MATRIX_ROWS)] for _ in range(layers - 1)]
        self._resp = None

    def write(self, data):
        d = bytes(data[1:])  # без report id
        cmd = d[0]
        r = bytearray(d)
        if cmd == via.CMD_GET_PROTOCOL_VERSION:
            r[1], r[2] = self.protocol >> 8, self.protocol & 0xFF
        elif cmd == via.CMD_GET_LAYER_COUNT:
            r[1] = self.layers
        elif cmd == via.CMD_GET_KEYCODE:
            kc = self.keymap[d[1]][d[2]][d[3]]
            r[4], r[5] = kc >> 8, kc & 0xFF
        elif cmd == via.CMD_SET_KEYCODE:
            self.keymap[d[1]][d[2]][d[3]] = (d[4] << 8) | d[5]
        elif cmd == via.CMD_CUSTOM_GET_VALUE and d[1] == via.CH_RGB_MATRIX:
            v = self.values[d[2]]
            r[3:3 + len(v)] = bytes(v)
        elif cmd == via.CMD_CUSTOM_SET_VALUE and d[1] == via.CH_RGB_MATRIX:
            n = len(self.values[d[2]])
            self.values[d[2]] = list(d[3:3 + n])
        elif cmd == via.CMD_CUSTOM_SAVE:
            self.saved = {k: list(v) for k, v in self.values.items()}
        elif cmd == via.CMD_MACRO_GET_COUNT:
            r[1] = self.macros
        elif cmd == via.CMD_MACRO_GET_BUFFER_SIZE:
            r[1], r[2] = len(self.buffer) >> 8, len(self.buffer) & 0xFF
        elif cmd == via.CMD_MACRO_GET_BUFFER:
            off, n = (d[1] << 8) | d[2], d[3]
            r[4:4 + n] = self.buffer[off:off + n]
        elif cmd == via.CMD_MACRO_SET_BUFFER:
            off, n = (d[1] << 8) | d[2], d[3]
            self.buffer[off:off + n] = d[4:4 + n]
        elif cmd == via.CMD_MACRO_RESET:
            self.buffer[:] = bytes(len(self.buffer))
        else:
            r = bytearray([via.CMD_UNHANDLED]) + r[1:]
        self._resp = bytes(r[:via.REPORT_SIZE])

    def read(self, size, timeout_ms):
        r, self._resp = self._resp, None
        return list(r or b"")

    def close(self):
        pass


def open_emulated(**kw):
    kb = via.ViaKeyboard(EmulatedKeyboard(**kw))
    kb.protocol = kb.get_protocol_version()
    return kb

"""Коды клавиш QMK: базовые HID-коды, модификаторы, слои, макросы."""

BASIC = {}


def _add(code, *names):
    for n in names:
        BASIC[n] = code


_add(0x00, "KC_NO")
_add(0x01, "KC_TRNS")
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _add(0x04 + i, "KC_" + ch)
for i, ch in enumerate("1234567890"):
    _add(0x1E + i, "KC_" + ch)
_add(0x28, "KC_ENT")
_add(0x29, "KC_ESC")
_add(0x2A, "KC_BSPC")
_add(0x2B, "KC_TAB")
_add(0x2C, "KC_SPC")
_add(0x2D, "KC_MINS")
_add(0x2E, "KC_EQL")
_add(0x2F, "KC_LBRC")
_add(0x30, "KC_RBRC")
_add(0x31, "KC_BSLS")
_add(0x33, "KC_SCLN")
_add(0x34, "KC_QUOT")
_add(0x35, "KC_GRV")
_add(0x36, "KC_COMM")
_add(0x37, "KC_DOT")
_add(0x38, "KC_SLSH")
_add(0x39, "KC_CAPS")
for i in range(12):
    _add(0x3A + i, f"KC_F{i + 1}")
_add(0x46, "KC_PSCR")
_add(0x47, "KC_SCRL")
_add(0x48, "KC_PAUS")
_add(0x49, "KC_INS")
_add(0x4A, "KC_HOME")
_add(0x4B, "KC_PGUP")
_add(0x4C, "KC_DEL")
_add(0x4D, "KC_END")
_add(0x4E, "KC_PGDN")
_add(0x4F, "KC_RGHT")
_add(0x50, "KC_LEFT")
_add(0x51, "KC_DOWN")
_add(0x52, "KC_UP")
_add(0x65, "KC_APP")
for i in range(12):
    _add(0x68 + i, f"KC_F{i + 13}")
_add(0xA5, "KC_PWR")
_add(0xA8, "KC_MUTE")
_add(0xA9, "KC_VOLU")
_add(0xAA, "KC_VOLD")
_add(0xAB, "KC_MNXT")
_add(0xAC, "KC_MPRV")
_add(0xAD, "KC_MSTP")
_add(0xAE, "KC_MPLY")
_add(0xE0, "KC_LCTL")
_add(0xE1, "KC_LSFT")
_add(0xE2, "KC_LALT")
_add(0xE3, "KC_LGUI")
_add(0xE4, "KC_RCTL")
_add(0xE5, "KC_RSFT")
_add(0xE6, "KC_RALT")
_add(0xE7, "KC_RGUI")

# Короткие подписи для сетки клавиш
LABELS = {v: k[3:] for k, v in BASIC.items() if k.startswith("KC_")}
LABELS[0x00] = ""
LABELS[0x01] = "▽"

MOD_BITS = {"R": 0x10, "C": 0x01, "S": 0x02, "A": 0x04, "G": 0x08}

# Пользовательские коды из VIA JSON NUT65 (по порядку QK_KB_0, QK_KB_1, …)
CUSTOM = [
    ("BT1", "BT1"), ("BT2", "BT2"), ("BT3", "BT3"), ("2.4G", "2.4G"), ("USB", "USB"),
    ("BATQ", "Заряд батареи"), ("L_TOG", "L_TOG"), ("LED_TOG", "Индикатор вкл/выкл"),
    ("DEB_TOG", "Режим задержки"), ("KC_TESTW", "Тест белым"), ("SYS_CUT", "Смена ОС"),
    ("RL_MOD", "Режим боковой подсветки"), ("MUS_CUT", "Музыкальный режим"),
    ("MUS_STA", "Калибровка музыки"), ("FREQU_T", "Тест частоты"),
    ("BT_TEST", "BT без пароля"), ("RL_VAI", "Боковая ярче"), ("RL_VAD", "Боковая тусклее"),
]


class Keycodes:
    """Диапазоны, зависящие от версии протокола VIA (до 12 и 12+)."""

    def __init__(self, protocol):
        self.v12 = protocol >= 12
        if self.v12:
            self.macro_base = 0x7700
            self.custom_base = 0x7E00
            self.mo_base, self.tg_base, self.to_base = 0x5220, 0x5260, 0x5200
            self.rgb = {0x7820: "RGB_TOG", 0x7821: "RGB_MOD", 0x7822: "RGB_RMOD",
                        0x7823: "RGB_HUI", 0x7824: "RGB_HUD", 0x7825: "RGB_SAI",
                        0x7826: "RGB_SAD", 0x7827: "RGB_VAI", 0x7828: "RGB_VAD",
                        0x7829: "RGB_SPI", 0x782A: "RGB_SPD"}
        else:
            self.macro_base = 0x5F12
            self.custom_base = 0x5F80
            self.mo_base, self.tg_base, self.to_base = 0x5100, 0x5300, 0x5010
            self.rgb = {}

    def macro(self, n):
        return self.macro_base + n

    def label(self, code):
        if code in LABELS:
            return LABELS[code]
        if self.macro_base <= code < self.macro_base + 16:
            return f"M{code - self.macro_base}"
        if self.custom_base <= code < self.custom_base + len(CUSTOM):
            return CUSTOM[code - self.custom_base][0]
        if self.mo_base <= code < self.mo_base + 16:
            return f"MO({code - self.mo_base})"
        if self.tg_base <= code < self.tg_base + 16:
            return f"TG({code - self.tg_base})"
        if code in self.rgb:
            return self.rgb[code]
        if 0x0100 <= code < 0x2000 and (code & 0xFF) in LABELS:
            mods = code >> 8
            prefix = "".join(k for k, b in MOD_BITS.items() if mods & b)
            return f"{prefix}+{LABELS[code & 0xFF]}"
        return f"0x{code:04X}"

    def parse(self, text):
        """Разбирает ввод пользователя: KC_A, M3, MO(1), 0x1234, C+KC_C."""
        t = text.strip().upper()
        if not t:
            raise ValueError("Пустой код")
        if t.startswith("0X"):
            return int(t, 16)
        if t in BASIC:
            return BASIC[t]
        if "KC_" + t in BASIC:
            return BASIC["KC_" + t]
        if t.startswith("M") and t[1:].isdigit():
            return self.macro(int(t[1:]))
        for name, base in (("MO", self.mo_base), ("TG", self.tg_base)):
            if t.startswith(name + "(") and t.endswith(")"):
                return base + int(t[len(name) + 1:-1])
        for code, name in self.rgb.items():
            if t == name:
                return code
        for i, (name, _) in enumerate(CUSTOM):
            if t == name.upper():
                return self.custom_base + i
        if "+" in t:
            mods, key = t.rsplit("+", 1)
            bits = 0
            for m in mods.replace("+", ""):
                if m not in MOD_BITS:
                    raise ValueError(f"Неизвестный модификатор {m}")
                bits |= MOD_BITS[m]
            return (bits << 8) | self.parse(key)
        raise ValueError(f"Неизвестный код клавиши: {text}")

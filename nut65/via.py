"""Протокол VIA (QMK raw HID) для Weikav NUT65.

Клавиатура отдаёт отдельный HID-интерфейс с usage page 0xFF60 / usage 0x61.
Обмен идёт пакетами по 32 байта: первый байт — команда, ответ эхом повторяет её.
"""
import time

VENDOR_ID = 0x342D
PRODUCT_ID = 0xE51A
USAGE_PAGE = 0xFF60
USAGE = 0x61
REPORT_SIZE = 32

# Команды VIA
CMD_GET_PROTOCOL_VERSION = 0x01
CMD_GET_KEYCODE = 0x04
CMD_SET_KEYCODE = 0x05
CMD_CUSTOM_SET_VALUE = 0x07
CMD_CUSTOM_GET_VALUE = 0x08
CMD_CUSTOM_SAVE = 0x09
CMD_MACRO_GET_COUNT = 0x0C
CMD_MACRO_GET_BUFFER_SIZE = 0x0D
CMD_MACRO_GET_BUFFER = 0x0E
CMD_MACRO_SET_BUFFER = 0x0F
CMD_MACRO_RESET = 0x10
CMD_GET_LAYER_COUNT = 0x11
CMD_UNHANDLED = 0xFF

# Канал и id значений подсветки (из официального VIA JSON NUT65)
CH_RGB_MATRIX = 3
RGB_BRIGHTNESS = 1
RGB_EFFECT = 2
RGB_SPEED = 3
RGB_COLOR = 4

MATRIX_ROWS = 6
MATRIX_COLS = 15

EFFECTS = [
    "All Off", "Solid Color", "Alphas Mods", "Gradient Up Down", "Gradient Left Right",
    "Breathing", "Band Sat", "Band Val", "Band Pinwheel Sat", "Band Pinwheel Val",
    "Band Spiral Sat", "Band Spiral Val", "Cycle All", "Cycle Left Right", "Cycle Up Down",
    "Rainbow Moving Chevron", "Cycle Out In", "Cycle Out In Dual", "Cycle Pinwheel",
    "Cycle Spiral", "Dual Beacon", "Rainbow Beacon", "Rainbow Pinwheels", "Raindrops",
    "Jellybean Raindrops", "Hue Breathing", "Hue Pendulum", "Hue Wave", "Pixel Rain",
    "Pixel Flow", "Pixel Fractal", "Typing Heatmap", "Digital Rain", "Solid Reactive Simple",
    "Solid Reactive", "Solid Reactive Wide", "Solid Reactive Multiwide", "Solid Reactive Cross",
    "Solid Reactive Multicross", "Solid Reactive Nexus", "Solid Reactive Multinexus", "Splash",
    "Multisplash", "Solid Splash", "Solid Multisplash", "Close All",
]
# Эффекты, у которых цвет не настраивается (как в VIA JSON)
EFFECTS_WITHOUT_COLOR = {0, 24, 28, 29, 32}

CHUNK = REPORT_SIZE - 4  # полезная нагрузка при чтении/записи буфера макросов


class ViaError(Exception):
    pass


def find_devices(hid_module=None, vid=VENDOR_ID, pid=PRODUCT_ID):
    """Ищет raw-HID интерфейсы VIA. Если vid/pid = None — любые VIA-устройства."""
    hid = hid_module or _import_hid()
    found = []
    for d in hid.enumerate():
        if d.get("usage_page") != USAGE_PAGE or d.get("usage") != USAGE:
            continue
        if vid is not None and d["vendor_id"] != vid:
            continue
        if pid is not None and d["product_id"] != pid:
            continue
        found.append(d)
    return found


def _import_hid():
    try:
        import hid  # пакет "hidapi"
    except ImportError as e:
        raise ViaError("Не установлен модуль hidapi: pip install hidapi") from e
    return hid


class ViaKeyboard:
    def __init__(self, transport):
        """transport — объект с методами write(bytes) и read(size, timeout_ms)."""
        self.t = transport
        self.protocol = 0

    @classmethod
    def open(cls, path, hid_module=None):
        hid = hid_module or _import_hid()
        dev = hid.device()
        dev.open_path(path)
        kb = cls(_HidTransport(dev))
        kb.protocol = kb.get_protocol_version()
        return kb

    def close(self):
        self.t.close()

    # --- низкий уровень ---
    def command(self, cmd, *args):
        pkt = bytes([cmd, *args])
        if len(pkt) > REPORT_SIZE:
            raise ViaError("Слишком длинный пакет")
        pkt = pkt.ljust(REPORT_SIZE, b"\0")
        # Первый байт — report id (0) для hidapi
        self.t.write(b"\0" + pkt)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            resp = bytes(self.t.read(REPORT_SIZE, 500))
            if not resp:
                continue
            if resp[0] == CMD_UNHANDLED and cmd != CMD_UNHANDLED:
                raise ViaError(f"Клавиатура не поддерживает команду 0x{cmd:02X}")
            if resp[0] == cmd:
                return resp
        raise ViaError("Клавиатура не ответила (подключите её проводом USB)")

    # --- общее ---
    def get_protocol_version(self):
        r = self.command(CMD_GET_PROTOCOL_VERSION)
        return (r[1] << 8) | r[2]

    def get_layer_count(self):
        return self.command(CMD_GET_LAYER_COUNT)[1]

    # --- подсветка ---
    def get_value(self, value_id, channel=CH_RGB_MATRIX):
        r = self.command(CMD_CUSTOM_GET_VALUE, channel, value_id)
        return r[3:]

    def set_value(self, value_id, *data, channel=CH_RGB_MATRIX):
        self.command(CMD_CUSTOM_SET_VALUE, channel, value_id, *data)

    def save_values(self, channel=CH_RGB_MATRIX):
        self.command(CMD_CUSTOM_SAVE, channel)

    def get_lighting(self):
        color = self.get_value(RGB_COLOR)
        return {
            "brightness": self.get_value(RGB_BRIGHTNESS)[0],
            "effect": self.get_value(RGB_EFFECT)[0],
            "speed": self.get_value(RGB_SPEED)[0],
            "hue": color[0],
            "sat": color[1],
        }

    def set_lighting(self, brightness=None, effect=None, speed=None, hue=None, sat=None):
        if effect is not None:
            self.set_value(RGB_EFFECT, effect)
        if brightness is not None:
            self.set_value(RGB_BRIGHTNESS, brightness)
        if speed is not None:
            self.set_value(RGB_SPEED, speed)
        if hue is not None and sat is not None:
            self.set_value(RGB_COLOR, hue, sat)

    # --- раскладка ---
    def get_keycode(self, layer, row, col):
        r = self.command(CMD_GET_KEYCODE, layer, row, col)
        return (r[4] << 8) | r[5]

    def set_keycode(self, layer, row, col, keycode):
        self.command(CMD_SET_KEYCODE, layer, row, col, keycode >> 8, keycode & 0xFF)

    # --- макросы ---
    def macro_count(self):
        return self.command(CMD_MACRO_GET_COUNT)[1]

    def macro_buffer_size(self):
        r = self.command(CMD_MACRO_GET_BUFFER_SIZE)
        return (r[1] << 8) | r[2]

    def read_macro_buffer(self):
        size = self.macro_buffer_size()
        buf = bytearray()
        offset = 0
        while offset < size:
            n = min(CHUNK, size - offset)
            r = self.command(CMD_MACRO_GET_BUFFER, offset >> 8, offset & 0xFF, n)
            buf += r[4:4 + n]
            offset += n
        return bytes(buf)

    def write_macro_buffer(self, data):
        size = self.macro_buffer_size()
        if len(data) > size:
            raise ViaError(f"Макросы занимают {len(data)} байт, а в памяти клавиатуры только {size}")
        data = bytes(data).ljust(size, b"\0")
        # Как VIA: сначала портим последний байт, в конце пишем его — чтобы
        # оборванная запись не оставила наполовину записанный буфер.
        self._write_chunk(size - 1, b"\xff")
        offset = 0
        while offset < size - 1:
            n = min(CHUNK, size - 1 - offset)
            self._write_chunk(offset, data[offset:offset + n])
            offset += n
        self._write_chunk(size - 1, data[size - 1:size])

    def _write_chunk(self, offset, chunk):
        self.command(CMD_MACRO_SET_BUFFER, offset >> 8, offset & 0xFF, len(chunk), *chunk)


class _HidTransport:
    def __init__(self, dev):
        self.dev = dev

    def write(self, data):
        self.dev.write(list(data))

    def read(self, size, timeout_ms):
        return self.dev.read(size, timeout_ms)

    def close(self):
        self.dev.close()

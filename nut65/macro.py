"""Перевод макросов между текстовой записью и форматом буфера VIA/QMK.

Запись (как в VIA):
  обычный текст        — печатается как есть (только латиница/ASCII, перевод строки = Enter)
  {KC_A}               — нажать и отпустить клавишу
  {KC_LCTL,KC_C}       — зажать клавиши по порядку и отпустить в обратном (сочетание)
  {+KC_LSFT} {-KC_LSFT} — только нажать / только отпустить
  {500}                — пауза 500 мс
  {{                   — символ «{»
"""
import re

from .keycodes import BASIC

PREFIX = 0x01
TAP, DOWN, UP, DELAY = 0x01, 0x02, 0x03, 0x04

_NAMES = {}
for _name, _code in BASIC.items():
    _NAMES.setdefault(_code, _name)

_TOKEN = re.compile(r"\{\{|\{([^{}]*)\}")


def _kc(name):
    n = name.strip().upper()
    if not n.startswith("KC_"):
        n = "KC_" + n
    if n not in BASIC or BASIC[n] < 0x04:
        raise ValueError(f"Неизвестная клавиша в макросе: {name.strip()}")
    return BASIC[n]


def encode(text):
    out = bytearray()
    pos = 0
    for m in _TOKEN.finditer(text):
        out += _encode_text(text[pos:m.start()])
        pos = m.end()
        if m.group(0) == "{{":
            out += b"{"
            continue
        body = m.group(1).strip()
        if body.isdigit():
            out += bytes([PREFIX, DELAY]) + body.encode() + b"|"
        elif body[:1] in "+-" and "," not in body:
            out += bytes([PREFIX, DOWN if body[0] == "+" else UP, _kc(body[1:])])
        else:
            keys = [_kc(k) for k in body.split(",") if k.strip()]
            if not keys:
                raise ValueError("Пустые фигурные скобки в макросе")
            if len(keys) == 1:
                out += bytes([PREFIX, TAP, keys[0]])
            else:
                for k in keys:
                    out += bytes([PREFIX, DOWN, k])
                for k in reversed(keys):
                    out += bytes([PREFIX, UP, k])
    out += _encode_text(text[pos:])
    return bytes(out)


def _encode_text(s):
    for ch in s:
        if not (ch in "\n\t" or 0x20 <= ord(ch) < 0x7F):
            raise ValueError(f"Символ «{ch}» нельзя напечатать макросом — "
                             "только латиница, цифры и знаки ASCII")
    return s.encode("ascii")


def decode(data):
    tokens = []  # ('text', str) | ('down'|'up'|'tap', code) | ('delay', ms)
    i = 0
    while i < len(data):
        b = data[i]
        if b == PREFIX and i + 1 < len(data):
            act = data[i + 1]
            if act in (TAP, DOWN, UP) and i + 2 < len(data):
                tokens.append(({TAP: "tap", DOWN: "down", UP: "up"}[act], data[i + 2]))
                i += 3
                continue
            if act == DELAY:
                end = data.find(b"|", i + 2)
                end = len(data) if end < 0 else end
                tokens.append(("delay", int(data[i + 2:end] or b"0")))
                i = end + 1
                continue
        tokens.append(("text", chr(b)))
        i += 1
    return _render(tokens)


def _name(code):
    return _NAMES.get(code, f"0x{code:02X}")


def _render(tokens):
    out = []
    i = 0
    while i < len(tokens):
        kind, val = tokens[i]
        if kind == "down":
            # Ищем сочетание: down a, down b, …, up …b, up a
            j = i
            downs = []
            while j < len(tokens) and tokens[j][0] == "down":
                downs.append(tokens[j][1])
                j += 1
            ups = [t[1] for t in tokens[j:j + len(downs)] if t[0] == "up"]
            if len(downs) > 1 and ups == list(reversed(downs)):
                out.append("{" + ",".join(_name(c) for c in downs) + "}")
                i = j + len(downs)
                continue
            out.append("{+" + _name(val) + "}")
        elif kind == "up":
            out.append("{-" + _name(val) + "}")
        elif kind == "tap":
            out.append("{" + _name(val) + "}")
        elif kind == "delay":
            out.append("{" + str(val) + "}")
        else:
            out.append("{{" if val == "{" else val)
        i += 1
    return "".join(out)


def split_buffer(buf, count):
    parts = bytes(buf).split(b"\0")
    parts += [b""] * count
    return parts[:count]


def join_buffer(macros):
    return b"".join(m + b"\0" for m in macros)

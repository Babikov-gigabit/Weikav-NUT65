import unittest

from nut65 import macro, via
from nut65.emulator import open_emulated
from nut65.keycodes import Keycodes


class MacroTest(unittest.TestCase):
    def test_roundtrip(self):
        for text in ["hello", "{KC_LCTL,KC_C}{200}{KC_ENT}", "{+KC_LSFT}abc{-KC_LSFT}",
                     "a{{b}", "line1\nline2", "{KC_F5}"]:
            self.assertEqual(macro.decode(macro.encode(text)), text)

    def test_bytes(self):
        self.assertEqual(macro.encode("{KC_LCTL,KC_V}"), bytes([1, 2, 0xE0, 1, 2, 0x19, 1, 3, 0x19, 1, 3, 0xE0]))
        self.assertEqual(macro.encode("{100}"), b"\x01\x04100|")
        self.assertEqual(macro.encode("ctrl"), b"ctrl")

    def test_errors(self):
        with self.assertRaises(ValueError):
            macro.encode("привет")
        with self.assertRaises(ValueError):
            macro.encode("{KC_NOPE}")


class KeycodeTest(unittest.TestCase):
    def test_parse_label(self):
        k = Keycodes(12)
        for t in ["KC_A", "M3", "MO(1)", "C+KC_C", "RGB_TOG", "BT1", "0x1234"]:
            code = k.parse(t)
            self.assertEqual(k.parse(k.label(code)) if not k.label(code).startswith("0x") else code, code)
        self.assertEqual(k.parse("M0"), 0x7700)
        self.assertEqual(Keycodes(10).parse("M0"), 0x5F12)


class ViaTest(unittest.TestCase):
    def test_lighting(self):
        kb = open_emulated()
        self.assertEqual(kb.protocol, 12)
        kb.set_lighting(brightness=50, effect=5, speed=10, hue=20, sat=30)
        self.assertEqual(kb.get_lighting(), {"brightness": 50, "effect": 5, "speed": 10, "hue": 20, "sat": 30})
        kb.save_values()
        self.assertEqual(kb.t.saved[via.RGB_EFFECT], [5])

    def test_macros(self):
        kb = open_emulated()
        n = kb.macro_count()
        macros = [macro.encode(f"macro {i} {{KC_ENT}}") for i in range(n)]
        kb.write_macro_buffer(macro.join_buffer(macros))
        back = macro.split_buffer(kb.read_macro_buffer(), n)
        self.assertEqual(back, macros)

    def test_keycode(self):
        kb = open_emulated()
        kb.set_keycode(1, 2, 3, 0x7705)
        self.assertEqual(kb.get_keycode(1, 2, 3), 0x7705)

    def test_overflow(self):
        kb = open_emulated(buffer_size=64)
        with self.assertRaises(via.ViaError):
            kb.write_macro_buffer(b"x" * 100)


if __name__ == "__main__":
    unittest.main()

"""Графическое приложение: подсветка, макросы и назначение клавиш для Weikav NUT65."""
import colorsys
import json
import sys
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from . import macro, via
from .emulator import open_emulated
from .keycodes import BASIC, CUSTOM, Keycodes

APP_TITLE = "NUT65 Control"

PRESET_COLORS = [("Красный", 0), ("Оранжевый", 21), ("Жёлтый", 43), ("Зелёный", 85),
                 ("Бирюзовый", 128), ("Синий", 170), ("Фиолетовый", 200), ("Розовый", 234)]

# Клавиши tkinter -> коды QMK для записи макросов с клавиатуры
_KEYSYMS = {
    "Control_L": "KC_LCTL", "Control_R": "KC_RCTL", "Shift_L": "KC_LSFT", "Shift_R": "KC_RSFT",
    "Alt_L": "KC_LALT", "Alt_R": "KC_RALT", "Super_L": "KC_LGUI", "Super_R": "KC_RGUI",
    "Win_L": "KC_LGUI", "Win_R": "KC_RGUI", "Meta_L": "KC_LGUI", "Meta_R": "KC_RGUI",
    "Return": "KC_ENT", "Escape": "KC_ESC", "BackSpace": "KC_BSPC", "Tab": "KC_TAB",
    "space": "KC_SPC", "minus": "KC_MINS", "equal": "KC_EQL", "bracketleft": "KC_LBRC",
    "bracketright": "KC_RBRC", "backslash": "KC_BSLS", "semicolon": "KC_SCLN",
    "apostrophe": "KC_QUOT", "grave": "KC_GRV", "comma": "KC_COMM", "period": "KC_DOT",
    "slash": "KC_SLSH", "Caps_Lock": "KC_CAPS", "Print": "KC_PSCR", "Scroll_Lock": "KC_SCRL",
    "Pause": "KC_PAUS", "Insert": "KC_INS", "Home": "KC_HOME", "Prior": "KC_PGUP",
    "Delete": "KC_DEL", "End": "KC_END", "Next": "KC_PGDN", "Right": "KC_RGHT",
    "Left": "KC_LEFT", "Down": "KC_DOWN", "Up": "KC_UP", "App": "KC_APP", "Menu": "KC_APP",
}
# Виртуальные коды Windows — работают при любой раскладке (в т.ч. русской)
_WIN_VK = {0x10: "KC_LSFT", 0x11: "KC_LCTL", 0x12: "KC_LALT", 0x5B: "KC_LGUI", 0x5C: "KC_RGUI",
           0x0D: "KC_ENT", 0x1B: "KC_ESC", 0x08: "KC_BSPC", 0x09: "KC_TAB", 0x20: "KC_SPC",
           0x2E: "KC_DEL", 0x2D: "KC_INS", 0x24: "KC_HOME", 0x23: "KC_END", 0x21: "KC_PGUP",
           0x22: "KC_PGDN", 0x25: "KC_LEFT", 0x26: "KC_UP", 0x27: "KC_RGHT", 0x28: "KC_DOWN",
           0xBD: "KC_MINS", 0xBB: "KC_EQL", 0xDB: "KC_LBRC", 0xDD: "KC_RBRC", 0xDC: "KC_BSLS",
           0xBA: "KC_SCLN", 0xDE: "KC_QUOT", 0xC0: "KC_GRV", 0xBC: "KC_COMM", 0xBE: "KC_DOT",
           0xBF: "KC_SLSH", 0x14: "KC_CAPS"}


def keysym_to_kc(event):
    if sys.platform == "win32":
        vk = event.keycode
        if 0x41 <= vk <= 0x5A:
            return BASIC["KC_" + chr(vk)]
        if 0x30 <= vk <= 0x39:
            return BASIC["KC_" + chr(vk)]
        if 0x70 <= vk <= 0x87:
            return BASIC[f"KC_F{vk - 0x6F}"]
        if vk in _WIN_VK:
            return BASIC[_WIN_VK[vk]]
    ks = event.keysym
    if ks in _KEYSYMS:
        return BASIC[_KEYSYMS[ks]]
    if len(ks) == 1 and ks.isalnum() and ks.isascii():
        return BASIC.get("KC_" + ks.upper())
    if ks.startswith("F") and ks[1:].isdigit():
        return BASIC.get("KC_" + ks)
    return None


def hs_to_hex(h, s, v=255):
    r, g, b = colorsys.hsv_to_rgb(h / 255, s / 255, v / 255)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x640")
        self.minsize(1000, 580)
        self.kb = None
        self.kc = Keycodes(12)
        self.devices = []
        self._apply_job = None
        self._loading = False
        self.macro_texts = []
        self.macro_buffer_size = 0
        self.keymap = []
        self.layers = 1

        self._build_top()
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tab_light = ttk.Frame(nb, padding=12)
        self.tab_macro = ttk.Frame(nb, padding=12)
        self.tab_keys = ttk.Frame(nb, padding=12)
        nb.add(self.tab_light, text="Подсветка")
        nb.add(self.tab_macro, text="Макросы")
        nb.add(self.tab_keys, text="Клавиши")
        self._build_lighting()
        self._build_macros()
        self._build_keys()
        self._set_enabled(False)
        self.refresh_devices()

    # ---------- подключение ----------
    def _build_top(self):
        f = ttk.Frame(self, padding=(8, 8))
        f.pack(fill="x")
        ttk.Label(f, text="Клавиатура:").pack(side="left")
        self.dev_var = tk.StringVar()
        self.dev_box = ttk.Combobox(f, textvariable=self.dev_var, state="readonly", width=48)
        self.dev_box.pack(side="left", padx=6)
        ttk.Button(f, text="Обновить", command=self.refresh_devices).pack(side="left")
        ttk.Button(f, text="Подключить", command=self.connect).pack(side="left", padx=4)
        ttk.Button(f, text="Демо", command=self.connect_demo).pack(side="left")
        self.any_via = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Все VIA-устройства", variable=self.any_via,
                        command=self.refresh_devices).pack(side="left", padx=8)
        self.status = ttk.Label(self, text="Не подключено", foreground="#a33",
                                relief="sunken", padding=(8, 3))
        self.status.pack(side="bottom", fill="x")

    def refresh_devices(self):
        try:
            if self.any_via.get():
                self.devices = via.find_devices(vid=None, pid=None)
            else:
                self.devices = via.find_devices()
        except via.ViaError as e:
            self.devices = []
            self.status.config(text=str(e))
        names = [f"{d.get('product_string') or 'NUT65'}  ({d['vendor_id']:04X}:{d['product_id']:04X})"
                 for d in self.devices]
        self.dev_box["values"] = names
        if names:
            self.dev_box.current(0)
        else:
            self.dev_var.set("Не найдено — подключите клавиатуру кабелем USB")

    def connect(self):
        if not self.devices:
            messagebox.showwarning(APP_TITLE, "Клавиатура не найдена.\n\nNUT65 настраивается только по "
                                   "кабелю USB (не по Bluetooth и не через 2.4G). Подключите кабель, "
                                   "переключите клавиатуру в режим USB и нажмите «Обновить».")
            return
        d = self.devices[max(self.dev_box.current(), 0)]
        self._disconnect()
        try:
            self._attach(via.ViaKeyboard.open(d["path"]), d.get("product_string") or "NUT65")
        except Exception as e:  # noqa: BLE001 — показываем любую ошибку HID пользователю
            messagebox.showerror(APP_TITLE, f"Не удалось подключиться: {e}")

    def connect_demo(self):
        self._disconnect()
        self._attach(open_emulated(), "Демо (без клавиатуры)")

    def _disconnect(self):
        if self.kb:
            try:
                self.kb.close()
            except Exception:  # noqa: BLE001
                pass
        self.kb = None
        self._set_enabled(False)

    def _attach(self, kb, name):
        self.kb = kb
        self.kc = Keycodes(kb.protocol)
        self.status.config(text=f"Подключено: {name} · VIA v{kb.protocol}", foreground="#272")
        self._set_enabled(True)
        self.safe(self.load_lighting)
        self.safe(self.load_macros)
        self.safe(self.load_keymap)

    def _set_enabled(self, on):
        state = "!disabled" if on else "disabled"
        for w in self._device_widgets:
            try:
                w.state([state])
            except (AttributeError, tk.TclError):
                w.config(state="normal" if on else "disabled")

    def safe(self, fn, *a):
        try:
            fn(*a)
            return True
        except (via.ViaError, OSError, ValueError) as e:
            messagebox.showerror(APP_TITLE, str(e))
            return False

    # ---------- подсветка ----------
    def _build_lighting(self):
        t = self.tab_light
        self._device_widgets = []
        t.columnconfigure(1, weight=1)

        ttk.Label(t, text="Эффект").grid(row=0, column=0, sticky="w", pady=6)
        self.effect_var = tk.StringVar()
        eff = ttk.Combobox(t, textvariable=self.effect_var, state="readonly", height=24,
                           values=[f"{i}. {n}" for i, n in enumerate(via.EFFECTS)])
        eff.grid(row=0, column=1, sticky="we", pady=6)
        eff.bind("<<ComboboxSelected>>", lambda e: self.on_light_change())

        self.bright = tk.IntVar()
        self.speed = tk.IntVar()
        self.hue = tk.IntVar()
        self.sat = tk.IntVar(value=255)
        sliders = []
        for row, (label, var) in enumerate([("Яркость", self.bright), ("Скорость", self.speed),
                                            ("Оттенок", self.hue), ("Насыщенность", self.sat)], 1):
            ttk.Label(t, text=label).grid(row=row, column=0, sticky="w", pady=6)
            s = ttk.Scale(t, from_=0, to=255, variable=var,
                          command=lambda _v, var=var: (var.set(round(float(var.get()))),
                                                       self.on_light_change()))
            s.grid(row=row, column=1, sticky="we", pady=6)
            ttk.Label(t, textvariable=var, width=4).grid(row=row, column=2)
            sliders.append(s)

        cf = ttk.Frame(t)
        cf.grid(row=5, column=0, columnspan=3, sticky="w", pady=10)
        self.swatch = tk.Label(cf, width=6, relief="groove", bg="#0000ff")
        self.swatch.pack(side="left", padx=(0, 8), ipady=6)
        pick = ttk.Button(cf, text="Выбрать цвет…", command=self.pick_color)
        pick.pack(side="left", padx=(0, 12))
        presets = []
        for name, h in PRESET_COLORS:
            b = tk.Button(cf, width=2, bg=hs_to_hex(h, 255), activebackground=hs_to_hex(h, 255),
                          relief="flat", command=lambda h=h: self.set_color(h, 255))
            b.pack(side="left", padx=2)
            presets.append(b)
        wb = tk.Button(cf, width=2, bg="#ffffff", relief="flat", command=lambda: self.set_color(0, 0))
        wb.pack(side="left", padx=2)
        presets.append(wb)

        self.color_note = ttk.Label(t, foreground="#777")
        self.color_note.grid(row=6, column=0, columnspan=3, sticky="w")

        bf = ttk.Frame(t)
        bf.grid(row=7, column=0, columnspan=3, sticky="w", pady=16)
        b1 = ttk.Button(bf, text="Сохранить в память клавиатуры", command=self.save_lighting)
        b1.pack(side="left")
        b2 = ttk.Button(bf, text="Прочитать с клавиатуры", command=lambda: self.safe(self.load_lighting))
        b2.pack(side="left", padx=6)
        b3 = ttk.Button(bf, text="Экспорт профиля…", command=self.export_profile)
        b3.pack(side="left", padx=(24, 6))
        b4 = ttk.Button(bf, text="Импорт профиля…", command=self.import_profile)
        b4.pack(side="left")

        ttk.Label(t, foreground="#777", justify="left", wraplength=820, text=(
            "Изменения применяются сразу, но без «Сохранить» сбросятся после отключения "
            "клавиатуры. Боковая световая полоса управляется с клавиатуры: Fn-сочетаниями или "
            "кодами RL_MOD / RL_VAI / RL_VAD, которые можно назначить на вкладке «Клавиши».")
        ).grid(row=8, column=0, columnspan=3, sticky="w")

        self._device_widgets += [eff, pick, b1, b2, b3, b4, *sliders, *presets]

    def load_lighting(self):
        L = self.kb.get_lighting()
        self._loading = True
        self.bright.set(L["brightness"])
        self.speed.set(L["speed"])
        self.hue.set(L["hue"])
        self.sat.set(L["sat"])
        eff = min(L["effect"], len(via.EFFECTS) - 1)
        self.effect_var.set(f"{eff}. {via.EFFECTS[eff]}")
        self._loading = False
        self._update_swatch()

    def current_effect(self):
        v = self.effect_var.get()
        return int(v.split(".")[0]) if v else 0

    def _update_swatch(self):
        self.swatch.config(bg=hs_to_hex(self.hue.get(), self.sat.get()))
        if self.current_effect() in via.EFFECTS_WITHOUT_COLOR:
            self.color_note.config(text="У этого эффекта свои цвета — выбор цвета на него не влияет.")
        else:
            self.color_note.config(text="")

    def set_color(self, h, s):
        self.hue.set(h)
        self.sat.set(s)
        self.on_light_change()

    def pick_color(self):
        rgb, _ = colorchooser.askcolor(color=hs_to_hex(self.hue.get(), self.sat.get()), parent=self)
        if rgb:
            h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
            self.set_color(round(h * 255) % 256, round(s * 255))
            if v < 0.99:
                self.bright.set(round(v * 255))

    def on_light_change(self):
        if self._loading:
            return
        self._update_swatch()
        if self._apply_job:
            self.after_cancel(self._apply_job)
        self._apply_job = self.after(80, self.apply_lighting)

    def apply_lighting(self):
        self._apply_job = None
        if self.kb:
            self.safe(self.kb.set_lighting, self.bright.get(), self.current_effect(),
                      self.speed.get(), self.hue.get(), self.sat.get())

    def save_lighting(self):
        self.apply_lighting()
        if self.safe(self.kb.save_values):
            self.status.config(text="Подсветка сохранена в память клавиатуры", foreground="#272")

    def export_profile(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                            filetypes=[("Профиль NUT65", "*.json")])
        if not path:
            return
        self._sync_macro_editor()
        data = {"lighting": {"brightness": self.bright.get(), "effect": self.current_effect(),
                             "speed": self.speed.get(), "hue": self.hue.get(), "sat": self.sat.get()},
                "macros": self.macro_texts}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_profile(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Профиль NUT65", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            messagebox.showerror(APP_TITLE, f"Не удалось прочитать профиль: {e}")
            return
        L = data.get("lighting")
        if L:
            self._loading = True
            self.bright.set(L["brightness"])
            self.speed.set(L["speed"])
            self.hue.set(L["hue"])
            self.sat.set(L["sat"])
            e = L["effect"]
            self.effect_var.set(f"{e}. {via.EFFECTS[e]}")
            self._loading = False
            self.on_light_change()
        if "macros" in data and self.macro_texts:
            n = len(self.macro_texts)
            self.macro_texts = (list(data["macros"]) + [""] * n)[:n]
            self._refresh_macro_list()
            self._show_macro(self.macro_list.curselection()[0] if self.macro_list.curselection() else 0)
            messagebox.showinfo(APP_TITLE, "Профиль загружен. Макросы попадут в клавиатуру после "
                                "кнопки «Записать в клавиатуру» на вкладке «Макросы».")

    # ---------- макросы ----------
    def _build_macros(self):
        t = self.tab_macro
        t.columnconfigure(1, weight=1)
        t.rowconfigure(1, weight=1)

        ttk.Label(t, text="Макросы").grid(row=0, column=0, sticky="w")
        self.macro_list = tk.Listbox(t, width=34, exportselection=False, activestyle="none")
        self.macro_list.grid(row=1, column=0, sticky="ns", padx=(0, 10))
        self.macro_list.bind("<<ListboxSelect>>", self._on_macro_select)
        self.current_macro = None

        right = ttk.Frame(t)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        self.macro_title = ttk.Label(right, text="Выберите макрос слева", font=("", 11, "bold"))
        self.macro_title.grid(row=0, column=0, sticky="w")
        self.editor = tk.Text(right, height=8, wrap="word", undo=True, font=("Consolas", 11))
        self.editor.grid(row=1, column=0, sticky="nsew", pady=6)
        self.editor.bind("<KeyPress>", self._rec_press)
        self.editor.bind("<KeyRelease>", self._rec_release)

        tools = ttk.Frame(right)
        tools.grid(row=2, column=0, sticky="w")
        self.rec_btn = ttk.Button(tools, text="● Записать нажатия", command=self.toggle_record)
        self.rec_btn.pack(side="left")
        self.rec_delays = tk.BooleanVar(value=False)
        ttk.Checkbutton(tools, text="с паузами", variable=self.rec_delays).pack(side="left", padx=(4, 12))
        ttk.Button(tools, text="+ Пауза", command=self.insert_delay).pack(side="left")
        ttk.Button(tools, text="+ Сочетание", command=self.insert_combo).pack(side="left", padx=4)
        ttk.Button(tools, text="Очистить", command=lambda: (self.editor.delete("1.0", "end"),
                                                            self._on_editor_change())).pack(side="left")

        self.macro_err = ttk.Label(right, foreground="#a33")
        self.macro_err.grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Label(right, foreground="#666", justify="left", text=(
            "Как писать:\n"
            "  обычный текст печатается как есть (только латиница)   ·   {KC_ENT} — нажать клавишу\n"
            "  {KC_LCTL,KC_C} — сочетание Ctrl+C   ·   {500} — пауза 500 мс\n"
            "  {+KC_LSFT} / {-KC_LSFT} — зажать / отпустить")
        ).grid(row=4, column=0, sticky="w", pady=6)

        bottom = ttk.Frame(t)
        bottom.grid(row=2, column=0, columnspan=2, sticky="we", pady=(8, 0))
        self.macro_usage = ttk.Label(bottom, text="")
        self.macro_usage.pack(side="left")
        w1 = ttk.Button(bottom, text="Записать в клавиатуру", command=self.write_macros)
        w1.pack(side="right")
        w2 = ttk.Button(bottom, text="Прочитать с клавиатуры", command=lambda: self.safe(self.load_macros))
        w2.pack(side="right", padx=6)
        self._device_widgets += [w1, w2]

        self.recording = False
        self._rec_tokens = []
        self._rec_down = set()
        self._rec_last = 0.0

    def load_macros(self):
        n = self.kb.macro_count()
        self.macro_buffer_size = self.kb.macro_buffer_size()
        parts = macro.split_buffer(self.kb.read_macro_buffer(), n)
        self.macro_texts = [macro.decode(p) for p in parts]
        self._refresh_macro_list()
        self._show_macro(0)

    def _refresh_macro_list(self):
        sel = self.macro_list.curselection()
        self.macro_list.delete(0, "end")
        for i, txt in enumerate(self.macro_texts):
            preview = txt.replace("\n", "⏎")
            self.macro_list.insert("end", f"M{i}   {preview[:26] or '— пусто —'}")
        if sel:
            self.macro_list.selection_set(sel[0])
        self._update_usage()

    def _update_usage(self):
        try:
            size = len(macro.join_buffer([macro.encode(t) for t in self.macro_texts]))
        except ValueError:
            return
        over = size > self.macro_buffer_size
        self.macro_usage.config(text=f"Память макросов: {size} из {self.macro_buffer_size} байт",
                                foreground="#a33" if over else "#333")

    def _on_macro_select(self, _e):
        sel = self.macro_list.curselection()
        if sel:
            self._sync_macro_editor()
            self._show_macro(sel[0])

    def _show_macro(self, i):
        if not self.macro_texts:
            return
        self.current_macro = i
        self.macro_list.selection_clear(0, "end")
        self.macro_list.selection_set(i)
        self.macro_title.config(text=f"Макрос M{i}  (назначьте его на клавишу во вкладке «Клавиши»)")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.macro_texts[i])
        self._on_editor_change()

    def _sync_macro_editor(self):
        if self.current_macro is not None and self.macro_texts:
            self.macro_texts[self.current_macro] = self.editor.get("1.0", "end-1c")

    def _on_editor_change(self):
        if self.recording:
            return
        text = self.editor.get("1.0", "end-1c")
        try:
            macro.encode(text)
            self.macro_err.config(text="")
        except ValueError as e:
            self.macro_err.config(text=str(e))
        if self.current_macro is not None and self.macro_texts:
            self.macro_texts[self.current_macro] = text
            preview = text.replace("\n", "⏎")
            self.macro_list.delete(self.current_macro)
            self.macro_list.insert(self.current_macro,
                                   f"M{self.current_macro}   {preview[:26] or '— пусто —'}")
            self.macro_list.selection_set(self.current_macro)
            self._update_usage()

    def insert_delay(self):
        ms = simpledialog.askinteger(APP_TITLE, "Пауза, мс:", parent=self, minvalue=1,
                                     maxvalue=60000, initialvalue=100)
        if ms:
            self.editor.insert("insert", "{%d}" % ms)
            self._on_editor_change()

    def insert_combo(self):
        s = simpledialog.askstring(APP_TITLE, "Клавиши через запятую, например: LCTL, LSFT, ESC",
                                   parent=self)
        if not s:
            return
        names = [n.strip().upper() for n in s.split(",") if n.strip()]
        names = [n if n.startswith("KC_") else "KC_" + n for n in names]
        bad = [n for n in names if n not in BASIC]
        if bad:
            messagebox.showerror(APP_TITLE, "Неизвестные клавиши: " + ", ".join(bad))
            return
        self.editor.insert("insert", "{" + ",".join(names) + "}")
        self._on_editor_change()

    def toggle_record(self):
        if self.current_macro is None:
            return
        self.recording = not self.recording
        if self.recording:
            self._rec_tokens, self._rec_down, self._rec_last = [], set(), 0.0
            self.rec_btn.config(text="■ Остановить запись")
            self.macro_err.config(text="Идёт запись: нажимайте клавиши в поле макроса. "
                                       "Остановить — кнопкой мышью.")
            self.editor.focus_set()
        else:
            self.rec_btn.config(text="● Записать нажатия")
            for code in list(self._rec_down):
                self._rec_tokens.append(("up", code))
            self.editor.insert("insert", macro._render(self._compact(self._rec_tokens)))
            self._on_editor_change()

    def _rec_delay(self):
        now = time.monotonic()
        if self.rec_delays.get() and self._rec_last and now - self._rec_last > 0.03:
            self._rec_tokens.append(("delay", int((now - self._rec_last) * 1000)))
        self._rec_last = now

    def _rec_press(self, e):
        if not self.recording:
            return None
        code = keysym_to_kc(e)
        if code is not None and code not in self._rec_down:
            self._rec_delay()
            self._rec_down.add(code)
            self._rec_tokens.append(("down", code))
        return "break"

    def _rec_release(self, e):
        if not self.recording:
            self._on_editor_change()
            return None
        code = keysym_to_kc(e)
        if code is not None and code in self._rec_down:
            self._rec_delay()
            self._rec_down.discard(code)
            self._rec_tokens.append(("up", code))
        return "break"

    @staticmethod
    def _compact(tokens):
        taps = []
        for tok in tokens:
            if tok[0] == "up" and taps and taps[-1] == ("down", tok[1]):
                taps[-1] = ("tap", tok[1])
            else:
                taps.append(tok)
        # Ctrl зажат, C нажата, Ctrl отпущен -> оставляем down/up, чтобы получилось {KC_LCTL,KC_C}
        out = []
        for i, tok in enumerate(taps):
            if (tok[0] == "tap" and 0 < i < len(taps) - 1 and taps[i - 1][0] == "down"
                    and taps[i + 1][0] == "up"):
                out += [("down", tok[1]), ("up", tok[1])]
            else:
                out.append(tok)
        return out

    def write_macros(self):
        self._sync_macro_editor()
        try:
            encoded = [macro.encode(t) for t in self.macro_texts]
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        self.config(cursor="watch")
        self.update()
        try:
            ok = self.safe(self.kb.write_macro_buffer, macro.join_buffer(encoded))
        finally:
            self.config(cursor="")
        if ok:
            self.status.config(text="Макросы записаны в клавиатуру", foreground="#272")

    # ---------- клавиши ----------
    def _build_keys(self):
        t = self.tab_keys
        top = ttk.Frame(t)
        top.pack(fill="x")
        ttk.Label(top, text="Слой:").pack(side="left")
        self.layer_var = tk.IntVar(value=0)
        self.layer_box = ttk.Combobox(top, width=5, state="readonly", values=[0])
        self.layer_box.current(0)
        self.layer_box.pack(side="left", padx=6)
        self.layer_box.bind("<<ComboboxSelected>>", lambda e: self._draw_keymap())
        r = ttk.Button(top, text="Прочитать раскладку", command=lambda: self.safe(self.load_keymap))
        r.pack(side="left", padx=6)
        ttk.Label(top, foreground="#666", text="Нажмите на клавишу, чтобы назначить макрос или другую функцию. "
                  "Слой 1 обычно — Fn.").pack(side="left", padx=10)
        self._device_widgets.append(r)

        self.grid_frame = ttk.Frame(t, padding=(0, 12))
        self.grid_frame.pack(fill="both", expand=True)
        self.key_buttons = {}
        for row in range(via.MATRIX_ROWS):
            for col in range(via.MATRIX_COLS):
                b = tk.Button(self.grid_frame, width=4, height=2, wraplength=56, font=("", 9),
                              command=lambda r=row, c=col: self.edit_key(r, c))
                b.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
                self.key_buttons[(row, col)] = b
                self.grid_frame.columnconfigure(col, weight=1, uniform="key")
                self._device_widgets.append(b)

    def load_keymap(self):
        self.layers = self.kb.get_layer_count()
        self.layer_box["values"] = list(range(self.layers))
        self.keymap = [[[self.kb.get_keycode(l, r, c) for c in range(via.MATRIX_COLS)]
                        for r in range(via.MATRIX_ROWS)] for l in range(self.layers)]
        self._draw_keymap()

    def _draw_keymap(self):
        if not self.keymap:
            return
        layer = int(self.layer_box.get() or 0)
        for (r, c), b in self.key_buttons.items():
            code = self.keymap[layer][r][c]
            label = self.kc.label(code)
            is_macro = label.startswith("M") and label[1:].isdigit()
            b.config(text=label, bg="#ffe9b3" if is_macro else "#f4f4f4")

    def edit_key(self, r, c):
        if not self.keymap:
            return
        layer = int(self.layer_box.get() or 0)
        KeyDialog(self, layer, r, c, self.keymap[layer][r][c])

    def assign_key(self, layer, r, c, code):
        self.kb.set_keycode(layer, r, c, code)
        self.keymap[layer][r][c] = code
        self._draw_keymap()


class KeyDialog(tk.Toplevel):
    def __init__(self, app, layer, r, c, code):
        super().__init__(app)
        self.app, self.layer, self.r, self.c = app, layer, r, c
        self.title(f"Клавиша {r},{c} · слой {layer}")
        self.transient(app)
        self.resizable(False, False)
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both")
        ttk.Label(f, text=f"Сейчас: {app.kc.label(code)}").grid(row=0, column=0, columnspan=2,
                                                                 sticky="w", pady=(0, 10))
        count = len(app.macro_texts) or 16
        ttk.Label(f, text="Макрос:").grid(row=1, column=0, sticky="w")
        self.macro_box = ttk.Combobox(f, state="readonly", width=38, values=[
            f"M{i}  {(app.macro_texts[i] if i < len(app.macro_texts) else '')[:24]}" for i in range(count)])
        self.macro_box.grid(row=1, column=1, pady=4)
        self.macro_box.bind("<<ComboboxSelected>>", lambda e: self.code_var.set(
            f"M{self.macro_box.current()}"))

        ttk.Label(f, text="Функция NUT65:").grid(row=2, column=0, sticky="w")
        self.special = ttk.Combobox(f, state="readonly", width=38, values=[
            f"{n} — {d}" for n, d in CUSTOM] + sorted(app.kc.rgb.values()))
        self.special.grid(row=2, column=1, pady=4)
        self.special.bind("<<ComboboxSelected>>", lambda e: self.code_var.set(
            self.special.get().split(" — ")[0]))

        ttk.Label(f, text="Код вручную:").grid(row=3, column=0, sticky="w")
        self.code_var = tk.StringVar(value=app.kc.label(code))
        ttk.Entry(f, textvariable=self.code_var, width=40).grid(row=3, column=1, pady=4)
        ttk.Label(f, foreground="#666", text="Например: KC_A, KC_F5, M2, MO(1), C+KC_C, KC_TRNS, 0x7700"
                  ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 10))
        bf = ttk.Frame(f)
        bf.grid(row=5, column=0, columnspan=2, sticky="e")
        ttk.Button(bf, text="Отмена", command=self.destroy).pack(side="right")
        ttk.Button(bf, text="Назначить", command=self.ok).pack(side="right", padx=6)
        self.wait_visibility()
        self.grab_set()

    def ok(self):
        try:
            code = self.app.kc.parse(self.code_var.get())
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e), parent=self)
            return
        self.app.safe(self.app.assign_key, self.layer, self.r, self.c, code)
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

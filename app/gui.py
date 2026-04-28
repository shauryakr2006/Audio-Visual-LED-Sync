"""
gui.py — GestoBridge Tk control panel
======================================
The single Tk root window.  All backend interactions go through module-level
functions imported from the other modules — no business logic lives here.

OPTIMISATION vs v3.5:
  • ttk.Style is now configured once in __init__ rather than on every
    _mk_slider / _mk_slider_bg call.
  • _hex helper is now rgb_to_hex() from color_utils (no local alias).
"""

from __future__ import annotations

import colorsys
import threading
import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog, ttk

import state
import audio_engine
import album_art as _album_art_mod
from auto_trigger import startup_get, startup_set
from color_utils import (WIN_ACCENT, apply_color_temp, kelvin_to_gains,
                         push_color_history, rgb_to_hex)
from config import (EFFECT_MODES, LED_MODES, M_BREATHE, M_CANDLE, M_MUSIC,
                    M_RAINBOW, M_SOLID, M_STROBE, M_SYNC, M_WAVE,
                    MODE_LABEL, gs, ss)
from hotkeys import hotkeys_ok

# ── Convenience alias so the legacy name works inside this file ───────────────
_hex = rgb_to_hex


# ══════════════════════════════════════════════════════════════════════════════
#  COLOUR PALETTE & FONTS
# ══════════════════════════════════════════════════════════════════════════════
C = dict(
    bg      = "#0a0a0a",
    panel   = "#111111",
    panel2  = "#181818",
    panel3  = "#1e1e1e",
    accent  = WIN_ACCENT,
    acc2    = "#ff3c6e",
    acc3    = "#7b61ff",
    text    = "#dcdcdc",
    dim     = "#505050",
    border  = "#1f1f1f",
    active  = "#141414",
    vu_bass = "#ff3c50",
    vu_mids = "#00e06c",
    vu_high = "#5cb3ff",
)
FM = ("Consolas", 10)
FS = ("Consolas",  8)
FL = ("Consolas",  9, "bold")
FT = ("Consolas", 14, "bold")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class GestoBridge(tk.Tk):

    def __init__(self):
        super().__init__()
        global _status_cb
        state._status_cb = self._cb_status
        state._app       = self

        self.title("Audio-Visual-LED-Sync")
        self.geometry("900x640")
        self.minsize(840, 560)
        self.resizable(True, True)
        self.configure(bg=C["bg"])

        # ── Configure ttk styles ONCE (not per slider call) ───────────────────
        sty = ttk.Style()
        sty.theme_use("clam")
        sty.configure("G.Horizontal.TScale", background=C["panel"],
                       troughcolor="#1a1a1a", sliderthickness=13,
                       sliderrelief=tk.FLAT)
        sty.configure("P.Horizontal.TScale", background=C["bg"],
                       troughcolor="#1c1c1c", sliderthickness=13,
                       sliderrelief=tk.FLAT)

        self._mode = tk.StringVar(value=gs("mode"))
        self._on   = tk.BooleanVar(value=gs("strip_on"))
        self._br   = tk.IntVar(value=gs("brightness"))
        self._spd  = tk.IntVar(value=gs("speed"))
        self._stat = tk.StringVar(value="● Connecting…")

        self._build_ui()
        self._poll_ble()
        # ── Close-button behaviour ─────────────────────────────────────────────
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── BLE status ────────────────────────────────────────────────────────────
    def _cb_status(self, s):
        try:
            self.after(0, self._apply_status, s)
        except Exception:
            pass

    def _apply_status(self, s):
        self._stat.set("● Connected" if s == "connected" else "● Reconnecting…")
        self._stat_lbl.config(fg=C["accent"] if s == "connected" else C["dim"])

    def _poll_ble(self):
        if state._ble_ok:
            self._stat.set("● Connected")
            self._stat_lbl.config(fg=C["accent"])
        self.after(3000, self._poll_ble)

    def _hk_set_brightness(self, b: int):
        self._br.set(b)
        self._br_lbl.config(text=f"{b}%")

    # ══════════════════════════════════════════════════════════════════════════
    #  UI BUILD
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=C["panel"], height=50)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="AV-LED", font=FT, bg=C["panel"],
                 fg=C["accent"]).pack(side=tk.LEFT, padx=(18, 2), pady=12)
        tk.Label(hdr, text="SYNC", font=FT, bg=C["panel"],
                 fg=C["text"]).pack(side=tk.LEFT, pady=12)
        tk.Label(hdr, text=" v3.6", font=FS, bg=C["panel"],
                 fg=C["dim"]).pack(side=tk.LEFT, pady=18)
        self._stat_lbl = tk.Label(hdr, textvariable=self._stat, font=FS,
                                   bg=C["panel"], fg=C["dim"])
        self._stat_lbl.pack(side=tk.RIGHT, padx=18)
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        # Body
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        # ── Sidebar ───────────────────────────────────────────────────────────
        side = tk.Frame(body, bg=C["panel"], width=185)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)

        def cat(txt):
            tk.Label(side, text=txt, font=FS, bg=C["panel"],
                     fg=C["dim"]).pack(anchor=tk.W, padx=16, pady=(10, 2))

        self._mbtns: dict = {}
        cat("── SMART SYNC")
        self._add_mode_btn(side, M_SYNC)
        self._add_mode_btn(side, M_MUSIC)
        cat("── COLOR")
        self._add_mode_btn(side, M_SOLID)
        cat("── EFFECTS")
        for m in EFFECT_MODES:
            self._add_mode_btn(side, m)
        cat("─────────────")
        self._add_mode_btn(side, "presets",  label="★  Presets",  accent=C["acc3"])
        self._add_mode_btn(side, "settings", label="⚙  Settings", accent=C["dim"])

        self._highlight_mode(gs("mode"))
        tk.Frame(body, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        # ── Panel area ────────────────────────────────────────────────────────
        ctrl = tk.Frame(body, bg=C["bg"])
        ctrl.pack(fill=tk.BOTH, expand=True)

        ALL_PANELS = LED_MODES + ["presets", "settings"]
        self._panels: dict = {}
        for k in ALL_PANELS:
            self._panels[k] = tk.Frame(ctrl, bg=C["bg"])

        self._build_sync_panel    (self._panels[M_SYNC])
        self._build_music_panel   (self._panels[M_MUSIC])
        self._build_solid_panel   (self._panels[M_SOLID])
        self._build_breathe_panel (self._panels[M_BREATHE])
        self._build_rainbow_panel (self._panels[M_RAINBOW])
        self._build_strobe_panel  (self._panels[M_STROBE])
        self._build_wave_panel    (self._panels[M_WAVE])
        self._build_candle_panel  (self._panels[M_CANDLE])
        self._build_presets_panel (self._panels["presets"])
        self._build_settings_panel(self._panels["settings"])
        self._show_panel(gs("mode"))

        # Footer
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)
        ftr = tk.Frame(self, bg=C["panel"], height=52)
        ftr.pack(fill=tk.X)
        ftr.pack_propagate(False)

        self._on_btn = tk.Label(ftr, text="  ON  ", font=FL, cursor="hand2",
                                 padx=2, pady=4)
        self._on_btn.pack(side=tk.LEFT, padx=(14, 10), pady=10)
        self._on_btn.bind("<Button-1>", self._toggle_on)
        self._refresh_on_btn()

        def ftr_slider(lbl, var, cmd):
            tk.Label(ftr, text=lbl, font=FS, bg=C["panel"],
                     fg=C["dim"]).pack(side=tk.LEFT, padx=(8, 2))
            self._mk_slider(ftr, var, 0, 100, cmd, length=100).pack(side=tk.LEFT)
            lbl2 = tk.Label(ftr, text=f"{var.get()}%", font=FS,
                             bg=C["panel"], fg=C["accent"], width=4)
            lbl2.pack(side=tk.LEFT)
            return lbl2

        self._br_lbl  = ftr_slider("FLOOR", self._br,  self._on_br)
        self._spd_lbl = ftr_slider("SPEED", self._spd, self._on_spd)

        self._ct_var = tk.IntVar(value=gs("ct_k"))
        tk.Label(ftr, text="TEMP", font=FS, bg=C["panel"],
                 fg=C["dim"]).pack(side=tk.LEFT, padx=(14, 2))
        self._mk_slider(ftr, self._ct_var, 1500, 9000,
                        self._on_ct_quick, length=90).pack(side=tk.LEFT)
        self._ct_lbl = tk.Label(ftr, text=f"{gs('ct_k')}K", font=FS,
                                 bg=C["panel"], fg=C["acc3"], width=5)
        self._ct_lbl.pack(side=tk.LEFT)

    # ── Sidebar helpers ───────────────────────────────────────────────────────
    def _add_mode_btn(self, parent, mode: str,
                       label: str = None, accent: str = None):
        txt   = label or f"  {MODE_LABEL.get(mode, mode)}"
        color = accent or C["text"]
        lbl   = tk.Label(parent, text=txt, font=FM, bg=C["panel"],
                          fg=color, anchor=tk.W, pady=5, cursor="hand2")
        lbl.pack(fill=tk.X, padx=6)
        lbl.bind("<Button-1>", lambda e, m=mode: self._select_mode(m))
        self._mbtns[mode] = lbl

    def _highlight_mode(self, active: str):
        for m, btn in self._mbtns.items():
            is_a = (m == active)
            btn.config(
                fg=(C["accent"] if is_a else
                    C["acc3"]  if m == "presets" else
                    C["dim"]   if m == "settings" else C["text"]),
                bg=C["active"] if is_a else C["panel"],
            )

    def _select_mode(self, m: str):
        self._mode.set(m)
        if m not in ("settings", "presets"):
            ss("mode", m)
        self._highlight_mode(m)
        self._show_panel(m)
        if m == "presets":
            self._refresh_presets_list()

    def _show_panel(self, m: str):
        for p in self._panels.values():
            p.pack_forget()
        self._panels[m].pack(fill=tk.BOTH, expand=True, padx=26, pady=16)

    # ── Footer controls ───────────────────────────────────────────────────────
    def _toggle_on(self, _=None):
        v = not self._on.get()
        self._on.set(v)
        ss("strip_on", v)
        self._refresh_on_btn()

    def _refresh_on_btn(self):
        if self._on.get():
            self._on_btn.config(text="  ON  ", bg=C["accent"], fg="#000")
        else:
            self._on_btn.config(text=" OFF  ", bg=C["panel3"], fg=C["dim"])

    def _on_br(self, v):
        n = int(float(v))
        ss("brightness", n, save=False)
        self._br_lbl.config(text=f"{n}%")

    def _on_spd(self, v):
        n = int(float(v))
        ss("speed", n, save=False)
        self._spd_lbl.config(text=f"{n}%")

    def _on_ct_quick(self, v):
        k = int(float(v))
        apply_color_temp(k)
        self._ct_lbl.config(text=f"{k}K")
        try:
            self._ct_settings_var.set(k)
        except AttributeError:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    #  WIDGET HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _mk_slider(self, parent, var, lo, hi, cmd, length=200):
        """Footer-style slider (panel background)."""
        return ttk.Scale(parent, variable=var, from_=lo, to=hi,
                         orient=tk.HORIZONTAL, length=length,
                         style="G.Horizontal.TScale", command=cmd)

    def _mk_slider_bg(self, parent, var, lo, hi, cmd, length=220):
        """Panel-body slider (bg background)."""
        return ttk.Scale(parent, variable=var, from_=lo, to=hi,
                         orient=tk.HORIZONTAL, length=length,
                         style="P.Horizontal.TScale", command=cmd)

    def _section(self, parent, txt, pady=(14, 4)):
        tk.Label(parent, text=txt, font=FL, bg=C["bg"],
                 fg=C["dim"]).pack(anchor=tk.W, pady=pady)

    def _swatch(self, parent, rgb, cb):
        sw = tk.Label(parent, bg=_hex(*rgb), width=8, height=2, cursor="hand2")
        sw.bind("<Button-1>", cb)
        return sw

    def _preset_row(self, parent, cols, cb):
        row = tk.Frame(parent, bg=C["bg"])
        row.pack(anchor=tk.W, pady=(4, 0))
        for col in cols:
            b = tk.Label(row, bg=_hex(*col), width=3, height=1, cursor="hand2")
            b.pack(side=tk.LEFT, padx=2)
            b.bind("<Button-1>", lambda e, c=col: cb(list(c)))

    def _pick(self, current_rgb, callback):
        res = colorchooser.askcolor(color=_hex(*current_rgb),
                                     title="Pick Colour", parent=self)
        if res and res[0]:
            callback([int(x) for x in res[0]])

    # ══════════════════════════════════════════════════════════════════════════
    #  SCREEN SYNC PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sync_panel(self, p: tk.Frame):
        tk.Label(p, text="SCREEN SYNC", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack(anchor=tk.W, pady=(0, 10))

        cols = tk.Frame(p, bg=C["bg"]); cols.pack(fill=tk.X, pady=(12, 0))
        left  = tk.Frame(cols, bg=C["bg"]); left.pack(side=tk.LEFT, fill=tk.Y)
        right = tk.Frame(cols, bg=C["bg"]); right.pack(side=tk.LEFT, padx=(20, 0))

        sr_var = tk.DoubleVar(value=gs("sample_region"))
        sr_lbl = tk.Label(left, text=f"{int(gs('sample_region')*100)} %",
                           font=FS, bg=C["bg"], fg=C["accent"])
        tk.Label(left, text="SAMPLE REGION", font=FL,
                 bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W)
        row1 = tk.Frame(left, bg=C["bg"]); row1.pack(anchor=tk.W, pady=(4, 0))
        def _on_sr(v):
            x = round(float(v), 2); ss("sample_region", x, save=False)
            sr_lbl.config(text=f"{int(x*100)} %")
            self._update_sample_canvas(x)
        self._mk_slider_bg(row1, sr_var, 0.10, 1.00, _on_sr, length=180).pack(side=tk.LEFT)
        sr_lbl.pack(side=tk.LEFT, padx=8)

        sm_var = tk.DoubleVar(value=gs("smoothing"))
        sm_lbl = tk.Label(left, text=f"{gs('smoothing'):.2f}",
                           font=FS, bg=C["bg"], fg=C["accent"])
        tk.Label(left, text="EMA SMOOTHING  (α)", font=FL,
                 bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W, pady=(12, 0))
        row2 = tk.Frame(left, bg=C["bg"]); row2.pack(anchor=tk.W, pady=(4, 0))
        def _on_sm(v):
            x = round(float(v), 2); ss("smoothing", x, save=False)
            sm_lbl.config(text=f"{x:.2f}")
        self._mk_slider_bg(row2, sm_var, 0.02, 1.00, _on_sm, length=180).pack(side=tk.LEFT)
        sm_lbl.pack(side=tk.LEFT, padx=8)

        bt_var = tk.IntVar(value=gs("black_thresh"))
        bt_lbl = tk.Label(left, text=f"{gs('black_thresh')}",
                           font=FS, bg=C["bg"], fg=C["accent"])
        tk.Label(left, text="BLACKOUT THRESHOLD", font=FL,
                 bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W, pady=(12, 0))
        row3 = tk.Frame(left, bg=C["bg"]); row3.pack(anchor=tk.W, pady=(4, 0))
        def _on_bt(v):
            x = int(float(v)); ss("black_thresh", x, save=False)
            bt_lbl.config(text=str(x))
        self._mk_slider_bg(row3, bt_var, 0, 60, _on_bt, length=180).pack(side=tk.LEFT)
        bt_lbl.pack(side=tk.LEFT, padx=8)

        tk.Label(right, text="SAMPLED AREA", font=FL,
                 bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W)
        self._sample_canvas = tk.Canvas(right, width=210, height=130,
                                         bg=C["bg"], highlightthickness=0)
        self._sample_canvas.pack(anchor=tk.W, pady=(8, 0))
        MX, MY, MW, MH = 15, 8, 175, 108
        self._sample_canvas.create_rectangle(MX-4, MY-4, MX+MW+4, MY+MH+4,
                                              fill="#1a1a1a", outline="#383838")
        self._sample_canvas.create_rectangle(MX, MY, MX+MW, MY+MH,
                                              fill="#0c0c0c", outline="#2e2e2e")
        cx = MX + MW // 2
        self._sample_canvas.create_rectangle(cx-14, MY+MH+4, cx+14, MY+MH+11,
                                              fill="#1a1a1a", outline="")
        self._sample_canvas.create_rectangle(cx-24, MY+MH+11, cx+24, MY+MH+15,
                                              fill="#1a1a1a", outline="")
        self._mon_rect = (MX, MY, MW, MH)
        self._sr_rect  = self._sample_canvas.create_rectangle(0, 0, 1, 1,
                                                               fill="#002b1a", outline=C["accent"])
        self._sr_text  = self._sample_canvas.create_text(0, 0, text="",
                                                          fill=C["accent"], font=("Consolas", 8))
        self._update_sample_canvas(gs("sample_region"))

        ll_sep = tk.Frame(p, bg=C["bg"]); ll_sep.pack(anchor=tk.W, pady=(16, 0))
        self._ll_var = tk.BooleanVar(value=gs("sc_low_latency"))
        self._ll_btn = tk.Label(ll_sep, text="", font=FL, cursor="hand2", padx=6, pady=4)
        self._ll_btn.pack(side=tk.LEFT)
        self._ll_btn.bind("<Button-1>", self._toggle_low_latency)
        self._refresh_ll_btn()
        tk.Label(ll_sep,
                 text="  LOW-LATENCY MODE  — skips smoothing & correction for fastest response",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(side=tk.LEFT)

    def _update_sample_canvas(self, frac: float):
        MX, MY, MW, MH = self._mon_rect
        sw = MW * frac; sh = MH * frac
        sx = MX + (MW - sw) / 2; sy = MY + (MH - sh) / 2
        self._sample_canvas.coords(self._sr_rect, sx, sy, sx+sw, sy+sh)
        self._sample_canvas.coords(self._sr_text, MX + MW/2, MY + MH/2)
        self._sample_canvas.itemconfig(self._sr_text, text=f"{int(frac*100)} %")

    def _toggle_low_latency(self, _=None):
        v = not self._ll_var.get(); self._ll_var.set(v); ss("sc_low_latency", v)
        self._refresh_ll_btn()

    def _refresh_ll_btn(self):
        on = self._ll_var.get()
        try:
            self._ll_btn.config(text=" ENABLED " if on else "  ENABLE  ",
                                 bg=C["accent"] if on else C["panel3"],
                                 fg="#000" if on else C["dim"])
        except (AttributeError, tk.TclError):
            pass

    # ══════════════════════════════════════════════════════════════════════════
    #  MUSIC SYNC PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_music_panel(self, p: tk.Frame):
        tk.Label(p, text="MUSIC SYNC", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["acc3"]).pack(anchor=tk.W, pady=(0, 6))

        if not audio_engine._PAW_OK and not audio_engine._SD_OK:
            tk.Label(p,
                text="No audio backend found.\n\n"
                     "Install the recommended backend:\n  pip install pyaudiowpatch\n\n"
                     "Or the fallback:\n  pip install sounddevice\n\nThen restart.",
                font=FM, bg=C["bg"], fg=C["acc2"]).pack(anchor=tk.W)
            return

        if not audio_engine._PAW_OK:
            tk.Label(p,
                text="⚠  pyaudiowpatch not found — using sounddevice fallback.\n"
                     "   For true silence when idle:  pip install pyaudiowpatch",
                font=FS, bg=C["bg"], fg=C["acc2"]).pack(anchor=tk.W, pady=(0, 4))

        self._section(p, "AUDIO OUTPUT DEVICE", pady=(0, 4))

        # Status labels
        self._mu_stat_lbl = tk.Label(p, text="", font=FS, bg=C["bg"], fg=C["dim"])
        self._mu_stat_lbl.pack(anchor=tk.W)
        self._mu_dev_lbl = tk.Label(p, text="", font=FS, bg=C["bg"], fg=C["acc3"])
        self._mu_dev_lbl.pack(anchor=tk.W)
        self._mu_err_lbl = tk.Label(p, text="", font=FS, bg=C["bg"], fg=C["acc2"],
                                     wraplength=560, justify=tk.LEFT)
        self._mu_err_lbl.pack(anchor=tk.W)
        self._refresh_mu_status()
        self.after(1500, self._poll_mu_status)

        # Restart audio button
        rst_row = tk.Frame(p, bg=C["bg"]); rst_row.pack(anchor=tk.W, pady=(4, 0))
        rst_btn = tk.Label(rst_row, text=" ↺ RESTART AUDIO ", font=FS,
                            bg=C["panel3"], fg=C["text"], cursor="hand2", padx=6, pady=3)
        rst_btn.pack(side=tk.LEFT)
        rst_btn.bind("<Button-1>",
                     lambda e: threading.Thread(
                         target=audio_engine.restart_audio, daemon=True).start())

        # VU Bars
        self._section(p, "LIVE SIGNAL  (Bass / Mids / Highs)", pady=(6, 4))
        VU_W, VU_H = 320, 74
        LABEL_W = 44; BAR_MAX = VU_W - LABEL_W - 4
        self._vu_canvas = tk.Canvas(p, width=VU_W, height=VU_H,
                                     bg="#0d0d0d", highlightthickness=1,
                                     highlightbackground=C["border"])
        self._vu_canvas.pack(anchor=tk.W, pady=(0, 6))
        _vu_cols = [C["vu_bass"], C["vu_mids"], C["vu_high"]]
        _vu_lbls = ["BASS", "MIDS", "HIGH"]
        for i, (lbl, col) in enumerate(zip(_vu_lbls, _vu_cols)):
            y = 12 + i * 22
            self._vu_canvas.create_text(4, y, text=lbl, fill=col,
                                         font=("Consolas", 7, "bold"), anchor=tk.W)
        self._vu_bars = []
        self._vu_peak_decay = [0.0, 0.0, 0.0]
        self._vu_peak_items = []
        for i in range(3):
            y1 = 5 + i * 22; y2 = y1 + 13
            self._vu_canvas.create_rectangle(LABEL_W, y1, LABEL_W + BAR_MAX, y2,
                                              fill="#1a1a1a", outline="")
            item = self._vu_canvas.create_rectangle(LABEL_W, y1, LABEL_W, y2,
                                                     fill=_vu_cols[i], outline="")
            self._vu_bars.append(item)
            pk = self._vu_canvas.create_rectangle(LABEL_W, y1, LABEL_W+2, y2,
                                                   fill="#ffffff", outline="")
            self._vu_peak_items.append(pk)
        self._vu_bar_max   = BAR_MAX
        self._vu_label_w   = LABEL_W
        self._vu_update()

        # Mode selector
        self._section(p, "VISUALISATION MODE", pady=(4, 4))
        self._mu_mode = tk.StringVar(value=gs("music_mode"))

        def _set_mu_mode(m):
            self._mu_mode.set(m); ss("music_mode", m)
            self._mu_spec_desc.config(fg=C["acc3"] if m == "spectrum" else C["dim"])
            self._mu_reac_desc.config(fg=C["acc3"] if m == "reactive"  else C["dim"])

        for txt, val in [
            ("◉  Spectrum   (Bass=R · Mids=G · Highs=B)", "spectrum"),
            ("◉  Reactive   (Hue tracks pitch · Brightness tracks beat)", "reactive"),
        ]:
            b = tk.Label(p, text=txt, font=FM, bg=C["bg"],
                          fg=C["acc3"] if gs("music_mode") == val else C["dim"],
                          cursor="hand2", pady=3)
            b.pack(anchor=tk.W)
            b.bind("<Button-1>", lambda e, v=val: _set_mu_mode(v))
            if val == "spectrum": self._mu_spec_desc = b
            else:                 self._mu_reac_desc = b

        # Reactive colour picker
        rc_frame = tk.Frame(p, bg=C["bg"]); rc_frame.pack(anchor=tk.W, pady=4)
        rc = gs("music_color")
        self._mu_rc_sw = tk.Label(rc_frame, bg=_hex(*rc),
                                    width=6, height=1, cursor="hand2")
        self._mu_rc_sw.pack(side=tk.LEFT, padx=(24, 6))
        tk.Label(rc_frame,
                 text="hue centre for reactive mode  (shifts ±0.38 with pitch)",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(side=tk.LEFT)
        self._mu_rc_sw.bind("<Button-1>",
            lambda e: self._pick(gs("music_color"), self._set_mu_color))

        # Album art
        aa_frame = tk.Frame(p, bg=C["bg"]); aa_frame.pack(anchor=tk.W, pady=(2, 4))
        self._aa_var = tk.BooleanVar(value=gs("album_art_enabled"))
        self._aa_btn = tk.Label(aa_frame, text="", font=FL, cursor="hand2", padx=6, pady=3)
        self._aa_btn.pack(side=tk.LEFT, padx=(24, 0))
        def _toggle_aa(_=None):
            v = not self._aa_var.get(); self._aa_var.set(v)
            ss("album_art_enabled", v)
            self._aa_btn.config(text=" ART COLOR ON " if v else " ART COLOR OFF",
                                 bg=C["acc3"] if v else C["panel3"],
                                 fg="#000" if v else C["dim"])
            if v:
                threading.Thread(target=_album_art_mod.fetch_album_art_color_thread,
                                 daemon=True, name="AlbumArtManual").start()
        self._aa_btn.bind("<Button-1>", _toggle_aa)
        is_aa = gs("album_art_enabled")
        self._aa_btn.config(text=" ART COLOR ON " if is_aa else " ART COLOR OFF",
                             bg=C["acc3"] if is_aa else C["panel3"],
                             fg="#000" if is_aa else C["dim"])
        tk.Label(aa_frame, text="  auto-match hue to now-playing album art  (Spotify)",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(side=tk.LEFT, padx=6)
        art_color = _album_art_mod.get_album_art_color()
        self._aa_swatch = tk.Label(aa_frame, bg=_hex(*art_color), width=3, height=1)
        self._aa_swatch.pack(side=tk.LEFT, padx=4)

        # Sensitivity
        self._section(p, "SENSITIVITY", pady=(8, 0))
        ms_var = tk.IntVar(value=gs("music_sens"))
        ms_lbl = tk.Label(p, text=f"{gs('music_sens')} %",
                           font=FS, bg=C["bg"], fg=C["acc3"])
        row = tk.Frame(p, bg=C["bg"]); row.pack(anchor=tk.W, pady=(4, 0))
        def _on_ms(v):
            x = int(float(v)); ss("music_sens", x, save=False)
            ms_lbl.config(text=f"{x} %")
        self._mk_slider_bg(row, ms_var, 0, 100, _on_ms, length=200).pack(side=tk.LEFT)
        ms_lbl.pack(side=tk.LEFT, padx=8)

    def _vu_update(self):
        try:
            DECAY = 0.06
            vu = audio_engine.get_vu_data()
            for i, val in enumerate(vu):
                x1 = self._vu_label_w
                x2 = x1 + max(1, int(val * self._vu_bar_max))
                y1 = 5 + i * 22; y2 = y1 + 13
                self._vu_canvas.coords(self._vu_bars[i], x1, y1, x2, y2)
                if val >= self._vu_peak_decay[i]:
                    self._vu_peak_decay[i] = val
                else:
                    self._vu_peak_decay[i] = max(self._vu_peak_decay[i] - DECAY, 0.0)
                px = x1 + max(0, int(self._vu_peak_decay[i] * self._vu_bar_max) - 2)
                self._vu_canvas.coords(self._vu_peak_items[i], px, y1, px+2, y2)
            self.after(50, self._vu_update)
        except tk.TclError:
            pass

    def _set_mu_color(self, rgb):
        ss("music_color", rgb)
        self._mu_rc_sw.config(bg=_hex(*rgb))

    def _apply_album_art_color(self, rgb: list):
        try:
            ss("music_color", rgb)
            self._mu_rc_sw.config(bg=_hex(*rgb))
            self._aa_swatch.config(bg=_hex(*rgb))
        except (AttributeError, tk.TclError):
            pass

    def _paste_clipboard_color(self):
        try:
            text = self.clipboard_get().strip().lstrip("#")
            if len(text) == 6:
                r = int(text[0:2], 16)
                g = int(text[2:4], 16)
                b = int(text[4:6], 16)
                rgb = [r, g, b]
                self._apply_solid(rgb)
                self._on_btn.config(bg=_hex(*rgb))
                self.after(400, self._refresh_on_btn)
        except Exception:
            pass

    def _refresh_mu_status(self):
        try:
            info = audio_engine.get_audio_status()
            st, dev, backend = info["status"], info["device"], info["backend"]
            if st == "running":
                be_tag = f"  [{backend}]" if backend else ""
                self._mu_stat_lbl.config(text=f"● capturing{be_tag}", fg=C["accent"])
                self._mu_dev_lbl.config(text=f"  ↳ {dev}" if dev else "", fg=C["acc3"])
                self._mu_err_lbl.config(text="")
            elif st == "starting":
                self._mu_stat_lbl.config(text="● starting…", fg=C["dim"])
                self._mu_dev_lbl.config(text=""); self._mu_err_lbl.config(text="")
            elif st == "error":
                self._mu_stat_lbl.config(text="● capture failed", fg=C["acc2"])
                self._mu_dev_lbl.config(text="")
                self._mu_err_lbl.config(text=info["error"] or "unknown error")
            else:
                self._mu_stat_lbl.config(text="● idle", fg=C["dim"])
                self._mu_dev_lbl.config(text=""); self._mu_err_lbl.config(text="")
        except tk.TclError:
            pass

    def _poll_mu_status(self):
        self._refresh_mu_status()
        try:
            self.after(1500, self._poll_mu_status)
        except tk.TclError:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    #  SOLID COLOR PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_solid_panel(self, p):
        tk.Label(p, text="SOLID COLOR", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack(anchor=tk.W, pady=(0, 8))
        col = gs("color")
        self._sol_sw = self._swatch(p, col,
                           lambda e: self._pick(gs("color"), self._apply_solid))
        self._sol_sw.pack(anchor=tk.W)
        self._sol_hex = tk.Label(p, text=_hex(*col), font=("Consolas", 11, "bold"),
                                  bg=C["bg"], fg=C["text"])
        self._sol_hex.pack(anchor=tk.W, pady=(4, 2))
        tk.Label(p, text="↑ click swatch to open colour picker",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W)
        self._section(p, "QUICK PRESETS")
        self._preset_row(p,
            [(255,0,80),(255,80,0),(255,200,0),(0,255,100),(0,180,255),
             (90,0,255),(255,0,200),(255,255,255),(255,130,0)],
            self._apply_solid)
        self._section(p, "COLOR HISTORY", pady=(14, 4))
        tk.Label(p, text="Last 16 applied colours — click to re-apply",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W, pady=(0, 4))
        self._hist_frame = tk.Frame(p, bg=C["bg"])
        self._hist_frame.pack(anchor=tk.W)
        self._refresh_color_history()

    def _refresh_color_history(self):
        try:
            for w in self._hist_frame.winfo_children():
                w.destroy()
            hist = gs("color_history")
            if not hist:
                tk.Label(self._hist_frame, text="(no history yet)",
                         font=FS, bg=C["bg"], fg=C["dim"]).pack(side=tk.LEFT)
                return
            for col in hist:
                b = tk.Label(self._hist_frame, bg=_hex(*col),
                              width=3, height=1, cursor="hand2")
                b.pack(side=tk.LEFT, padx=2)
                b.bind("<Button-1>", lambda e, c=col: self._apply_solid(list(c)))
        except tk.TclError:
            pass

    def _apply_solid(self, rgb):
        ss("color", rgb); h = _hex(*rgb)
        try:
            self._sol_sw.config(bg=h); self._sol_hex.config(text=h)
        except (AttributeError, tk.TclError):
            pass
        self._sync_shared(rgb)
        push_color_history(rgb)

    # ══════════════════════════════════════════════════════════════════════════
    #  EFFECT PANELS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_breathe_panel(self, p):
        tk.Label(p, text="BREATHING", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack(anchor=tk.W, pady=(0, 10))
        rb_row = tk.Frame(p, bg=C["bg"]); rb_row.pack(anchor=tk.W, pady=(0, 10))
        self._br_rb_var = tk.BooleanVar(value=gs("breathe_rainbow"))
        self._br_rb_btn = tk.Label(rb_row, text="", font=FL, cursor="hand2", padx=6, pady=4)
        self._br_rb_btn.pack(side=tk.LEFT)
        def _toggle_br_rb(_=None):
            v = not self._br_rb_var.get(); self._br_rb_var.set(v)
            ss("breathe_rainbow", v)
            self._br_rb_btn.config(text=" RAINBOW ON " if v else " RAINBOW OFF",
                                    bg=C["acc3"] if v else C["panel3"],
                                    fg="#000" if v else C["dim"])
            self._br_color_frame.pack_forget() if v else self._br_color_frame.pack(anchor=tk.W)
        self._br_rb_btn.bind("<Button-1>", _toggle_br_rb)
        is_rb = gs("breathe_rainbow")
        self._br_rb_btn.config(text=" RAINBOW ON " if is_rb else " RAINBOW OFF",
                                bg=C["acc3"] if is_rb else C["panel3"],
                                fg="#000" if is_rb else C["dim"])
        tk.Label(rb_row, text="  cycle through all hues while breathing",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(side=tk.LEFT)
        self._section(p, "COLOUR")
        self._br_color_frame = tk.Frame(p, bg=C["bg"])
        self._br_sw = self._swatch(self._br_color_frame, gs("color"),
                           lambda e: self._pick(gs("color"), self._apply_shared))
        self._br_sw.pack(anchor=tk.W)
        self._br_hex = tk.Label(self._br_color_frame, text=_hex(*gs("color")),
                                  font=FM, bg=C["bg"], fg=C["text"])
        self._br_hex.pack(anchor=tk.W, pady=(4, 0))
        self._preset_row(self._br_color_frame,
            [(0,255,140),(0,180,255),(255,0,80),(255,255,255),(255,100,0)],
            self._apply_shared)
        if not is_rb:
            self._br_color_frame.pack(anchor=tk.W)

    def _build_rainbow_panel(self, p):
        tk.Label(p, text="RAINBOW CYCLE", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack(anchor=tk.W, pady=(0, 10))
        bar = tk.Canvas(p, width=340, height=22, bg=C["bg"], highlightthickness=0)
        bar.pack(anchor=tk.W)
        for i in range(340):
            r, g, b = (int(x*255) for x in colorsys.hsv_to_rgb(i/340, 1.0, 1.0))
            bar.create_line(i, 0, i, 22, fill=_hex(r, g, b))
        tk.Label(p, text="← full spectrum preview",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W, pady=(4, 0))

    def _build_strobe_panel(self, p):
        tk.Label(p, text="STROBE", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack(anchor=tk.W, pady=(0, 10))
        rb_row = tk.Frame(p, bg=C["bg"]); rb_row.pack(anchor=tk.W, pady=(0, 10))
        self._st_rb_var = tk.BooleanVar(value=gs("strobe_rainbow"))
        self._st_rb_btn = tk.Label(rb_row, text="", font=FL, cursor="hand2", padx=6, pady=4)
        self._st_rb_btn.pack(side=tk.LEFT)
        def _toggle_st_rb(_=None):
            v = not self._st_rb_var.get(); self._st_rb_var.set(v)
            ss("strobe_rainbow", v)
            self._st_rb_btn.config(text=" RAINBOW ON " if v else " RAINBOW OFF",
                                    bg=C["acc3"] if v else C["panel3"],
                                    fg="#000" if v else C["dim"])
            self._st_color_frame.pack_forget() if v else self._st_color_frame.pack(anchor=tk.W)
        self._st_rb_btn.bind("<Button-1>", _toggle_st_rb)
        is_rb_st = gs("strobe_rainbow")
        self._st_rb_btn.config(text=" RAINBOW ON " if is_rb_st else " RAINBOW OFF",
                                bg=C["acc3"] if is_rb_st else C["panel3"],
                                fg="#000" if is_rb_st else C["dim"])
        tk.Label(rb_row, text="  flash through full spectrum on each strobe pulse",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(side=tk.LEFT)
        self._section(p, "STROBE COLOUR")
        self._st_color_frame = tk.Frame(p, bg=C["bg"])
        self._st_sw = self._swatch(self._st_color_frame, gs("color"),
                           lambda e: self._pick(gs("color"), self._apply_shared))
        self._st_sw.pack(anchor=tk.W)
        self._st_hex = tk.Label(self._st_color_frame, text=_hex(*gs("color")),
                                  font=FM, bg=C["bg"], fg=C["text"])
        self._st_hex.pack(anchor=tk.W, pady=(4, 0))
        self._preset_row(self._st_color_frame,
            [(255,255,255),(255,0,80),(0,200,255),(255,150,0),(0,255,100)],
            self._apply_shared)
        if not is_rb_st:
            self._st_color_frame.pack(anchor=tk.W)

    def _apply_shared(self, rgb):
        ss("color", rgb); self._sync_shared(rgb)
        push_color_history(rgb)

    def _sync_shared(self, rgb):
        h = _hex(*rgb)
        for sw, lx in [("_br_sw", "_br_hex"), ("_st_sw", "_st_hex")]:
            try:
                getattr(self, sw).config(bg=h)
                getattr(self, lx).config(text=h)
            except (AttributeError, tk.TclError):
                pass

    def _build_wave_panel(self, p):
        tk.Label(p, text="COLOR WAVE", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack(anchor=tk.W, pady=(0, 10))
        self._section(p, "COLOUR STOPS")
        self._wc_frame = tk.Frame(p, bg=C["bg"]); self._wc_frame.pack(anchor=tk.W)
        self._rebuild_wave()

    def _rebuild_wave(self):
        for w in self._wc_frame.winfo_children(): w.destroy()
        wc = gs("wave_colors")
        for i, col in enumerate(wc):
            card = tk.Frame(self._wc_frame, bg=C["bg"]); card.pack(side=tk.LEFT, padx=4)
            sw = tk.Label(card, bg=_hex(*col), width=6, height=2, cursor="hand2")
            sw.pack()
            sw.bind("<Button-1>", lambda e, idx=i, c=col:
                    self._pick(c, lambda rgb, ii=idx: self._wc_set(ii, rgb)))
            if len(wc) > 1:
                d = tk.Label(card, text="✕", font=FS, bg=C["bg"],
                              fg=C["dim"], cursor="hand2")
                d.pack()
                d.bind("<Button-1>", lambda e, idx=i: self._wc_del(idx))
        if len(wc) < 8:
            add = tk.Label(self._wc_frame, text=" + ", font=("Consolas", 12),
                            bg=C["panel3"], fg=C["accent"], cursor="hand2",
                            padx=6, pady=10)
            add.pack(side=tk.LEFT, padx=4)
            add.bind("<Button-1>", lambda e: self._pick((128,128,128), self._wc_add))

    def _wc_set(self, idx, rgb):
        wc = gs("wave_colors"); wc[idx] = list(rgb); ss("wave_colors", wc); self._rebuild_wave()
    def _wc_del(self, idx):
        wc = gs("wave_colors")
        if len(wc) > 1: wc.pop(idx); ss("wave_colors", wc); self._rebuild_wave()
    def _wc_add(self, rgb):
        wc = gs("wave_colors"); wc.append(list(rgb)); ss("wave_colors", wc); self._rebuild_wave()

    def _build_candle_panel(self, p):
        tk.Label(p, text="CANDLELIGHT", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack(anchor=tk.W, pady=(0, 10))
        row = tk.Frame(p, bg=C["bg"]); row.pack(anchor=tk.W)
        for col in [(255,147,41),(255,100,10),(255,180,50),(255,60,0),(255,200,80)]:
            tk.Label(row, bg=_hex(*col), width=5, height=2).pack(side=tk.LEFT, padx=3)
        tk.Label(row, text=" ← warm palette (automatic)",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(side=tk.LEFT, padx=8)

    # ══════════════════════════════════════════════════════════════════════════
    #  PRESETS PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_presets_panel(self, p: tk.Frame):
        tk.Label(p, text="PRESETS", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["acc3"]).pack(anchor=tk.W, pady=(0, 4))
        tk.Label(p, text="Apply a scene instantly · Save your own · Delete unwanted.",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W, pady=(0, 10))
        save_row = tk.Frame(p, bg=C["bg"]); save_row.pack(anchor=tk.W, pady=(0, 10))
        save_btn = tk.Label(save_row, text=" + SAVE CURRENT ", font=FL,
                             bg=C["acc3"], fg="#000", cursor="hand2", padx=6, pady=4)
        save_btn.pack(side=tk.LEFT)
        save_btn.bind("<Button-1>", self._save_scene)
        tk.Label(save_row, text="  saves mode + colour + brightness + speed",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(side=tk.LEFT)
        tk.Frame(p, bg=C["border"], height=1).pack(fill=tk.X, pady=(0, 8))
        outer = tk.Frame(p, bg=C["bg"]); outer.pack(fill=tk.BOTH, expand=True)
        self._sc_canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=self._sc_canvas.yview)
        self._sc_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._sc_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._sc_inner = tk.Frame(self._sc_canvas, bg=C["bg"])
        _wid = self._sc_canvas.create_window((0, 0), window=self._sc_inner, anchor="nw")
        self._sc_canvas.bind("<Configure>", lambda e: self._sc_canvas.itemconfig(_wid, width=e.width))
        self._sc_inner.bind("<Configure>", lambda e: self._sc_canvas.configure(
            scrollregion=self._sc_canvas.bbox("all")))
        self._sc_canvas.bind_all("<MouseWheel>",
            lambda e: self._sc_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._refresh_presets_list()

    def _refresh_presets_list(self):
        try:
            for w in self._sc_inner.winfo_children(): w.destroy()
        except (AttributeError, tk.TclError): return
        scenes = gs("scenes")
        if not scenes:
            tk.Label(self._sc_inner, text="No presets saved yet.",
                     font=FM, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W, pady=8)
            return
        for name, data in scenes.items():
            col  = data.get("color", [0, 255, 140])
            mode = data.get("mode", M_SOLID)
            br   = data.get("brightness", 75); spd = data.get("speed", 50)
            row  = tk.Frame(self._sc_inner, bg=C["panel2"])
            row.pack(fill=tk.X, pady=3, padx=4)
            tk.Label(row, bg=_hex(*col), width=5, height=2).pack(side=tk.LEFT, padx=(8,6))
            info = tk.Frame(row, bg=C["panel2"]); info.pack(side=tk.LEFT, fill=tk.Y, pady=6)
            tk.Label(info, text=name, font=FL, bg=C["panel2"], fg=C["text"]).pack(anchor=tk.W)
            tk.Label(info,
                     text=f"{MODE_LABEL.get(mode, mode)}  ·  {br}% bright  ·  {spd}% speed",
                     font=FS, bg=C["panel2"], fg=C["dim"]).pack(anchor=tk.W)
            btn_f = tk.Frame(row, bg=C["panel2"]); btn_f.pack(side=tk.RIGHT, padx=8)
            apply_b = tk.Label(btn_f, text=" ▶ APPLY ", font=FS,
                                bg=C["accent"], fg="#000", cursor="hand2", padx=4, pady=3)
            apply_b.pack(pady=(8, 2))
            apply_b.bind("<Button-1>", lambda e, d=data: self._apply_scene(d))
            del_b = tk.Label(btn_f, text=" ✕ DELETE ", font=FS,
                              bg=C["panel3"], fg=C["acc2"], cursor="hand2", padx=4, pady=3)
            del_b.pack(pady=(0, 8))
            del_b.bind("<Button-1>", lambda e, n=name: self._delete_scene(n))

    def _apply_scene(self, data: dict):
        mode = data.get("mode", M_SOLID); col = data.get("color", [0, 255, 140])
        br   = data.get("brightness", 75); spd = data.get("speed", 50)
        ss("mode", mode); ss("color", col); ss("brightness", br); ss("speed", spd)
        self._br.set(br);  self._br_lbl.config(text=f"{br}%")
        self._spd.set(spd); self._spd_lbl.config(text=f"{spd}%")
        self._select_mode(mode)

    def _save_scene(self, _=None):
        name = simpledialog.askstring("Save Preset", "Name for this preset:", parent=self)
        if not name or not name.strip(): return
        name = name.strip()[:24]
        scenes = dict(gs("scenes"))
        scenes[name] = {"mode": gs("mode"), "color": gs("color"),
                         "brightness": gs("brightness"), "speed": gs("speed")}
        ss("scenes", scenes); self._refresh_presets_list()

    def _delete_scene(self, name: str):
        if not messagebox.askyesno("Delete Preset", f'Delete preset "{name}"?', parent=self): return
        scenes = dict(gs("scenes")); scenes.pop(name, None)
        ss("scenes", scenes); self._refresh_presets_list()

    # ══════════════════════════════════════════════════════════════════════════
    #  SETTINGS PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_settings_panel(self, p_outer: tk.Frame):
        outer = tk.Frame(p_outer, bg=C["bg"]); outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        vsb    = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner  = tk.Frame(canvas, bg=C["bg"])
        _wid   = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(_wid, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        p = inner

        tk.Label(p, text="SETTINGS", font=("Consolas", 12, "bold"),
                 bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W, pady=(0, 4))

        # ── Color Temperature ─────────────────────────────────────────────────
        self._section(p, "COLOR TEMPERATURE", pady=(4, 4))
        tk.Label(p, text="Shifts warmth/coolness of every mode.  6500 K = neutral daylight.",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W)
        self._ct_settings_var = tk.IntVar(value=gs("ct_k"))
        ct_bar = tk.Canvas(p, width=300, height=12, bg=C["bg"], highlightthickness=0)
        ct_bar.pack(anchor=tk.W, pady=(8, 2))
        for i in range(300):
            k_val = int(1500 + (i / 299) * (9000 - 1500))
            r, g, b = kelvin_to_gains(k_val)
            mx = max(r, g, b, 1e-9)
            r8 = int(r/mx*200); g8 = int(g/mx*200); b8 = int(b/mx*200)
            ct_bar.create_line(i, 0, i, 12, fill=f"#{r8:02x}{g8:02x}{b8:02x}")
        ct_bar.create_text(4,   6, text="1500K", fill="#555", font=("Consolas",6), anchor=tk.W)
        ct_bar.create_text(296, 6, text="9000K", fill="#555", font=("Consolas",6), anchor=tk.E)
        ct_lbl_v = tk.Label(p, text=f"{gs('ct_k')} K", font=FL, bg=C["bg"], fg=C["acc3"])
        ct_lbl_v.pack(anchor=tk.W)
        def _on_ct_settings(v):
            k = int(float(v)); apply_color_temp(k)
            ct_lbl_v.config(text=f"{k} K")
            self._ct_lbl.config(text=f"{k}K"); self._ct_var.set(k)
        self._mk_slider_bg(p, self._ct_settings_var, 1500, 9000,
                           _on_ct_settings, length=280).pack(anchor=tk.W, pady=(0, 6))
        ct_pre_row = tk.Frame(p, bg=C["bg"]); ct_pre_row.pack(anchor=tk.W, pady=(0, 4))
        tk.Label(ct_pre_row, text="Presets:", font=FS, bg=C["bg"],
                 fg=C["dim"]).pack(side=tk.LEFT, padx=(0, 6))
        for lbl, k_val in [("Candle",1800),("Warm",2700),("Neutral",6500),
                            ("Daylight",7500),("Cool",9000)]:
            def _set_ct(kv=k_val):
                apply_color_temp(kv); self._ct_settings_var.set(kv)
                self._ct_var.set(kv); self._ct_lbl.config(text=f"{kv}K")
                ct_lbl_v.config(text=f"{kv} K")
            b = tk.Label(ct_pre_row, text=f" {lbl} ", font=FS,
                          bg=C["panel3"], fg=C["text"], cursor="hand2", padx=5, pady=3)
            b.pack(side=tk.LEFT, padx=2)
            b.bind("<Button-1>", lambda e, fn=_set_ct: fn())

        # ── White Balance ─────────────────────────────────────────────────────
        self._section(p, "LED WHITE BALANCE", pady=(14, 4))
        tk.Label(p, text="Per-channel gain applied before every write.  "
                          "Tuned for Gesto strip (R weak, B strong).",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W)
        wb_vars = {"R": tk.DoubleVar(value=gs("wb_r")),
                   "G": tk.DoubleVar(value=gs("wb_g")),
                   "B": tk.DoubleVar(value=gs("wb_b"))}
        wb_lbls = {}
        wb_cols = {"R": "#ff5566", "G": "#44ee88", "B": "#5599ff"}
        wb_keys = {"R": "wb_r",   "G": "wb_g",   "B": "wb_b"}
        for ch, var in wb_vars.items():
            row = tk.Frame(p, bg=C["bg"]); row.pack(anchor=tk.W, pady=2)
            tk.Label(row, text=ch, font=FL, bg=C["bg"],
                     fg=wb_cols[ch], width=2).pack(side=tk.LEFT)
            lbl = tk.Label(row, text=f"{var.get():.2f}", font=FS,
                            bg=C["bg"], fg=wb_cols[ch], width=4)
            def _on_wb(v, k=wb_keys[ch], l=lbl):
                x = round(float(v), 2); ss(k, x, save=False); l.config(text=f"{x:.2f}")
            self._mk_slider_bg(row, var, 0.50, 1.50, _on_wb, length=200).pack(side=tk.LEFT, padx=4)
            lbl.pack(side=tk.LEFT); wb_lbls[ch] = lbl
        row_pre = tk.Frame(p, bg=C["bg"]); row_pre.pack(anchor=tk.W, pady=(6, 0))
        tk.Label(row_pre, text="Presets:", font=FS, bg=C["bg"],
                 fg=C["dim"]).pack(side=tk.LEFT, padx=(0, 8))
        for lbl_t, r, g, b in [("Warm",1.05,0.52,0.44),("Neutral",1.00,1.00,1.00),
                                 ("Cool",0.95,0.98,1.05),("Reset",1.00,0.57,0.49)]:
            def _apply_wb(rv=r, gv=g, bv=b):
                ss("wb_r", rv); ss("wb_g", gv); ss("wb_b", bv)
                wb_vars["R"].set(rv); wb_vars["G"].set(gv); wb_vars["B"].set(bv)
                wb_lbls["R"].config(text=f"{rv:.2f}")
                wb_lbls["G"].config(text=f"{gv:.2f}")
                wb_lbls["B"].config(text=f"{bv:.2f}")
            btn = tk.Label(row_pre, text=f" {lbl_t} ", font=FS, bg=C["panel3"],
                            fg=C["text"], cursor="hand2", padx=6, pady=3)
            btn.pack(side=tk.LEFT, padx=3)
            btn.bind("<Button-1>", lambda e, fn=_apply_wb: fn())

        # ── Global Hotkeys ────────────────────────────────────────────────────
        self._section(p, "GLOBAL HOTKEYS", pady=(18, 4))
        hk_col = C["accent"] if hotkeys_ok else C["acc2"]
        tk.Label(p,
                 text=f"Status: {'Registered ✓' if hotkeys_ok else 'Not registered (may need admin)'}",
                 font=FS, bg=C["bg"], fg=hk_col).pack(anchor=tk.W)
        hk_frame = tk.Frame(p, bg=C["bg"]); hk_frame.pack(anchor=tk.W, pady=(6, 0))
        for hk, desc in [
            ("Ctrl+Alt+G",  "Toggle strip on/off"),
            ("Ctrl+Alt+M",  "Open control panel"),
            ("Ctrl+Alt+→",  "Cycle to next mode"),
            ("Ctrl+Alt+↑",  "Brightness +10 %"),
            ("Ctrl+Alt+↓",  "Brightness −10 %"),
            ("Ctrl+Alt+V",  "Paste clipboard hex color to strip"),
        ]:
            row = tk.Frame(hk_frame, bg=C["bg"]); row.pack(anchor=tk.W, pady=1)
            tk.Label(row, text=hk, font=FL, bg=C["bg"],
                     fg=C["accent"], width=16, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(row, text=desc, font=FS, bg=C["bg"], fg=C["dim"]).pack(side=tk.LEFT)

        # ── Startup with Windows ──────────────────────────────────────────────
        self._section(p, "STARTUP WITH WINDOWS", pady=(18, 4))
        self._startup_var = tk.BooleanVar(value=startup_get())
        su_row = tk.Frame(p, bg=C["bg"]); su_row.pack(anchor=tk.W, pady=(8, 0))
        self._su_btn = tk.Label(su_row, text="", font=FL, cursor="hand2", padx=4, pady=4)
        self._su_btn.pack(side=tk.LEFT)
        self._su_btn.bind("<Button-1>", self._toggle_startup)
        self._refresh_su_btn()
        self._su_status = tk.Label(su_row, text="", font=FS, bg=C["bg"], fg=C["dim"])
        self._su_status.pack(side=tk.LEFT, padx=12)
        self._refresh_su_status()

        # ── Close behaviour ───────────────────────────────────────────────────
        self._section(p, "CLOSE BUTTON BEHAVIOUR", pady=(18, 4))
        tk.Label(p, text="Choose what happens when you click ✕ on the window.",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W, pady=(0, 6))
        self._ctt_var = tk.BooleanVar(value=gs("close_to_tray"))

        ctt_row = tk.Frame(p, bg=C["bg"]); ctt_row.pack(anchor=tk.W)

        def _pick_close(to_tray: bool):
            self._ctt_var.set(to_tray)
            ss("close_to_tray", to_tray)
            _refresh_ctt()

        self._ctt_btn_min  = tk.Label(ctt_row, font=FL, cursor="hand2", padx=10, pady=5)
        self._ctt_btn_quit = tk.Label(ctt_row, font=FL, cursor="hand2", padx=10, pady=5)
        self._ctt_btn_min .pack(side=tk.LEFT, padx=(0, 6))
        self._ctt_btn_quit.pack(side=tk.LEFT)
        self._ctt_btn_min .bind("<Button-1>", lambda e: _pick_close(True))
        self._ctt_btn_quit.bind("<Button-1>", lambda e: _pick_close(False))

        def _refresh_ctt():
            to_tray = self._ctt_var.get()
            self._ctt_btn_min.config(
                text=" Minimize to Tray ",
                bg=C["accent"] if to_tray else C["panel3"],
                fg="#000"      if to_tray else C["dim"])
            self._ctt_btn_quit.config(
                text=" Quit App ",
                bg=C["acc2"]   if not to_tray else C["panel3"],
                fg="#000"      if not to_tray else C["dim"])

        _refresh_ctt()
        tk.Label(p,
                 text="  Tip: you can always quit via the tray icon → Quit",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W, pady=(6, 0))

        # ── Schedule / Night Mode ─────────────────────────────────────────────
        self._section(p, "SCHEDULE / NIGHT MODE", pady=(18, 4))
        tk.Label(p, text="Automatically dim + change mode during a time window.",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W)
        self._sched_on = tk.BooleanVar(value=gs("schedule_enabled"))
        sc_row = tk.Frame(p, bg=C["bg"]); sc_row.pack(anchor=tk.W, pady=(8, 4))
        self._sc_btn = tk.Label(sc_row, text="", font=FL, cursor="hand2", padx=4, pady=4)
        self._sc_btn.pack(side=tk.LEFT)
        self._sc_btn.bind("<Button-1>", self._toggle_schedule)
        self._refresh_sc_btn()
        sc_fields = tk.Frame(p, bg=C["bg"]); sc_fields.pack(anchor=tk.W, padx=16)
        def time_row(lbl, key):
            r = tk.Frame(sc_fields, bg=C["bg"]); r.pack(anchor=tk.W, pady=3)
            tk.Label(r, text=lbl, font=FS, bg=C["bg"],
                     fg=C["dim"], width=18, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar(value=gs(key))
            ent = tk.Entry(r, textvariable=var, font=FM, width=7,
                           bg=C["panel2"], fg=C["text"], insertbackground=C["accent"],
                           relief=tk.FLAT)
            ent.pack(side=tk.LEFT, padx=4)
            ent.bind("<FocusOut>", lambda e, k=key, v=var: ss(k, v.get()))
            return var
        time_row("Night start (HH:MM)", "schedule_night_start")
        time_row("Night end   (HH:MM)", "schedule_night_end")

        # ── Auto-Trigger ──────────────────────────────────────────────────────
        self._section(p, "AUTO-TRIGGER", pady=(18, 4))
        tk.Label(p, text="Switch modes automatically when specific apps launch.",
                 font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W)
        at_row = tk.Frame(p, bg=C["bg"]); at_row.pack(anchor=tk.W, pady=(8, 4))
        self._at_on  = tk.BooleanVar(value=gs("auto_trigger"))
        self._at_btn = tk.Label(at_row, text="", font=FL, cursor="hand2", padx=4, pady=4)
        self._at_btn.pack(side=tk.LEFT)
        self._at_btn.bind("<Button-1>", self._toggle_at)
        self._refresh_at_btn()
        self._at_status = tk.Label(p, text="", font=FS, bg=C["bg"], fg=C["dim"])
        self._at_status.pack(anchor=tk.W)
        self._update_at_status()

        # Custom triggers
        self._section(p, "CUSTOM TRIGGERS", pady=(14, 4))
        add_row = tk.Frame(p, bg=C["bg"]); add_row.pack(anchor=tk.W, pady=(0, 6))
        add_btn = tk.Label(add_row, text=" + ADD TRIGGER ", font=FL,
                            bg=C["panel3"], fg=C["accent"], cursor="hand2", padx=6, pady=4)
        add_btn.pack(side=tk.LEFT)
        add_btn.bind("<Button-1>", self._add_custom_trigger)
        self._ct_frame = tk.Frame(p, bg=C["bg"]); self._ct_frame.pack(anchor=tk.W, fill=tk.X)
        self._refresh_custom_triggers()

    def _refresh_custom_triggers(self):
        for w in self._ct_frame.winfo_children(): w.destroy()
        triggers = gs("custom_triggers")
        if not triggers:
            tk.Label(self._ct_frame, text="No custom triggers yet.",
                     font=FS, bg=C["bg"], fg=C["dim"]).pack(anchor=tk.W)
            return
        for i, entry in enumerate(triggers):
            proc  = entry.get("process", "")
            mode  = entry.get("mode", M_SOLID)
            label = entry.get("label", proc)
            row   = tk.Frame(self._ct_frame, bg=C["panel2"])
            row.pack(fill=tk.X, pady=2, padx=0)
            tk.Label(row, text=f"  {label}", font=FL, bg=C["panel2"],
                     fg=C["text"], width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(4,0))
            tk.Label(row, text=proc, font=FS, bg=C["panel2"],
                     fg=C["dim"], width=20, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(row, text=f"→  {MODE_LABEL.get(mode, mode)}", font=FS,
                     bg=C["panel2"], fg=C["acc3"]).pack(side=tk.LEFT, padx=8)
            del_b = tk.Label(row, text=" ✕ ", font=FS, bg=C["panel3"],
                              fg=C["acc2"], cursor="hand2", padx=4, pady=3)
            del_b.pack(side=tk.RIGHT, padx=6, pady=4)
            del_b.bind("<Button-1>", lambda e, idx=i: self._delete_custom_trigger(idx))

    def _add_custom_trigger(self, _=None):
        dlg = tk.Toplevel(self); dlg.title("Add Custom Trigger")
        dlg.configure(bg=C["bg"]); dlg.resizable(False, False); dlg.geometry("360x220")
        tk.Label(dlg, text="ADD CUSTOM TRIGGER", font=FL, bg=C["bg"],
                 fg=C["accent"]).pack(anchor=tk.W, padx=16, pady=(12, 6))
        def field(lbl, default=""):
            r = tk.Frame(dlg, bg=C["bg"]); r.pack(anchor=tk.W, padx=16, pady=3)
            tk.Label(r, text=lbl, font=FS, bg=C["bg"],
                     fg=C["dim"], width=14, anchor=tk.W).pack(side=tk.LEFT)
            v = tk.StringVar(value=default)
            e = tk.Entry(r, textvariable=v, font=FM, width=20,
                         bg=C["panel2"], fg=C["text"],
                         insertbackground=C["accent"], relief=tk.FLAT)
            e.pack(side=tk.LEFT, padx=4); return v
        label_var = field("Display name:", "My App")
        proc_var  = field("Process name:", "myapp.exe")
        r2 = tk.Frame(dlg, bg=C["bg"]); r2.pack(anchor=tk.W, padx=16, pady=3)
        tk.Label(r2, text="Mode:", font=FS, bg=C["bg"],
                 fg=C["dim"], width=14, anchor=tk.W).pack(side=tk.LEFT)
        mode_var = tk.StringVar(value=MODE_LABEL[M_SOLID])
        cb = ttk.Combobox(r2, textvariable=mode_var,
                           values=[MODE_LABEL[m] for m in LED_MODES],
                           state="readonly", font=FS, width=18)
        cb.pack(side=tk.LEFT, padx=4); cb.set(MODE_LABEL[M_SOLID])
        _label_to_mode = {v: k for k, v in MODE_LABEL.items()}
        def _save():
            proc  = proc_var.get().strip().lower()
            label = label_var.get().strip() or proc
            mode  = _label_to_mode.get(mode_var.get(), M_SOLID)
            if not proc:
                messagebox.showwarning("Missing", "Enter a process name.", parent=dlg); return
            triggers = list(gs("custom_triggers"))
            triggers.append({"process": proc, "mode": mode, "label": label})
            ss("custom_triggers", triggers); self._refresh_custom_triggers(); dlg.destroy()
        btn_row = tk.Frame(dlg, bg=C["bg"]); btn_row.pack(anchor=tk.W, padx=16, pady=(12, 0))
        save_b = tk.Label(btn_row, text=" SAVE ", font=FL, bg=C["accent"], fg="#000",
                           cursor="hand2", padx=8, pady=4)
        save_b.pack(side=tk.LEFT)
        save_b.bind("<Button-1>", lambda e: _save())
        cancel_b = tk.Label(btn_row, text=" CANCEL ", font=FS, bg=C["panel3"],
                             fg=C["dim"], cursor="hand2", padx=8, pady=4)
        cancel_b.pack(side=tk.LEFT, padx=(8, 0))
        cancel_b.bind("<Button-1>", lambda e: dlg.destroy())
        dlg.transient(self); dlg.grab_set()

    def _delete_custom_trigger(self, idx: int):
        triggers = list(gs("custom_triggers"))
        if 0 <= idx < len(triggers):
            if messagebox.askyesno("Delete Trigger",
                                    f"Delete trigger for \"{triggers[idx].get('label', '')}\"?",
                                    parent=self):
                triggers.pop(idx); ss("custom_triggers", triggers)
                self._refresh_custom_triggers()

    # ── Settings button helpers ───────────────────────────────────────────────
    def _toggle_startup(self, _=None):
        new_val = not self._startup_var.get()
        self._startup_var.set(new_val); startup_set(new_val)
        self._refresh_su_btn(); self._refresh_su_status()

    def _refresh_su_btn(self):
        on = self._startup_var.get()
        try:
            self._su_btn.config(text=" ENABLED " if on else "  ENABLE  ",
                                 bg=C["accent"] if on else C["panel3"],
                                 fg="#000" if on else C["dim"])
        except (AttributeError, tk.TclError): pass

    def _refresh_su_status(self):
        actual = startup_get()
        try:
            self._su_status.config(text="Registry key written ✓" if actual else "",
                                   fg=C["dim"])
        except (AttributeError, tk.TclError): pass

    def _toggle_schedule(self, _=None):
        v = not self._sched_on.get(); self._sched_on.set(v); ss("schedule_enabled", v)
        self._refresh_sc_btn()

    def _refresh_sc_btn(self):
        on = self._sched_on.get()
        try:
            self._sc_btn.config(text=" ENABLED " if on else "  ENABLE  ",
                                  bg=C["accent"] if on else C["panel3"],
                                  fg="#000" if on else C["dim"])
        except (AttributeError, tk.TclError): pass

    def _toggle_at(self, _=None):
        v = not self._at_on.get(); self._at_on.set(v); ss("auto_trigger", v)
        self._refresh_at_btn()

    def _refresh_at_btn(self):
        on = self._at_on.get()
        try:
            self._at_btn.config(text=" ENABLED " if on else " ENABLE ",
                                 bg=C["accent"] if on else C["panel3"],
                                 fg="#000" if on else C["dim"])
        except (AttributeError, tk.TclError): pass

    def _update_at_status(self):
        try:
            import psutil
            names  = {pr.name().lower() for pr in psutil.process_iter(["name"])}
            parts  = []
            parts.append("VLC: running ✓" if "vlc.exe" in names else "VLC: not detected")
            if "spotify.exe" in names:
                from auto_trigger import _is_spotify_playing
                playing = _is_spotify_playing()
                parts.append(f"Spotify: {'playing ✓' if playing else 'paused / idle'}")
            else:
                parts.append("Spotify: not detected")
            self._at_status.config(text="  ·  ".join(parts))
        except Exception:
            pass
        self.after(4000, self._update_at_status)

    # ── Window show / hide / close ────────────────────────────────────────────
    def hide(self): self.withdraw()
    def show(self): self.deiconify(); self.lift(); self.focus_force()

    def _on_close(self):
        """Called when the user clicks the window's ✕ button."""
        if gs("close_to_tray"):
            self.hide()
        else:
            # Full quit — same path as tray → Quit
            import state as _state
            from config import _persist
            _state._running = False
            _persist()
            self.destroy()

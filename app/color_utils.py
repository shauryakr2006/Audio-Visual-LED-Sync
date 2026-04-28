"""
color_utils.py — Color math helpers
=====================================
Pure functions for BLE command building, color arithmetic, Kelvin→RGB gains,
color history, and Windows accent detection.  No GUI imports.
"""

from __future__ import annotations

import colorsys
import math

import state
from config import WRITE_UUID, _lock, _S, _persist, gs, ss

# ── Windows accent colour ─────────────────────────────────────────────────────

def get_win_accent() -> str:
    """Read the current Windows accent colour from the registry."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\DWM")
        val, _ = winreg.QueryValueEx(key, "AccentColor")
        winreg.CloseKey(key)
        r = val & 0xFF
        g = (val >> 8)  & 0xFF
        b = (val >> 16) & 0xFF
        if max(r, g, b) < 60:
            return "#00ff8c"
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#00ff8c"


# Evaluated once at import time so every module that needs the accent can use it
WIN_ACCENT = get_win_accent()


# ── Primitive helpers ─────────────────────────────────────────────────────────

def clip255(x: float) -> int:
    return max(0, min(255, int(x)))


def make_cmd(r: float, g: float, b: float) -> bytearray:
    """Build the 9-byte ELK-BLEDOM colour command."""
    return bytearray([0x7e, 0x00, 0x05, 0x03,
                      clip255(r), clip255(g), clip255(b),
                      0x00, 0xef])


def rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(clip255(r), clip255(g), clip255(b))


def dim(r: float, g: float, b: float, pct: float) -> tuple[float, float, float]:
    """Scale RGB by a brightness percentage (0–100)."""
    f = pct / 100.0
    return r * f, g * f, b * f


# ── Kelvin → per-channel gain ─────────────────────────────────────────────────

def kelvin_to_gains(k: int) -> tuple[float, float, float]:
    """Return normalised (r, g, b) multipliers for a colour temperature in K."""
    k = max(1000, min(10000, k))
    t = k / 100.0
    if t <= 66:
        r = 255.0
        g = max(0.0, 99.4708025861 * math.log(max(t, 1)) - 161.1195681661)
        b = (0.0 if t <= 19
             else max(0.0, 138.5177312231 * math.log(t - 10.0) - 305.0447927307))
    else:
        r = max(0.0, 329.698727466  * ((t - 60.0) ** -0.1332047592))
        g = max(0.0, 288.1221695283 * ((t - 60.0) ** -0.0755148492))
        b = 255.0
    r = min(r, 255.0) / 255.0
    g = min(g, 255.0) / 255.0
    b = min(b, 255.0) / 255.0
    mx = max(r, g, b, 1e-9)
    return r / mx, g / mx, b / mx


def apply_color_temp(k: int):
    """Compute Kelvin gains and write them back into settings."""
    r, g, b = kelvin_to_gains(k)
    with _lock:
        _S["ct_k"] = k
        _S["ct_r"] = round(r, 4)
        _S["ct_g"] = round(g, 4)
        _S["ct_b"] = round(b, 4)
    _persist()


# ── Color history ─────────────────────────────────────────────────────────────

_COLOR_HIST_MAX = 16


def push_color_history(rgb: list):
    """Prepend *rgb* to the persistent color history and notify the GUI."""
    with _lock:
        hist = _S.get("color_history", [])
        hist = [c for c in hist if c != rgb]
        hist.insert(0, list(rgb))
        _S["color_history"] = hist[:_COLOR_HIST_MAX]
    _persist()
    if state._app:
        state._app.after(0, state._app._refresh_color_history)

"""
config.py — Hardware constants, settings store & persistence
=============================================================
All mode names, the settings dict ``_S``, and the thread-safe gs/ss helpers
live here.  No GUI imports; safe to import from any module.
"""

import json
import os
import threading

# ── Hardware ─────────────────────────────────────────────────────────────────
MAC_ADDR   = "BE:37:63:00:0C:80"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "avls_settings.json"
)

# ── Mode identifiers ──────────────────────────────────────────────────────────
M_SYNC    = "screen_sync"
M_MUSIC   = "music_sync"
M_SOLID   = "solid"
M_BREATHE = "breathing"
M_RAINBOW = "rainbow"
M_STROBE  = "strobe"
M_WAVE    = "wave"
M_CANDLE  = "candle"

MODE_LABEL = {
    M_SYNC:    "Screen Sync",
    M_MUSIC:   "Music Sync",
    M_SOLID:   "Solid Color",
    M_BREATHE: "Breathing",
    M_RAINBOW: "Rainbow Cycle",
    M_STROBE:  "Strobe",
    M_WAVE:    "Color Wave",
    M_CANDLE:  "Candlelight",
}

EFFECT_MODES = [M_BREATHE, M_RAINBOW, M_STROBE, M_WAVE, M_CANDLE]
LED_MODES    = [M_SYNC, M_MUSIC, M_SOLID] + EFFECT_MODES

# ── Thread lock ───────────────────────────────────────────────────────────────
_lock = threading.Lock()

# ── Default settings ──────────────────────────────────────────────────────────
# FIX: removed duplicate keys that existed in v3.5 (_S had sample_region,
#      black_thresh, smoothing, sc_correction, gamma defined twice).
_S: dict = {
    "mac_address":     MAC_ADDR,
    "mode":            M_SOLID,
    "strip_on":        True,
    "color":           [0, 255, 140],
    "brightness":      75,
    "speed":           50,

    # White Balance
    "wb_r":            1.00,
    "wb_g":            0.57,
    "wb_b":            0.49,

    # Color Temperature
    "ct_k":            6500,
    "ct_r":            1.00,
    "ct_g":            1.00,
    "ct_b":            1.00,

    # Screen Sync
    "sample_region":   0.50,
    "black_thresh":    15,
    "smoothing":       0.30,
    "sc_correction":   [1.0, 1.0, 0.85],
    "gamma":           2.2,
    "sc_low_latency":  False,

    # Music Sync
    "music_mode":      "spectrum",
    "music_sens":      75,
    "music_color":     [0, 180, 255],
    "album_art_enabled":           False,
    "selected_audio_device":       -1,
    "selected_audio_device_type":  "",

    # Effects
    "wave_colors":     [[255, 0, 80], [0, 180, 255], [255, 160, 0]],
    "breathe_rainbow": False,
    "strobe_rainbow":  False,

    # Color history
    "color_history":   [],
    "auto_trigger":    False,
    "auto_vlc":        True,
    "auto_spotify":    True,

    # Custom app triggers  [{process, mode, label}]
    "custom_triggers": [],

    # Startup
    "startup_with_windows": False,
    "close_to_tray":        True,   # minimize to tray on window close

    # Schedule / Night mode
    "schedule_enabled":     False,
    "schedule_night_start": "22:00",
    "schedule_night_end":   "07:00",
    "night_brightness":     15,
    "night_mode":           M_SOLID,
    "night_color":          [255, 50, 0],

    # Scenes
    "scenes": {
        "Chill":  {"mode": M_BREATHE, "color": [0, 255, 140],  "brightness": 50,  "speed": 25},
        "Party":  {"mode": M_RAINBOW, "color": [255, 0, 80],   "brightness": 100, "speed": 80},
        "Focus":  {"mode": M_SOLID,   "color": [255, 200, 80], "brightness": 65,  "speed": 50},
        "Cinema": {"mode": M_SYNC,    "color": [0, 0, 0],      "brightness": 35,  "speed": 50},
        "Night":  {"mode": M_SOLID,   "color": [255, 40, 0],   "brightness": 8,   "speed": 50},
    },
}


# ── Thread-safe accessors ─────────────────────────────────────────────────────

def gs(key):
    """Get setting (thread-safe)."""
    with _lock:
        return _S[key]


def ss(key, val, save: bool = True):
    """Set setting (thread-safe) and optionally persist to disk."""
    with _lock:
        _S[key] = val
    if save:
        _persist()


def _persist():
    """Write current settings to JSON on disk (best-effort)."""
    try:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(_S, f, indent=2)
    except Exception:
        pass


def load_settings():
    """Merge saved settings from disk into ``_S`` at startup."""
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH) as f:
                data = json.load(f)
            with _lock:
                _S.update(data)
    except Exception:
        pass

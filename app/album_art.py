"""
album_art.py — Album art dominant-colour extraction
=====================================================
Polls the Spotify window title, queries the iTunes Search API (no auth
required), downloads the thumbnail, and extracts the dominant vivid hue using
a weighted circular mean.  Runs in a short-lived daemon thread spawned by
auto_trigger.py every few seconds when the feature is enabled.
"""

from __future__ import annotations

import colorsys
import json
import math
import threading
import urllib.parse
import urllib.request
from io import BytesIO

from PIL import Image

import state

_album_art_lock        = threading.Lock()
_album_art_color: list = [0, 180, 255]   # last extracted dominant colour
_last_art_track: str   = ""              # dedup key — window title string


def extract_dominant_hue(img_bytes: bytes) -> list:
    """Return ``[r, g, b]`` dominant vivid colour from raw image bytes.

    Uses a weighted circular mean of hue across all pixels so that achromatic
    pixels (grey, white, black) contribute little weight.
    """
    try:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        img = img.resize((40, 40), Image.LANCZOS)
        pixels = list(img.getdata())
        sin_sum = cos_sum = total_w = bright_sum = sat_sum = 0.0
        for r8, g8, b8 in pixels:
            h, s, v = colorsys.rgb_to_hsv(r8 / 255.0, g8 / 255.0, b8 / 255.0)
            w = max(s * v, 0.0)
            sin_sum   += math.sin(h * math.tau) * w
            cos_sum   += math.cos(h * math.tau) * w
            total_w   += w
            sat_sum   += s * w
            bright_sum += v * w
        if total_w < 1e-6:
            return [0, 180, 255]
        dom_hue = (math.atan2(sin_sum, cos_sum) / math.tau) % 1.0
        dom_sat = min(sat_sum / total_w * 1.4, 1.0)   # boost saturation
        dom_val = min(bright_sum / total_w * 1.2, 1.0)
        dom_sat = max(dom_sat, 0.6)
        dom_val = max(dom_val, 0.65)
        return [int(x * 255) for x in colorsys.hsv_to_rgb(dom_hue, dom_sat, dom_val)]
    except Exception:
        return [0, 180, 255]


def fetch_album_art_color_thread():
    """Background: Spotify window title → iTunes API → dominant colour."""
    global _album_art_color, _last_art_track

    try:
        import ctypes as _ct
        import ctypes.wintypes as _cw

        # ── 1. Read Spotify window title ──────────────────────────────────────
        found_title = None
        WNDENUMPROC = _ct.WINFUNCTYPE(_ct.c_bool, _cw.HWND, _cw.LPARAM)

        def _cb(hwnd, _):
            nonlocal found_title
            if _ct.windll.user32.IsWindowVisible(hwnd):
                n = _ct.windll.user32.GetWindowTextLengthW(hwnd)
                if n > 3:
                    buf = _ct.create_unicode_buffer(n + 1)
                    _ct.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
                    t = buf.value
                    if t and " - " in t and t.lower() not in ("spotify", ""):
                        found_title = t
            return True

        _ct.windll.user32.EnumWindows(WNDENUMPROC(_cb), 0)

        if not found_title or found_title == _last_art_track:
            return

        # ── 2. Query iTunes Search API (free, no auth) ────────────────────────
        parts = found_title.split(" - ", 1)
        if len(parts) < 2:
            return
        artist, track = parts[0].strip(), parts[1].strip()
        term    = urllib.parse.quote(f"{artist} {track}")
        url     = f"https://itunes.apple.com/search?term={term}&media=music&limit=1"
        req     = urllib.request.urlopen(url, timeout=6)
        data    = json.loads(req.read())
        results = data.get("results", [])
        if not results:
            return
        art_url = results[0].get("artworkUrl100", "")
        if not art_url:
            return
        art_url = art_url.replace("100x100bb", "300x300bb")

        # ── 3. Download and extract dominant vivid colour ─────────────────────
        img_bytes = urllib.request.urlopen(art_url, timeout=6).read()
        rgb = extract_dominant_hue(img_bytes)

        with _album_art_lock:
            _album_art_color = rgb
        _last_art_track = found_title

        if state._app:
            state._app.after(0, lambda c=rgb: state._app._apply_album_art_color(c))

    except Exception:
        pass


def get_album_art_color() -> list:
    """Return the most recently extracted album art dominant colour."""
    with _album_art_lock:
        return list(_album_art_color)

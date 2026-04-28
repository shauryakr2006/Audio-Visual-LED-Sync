"""
tray.py — System tray icon & menu
===================================
Builds a pystray icon that sits in the Windows notification area.
All menu callbacks schedule work on the Tk main thread via app.after().

Tray fix notes (v3.6):
  • build_tray() no longer calls run_detached() — main.py does that AFTER
    state._app is set, so callbacks never race against a None app reference.
  • _tray_open polls state._app with a short retry so double-clicking the
    icon works even if Tk is still initialising.
  • _tray_quit destroys the Tk window cleanly then stops the icon, avoiding
    the mainloop hang caused by calling icon.stop() before app.destroy().
  • _with_app() centralises the "wait for app" retry pattern.
"""

from __future__ import annotations

import threading
import time

from PIL import Image, ImageDraw
import pystray

import state
from config import LED_MODES, MODE_LABEL, gs, ss, _persist


# ── Tray icon image ───────────────────────────────────────────────────────────

def _tray_img() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.ellipse([5, 5, 59, 59], outline=(0, 255, 140), width=5)
    d.ellipse([20, 20, 44, 44], fill=(0, 255, 140))
    return img


# ── Helper: schedule fn on Tk thread, retrying until app is ready ─────────────

def _with_app(fn, retries: int = 10, delay: float = 0.3):
    """Call fn(app) on the Tk thread. Retries up to `retries` times if
    state._app is not yet set (race between tray start and Tk init)."""
    def _attempt(n):
        app = state._app
        if app:
            try:
                app.after(0, lambda: fn(app))
            except Exception:
                pass
        elif n > 0:
            threading.Timer(delay, _attempt, args=(n - 1,)).start()
    _attempt(retries)


# ── Menu callbacks ────────────────────────────────────────────────────────────

def _tray_open(icon=None, item=None):
    _with_app(lambda app: app.show())


def _tray_mode(m):
    def _fn(icon, item):
        ss("mode", m)
        _with_app(lambda app: app._select_mode(m))
    return _fn


def _tray_toggle(icon, item):
    ss("strip_on", not gs("strip_on"))
    _with_app(lambda app: app._refresh_on_btn())


def _tray_quit(icon, item):
    """Shut down cleanly: stop BLE loop → destroy Tk → stop tray icon."""
    state._running = False
    _persist()

    def _do_quit(app):
        try:
            app.destroy()
        except Exception:
            pass
        # Stop the tray icon after Tk is gone so its thread can exit cleanly
        threading.Timer(0.4, icon.stop).start()

    app = state._app
    if app:
        try:
            app.after(0, lambda: _do_quit(app))
        except Exception:
            icon.stop()
    else:
        icon.stop()


# ── Build tray ────────────────────────────────────────────────────────────────

def build_tray() -> pystray.Icon:
    mode_menu = pystray.Menu(
        *[pystray.MenuItem(MODE_LABEL[m], _tray_mode(m)) for m in LED_MODES]
    )
    return pystray.Icon(
        "Audio-Visual-LED-Sync",
        _tray_img(),
        "Audio-Visual-LED-Sync v3.6",
        menu=pystray.Menu(
            pystray.MenuItem("Open Control Panel", _tray_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Mode", mode_menu),
            pystray.MenuItem("Toggle Strip", _tray_toggle),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", _tray_quit),
        ),
    )

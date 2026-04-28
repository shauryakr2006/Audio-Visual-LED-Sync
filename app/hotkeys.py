"""
hotkeys.py — Global hotkey listener (Windows only)
====================================================
Registers six Win32 hotkeys via RegisterHotKey and handles them in a message
loop on its own daemon thread so they work even when the window is hidden.

Hotkeys:
  Ctrl+Alt+G    Toggle strip on/off
  Ctrl+Alt+M    Show control panel
  Ctrl+Alt+→    Cycle to next mode
  Ctrl+Alt+↑    Brightness +10 %
  Ctrl+Alt+↓    Brightness −10 %
  Ctrl+Alt+V    Paste clipboard hex colour
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import time

import state
from config import LED_MODES, gs, ss

# ── Win32 constants ───────────────────────────────────────────────────────────
MOD_CTRL  = 0x0002
MOD_ALT   = 0x0001
VK_G      = 0x47
VK_M      = 0x4D
VK_RIGHT  = 0x27
VK_UP     = 0x26
VK_DOWN   = 0x28
VK_V      = 0x56
WM_HOTKEY = 0x0312

hotkeys_ok = False   # exposed for GUI status display


def hotkey_thread():
    """Register hotkeys and run the Win32 message pump."""
    global hotkeys_ok
    try:
        user32 = ctypes.windll.user32
        mod    = MOD_CTRL | MOD_ALT
        user32.RegisterHotKey(None, 1, mod, VK_G)
        user32.RegisterHotKey(None, 2, mod, VK_M)
        user32.RegisterHotKey(None, 3, mod, VK_RIGHT)
        user32.RegisterHotKey(None, 4, mod, VK_UP)
        user32.RegisterHotKey(None, 5, mod, VK_DOWN)
        user32.RegisterHotKey(None, 6, mod, VK_V)
        hotkeys_ok = True

        msg = ctypes.wintypes.MSG()
        while state._running:
            if user32.PeekMessageW(ctypes.byref(msg), None,
                                   WM_HOTKEY, WM_HOTKEY, 1):
                _dispatch(msg.wParam)
            time.sleep(0.05)

    except Exception:
        hotkeys_ok = False
    finally:
        try:
            u = ctypes.windll.user32
            for i in range(1, 7):
                u.UnregisterHotKey(None, i)
        except Exception:
            pass


def _dispatch(wid: int):
    """Handle a hotkey message by ID."""
    app = state._app

    if wid == 1:   # toggle strip
        v = not gs("strip_on")
        ss("strip_on", v)
        if app:
            app.after(0, app._refresh_on_btn)

    elif wid == 2:   # show panel
        if app:
            app.after(0, app.show)

    elif wid == 3:   # cycle mode
        cur = gs("mode")
        idx = (LED_MODES.index(cur) + 1) % len(LED_MODES) \
              if cur in LED_MODES else 0
        m = LED_MODES[idx]
        ss("mode", m)
        if app:
            app.after(0, lambda mm=m: app._select_mode(mm))

    elif wid == 4:   # brightness up
        new_br = min(100, gs("brightness") + 10)
        ss("brightness", new_br)
        if app:
            app.after(0, lambda b=new_br: app._hk_set_brightness(b))

    elif wid == 5:   # brightness down
        new_br = max(0, gs("brightness") - 10)
        ss("brightness", new_br)
        if app:
            app.after(0, lambda b=new_br: app._hk_set_brightness(b))

    elif wid == 6:   # paste clipboard colour
        if app:
            app.after(0, app._paste_clipboard_color)

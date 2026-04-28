"""
main.pyw — Audio-Visual-LED-Sync entry point
=============================================
Boots all daemon threads and the Tkinter main loop.

Thread layout:
  BLE      — asyncio loop, BleakClient connection + LED tick functions
  BgLoop   — auto-trigger watcher, night schedule, album-art poller (3 s tick)
  HotKey   — Win32 RegisterHotKey message pump
  [Tk]     — main thread (Tkinter)
  [Tray]   — pystray (run_detached spawns its own thread)

Tray fix (v3.6): tray.run_detached() is called AFTER state._app is set so
that all tray menu callbacks can immediately find the Tk window. Previously
the tray was started before GestoBridge() was constructed, causing _tray_open
and other callbacks to silently no-op on first use.
"""

import sys
import threading

import state
from auto_trigger import bg_loop
from ble_engine import ble_thread_main
from color_utils import apply_color_temp
from config import _persist, gs, load_settings
from gui import GestoBridge
from hotkeys import hotkey_thread
from tray import build_tray


def main():
    # ── 1. Load persisted settings ────────────────────────────────────────────
    load_settings()
    apply_color_temp(gs("ct_k"))

    # ── 2. Start daemon threads ───────────────────────────────────────────────
    threading.Thread(target=ble_thread_main, daemon=True, name="BLE").start()
    threading.Thread(target=bg_loop,         daemon=True, name="BgLoop").start()
    threading.Thread(target=hotkey_thread,   daemon=True, name="HotKey").start()

    # ── 3. Build tray object (do NOT run_detached yet) ────────────────────────
    tray = build_tray()

    # ── 4. Create Tk window and expose it to all threads ─────────────────────
    app = GestoBridge()
    state._app = app

    # ── 5. Start tray NOW — state._app is set, callbacks won't race ──────────
    tray.run_detached()

    # ── 6. Tk main loop (blocks until window is destroyed) ────────────────────
    app.mainloop()

    # ── 7. Clean shutdown ─────────────────────────────────────────────────────
    state._running = False
    _persist()
    try:
        tray.stop()
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()

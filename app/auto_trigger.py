"""
auto_trigger.py — Auto-trigger watcher, night schedule & startup helpers
=========================================================================
Runs as a single background daemon thread every 3 s.  Handles:
  • Built-in triggers (VLC → Screen Sync, Spotify → Music Sync)
  • User-defined custom process triggers
  • Night-mode schedule (dim + colour shift between configurable hours)
  • Album-art polling (spawns a short-lived thread when enabled)
  • Windows startup registry read/write
"""

from __future__ import annotations

import sys
import os
import threading
import time
from datetime import datetime, time as dtime
from tkinter import messagebox

import state
from config import M_MUSIC, M_SOLID, M_SYNC, gs, ss

# Optional psutil for process listing
try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False

# ── Process detection ─────────────────────────────────────────────────────────

def _is_spotify_playing() -> bool:
    """Return True if Spotify has a visible 'Artist - Track' window title."""
    try:
        import ctypes as ct
        import ctypes.wintypes as cw
        found = []
        WNDENUMPROC = ct.WINFUNCTYPE(ct.c_bool, cw.HWND, cw.LPARAM)

        def _cb(hwnd, _):
            if ct.windll.user32.IsWindowVisible(hwnd):
                n = ct.windll.user32.GetWindowTextLengthW(hwnd)
                if n > 3:
                    buf = ct.create_unicode_buffer(n + 1)
                    ct.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
                    t = buf.value
                    if t and " - " in t and t.lower() != "spotify":
                        found.append(t)
            return True

        ct.windll.user32.EnumWindows(WNDENUMPROC(_cb), 0)
        return bool(found)
    except Exception:
        return False


# ── Night schedule ────────────────────────────────────────────────────────────

def _is_night_now() -> bool:
    try:
        now   = datetime.now().time()
        start = dtime(*map(int, gs("schedule_night_start").split(":")))
        end   = dtime(*map(int, gs("schedule_night_end").split(":")))
        # Handle midnight-spanning ranges (e.g. 22:00 → 07:00)
        if start <= end:
            return start <= now < end
        else:
            return now >= start or now < end
    except Exception:
        return False


# ── Background loop ───────────────────────────────────────────────────────────

_prev_vlc     = False
_prev_spotify = False
_night_active = False
_custom_prev: dict = {}   # process_name_lower → was_running bool


def bg_loop():
    """Main auto-trigger + schedule watcher.  Runs on a daemon thread."""
    global _prev_vlc, _prev_spotify, _night_active, _custom_prev

    while state._running:
        time.sleep(3.0)
        app = state._app

        # ── Auto-trigger (built-in + custom) ──────────────────────────────────
        if gs("auto_trigger") and _PSUTIL_OK:
            try:
                names = {p.name().lower() for p in psutil.process_iter(["name"])}

                vlc     = "vlc.exe" in names and gs("auto_vlc")
                spotify = ("spotify.exe" in names
                           and gs("auto_spotify")
                           and _is_spotify_playing())

                if vlc and not _prev_vlc:
                    ss("mode", M_SYNC)
                    if app:
                        app.after(0, lambda: app._select_mode(M_SYNC))
                elif spotify and not _prev_spotify:
                    ss("mode", M_MUSIC)
                    if app:
                        app.after(0, lambda: app._select_mode(M_MUSIC))

                _prev_vlc     = vlc
                _prev_spotify = spotify

                for ct_entry in gs("custom_triggers"):
                    proc = ct_entry.get("process", "").lower().strip()
                    mode = ct_entry.get("mode", M_SOLID)
                    if not proc:
                        continue
                    running_now = proc in names
                    was_running = _custom_prev.get(proc, False)
                    if running_now and not was_running:
                        ss("mode", mode)
                        if app:
                            app.after(0, lambda m=mode: app._select_mode(m))
                    _custom_prev[proc] = running_now

            except Exception:
                pass
        else:
            _prev_vlc = _prev_spotify = False

        # ── Album art colour (background thread) ──────────────────────────────
        if gs("album_art_enabled") and gs("mode") == M_MUSIC:
            from album_art import fetch_album_art_color_thread
            threading.Thread(target=fetch_album_art_color_thread,
                             daemon=True, name="AlbumArt").start()

        # ── Schedule / Night mode ──────────────────────────────────────────────
        if gs("schedule_enabled"):
            night = _is_night_now()
            if night and not _night_active:
                _night_active = True
                ss("brightness", gs("night_brightness"))
                nm  = gs("night_mode")
                ss("mode", nm)
                col = gs("night_color")
                ss("color", col)
                if app:
                    def _apply_night():
                        app._br.set(gs("night_brightness"))
                        app._br_lbl.config(text=f'{gs("night_brightness")}%')
                        app._select_mode(nm)
                    app.after(0, _apply_night)
            elif not night and _night_active:
                _night_active = False
                ss("brightness", 60)
                ss("mode", M_SOLID)
                if app:
                    def _apply_dawn():
                        app._br.set(60)
                        app._br_lbl.config(text="60%")
                        app._select_mode(M_SOLID)
                    app.after(0, _apply_dawn)


# ── Windows startup registry ──────────────────────────────────────────────────

_RUN_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "Audio-Visual-LED-Sync"


def startup_get() -> bool:
    """Return True if the startup registry entry exists."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY)
        winreg.QueryValueEx(key, _APP_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def startup_set(enable: bool):
    """Create or delete the startup registry entry."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY,
                             0, winreg.KEY_SET_VALUE)
        if enable:
            exe = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(exe):
                exe = sys.executable
            val = f'"{exe}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, val)
        else:
            try:
                winreg.DeleteValue(key, _APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        ss("startup_with_windows", enable)
    except Exception as e:
        messagebox.showerror("Startup Error", str(e))

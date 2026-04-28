"""
ble_engine.py — BLE connection loop & mode dispatcher
======================================================
Manages the persistent BleakClient connection with exponential-backoff retry,
dispatches to per-mode tick functions, and starts/stops the audio engine
whenever the mode changes to/from Music Sync.
"""

from __future__ import annotations

import asyncio

from bleak import BleakClient, BleakError

import state
from audio_engine import start_audio, stop_audio, tick_music
from config import (MAC_ADDR, M_MUSIC, M_SYNC, gs,
                    M_BREATHE, M_CANDLE, M_RAINBOW, M_SOLID, M_STROBE, M_WAVE)
from effects import tick_breathe, tick_candle, tick_rainbow, tick_solid, tick_strobe, tick_wave
from screen_sync import close_mss, init_mss, tick_sync

# ── Mode → tick function map ──────────────────────────────────────────────────
_TICKS = {
    M_SOLID:   tick_solid,
    M_BREATHE: tick_breathe,
    M_RAINBOW: tick_rainbow,
    M_STROBE:  tick_strobe,
    M_WAVE:    tick_wave,
    M_CANDLE:  tick_candle,
    M_MUSIC:   tick_music,
    M_SYNC:    tick_sync,
}


async def _ble_engine():
    state._ble_ok = False
    init_mss()
    retry     = 2.0
    prev_mode = None

    while state._running:
        try:
            async with BleakClient(MAC_ADDR, timeout=12.0) as client:
                state._ble_ok = True
                retry         = 2.0
                if state._status_cb:
                    state._status_cb("connected")

                while state._running and client.is_connected:
                    mode = gs("mode")

                    # Start/stop audio on mode transitions
                    if mode != prev_mode:
                        if prev_mode == M_MUSIC:
                            stop_audio()
                        if mode == M_MUSIC:
                            start_audio()
                        prev_mode = mode

                    if not gs("strip_on"):
                        from effects import _write
                        await _write(client, 0, 0, 0)
                        await asyncio.sleep(0.10)
                        continue

                    await _TICKS[mode](client)

        except Exception:
            pass   # BleakError, OSError, etc. — retry below

        state._ble_ok = False
        if state._status_cb:
            state._status_cb("disconnected")
        if state._running:
            await asyncio.sleep(retry)
            retry = min(retry * 1.5, 30.0)

    stop_audio()
    close_mss()


def ble_thread_main():
    """Entry point for the BLE daemon thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_ble_engine())

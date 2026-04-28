"""
screen_sync.py — Screen capture & Ambilight tick
=================================================
Captures a central region of monitor 1 using mss, computes a
saturation-weighted average colour, and writes it to the LED strip.

Two paths:
  • Standard  — temporal smoothing + correction curve + gamma
  • Low-latency — raw weighted average, ~16 ms round-trip
"""

from __future__ import annotations

import asyncio

import numpy as np
from mss import mss
from mss.exception import ScreenShotError

from color_utils import clip255
from config import WRITE_UUID, gs

# Module-level mss context (initialised by ble_engine before the loop starts)
_sct    = None
_smooth = np.zeros(3, dtype=np.float64)


def init_mss():
    """Create (or recreate) the mss screenshot context."""
    global _sct
    _sct = mss()


def close_mss():
    global _sct
    if _sct is not None:
        try:
            _sct.close()
        except Exception:
            pass
        _sct = None


async def tick_sync(client):
    """One frame of Screen Sync; called continuously from the BLE engine loop."""
    global _sct, _smooth

    rfrac   = gs("sample_region")
    thresh  = gs("black_thresh")
    br      = gs("brightness") / 100.0
    low_lat = gs("sc_low_latency")

    try:
        mon = _sct.monitors[1]
        reg = {
            "top":    int(mon["top"]  + mon["height"] * (1 - rfrac) / 2),
            "left":   int(mon["left"] + mon["width"]  * (1 - rfrac) / 2),
            "width":  max(1, int(mon["width"]  * rfrac)),
            "height": max(1, int(mon["height"] * rfrac)),
        }
        img = _sct.grab(reg)
        # mss returns BGRA — drop alpha, reshape to (N,3) in BGR order
        px  = np.array(img)[:, :, :3].astype(np.float64).reshape(-1, 3)

        mx      = px.max(1)
        mn      = px.min(1)
        weights = np.square((mx - mn) * mx) + 0.1   # saturation × brightness
        avg     = np.average(px, axis=0, weights=weights)
        raw     = np.array([avg[2], avg[1], avg[0]])   # BGR → RGB

        if low_lat:
            # ── Low-latency path: no smoothing / correction / gamma ───────────
            r, g, b = raw
            if max(r, g, b) < thresh:
                r = g = b = 0.0
            else:
                r = min(r * br, 255.0)
                g = min(g * br, 255.0)
                b = min(b * br, 255.0)
            _smooth = raw   # keep smooth in sync to avoid jump on mode switch
        else:
            # ── Standard path: smoothing + correction + gamma ─────────────────
            alpha = gs("smoothing")
            corr  = np.array(gs("sc_correction"), dtype=np.float64)
            gamma = gs("gamma")
            floor = br * 0.5
            _smooth = alpha * raw + (1 - alpha) * _smooth
            r, g, b = _smooth
            if max(r, g, b) < thresh:
                r = g = b = 0.0
            else:
                col  = np.clip(_smooth * corr / 255.0, 0.0, 1.0)
                col  = np.power(col, gamma)
                peak = col.max()
                dyn  = 0.45 + 0.55 * peak ** 2
                scale = floor + (1.0 - floor) * dyn
                col   = np.clip(col * scale * 255.0, 0.0, 255.0)
                r, g, b = col

        # Apply white-balance & colour-temperature gains
        r2 = r * gs("wb_r") * gs("ct_r")
        g2 = g * gs("wb_g") * gs("ct_g")
        b2 = b * gs("wb_b") * gs("ct_b")
        await client.write_gatt_char(
            WRITE_UUID,
            bytearray([0x7e, 0x00, 0x05, 0x03,
                       clip255(r2), clip255(g2), clip255(b2),
                       0x00, 0xef]),
            response=False,
        )

    except ScreenShotError:
        # Monitor disconnected / resolution changed — recreate mss context
        if _sct:
            try:
                _sct.close()
            except Exception:
                pass
        _sct = mss()
    except Exception:
        pass

    await asyncio.sleep(0.016 if low_lat else 0.050)

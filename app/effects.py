"""
effects.py — LED effect tick functions
=======================================
Each async function runs once per BLE frame for its corresponding mode.
They share the same write helper so white-balance and colour-temperature
gains are applied uniformly before every BLE transmission.
"""

from __future__ import annotations

import asyncio
import colorsys
import math
import random
import time

from color_utils import clip255
from config import WRITE_UUID, gs


# ── Shared write helper ───────────────────────────────────────────────────────

async def _write(client, r: float, g: float, b: float):
    """Apply WB + CT gains and send an ELK-BLEDOM colour command."""
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


def _dim(r: float, g: float, b: float, pct: float) -> tuple[float, float, float]:
    f = pct / 100.0
    return r * f, g * f, b * f


# ── Effect ticks ──────────────────────────────────────────────────────────────

async def tick_solid(client):
    await _write(client, *_dim(*gs("color"), gs("brightness")))
    await asyncio.sleep(0.10)


async def tick_breathe(client):
    period = 0.5 + (1 - gs("speed") / 100) * 5.5
    t      = (time.monotonic() % period) / period
    lvl    = (math.sin(t * math.tau - math.pi / 2) + 1) / 2
    if gs("breathe_rainbow"):
        hue = (time.monotonic() / 12.0) % 1.0
        rgb = [x * 255 for x in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
    else:
        rgb = list(gs("color"))
    await _write(client, *_dim(*rgb, gs("brightness") * lvl))
    await asyncio.sleep(0.030)


async def tick_rainbow(client):
    period = 0.5 + (1 - gs("speed") / 100) * 11.5
    hue    = (time.monotonic() % period) / period
    rgb    = [x * 255 for x in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
    await _write(client, *_dim(*rgb, gs("brightness")))
    await asyncio.sleep(0.030)


async def tick_strobe(client):
    period = 0.05 + (1 - gs("speed") / 100) * 0.95
    on     = (time.monotonic() % period) < (period / 2)
    if on:
        if gs("strobe_rainbow"):
            hue = (time.monotonic() / 3.0) % 1.0
            rgb = [x * 255 for x in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
        else:
            rgb = list(gs("color"))
        await _write(client, *_dim(*rgb, gs("brightness")))
    else:
        await _write(client, 0, 0, 0)
    await asyncio.sleep(0.018)


async def tick_wave(client):
    wc = gs("wave_colors")
    n  = len(wc)
    if not n:
        await asyncio.sleep(0.05)
        return
    period  = 0.5 + (1 - gs("speed") / 100) * 9.5
    t       = (time.monotonic() % period) / period * n
    idx     = int(t) % n
    nxt     = (idx + 1) % n
    frac    = t - int(t)
    blended = [wc[idx][i] * (1 - frac) + wc[nxt][i] * frac for i in range(3)]
    await _write(client, *_dim(*blended, gs("brightness")))
    await asyncio.sleep(0.030)


async def tick_candle(client):
    hue = random.uniform(0.033, 0.095)
    flk = random.uniform(0.45, 1.00)
    rgb = [x * 255 for x in colorsys.hsv_to_rgb(hue, 0.93, flk)]
    await _write(client, *_dim(*rgb, gs("brightness")))
    await asyncio.sleep(0.05 + (1 - gs("speed") / 100) * 0.35)

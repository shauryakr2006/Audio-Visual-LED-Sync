"""
audio_engine.py — Audio capture & Music Sync ("Prism Engine")
=============================================================
Supports two capture backends (priority order):
  1. pyaudiowpatch  — most reliable WASAPI loopback on Windows
  2. sounddevice    — WASAPI loopback fallback

Music Sync v3.4 "Prism Engine" — see _tick_music docstring for algorithm notes.

OPTIMISATION vs v3.5:
  • _BAND_HUE is now a module-level constant (was re-created every tick).
  • SILENCE_FLOOR and MEL_BOUNDS are also module-level constants.
"""

from __future__ import annotations

import asyncio
import collections
import threading
import time

import numpy as np

import state
from color_utils import clip255
from config import WRITE_UUID, gs

# ── Optional backends ─────────────────────────────────────────────────────────
try:
    import sounddevice as sd
    _SD_OK = True
except ImportError:
    _SD_OK = False

try:
    import pyaudiowpatch as pyaudio
    _PAW_OK = True
except ImportError:
    _PAW_OK = False

# ── Audio constants ───────────────────────────────────────────────────────────
_SR           = 44100
_BLOCK        = 2048
SILENCE_FLOOR = 3e-4   # RMS below this → treat block as silence

# Six mel-scaled frequency bands (module-level — not recreated each tick)
MEL_BOUNDS = [
    ( 20,    80),   # sub-bass  → hue anchor 0.00  (red)
    ( 80,   250),   # bass      → hue anchor 0.08  (orange)
    (250,   800),   # low-mid   → hue anchor 0.22  (yellow-green)
    (800,  2500),   # mid       → hue anchor 0.50  (cyan)
    (2500, 6000),   # hi-mid    → hue anchor 0.67  (blue-violet)
    (6000,20000),   # treble    → hue anchor 0.85  (magenta-pink)
]
# NOTE: not evenly spaced — bass gets extra warm room so bass-heavy tracks
#       read as warm red/orange rather than neutral.
_BAND_HUE = np.array([0.00, 0.08, 0.22, 0.50, 0.67, 0.85], dtype=np.float64)

# ── Shared audio buffer ───────────────────────────────────────────────────────
_audio_buf   = collections.deque(maxlen=_SR * 2)
_audio_lock  = threading.Lock()
_audio_stream  = None
_paw_instance  = None       # PyAudio instance kept alive for pyaudiowpatch path
_audio_status  = "idle"
_audio_error   = ""
_audio_device_name = ""
_audio_backend = ""

# ── Music sync state ──────────────────────────────────────────────────────────
_rms_hist        = collections.deque(maxlen=43)
_band_smooth     = np.zeros(6, dtype=np.float64)
_beat_val        = 0.0
_vu_data         = [0.0, 0.0, 0.0]
_band_peak_fast  = np.ones(6,  dtype=np.float64) * 1e-6
_band_peak_slow  = np.zeros(3, dtype=np.float64)
_hue_smooth      = 0.0
_sat_smooth      = 1.0
_val_smooth      = 0.0
_beat_flash      = 0.0
_silence_frames  = 0

# Prism engine extras
_hue_phase      = 0.0
_bpm_est        = 120.0
_bpm_smooth     = 120.0
_onset_env      = collections.deque(maxlen=300)
_prev_mag       = None
_flux_smooth    = 0.0
_beat_hue_jump  = 0.0
_compl_fade     = 0.0
_last_bpm_calc  = 0.0


# ── Buffer helpers ────────────────────────────────────────────────────────────

def _flush_audio_buf():
    with _audio_lock:
        _audio_buf.clear()


def _reset_music_state():
    global _band_smooth, _beat_val, _band_peak_fast, _band_peak_slow
    global _hue_smooth, _sat_smooth, _val_smooth, _beat_flash, _silence_frames
    global _hue_phase, _bpm_est, _bpm_smooth, _onset_env, _prev_mag
    global _flux_smooth, _beat_hue_jump, _compl_fade, _last_bpm_calc, _rms_hist
    _band_smooth[:]    = 0.0
    _beat_val          = 0.0
    _band_peak_fast[:] = 1e-6
    _band_peak_slow[:] = 0.0
    _hue_smooth        = 0.0
    _sat_smooth        = 1.0
    _val_smooth        = 0.0
    _beat_flash        = 0.0
    _silence_frames    = 0
    _hue_phase         = 0.0
    _bpm_est           = 120.0
    _bpm_smooth        = 120.0
    _onset_env.clear()
    _prev_mag          = None
    _flux_smooth       = 0.0
    _beat_hue_jump     = 0.0
    _compl_fade        = 0.0
    _last_bpm_calc     = 0.0
    _rms_hist.clear()


# ── Sounddevice callback ──────────────────────────────────────────────────────

def _audio_cb_sd(indata, frames, t, status):
    try:
        arr = indata[:, 0].astype(np.float64)
        rms = float(np.sqrt(np.mean(arr ** 2)))
        if rms < SILENCE_FLOOR:
            arr = np.zeros(frames, dtype=np.float64)
        with _audio_lock:
            _audio_buf.extend(arr.tolist())
    except Exception:
        pass


# ── pyaudiowpatch capture ─────────────────────────────────────────────────────

def _start_audio_paw() -> bool:
    global _audio_stream, _paw_instance, _audio_status
    global _audio_error, _audio_device_name, _audio_backend

    if not _PAW_OK:
        return False

    p = pyaudio.PyAudio()
    selected     = gs("selected_audio_device")
    selected_type = gs("selected_audio_device_type")

    lb_list = []
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if (dev.get("hostApi") == wasapi_info["index"]
                    and dev.get("isLoopbackDevice", False)):
                lb_list.append(dev)
    except Exception as e:
        p.terminate()
        _audio_error = f"pyaudiowpatch WASAPI enum failed: {e}"
        return False

    if not lb_list:
        p.terminate()
        _audio_error = "No WASAPI loopback devices found (pyaudiowpatch)."
        return False

    target_lb = None
    if selected != -1 and selected_type != "input_loopback":
        for lb in lb_list:
            if lb["index"] == selected:
                target_lb = lb
                break

    if target_lb is None:
        default_name = None
        try:
            default_out  = p.get_default_output_device_info()["index"]
            default_name = p.get_device_info_by_index(default_out)["name"]
        except Exception:
            pass
        if default_name:
            for lb in lb_list:
                if default_name[:20] in lb["name"] or lb["name"][:20] in default_name:
                    target_lb = lb
                    break
        if target_lb is None:
            target_lb = lb_list[0]

    sr     = int(target_lb.get("defaultSampleRate", _SR))
    ch     = max(1, int(target_lb.get("maxInputChannels", 2)))
    ch_ref = [ch]

    def _paw_cb(in_data, frame_count, time_info, status):
        try:
            arr = np.frombuffer(in_data, dtype=np.float32).copy()
            if ch_ref[0] > 1:
                arr = arr.reshape(-1, ch_ref[0])[:, 0]
            rms = float(np.sqrt(np.mean(arr.astype(np.float64) ** 2)))
            if rms < SILENCE_FLOOR:
                arr = np.zeros(frame_count, dtype=np.float32)
            with _audio_lock:
                _audio_buf.extend(arr.tolist())
        except Exception:
            pass
        return (None, pyaudio.paContinue)

    try:
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=ch,
            rate=sr,
            input=True,
            input_device_index=int(target_lb["index"]),
            frames_per_buffer=_BLOCK,
            stream_callback=_paw_cb,
        )
        stream.start_stream()
        _paw_instance      = p
        _audio_stream      = stream
        _audio_status      = "running"
        _audio_device_name = target_lb["name"].replace(" [Loopback]", "").strip()
        _audio_backend     = "pyaudiowpatch"
        return True
    except Exception as e:
        p.terminate()
        _audio_error = f"pyaudiowpatch open failed: {e}"
        return False


# ── sounddevice WASAPI loopback ───────────────────────────────────────────────

def _start_audio_sd():
    global _audio_stream, _audio_status, _audio_error, _audio_device_name, _audio_backend

    errors:   list = []
    selected       = gs("selected_audio_device")
    selected_type  = gs("selected_audio_device_type")
    wasapi_lb = None
    try:
        wasapi_lb = sd.WasapiSettings(loopback=True)
    except Exception:
        pass

    wasapi_api_idx = -1
    try:
        for api in sd.query_hostapis():
            if "wasapi" in api.get("name", "").lower():
                wasapi_api_idx = int(api["index"])
                break
    except Exception:
        pass

    candidates: list = []

    if selected != -1 and selected_type == "input_loopback":
        try:
            info = sd.query_devices(selected)
            sr   = int(info.get("default_samplerate", _SR))
            ch   = min(2, max(1, int(info.get("max_input_channels", 2))))
            candidates.append({"device": selected, "samplerate": sr,
                               "channels": ch, "extra": None,
                               "name": info.get("name", f"Device {selected}")})
        except Exception as e:
            errors.append(str(e))

    elif selected != -1:
        if wasapi_lb is None:
            errors.append("WasapiSettings not available")
        else:
            try:
                info    = sd.query_devices(selected)
                api_idx = int(info.get("hostapi", -1))
                if wasapi_api_idx == -1 or api_idx == wasapi_api_idx:
                    sr = int(info.get("default_samplerate", _SR))
                    ch = min(2, max(1, int(info.get("max_output_channels", 2))))
                    candidates.append({"device": selected, "samplerate": sr,
                                       "channels": ch, "extra": wasapi_lb,
                                       "name": info.get("name", f"Device {selected}")})
                else:
                    errors.append(
                        f"Device {selected} is not a WASAPI device "
                        f"(hostapi={api_idx}, need {wasapi_api_idx})"
                    )
            except Exception as e:
                errors.append(str(e))
    else:
        if wasapi_lb is None:
            errors.append("WasapiSettings not available — install pyaudiowpatch")
        else:
            default_idx = -1
            try:
                default_idx = int(sd.default.device[1])
            except Exception:
                try:
                    default_idx = int(sd.query_devices(kind="output")["index"])
                except Exception:
                    pass

            if default_idx >= 0:
                try:
                    info    = sd.query_devices(default_idx)
                    api_idx = int(info.get("hostapi", -1))
                    if wasapi_api_idx == -1 or api_idx == wasapi_api_idx:
                        sr = int(info.get("default_samplerate", _SR))
                        ch = min(2, max(1, int(info.get("max_output_channels", 2))))
                        candidates.append({"device": default_idx, "samplerate": sr,
                                           "channels": ch, "extra": wasapi_lb,
                                           "name": info.get("name", "Default Output")})
                    else:
                        errors.append(
                            f"Default output (idx={default_idx}) hostapi={api_idx} "
                            "is not WASAPI. Install pyaudiowpatch for loopback."
                        )
                except Exception as e:
                    errors.append(f"default device query: {e}")
            else:
                errors.append("Could not determine default output device")

    for cfg in candidates:
        try:
            kwargs = dict(device=cfg["device"], samplerate=cfg["samplerate"],
                          channels=cfg["channels"], blocksize=_BLOCK,
                          dtype="float32", callback=_audio_cb_sd)
            if cfg.get("extra") is not None:
                kwargs["extra_settings"] = cfg["extra"]
            stream = sd.InputStream(**kwargs)
            stream.start()
            _audio_stream      = stream
            _audio_status      = "running"
            _audio_error       = ""
            _audio_device_name = cfg["name"]
            _audio_backend     = "sounddevice"
            return
        except Exception as e:
            errors.append(f"dev={cfg['device']} sr={cfg['samplerate']}: {e}")

    _audio_stream      = None
    _audio_status      = "error"
    _audio_device_name = ""
    _audio_error       = (
        ("sounddevice capture failed:\n" + "\n".join(errors[:6]))
        if errors else
        "No suitable WASAPI device found.\nInstall pyaudiowpatch:\n  pip install pyaudiowpatch"
    )


# ── Public start / stop / restart ─────────────────────────────────────────────

def start_audio():
    global _audio_stream, _audio_status, _audio_error
    if not _SD_OK and not _PAW_OK:
        _audio_status = "error"
        _audio_error  = "No audio backend.\nRun:  pip install pyaudiowpatch"
        return
    if _audio_stream is not None:
        return
    _flush_audio_buf()
    _reset_music_state()
    _audio_status = "starting"
    _audio_error  = ""
    if _PAW_OK and _start_audio_paw():
        return
    if _SD_OK:
        _start_audio_sd()
    else:
        _audio_status = "error"
        _audio_error  = "All capture methods failed.\nInstall pyaudiowpatch: pip install pyaudiowpatch"


def stop_audio():
    global _audio_stream, _audio_status, _audio_error
    global _audio_device_name, _audio_backend, _paw_instance
    if _audio_stream:
        try:
            _audio_stream.stop()
            _audio_stream.close()
        except Exception:
            pass
        _audio_stream = None
    if _paw_instance:
        try:
            _paw_instance.terminate()
        except Exception:
            pass
        _paw_instance = None
    _flush_audio_buf()
    _audio_status      = "idle"
    _audio_error       = ""
    _audio_device_name = ""
    _audio_backend     = ""


def restart_audio():
    stop_audio()
    time.sleep(0.3)
    start_audio()


# ── BPM estimation ────────────────────────────────────────────────────────────

def _estimate_bpm(env: np.ndarray) -> float:
    """Autocorrelation BPM from onset envelope sampled at ~40 Hz (40–220 BPM)."""
    if len(env) < 80:
        return 120.0
    x   = env - float(np.mean(env))
    acf = np.correlate(x, x, mode="full")
    acf = acf[len(acf) // 2:]
    peak0 = acf[0] if acf[0] > 0 else 1.0
    acf   = acf / peak0
    fps      = 40
    lag_min  = max(1, int(fps * 60 / 220))
    lag_max  = min(len(acf) - 1, int(fps * 60 / 40))
    if lag_min >= lag_max:
        return 120.0
    peak_lag = int(np.argmax(acf[lag_min:lag_max])) + lag_min
    bpm = 60.0 * fps / peak_lag if peak_lag > 0 else 120.0
    half_lag = peak_lag // 2
    if half_lag >= lag_min and acf[half_lag] > 0.4:
        bpm = 60.0 * fps / half_lag
    return float(np.clip(bpm, 40.0, 220.0))


# ── Music Sync tick ───────────────────────────────────────────────────────────

async def tick_music(client):
    """
    Music Sync v3.4 — Prism Engine
    ═══════════════════════════════════════════════════════════════════════
    Hue is a CONTINUOUSLY ROTATING PHASE driven by BPM.  Band energy
    *pulls* the phase toward each band's hue sector via circular mean,
    so it influences but never locks the colour.  Beats fire a ≈180°
    complementary jump, guaranteeing all colours visit regularly.

    • 6 mel-scaled bands (20 Hz → 20 kHz, perceptually uniform)
    • BPM via autocorrelation of onset envelope every 2 s
    • Hue phase rotates at (BPM / 8) cycles/minute = full wheel per 8 beats
    • Spectral flux drives saturation (dynamic music = vivid, static = muted)
    • Beat: brightness spike + ≈180° complementary hue jump + white flash
    """
    import colorsys
    import math

    global _band_smooth, _beat_val, _vu_data
    global _band_peak_fast, _band_peak_slow
    global _hue_smooth, _sat_smooth, _val_smooth, _beat_flash, _silence_frames
    global _hue_phase, _bpm_est, _bpm_smooth, _onset_env, _prev_mag
    global _flux_smooth, _beat_hue_jump, _compl_fade, _last_bpm_calc
    global _rms_hist

    with _audio_lock:
        data = np.array(list(_audio_buf), dtype=np.float64)

    if len(data) < _BLOCK:
        await asyncio.sleep(0.025)
        return

    chunk   = data[-_BLOCK:]
    window  = chunk * np.hanning(_BLOCK)
    fft_mag = np.abs(np.fft.rfft(window))
    freqs   = np.fft.rfftfreq(_BLOCK, 1.0 / _SR)

    # ── 1. Six mel-scaled bands ───────────────────────────────────────────────
    raw6 = np.zeros(6, dtype=np.float64)
    for i, (lo, hi) in enumerate(MEL_BOUNDS):
        mask = (freqs >= lo) & (freqs < hi)
        if mask.any():
            raw6[i] = float(np.sqrt(np.mean(fft_mag[mask] ** 2)))

    # ── 2. Spectral flux ──────────────────────────────────────────────────────
    if _prev_mag is not None and len(_prev_mag) == len(fft_mag):
        pos_diff   = np.sum(np.maximum(fft_mag - _prev_mag, 0.0))
        total_e    = float(np.sum(fft_mag)) + 1e-9
        flux_norm  = float(min(pos_diff / total_e, 1.0))
    else:
        flux_norm = 0.0
    _prev_mag    = fft_mag.copy()
    _flux_smooth = 0.12 * flux_norm + 0.88 * _flux_smooth

    # ── 3. Per-band AGC ───────────────────────────────────────────────────────
    sens = gs("music_sens") / 100.0
    ATK  = 0.85
    REL  = 0.993 - sens * 0.012
    for i in range(6):
        if raw6[i] > _band_peak_fast[i]:
            _band_peak_fast[i] = ATK * raw6[i] + (1 - ATK) * _band_peak_fast[i]
        else:
            _band_peak_fast[i] *= REL
        _band_peak_fast[i] = max(_band_peak_fast[i], 1e-7)

    GATE  = 0.04
    bn_raw = np.clip(raw6 / _band_peak_fast, 0.0, 1.0)
    _band_smooth[:] = 0.35 * bn_raw + 0.65 * _band_smooth

    # ── 4. RMS / silence gating ───────────────────────────────────────────────
    rms = float(np.sqrt(np.mean(chunk ** 2)))
    _rms_hist.append(rms)
    rms_smooth = float(np.mean(_rms_hist))
    in_silence = rms_smooth < SILENCE_FLOOR * 2

    if in_silence:
        _silence_frames += 1
    else:
        _silence_frames = 0

    # ── 5. Onset detection ────────────────────────────────────────────────────
    sub_bass_energy = float(_band_smooth[0])
    bass_energy     = float(_band_smooth[1])
    _onset_env.append(sub_bass_energy + bass_energy * 0.6)

    now = time.monotonic()
    if now - _last_bpm_calc > 2.0 and len(_onset_env) >= 80:
        env_arr  = np.array(_onset_env, dtype=np.float64)
        _bpm_est = _estimate_bpm(env_arr)
        _last_bpm_calc = now
    _bpm_smooth = 0.05 * _bpm_est + 0.95 * _bpm_smooth

    br = gs("brightness") / 100.0

    # ── 6. Mode dispatch ──────────────────────────────────────────────────────
    from album_art import get_album_art_color
    music_mode = gs("music_mode")

    if music_mode == "reactive":
        # ── Reactive: user hue + BPM cycling + bass/treble tilt + beat ───────
        user_rgb = gs("music_color")
        user_hue, user_sat, user_val = colorsys.rgb_to_hsv(
            user_rgb[0] / 255.0, user_rgb[1] / 255.0, user_rgb[2] / 255.0
        )
        if gs("album_art_enabled"):
            aa = get_album_art_color()
            user_hue, _, _ = colorsys.rgb_to_hsv(
                aa[0] / 255.0, aa[1] / 255.0, aa[2] / 255.0
            )

        overall_energy = float(np.mean(_band_smooth))
        bass_tilt      = float(_band_smooth[0] + _band_smooth[1]) * 0.4
        treble_tilt    = float(_band_smooth[4] + _band_smooth[5]) * 0.15
        hue_tilt       = bass_tilt * -0.04 + treble_tilt * 0.04

        bpm_rate  = (_bpm_smooth / 8.0) / 60.0
        _hue_phase = (_hue_phase + bpm_rate * 0.025) % 1.0

        onset_val  = sub_bass_energy + bass_energy * 0.6
        beat_thr   = max(float(np.mean(_onset_env)) * 1.35, SILENCE_FLOOR * 4) \
                     if len(_onset_env) > 10 else 1e9
        if onset_val > beat_thr and not in_silence:
            _beat_flash    = 1.0
            _beat_hue_jump = 0.48 + (sub_bass_energy - 0.5) * 0.15
            _compl_fade    = 1.0

        _beat_flash = max(0.0, _beat_flash - 0.12)
        _compl_fade = max(0.0, _compl_fade - 0.08)

        base_hue    = (user_hue + _hue_phase * 0.12 + hue_tilt) % 1.0
        target_val  = max(0.06, overall_energy ** 0.65 + _beat_flash * 0.50)
        VAL_A       = 0.55 if target_val > _val_smooth else 0.25
        _val_smooth = VAL_A * target_val + (1 - VAL_A) * _val_smooth
        target_sat  = 0.60 + _flux_smooth * 0.40 - _compl_fade * 0.40
        _sat_smooth = 0.35 * target_sat + 0.65 * _sat_smooth

        if in_silence:
            _val_smooth = max(_val_smooth * 0.96, 0.04)

        r, g, b = [x * 255 * br for x in
                   colorsys.hsv_to_rgb(base_hue,
                                       min(_sat_smooth, 1.0),
                                       min(_val_smooth, 1.0))]

    else:
        # ── Spectrum (default prism) mode ─────────────────────────────────────
        if gs("album_art_enabled"):
            aa = get_album_art_color()
            forced_hue, _, _ = colorsys.rgb_to_hsv(
                aa[0] / 255.0, aa[1] / 255.0, aa[2] / 255.0
            )
            _hue_phase = forced_hue

        # Weighted circular mean of band hues
        bn = np.maximum(_band_smooth - GATE, 0.0)
        total_w = float(bn.sum()) + 1e-9
        sin_sum = float(np.sum(np.sin(_BAND_HUE * math.tau) * bn))
        cos_sum = float(np.sum(np.cos(_BAND_HUE * math.tau) * bn))
        pull_hue = (math.atan2(sin_sum, cos_sum) / math.tau) % 1.0

        bpm_rate  = (_bpm_smooth / 8.0) / 60.0
        _hue_phase = (_hue_phase + bpm_rate * 0.025) % 1.0
        # Blend: phase + pull (stronger at high energy)
        pull_str  = min(total_w * 0.35, 0.55)
        dh        = (pull_hue - _hue_phase + 0.5) % 1.0 - 0.5
        _hue_phase = (_hue_phase + dh * pull_str * 0.08) % 1.0

        # Sub-bass kick → warm hue pull toward red/orange
        kick_pull = float(_band_smooth[0]) * 0.18 + float(_band_smooth[1]) * 0.09
        _hue_phase = (_hue_phase - kick_pull * 0.15) % 1.0

        overall_energy = float(np.mean(_band_smooth))
        onset_val = sub_bass_energy + bass_energy * 0.6
        beat_thr  = max(float(np.mean(_onset_env)) * 1.4, SILENCE_FLOOR * 4) \
                    if len(_onset_env) > 10 else 1e9

        if onset_val > beat_thr and not in_silence:
            _beat_flash    = 1.0
            _beat_hue_jump = 0.50 + (sub_bass_energy - 0.5) * 0.10
            _compl_fade    = 1.0

        _beat_flash = max(0.0, _beat_flash - 0.10)
        _compl_fade = max(0.0, _compl_fade - 0.07)

        if _beat_hue_jump > 0.0:
            _hue_phase    = (_hue_phase + _beat_hue_jump) % 1.0
            _beat_hue_jump = 0.0

        _hue_smooth = _hue_phase

        target_val  = max(0.06, overall_energy ** 0.65 + _beat_flash * 0.60)
        VAL_A       = 0.60 if target_val > _val_smooth else 0.28
        _val_smooth = VAL_A * target_val + (1 - VAL_A) * _val_smooth

        target_sat  = 0.50 + _flux_smooth * 0.50 - _compl_fade * 0.55
        _sat_smooth = 0.38 * max(0.0, target_sat) + 0.62 * _sat_smooth

        if in_silence:
            _hue_smooth = (_hue_smooth + 0.0018) % 1.0
            _val_smooth = max(_val_smooth * 0.96, 0.04)

        r, g, b = [x * 255 * br for x in
                   colorsys.hsv_to_rgb(_hue_smooth,
                                       min(_sat_smooth, 1.0),
                                       min(_val_smooth, 1.0))]

    # ── VU data for GUI meters ────────────────────────────────────────────────
    _vu_data[0] = float(_band_smooth[0] + _band_smooth[1]) / 2   # bass
    _vu_data[1] = float(_band_smooth[2] + _band_smooth[3]) / 2   # mids
    _vu_data[2] = float(_band_smooth[4] + _band_smooth[5]) / 2   # high

    # Apply white-balance & colour-temperature gains
    from color_utils import clip255
    r2 = r * gs("wb_r") * gs("ct_r")
    g2 = g * gs("wb_g") * gs("ct_g")
    b2 = b * gs("wb_b") * gs("ct_b")
    from config import WRITE_UUID
    await client.write_gatt_char(WRITE_UUID,
                                  bytearray([0x7e, 0x00, 0x05, 0x03,
                                             clip255(r2), clip255(g2), clip255(b2),
                                             0x00, 0xef]),
                                  response=False)
    await asyncio.sleep(0.025)


def get_vu_data() -> list:
    return list(_vu_data)


def get_audio_status() -> dict:
    return {
        "status": _audio_status,
        "error":  _audio_error,
        "device": _audio_device_name,
        "backend": _audio_backend,
    }

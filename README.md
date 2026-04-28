# Audio-Visual-LED-Sync 🎨✨

> **Sync your single-colour LED strip to music, screen content, and dynamic effects with real-time responsiveness.**

Transform any ELK-BLEDOM RGB LED strip into an immersive audio-visual display. Control brightness, speed, and colour in real time with a sleek Windows desktop app featuring global hotkeys, presets, and advanced DSP algorithms.

---

## ✨ Features

### 🎵 Smart Sync Modes

- **🎼 Screen Sync** — Capture average screen colour in real time with saturation-weighted sampling and temporal smoothing
- **🎶 Music Sync** — Prism Engine: BPM-driven hue cycling, spectral analysis across 6 mel-scaled bands, beat detection, and reactive colour shifts
- **🎨 Solid Color** — Pick any RGB colour with a live 16-colour history and quick presets
- **💨 Breathing** — Smooth pulsing; optional rainbow mode
- **🌈 Rainbow Cycle** — Full spectrum rotation at variable speed
- **⚡ Strobe** — Crisp flashing; optional spectrum mode
- **🌊 Color Wave** — Blend between custom colour stops (up to 8 stops)
- **🕯️ Candlelight** — Warm, flickering flames with randomized hue

### ⚡ Advanced Features

- **🔊 VU Meters** — Real-time bass/mids/highs visualization (Music Sync only)
- **🌡️ Colour Temperature** — Adjust warmth (1500K–9000K) globally across all modes
- **⚪ White Balance** — Per-channel gains tuned for your specific LED strip
- **🎬 Auto-Trigger** — Detect VLC, Spotify, or custom processes and switch modes instantly
- **📅 Night Schedule** — Auto-dim and change mode during configured hours
- **💾 Presets (Scenes)** — Save and recall mode + colour + brightness + speed snapshots
- **⌨️ Global Hotkeys** — Control the strip without opening the app:
  - `Ctrl+Alt+G` — Toggle strip on/off
  - `Ctrl+Alt+M` — Show control panel
  - `Ctrl+Alt+→` — Cycle to next mode
  - `Ctrl+Alt+↑` — Brightness +10%
  - `Ctrl+Alt+↓` — Brightness −10%
  - `Ctrl+Alt+V` — Paste hex colour from clipboard
- **📌 System Tray** — Run minimized with quick-access mode menu
- **🪟 Windows Startup** — Optional auto-launch at login
- **📊 Persistent Settings** — All configurations saved to `avls_settings.json`

---

## 🎯 Compatibility

### Supported LED Strips

This app works with **any single-colour RGB LED strip using the ELK-BLEDOM Bluetooth protocol**, including:

- **Gesto Smart LED Strip** (my LED)
- **ELK-BLEDOM generic RGB strips** (most common budget option)
- Any BLE RGB controller compatible with the ELK-BLEDOM protocol

## To support a your MAC address or UUID, edit `config.py`:
```python
MAC_ADDR   = "YOUR:DEVICE:MAC:ADDRESS"  # Default: "BE:37:63:00:0C:80"
WRITE_UUID = "your-characteristic-uuid"  # Default: "0000fff3-0000-1000-8000-00805f9b34fb"
```

### System Requirements

- **Windows 10 / 11** (Bluetooth + Win32 API)
- **Python 3.10+** (if running from source)
- **Bluetooth adapter** (built-in or USB)

---

## 📦 Installation

### Option 1: Download & Run (.exe) — **Easiest for Non-Programmers**

1. Go to [**Releases**](../../releases)
2. Download `Audio-Visual-LED-Sync.exe` (latest version)
3. Double-click to launch — no installation needed, no dependencies required
4. Pair your LED strip via Windows Bluetooth settings first

### Option 2: Install from Source (Python)(Recommended)

**Requirements:**
- Python 3.10 or higher
- pip (Python package manager)

**Steps:**

```bash
# Clone the repository
git clone https://github.com/shauryakr2006/Audio-Visual-LED-Sync.git
cd Audio-Visual-LED-Sync

# Create virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

---

## 🚀 Quick Start

### 1. Pair Your LED Strip

1. Open a AI chatbot
2. Power on your LED strip
3. Tell ur chatbot which LED u have, its protocol
4. Match the protocol (or maybe ask if ur protocol will work with this project)
5. Ask it how to find your strip's MAC address and UUID
6. Configure that in your config.py file

### 2. Launch the App

- **From .exe:** Double-click `Audio-Visual-LED-Sync.exe`
- **From source:** in terminal within cloned directory/app/ `python main.py`

### 3. Start Syncing!

- Select a mode from the sidebar (Screen Sync, Music Sync, Breathing, etc.)
- Adjust **Brightness**, **Speed**, and **Colour** using footer sliders
- Open **⚙ Settings** for advanced tuning

---

## 🎛️ Mode Guide

### Screen Sync
Captures your primary monitor's central region and renders it on the LED strip with customizable:
- **Sample Region** — What % of the screen to sample (10–100%)
- **Blackout Threshold** — Minimum brightness to trigger colour (0–60)
- **EMA Smoothing** — Temporal averaging (0.02–1.00); lower = more responsive
- **Low-Latency Mode** — Skip smoothing for ~16 ms response time

**Pro tip:** Use "Low-Latency" for gaming; standard mode for films.

### Music Sync (Prism Engine v3.4)

Two modes:
- **Spectrum** — Real-time mel-scaled frequency analysis (bass=red, mids=cyan, treble=magenta)
- **Reactive** — User-selected hue with BPM cycling and beat-driven flashes

Features:
- 6-band mel-scaled frequency decomposition (perceptually uniform)
- Automatic BPM detection via onset envelope autocorrelation
- Spectral flux drives saturation (dynamic music = vivid, silence = muted)
- Beat detection with ≈180° complementary colour jump
- Optional album art dominant colour extraction (Spotify)

**Audio backends (in priority order):**
1. **pyaudiowpatch** (recommended) — WASAPI loopback, true silence
2. **sounddevice** (fallback) — WASAPI, may capture self-audio at idle

### Effects Modes

| Mode | Behaviour | Settings |
|------|-----------|----------|
| **Breathing** | Smooth pulsing sinewave | Speed, optional rainbow |
| **Rainbow** | Full spectrum rotation | Speed |
| **Strobe** | Crisp on/off flashing | Speed, optional spectrum |
| **Color Wave** | Blend between custom colours | Speed, up to 8 colour stops |
| **Candlelight** | Warm, flickering flames | Speed (flicker rate) |

---

## ⚙️ Configuration

All settings are persisted in `avls_settings.json`. Key configurations:

```json
{
  "mode": "screen_sync",
  "brightness": 75,
  "color": [0, 255, 140],
  "speed": 50,
  "ct_k": 6500,
  "sc_low_latency": false,
  "schedule_enabled": true,
  "schedule_night_start": "22:00",
  "schedule_night_end": "07:00",
  "close_to_tray": true
}
```

### Manual Adjustments

Edit `avls_settings.json` directly to tweak:
- **Colour temperature gains** (`ct_r`, `ct_g`, `ct_b`)
- **White balance** (`wb_r`, `wb_g`, `wb_b`)
- **Screen sync correction** (`sc_correction`)

Or use the **Settings** panel in the GUI for a visual approach.

---

## 🔧 Build Your Own .exe

To build a standalone Windows executable with PyInstaller:

```bash
pip install pyinstaller pillow

python build_exe.py
# or with custom icon:
python build_exe.py --icon myicon.ico
```

Output: `dist/Audio-Visual-LED-Sync.exe` (~100 MB)

---

## 🏗️ Project Structure

```
Audio-Visual-LED-Sync/
├── main.pyw                   # Entry point; boots daemon threads & Tk loop
├── config.py                  # Hardware constants, mode names, settings store
├── state.py                   # Shared runtime globals
├── gui.py                     # Tkinter control panel (900x640 min)
├── ble_engine.py              # BLE connection loop & mode dispatcher
├── audio_engine.py            # Audio capture & Prism Engine DSP
├── screen_sync.py             # Screen capture & ambilight logic
├── effects.py                 # LED effect tick functions
├── album_art.py               # Spotify album art colour extraction
├── auto_trigger.py            # Process detection, night schedule, startup
├── hotkeys.py                 # Global Win32 hotkey listener
├── color_utils.py             # Color math (Kelvin→RGB, history, etc.)
├── tray.py                    # System tray icon & menu
├── build_exe.py               # PyInstaller build script
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── LICENSE                    # MIT License
├── .gitignore                 # Git exclusions
└── docs/
    ├── INSTALLATION.md        # Detailed installation guide
    ├── MODES.md               # Deep dive into each sync mode
    ├── TROUBLESHOOTING.md     # Common issues & solutions
    └── CONTRIBUTING.md        # Developer guidelines
```

---

## 🔌 Architecture

### Thread Model

- **Main (Tk)** — GUI event loop
- **BLE** — Async/await BleakClient connection, mode dispatcher
- **BgLoop** — Auto-trigger watcher, night schedule, album-art poller (3 s tick)
- **HotKey** — Win32 global hotkey message pump
- **Tray** — pystray icon loop (spawned by run_detached)

### DSP Pipeline

**Music Sync:**
1. Capture 2048 samples @ 44.1 kHz (BLE callback)
2. Hann windowing + FFT
3. 6-band mel-scaled energy extraction
4. Per-band AGC (attack/release feedback)
5. RMS gating (silence detection)
6. Onset envelope → autocorrelation → BPM estimation
7. Circular mean hue pull (band energy weighted)
8. Beat detection + complementary flash
9. Apply WB + CT gains → BLE write

**Screen Sync:**
1. Capture central region (configurable %)
2. Saturation × brightness weighting (avoid greys)
3. Temporal EMA smoothing
4. Blackout thresholding
5. Correction curve + gamma
6. Apply WB + CT gains → BLE write

---

## 🐛 Troubleshooting

### Strip won't connect
1. Restart Bluetooth adapter (disable/enable in Settings)
2. Forget the device and re-pair
3. Ensure MAC_ADDR in `config.py` matches your device
4. Check device is powered and within range

### Music Sync is silent or shows "No audio backend"
- Install pyaudiowpatch: `pip install pyaudiowpatch`
- Or install sounddevice fallback: `pip install sounddevice`
- Restart the app

### Colours look wrong / shifted
- Adjust **White Balance** or **Colour Temperature** in Settings
- Some strips have weak red channels — increase R gain

### Hotkeys not working
- Run the app as Administrator
- Check **Global Hotkeys** status in Settings
- Ensure no conflicting hotkeys in other apps

See **[Troubleshooting](docs/TROUBLESHOOTING.md)** for more.

---

## 🤝 Contributing

We welcome contributions! Whether you're fixing bugs, adding features, or improving docs:

1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/amazing-thing`)
3. **Commit** with clear messages
4. **Push** and open a **Pull Request**

See **[Contributing Guide](docs/CONTRIBUTING.md)** for detailed guidelines.

### Ideas for Contribution

- [ ] Support for additional LED protocols (LIFX, Nanoleaf, Razer Chroma)
- [ ] macOS/Linux support (requires BLE refactor)
- [ ] Beatport API integration for real-time BPM sync
- [ ] Multi-strip synchronization
- [ ] WebUI dashboard
- [ ] Dark mode / additional themes
- [ ] Performance optimizations
- [ ] Unit tests & CI/CD

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

You're free to use, modify, and distribute this software provided you include the license text.

---

## 💬 Support & Feedback

- **Found a bug?** [Open an issue](../../issues)
- **Have a feature idea?** [Start a discussion](../../discussions)
- **Want to chat?** Check out the [issues](../../issues) tab for community Q&A

---

## ⭐ Star History

If you find this project useful, please consider starring it on GitHub! It helps other users discover the project.

---

**Made with ❤️ for LED enthusiasts, music lovers, and open-source contributors worldwide.**

*Last updated: April 2026 | v3.6*

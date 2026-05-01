# Audio-Visual-LED-Sync 🎨✨

> **Sync your single-colour LED strip to music, screen content, and dynamic effects with real-time responsiveness.**

Transform any ELK-BLEDOM RGB LED strip into an immersive audio-visual display. Control brightness, speed, and colour in real time with a sleek Windows desktop app featuring global hotkeys, presets, and advanced syncing algorithms.

---

## ✨ Features

- **🎼 Screen Sync** — Matches your LED strip to the dominant colours on your screen.
- **🎶 Music Sync** — Reacts to audio with beat detection, spectral analysis, and VU meters.
- **🎨 Solid Color & Effects** — Choose solid colours, Breathing, Rainbow Cycle, Strobe, Color Wave, or Candlelight effects.
- **⚡ Advanced Controls** — White balance tuning, colour temperature, and low-latency modes.
- **🎬 Automation** — Auto-trigger modes based on running apps (like Spotify or VLC) and set night schedules.
- **⌨️ Global Hotkeys** — Control your lights without opening the app window.

---

## 🎯 Compatibility

This app works with **Windows 10 / 11** and **any single-colour RGB LED strip using the ELK-BLEDOM Bluetooth protocol**, including:
- **Gesto Smart LED Strip**
- **Lotus Lantern / Triones / ELK-BLEDOM generic RGB strips**

---

## 📦 Installation

**Requirements:**
- Python 3.10+
- A Windows PC with Bluetooth

**Steps:**
1. Clone the repository:
   ```bash
   git clone https://github.com/shauryakr2006/Audio-Visual-LED-Sync.git
   cd Audio-Visual-LED-Sync
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python app/main.py
   ```

---

## 🚀 Quick Start & Setup

### 1. Find Your LED Strip's MAC Address
Make sure your LED strip is powered on and Bluetooth is enabled on your PC.
Run the included finder script:
```bash
python MacAddFinder.py
```
Copy the **Address** (e.g., `BE:37:63:00:0C:80`) of your device from the console output.

### 2. Configure the App
1. Launch the application (`python app/main.py`).
2. Go to the **Settings ⚙** tab in the sidebar.
3. Paste your copied MAC address into the **Hardware Configuration** section.
4. Click anywhere else or press Enter to save.

### 3. Start Syncing!
- Click the **ON** button in the footer to connect.
- Select a mode from the sidebar (Screen Sync, Music Sync, etc.).
- Adjust **Brightness**, **Speed**, and **Colour** using the footer sliders.

---

## 🐛 Troubleshooting

- **Strip won't connect:** Ensure Bluetooth is on, the strip is powered, and the MAC address in Settings is exactly correct.
- **Music Sync is silent:** Install the recommended audio backend by running `pip install pyaudiowpatch` and restart the app.
- **Colours look wrong:** Adjust the **White Balance** or **Colour Temperature** in the Settings tab.


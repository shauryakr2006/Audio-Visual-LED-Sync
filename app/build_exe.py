"""
build_exe.py — Build Audio-Visual-LED-Sync into a standalone Windows .exe
==========================================================================
Usage:
    python build_exe.py                  # use default generated icon
    python build_exe.py --icon myicon.ico

Requirements:
    pip install pyinstaller pillow

What it does:
  1. Generates a green-ring .ico icon (unless --icon is supplied)
  2. Runs PyInstaller with the right hidden-imports and options
  3. Copies the final .exe to dist/Audio-Visual-LED-Sync.exe

PyInstaller flags used:
  --onefile       Single portable .exe
  --windowed      No console window (same as .pyw behaviour)
  --icon          Embed the .ico into the .exe
  --hidden-import For packages PyInstaller misses via static analysis
  --name          Output name
"""

import argparse
import os
import subprocess
import sys


# ── Icon generation ───────────────────────────────────────────────────────────

def generate_icon(out_path: str = "avls_icon.ico"):
    """Create a simple green-ring icon and save as .ico (multi-size)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("[build] Pillow not installed. Run:  pip install pillow")
        sys.exit(1)

    sizes = [256, 128, 64, 48, 32, 16]
    frames = []
    for s in sizes:
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        pad = max(1, s // 20)
        # Outer ring
        d.ellipse([pad, pad, s-pad, s-pad],
                  outline=(0, 255, 140, 255), width=max(2, s // 18))
        # Inner dot
        c  = s // 2
        r2 = max(2, s // 6)
        d.ellipse([c-r2, c-r2, c+r2, c+r2], fill=(0, 255, 140, 255))
        frames.append(img)

    frames[0].save(
        out_path,
        format="ICO",
        sizes=[(f.width, f.height) for f in frames],
        append_images=frames[1:],
    )
    print(f"[build] Icon written → {out_path}")
    return out_path


# ── PyInstaller invocation ────────────────────────────────────────────────────

HIDDEN_IMPORTS = [
    "bleak",
    "bleak.backends.winrt",           # Windows BLE backend
    "bleak.backends.winrt.client",
    "mss",
    "mss.windows",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "pystray",
    "pystray._win32",
    "numpy",
    "colorsys",
    "sounddevice",
    "pyaudiowpatch",
    "psutil",
    "winreg",
    "ctypes.wintypes",
    # GestoBridge modules
    "state",
    "config",
    "color_utils",
    "effects",
    "screen_sync",
    "audio_engine",
    "album_art",
    "ble_engine",
    "hotkeys",
    "auto_trigger",
    "tray",
    "gui",
]

# Extra data files to bundle (source → destination inside the bundle)
# Add your custom icon or any other assets here.
ADD_DATA: list[tuple[str, str]] = [
    # ("assets/banner.png", "assets"),  # example
]


def build(icon_path: str):
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "main.py",
        "--onefile",
        "--windowed",            # no console (same as .pyw)
        f"--icon={icon_path}",
        "--name=Audio-Visual-LED-Sync",
        "--clean",               # delete previous build cache
        "--noconfirm",           # overwrite dist without asking
    ]

    for hi in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", hi]

    for src, dst in ADD_DATA:
        if os.path.exists(src):
            cmd += ["--add-data", f"{src}{os.pathsep}{dst}"]

    # Windows: set version info (optional, edit to taste)
    version_file = "version_info.txt"
    if os.path.exists(version_file):
        cmd += [f"--version-file={version_file}"]

    print("[build] Running PyInstaller…")
    print("        " + " ".join(cmd[:6]) + " …")
    result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        exe = os.path.join("dist", "Audio-Visual-LED-Sync.exe")
        if os.path.exists(exe):
            size_mb = os.path.getsize(exe) / 1_048_576
            print(f"\n✓  Build complete → {exe}  ({size_mb:.1f} MB)")
            print("   Double-click to run, or add to Windows Startup.")
        else:
            print("\n⚠  PyInstaller succeeded but exe not found at expected path.")
    else:
        print(f"\n✗  PyInstaller failed (exit code {result.returncode}).")
        print("   Check the output above for errors.")
        sys.exit(result.returncode)


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build Audio-Visual-LED-Sync into a standalone .exe")
    parser.add_argument(
        "--icon", default=None,
        help="Path to a .ico file to embed (default: auto-generated)")
    args = parser.parse_args()

    if args.icon:
        if not os.path.exists(args.icon):
            print(f"[build] Icon file not found: {args.icon}")
            sys.exit(1)
        icon_path = args.icon
    else:
        icon_path = generate_icon("avls_icon.ico")

    # Ensure PyInstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[build] PyInstaller not installed. Run:  pip install pyinstaller")
        sys.exit(1)

    build(icon_path)


if __name__ == "__main__":
    main()

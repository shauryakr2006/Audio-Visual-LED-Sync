"""
state.py — Shared runtime globals
==================================
Centralises every mutable singleton that multiple modules need to read *and*
write.  Import this module anywhere; never assign to these names with
  from state import _app       ← wrong (creates a local binding)
Always use:
  import state
  state._app = ...             ← correct (mutates the module attribute)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui import GestoBridge  # only for type hints, never at runtime

# The Tkinter root window (set in main.py after GestoBridge() is created)
_app: "GestoBridge | None" = None

# Set False to signal all threads to exit cleanly
_running: bool = True

# True while BLE is connected
_ble_ok: bool = False

# Callback invoked by the BLE engine to report connection state changes
# Signature: (status: str) -> None   where status in {"connected","disconnected"}
_status_cb = None

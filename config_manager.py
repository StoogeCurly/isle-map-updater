"""
Configuration management for Isle Map Updater.
Handles saving and loading of user preferences.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple


class ConfigManager:
    def __init__(self, config_file: Optional[str] = None):
        base_dir = self._get_persistent_base_dir()
        self.config_file = config_file or os.path.join(base_dir, "map_config.json")
        self.selected_map: Optional[str] = None
        self.last_selected_label: Optional[str] = None
        self.capture_hotkey: str = "F8"
        self.coord_click_position: Optional[Tuple[int, int]] = None
        self.close_overlay_after_capture: bool = True
        self.restore_mouse_after_capture: bool = True
        self.open_map_on_startup: bool = False
        self.load_config()

    def _get_persistent_base_dir(self) -> str:
        """Return a stable directory that survives app restarts and packaged EXE launches."""
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    def load_config(self) -> None:
        """Load configuration from JSON file."""
        try:
            if not os.path.exists(self.config_file):
                print(f"[CONFIG] No config file found, will create on first save: {self.config_file}")
                return

            with open(self.config_file, "r", encoding="utf-8") as f:
                config: Dict[str, Any] = json.load(f)

            self.selected_map = config.get("selected_map")
            self.last_selected_label = config.get("last_selected_label")
            self.capture_hotkey = config.get("capture_hotkey", "F8") or "F8"

            click_position = config.get("coord_click_position")
            if isinstance(click_position, (list, tuple)) and len(click_position) == 2:
                self.coord_click_position = (int(click_position[0]), int(click_position[1]))
            else:
                self.coord_click_position = None

            self.close_overlay_after_capture = bool(config.get("close_overlay_after_capture", True))
            self.restore_mouse_after_capture = bool(config.get("restore_mouse_after_capture", True))
            self.open_map_on_startup = bool(config.get("open_map_on_startup", False))

            print(f"[CONFIG] Loaded saved map: {self.selected_map}")
            print(f"[CONFIG] Loaded capture hotkey: {self.capture_hotkey}")
            print(f"[CONFIG] Loaded click position: {self.coord_click_position}")
        except Exception as e:
            print(f"[ERROR] Failed to load config: {e}")

    def save_config(self) -> None:
        """Save configuration atomically to JSON file."""
        try:
            config = {
                "selected_map": self.selected_map,
                "last_selected_label": self.last_selected_label,
                "capture_hotkey": self.capture_hotkey,
                "coord_click_position": list(self.coord_click_position) if self.coord_click_position else None,
                "close_overlay_after_capture": self.close_overlay_after_capture,
                "restore_mouse_after_capture": self.restore_mouse_after_capture,
                "open_map_on_startup": self.open_map_on_startup,
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            temp_file = f"{self.config_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            os.replace(temp_file, self.config_file)
            print(f"[CONFIG] Saved config to: {self.config_file}")
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")

    def set_selected_map(self, map_value: str, map_label: Optional[str] = None) -> None:
        self.selected_map = map_value
        if map_label:
            self.last_selected_label = map_label
        self.save_config()

    def get_selected_map(self) -> Optional[str]:
        return self.selected_map

    def set_capture_hotkey(self, hotkey_text: str) -> None:
        self.capture_hotkey = hotkey_text
        self.save_config()

    def get_capture_hotkey(self) -> str:
        return self.capture_hotkey

    def set_coord_click_position(self, x: int, y: int) -> None:
        self.coord_click_position = (int(x), int(y))
        self.save_config()

    def get_coord_click_position(self) -> Optional[Tuple[int, int]]:
        return self.coord_click_position

    def set_close_overlay_after_capture(self, enabled: bool) -> None:
        self.close_overlay_after_capture = bool(enabled)
        self.save_config()

    def get_close_overlay_after_capture(self) -> bool:
        return self.close_overlay_after_capture

    def set_restore_mouse_after_capture(self, enabled: bool) -> None:
        self.restore_mouse_after_capture = bool(enabled)
        self.save_config()

    def get_restore_mouse_after_capture(self) -> bool:
        return self.restore_mouse_after_capture

    def set_open_map_on_startup(self, enabled: bool) -> None:
        self.open_map_on_startup = bool(enabled)
        self.save_config()

    def get_open_map_on_startup(self) -> bool:
        return self.open_map_on_startup

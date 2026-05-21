#!/usr/bin/env python3
"""
Isle Map Updater v1
Reimagined and maintained by StoogeCurly for the Isle Map Updater project.
Inspired by GitHub Muslix / the-isle-map-updater.

This file starts the GUI, loads saved settings, connects the hotkey/capture
system, starts the browser/map manager, watches the clipboard for copied
The Isle coordinates, and sends those coordinates to the Vulnona map so the
map position can be updated automatically while in game.

Saved user data such as map_config.json and the Chrome browser profile should
be stored in:

    C:\\Users\\YourName\\AppData\\Local\\Isle Map Updater\\
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
import winsound
from typing import Optional, Tuple

import psutil
import pyperclip

from browser_manager import BrowserManager
from config_manager import ConfigManager
from coordinate_parser import CoordinateParser
from gui_manager import GUIManager
from hotkey_capture import CaptureAutomation, GlobalHotkeyManager


# ============================================================
# APPDATA SAVE LOCATION
#
# Saves here:
# C:\Users\YourName\AppData\Local\Isle Map Updater\
# ============================================================

APPDATA_BASE = os.getenv("LOCALAPPDATA")

if APPDATA_BASE:
    APPDATA_DIR = os.path.join(APPDATA_BASE, "Isle Map Updater")
else:
    # Fallback just in case LOCALAPPDATA is unavailable.
    APPDATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Isle Map Updater")

os.makedirs(APPDATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(APPDATA_DIR, "map_config.json")
CHROME_PROFILE_DIR = os.path.join(APPDATA_DIR, "chrome_profile")
os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)


class IsleMapUpdater:
    def __init__(self):
        self.running = False
        self.test_mode = False
        self.last_clipboard_text = ""
        self.last_clipboard_sequence = self._get_clipboard_sequence_number()
        self.last_valid_coordinates: Optional[str] = None
        self.last_update_time = 0.0
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_lock = threading.Lock()
        self.capture_lock = threading.Lock()
        self.capture_in_progress = False

        # ------------------------------------------------------------
        # Config Manager
        # ------------------------------------------------------------
        try:
            self.config_manager = ConfigManager(CONFIG_FILE)
        except TypeError:
            self.config_manager = ConfigManager()

            # Common names different versions may use.
            self.config_manager.config_file = CONFIG_FILE
            self.config_manager.config_path = CONFIG_FILE
            self.config_manager.file_path = CONFIG_FILE

        # ------------------------------------------------------------
        # Browser Manager
        # ------------------------------------------------------------
        try:
            self.browser_manager = BrowserManager(CHROME_PROFILE_DIR)
        except TypeError:
            self.browser_manager = BrowserManager()

            # Common names different versions may use.
            self.browser_manager.chrome_profile_dir = CHROME_PROFILE_DIR
            self.browser_manager.profile_dir = CHROME_PROFILE_DIR
            self.browser_manager.profile_path = CHROME_PROFILE_DIR
            self.browser_manager.user_data_dir = CHROME_PROFILE_DIR

        self.coordinate_parser = CoordinateParser()
        self.gui_manager = GUIManager(self)
        self.capture_automation = CaptureAutomation() if sys.platform.startswith("win") else None
        self.hotkey_manager = GlobalHotkeyManager(self.on_capture_hotkey_pressed) if sys.platform.startswith("win") else None

    def _get_clipboard_sequence_number(self) -> Optional[int]:
        if not sys.platform.startswith("win"):
            return None
        try:
            return ctypes.windll.user32.GetClipboardSequenceNumber()
        except Exception:
            return None

    def is_the_isle_running(self) -> bool:
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                name = proc.info.get("name")
                if name and "isle" in name.lower():
                    return True
            return False
        except Exception:
            return False

    def _clipboard_changed(self, current_clipboard: str, current_sequence: Optional[int]) -> bool:
        if current_sequence is not None and self.last_clipboard_sequence is not None:
            return current_sequence != self.last_clipboard_sequence
        return current_clipboard != self.last_clipboard_text

    def _is_left_mouse_down(self) -> bool:
        if not sys.platform.startswith("win"):
            return False
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        except Exception:
            return False

    def _play_calibration_sound(self):
        try:
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    def monitor_clipboard(self):
        print("[CLIPBOARD] Monitoring clipboard for coordinate changes...")
        print("[INFO] Copy Isle coordinates to clipboard (e.g., 88,879.526, -288,696.11, 21,112.882)")
        print("[INFO] Clipboard sequence tracking is enabled when available")
        print("[MONITOR] Waiting for clipboard changes...")

        while self.running:
            try:
                current_clipboard = pyperclip.paste()
                current_sequence = self._get_clipboard_sequence_number()

                if current_clipboard and self._clipboard_changed(current_clipboard, current_sequence):
                    raw_coords = self.coordinate_parser.parse_coordinates(current_clipboard)
                    self.last_clipboard_text = current_clipboard
                    self.last_clipboard_sequence = current_sequence

                    if raw_coords is not None:
                        self.last_valid_coordinates = raw_coords
                        msg = f"[FOUND] Isle coordinates: {raw_coords}"
                        print(msg)
                        self.gui_manager.log_to_gui(msg)
                        self.gui_manager.update_last_coords_label(raw_coords)

                        if self.browser_manager.is_browser_alive():
                            success = self.browser_manager.update_map_position(raw_coords)
                            if success:
                                self.last_update_time = time.time()
                                success_msg = "[OK] Map updated successfully!"
                                print(success_msg)
                                self.gui_manager.log_to_gui(success_msg)
                                if self.gui_manager.resend_button:
                                    self.gui_manager._run_on_ui(
                                        lambda: self.gui_manager.resend_button.config(state="normal")
                                    )
                            else:
                                error_msg = self.browser_manager.get_last_error() or "[WARNING] Map update failed"
                                print(error_msg)
                                self.gui_manager.log_to_gui(error_msg)
                        else:
                            self.gui_manager.log_to_gui("[WARNING] Browser is not running; coordinates saved for resend")
                    else:
                        if len(current_clipboard.strip()) < 200:
                            info_msg = f"[INFO] Clipboard ignored: '{current_clipboard[:40]}...'"
                            print(info_msg)

                time.sleep(0.25)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ERROR] Monitoring error: {e}")
                time.sleep(1)

    def start_monitoring(self):
        with self.monitor_lock:
            if self.running:
                return
            if not self.browser_manager.is_browser_alive() or not self.config_manager.get_selected_map():
                return
            self.running = True
            self.gui_manager.log_to_gui("Starting coordinate monitoring...")
            self.gui_manager.log_to_gui("Copy Isle coordinates from The Isle to update the map")
            self.monitor_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
            self.monitor_thread.start()

    def resend_last_coordinates(self) -> Tuple[bool, str]:
        if not self.last_valid_coordinates:
            return False, "[INFO] No valid coordinates have been captured yet."
        if not self.browser_manager.is_browser_alive():
            return False, "[WARNING] Browser is not running. Start the browser first."

        success = self.browser_manager.update_map_position(self.last_valid_coordinates)
        if success:
            self.last_update_time = time.time()
            return True, f"[OK] Resent last coordinates: {self.last_valid_coordinates}"
        return False, self.browser_manager.get_last_error() or "[WARNING] Failed to resend last coordinates"

    def register_capture_hotkey(self) -> Tuple[bool, str]:
        if not self.hotkey_manager:
            return False, "Global hotkeys are supported on Windows only."
        hotkey_text = self.config_manager.get_capture_hotkey()
        return self.hotkey_manager.register(hotkey_text)

    def update_capture_hotkey(self, hotkey_text: str) -> Tuple[bool, str]:
        if not self.hotkey_manager:
            return False, "Global hotkeys are supported on Windows only."
        success, message = self.hotkey_manager.register(hotkey_text)
        if success:
            self.config_manager.set_capture_hotkey(hotkey_text)
        return success, message

    def on_capture_hotkey_pressed(self):
        self.trigger_coordinate_capture(source="hotkey")

    def trigger_coordinate_capture(self, source: str = "manual") -> Tuple[bool, str]:
        if not sys.platform.startswith("win") or not self.capture_automation:
            return False, "Capture automation is supported on Windows only."

        coord_position = self.config_manager.get_coord_click_position()
        if not coord_position:
            return False, "Coordinate click point is not calibrated yet."

        if self.capture_in_progress:
            return False, "A coordinate capture is already running."

        if not self.is_the_isle_running():
            self.gui_manager.log_to_gui("[INFO] The Isle process was not detected. Capture will still try to run.")

        def worker():
            with self.capture_lock:
                self.capture_in_progress = True
                try:
                    x, y = coord_position
                    ok, message = self.capture_automation.perform_capture(
                        x,
                        y,
                        close_overlay=self.config_manager.get_close_overlay_after_capture(),
                        restore_mouse=self.config_manager.get_restore_mouse_after_capture(),
                    )
                    if ok:
                        self.gui_manager.log_to_gui(f"[CAPTURE] Triggered from {source}; waiting for clipboard update...")
                    else:
                        self.gui_manager.log_to_gui(f"[ERROR] {message}")
                finally:
                    self.capture_in_progress = False

        threading.Thread(target=worker, daemon=True).start()
        return True, "Capture started"

    def calibrate_coordinate_click(self, countdown_seconds: int = 5) -> Tuple[bool, str]:

        if not sys.platform.startswith("win") or not self.capture_automation:
            return False, "Calibration is supported on Windows only."

        if self.capture_in_progress:
            return False, "A coordinate capture is already running."

        def worker():
            with self.capture_lock:
                self.capture_in_progress = True

                try:
                    self.gui_manager.log_to_gui("[CALIBRATE] Calibration started.")
                    self.gui_manager.log_to_gui("[CALIBRATE] Click the in-game coordinate text.")
                    self.gui_manager.log_to_gui("[CALIBRATE] I will save the spot only after valid coords copy.")
                    self.gui_manager.log_to_gui("[CALIBRATE] Calibration will cancel after 70 seconds if no valid coords are detected.")

                    # Ignore the mouse click that pressed the GUI button.
                    while self._is_left_mouse_down():
                        time.sleep(0.05)

                    start_time = time.time()
                    last_logged_second = -1
                    calibration_timeout_seconds = 70

                    while True:
                        elapsed = int(time.time() - start_time)

                        if elapsed >= calibration_timeout_seconds:
                            self.gui_manager.log_to_gui(
                                "[CALIBRATE] Calibration cancelled. No valid coordinate click/copy was detected within 70 seconds."
                            )
                            break

                        if elapsed != last_logged_second:
                            last_logged_second = elapsed
                            self.gui_manager.log_to_gui(
                                f"[CALIBRATE] Waiting for coordinate click/copy... {elapsed}s"
                            )

                        if self._is_left_mouse_down():
                            clicked_x, clicked_y = self.capture_automation.get_cursor_pos()

                            # Save clipboard state before the click completes.
                            before_clipboard = pyperclip.paste()
                            before_sequence = self._get_clipboard_sequence_number()

                            # Wait for the click to release.
                            while self._is_left_mouse_down():
                                time.sleep(0.05)

                            # Give the game a moment to copy coordinates.
                            copied_coords = None
                            wait_start = time.time()

                            while time.time() - wait_start < 3.0:
                                current_clipboard = pyperclip.paste()
                                current_sequence = self._get_clipboard_sequence_number()

                                clipboard_changed_from_before = (
                                    current_clipboard != before_clipboard
                                    or current_sequence != before_sequence
                                )

                                clipboard_changed_from_last_seen = self._clipboard_changed(
                                    current_clipboard,
                                    current_sequence,
                                )

                                if clipboard_changed_from_before or clipboard_changed_from_last_seen:
                                    raw_coords = self.coordinate_parser.parse_coordinates(current_clipboard)
                                    if raw_coords is not None:
                                        copied_coords = raw_coords
                                        self.last_clipboard_text = current_clipboard
                                        self.last_clipboard_sequence = current_sequence
                                        break

                                time.sleep(0.1)

                            if copied_coords:
                                self.config_manager.set_coord_click_position(clicked_x, clicked_y)
                                self.last_valid_coordinates = copied_coords

                                self.gui_manager.log_to_gui(
                                    f"[CALIBRATE] Saved coordinate click position: ({clicked_x}, {clicked_y})"
                                )
                                self.gui_manager.log_to_gui(f"[CALIBRATE] Confirmed copied coords: {copied_coords}")

                                self.gui_manager.update_capture_settings_display()
                                self.gui_manager.update_last_coords_label(copied_coords)

                                self._play_calibration_sound()

                                self.gui_manager.log_to_gui("[CALIBRATE] Calibration complete.")
                                break

                            self.gui_manager.log_to_gui(
                                "[CALIBRATE] Click ignored. No valid coordinates copied. Try clicking the coords again."
                            )

                        time.sleep(0.05)

                finally:
                    self.capture_in_progress = False

        threading.Thread(target=worker, daemon=True).start()
        return True, "Calibration started"

    def start(self):

        self.gui_manager.create_gui()

        self.gui_manager.log_to_gui("Isle Map Updater Ready!")
        self.gui_manager.log_to_gui("Inspired by GitHub Muslix / the-isle-map-updater")
        self.gui_manager.log_to_gui("Reimagined by StoogeCurly • v1")

        # Optional debug line to confirm saved data is using AppData.
        self.gui_manager.log_to_gui(f"Save folder: {APPDATA_DIR}")

        selected_map = self.config_manager.get_selected_map()
        if selected_map:
            self.gui_manager.log_to_gui(f"Saved default map: {selected_map}")
            if self.config_manager.get_open_map_on_startup():
                self.gui_manager.log_to_gui("Open map on startup is enabled.")
            else:
                self.gui_manager.log_to_gui("Click 'Setup Browser & Load Maps' to restore it")
        else:
            self.gui_manager.log_to_gui("Click 'Setup Browser & Load Maps' to begin")

        hotkey_ok, hotkey_message = self.register_capture_hotkey() if self.hotkey_manager else (False, "Windows only")
        if hotkey_ok:
            self.gui_manager.log_to_gui(f"Capture hotkey active: {hotkey_message}")
        else:
            self.gui_manager.log_to_gui(f"Capture hotkey inactive: {hotkey_message}")

        if self.config_manager.get_coord_click_position():
            self.gui_manager.log_to_gui(
                f"Saved click point loaded: {self.config_manager.get_coord_click_position()}"
            )

        self.gui_manager.schedule_open_map_on_startup()
        self.gui_manager.start_mainloop()

    def stop(self):
        self.running = False

        if self.hotkey_manager:
            try:
                self.hotkey_manager.stop()
            except Exception:
                pass

        self.browser_manager.stop()
        print("[STOP] Isle Map Updater stopped")


def main():
    print("Isle Map Updater - Starting...")
    print(f"[APPDATA] Save folder: {APPDATA_DIR}")
    print(f"[APPDATA] Config file: {CONFIG_FILE}")
    print(f"[APPDATA] Chrome profile: {CHROME_PROFILE_DIR}")

    try:
        updater = IsleMapUpdater()
        updater.start()
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
    finally:
        print("[EXIT] Isle Map Updater terminated")


if __name__ == "__main__":
    main()
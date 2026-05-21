"""
Hotkey registration and capture automation for Isle Map Updater.
Windows-only helpers for global hotkeys and simulated input.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

MODIFIER_ORDER = ["CTRL", "ALT", "SHIFT", "WIN"]
MODIFIER_TO_FLAG = {
    "CTRL": MOD_CONTROL,
    "ALT": MOD_ALT,
    "SHIFT": MOD_SHIFT,
    "WIN": MOD_WIN,
}

KEY_NAME_TO_VK = {chr(code): code for code in range(ord("A"), ord("Z") + 1)}
KEY_NAME_TO_VK.update({str(d): ord(str(d)) for d in range(10)})
KEY_NAME_TO_VK.update({f"F{i}": 0x6F + i for i in range(1, 13)})
KEY_NAME_TO_VK.update(
    {
        "SPACE": 0x20,
        "TAB": 0x09,
        "ENTER": 0x0D,
        "ESC": 0x1B,
        "UP": 0x26,
        "DOWN": 0x28,
        "LEFT": 0x25,
        "RIGHT": 0x27,
        "HOME": 0x24,
        "END": 0x23,
        "PAGEUP": 0x21,
        "PAGEDOWN": 0x22,
        "INSERT": 0x2D,
        "DELETE": 0x2E,
        "`": 0xC0,
        "~": 0xC0,
    }
)
VK_TO_KEY_NAME = {value: key for key, value in KEY_NAME_TO_VK.items()}


@dataclass
class HotkeySpec:
    modifiers: Tuple[str, ...]
    key_name: str

    def display(self) -> str:
        parts = list(self.modifiers) + [self.key_name]
        return "+".join(parts)

    def register_parts(self) -> Tuple[int, int]:
        modifier_flags = 0
        for mod in self.modifiers:
            modifier_flags |= MODIFIER_TO_FLAG[mod]
        vk = KEY_NAME_TO_VK[self.key_name]
        return modifier_flags, vk


def normalize_key_name(key_name: str) -> Optional[str]:
    key_name = (key_name or "").strip().upper()
    aliases = {
        "PRIOR": "PAGEUP",
        "NEXT": "PAGEDOWN",
        "RETURN": "ENTER",
        "ESCAPE": "ESC",
        "GRAVE": "`",
        "QUOTELEFT": "`",
        "ASCIITILDE": "`",
    }
    key_name = aliases.get(key_name, key_name)
    if key_name in KEY_NAME_TO_VK:
        return key_name
    return None


def parse_hotkey_string(hotkey_text: str) -> Tuple[Optional[HotkeySpec], str]:
    if not hotkey_text:
        return None, "No hotkey selected"

    parts = [part.strip().upper() for part in hotkey_text.split("+") if part.strip()]
    if not parts:
        return None, "No hotkey selected"

    key_name = normalize_key_name(parts[-1])
    if not key_name:
        return None, f"Unsupported hotkey key: {parts[-1]}"

    modifiers = []
    for mod in parts[:-1]:
        if mod not in MODIFIER_TO_FLAG:
            return None, f"Unsupported modifier: {mod}"
        if mod not in modifiers:
            modifiers.append(mod)

    ordered_modifiers = tuple(mod for mod in MODIFIER_ORDER if mod in modifiers)
    return HotkeySpec(ordered_modifiers, key_name), ""


class GlobalHotkeyManager:
    def __init__(self, callback: Callable[[], None]):
        self.callback = callback
        self.hotkey_id = 1
        self.hotkey_spec: Optional[HotkeySpec] = None
        self.listener_thread: Optional[threading.Thread] = None
        self.listener_thread_id: Optional[int] = None
        self._stop_event = threading.Event()
        self._registered = False
        self._lock = threading.Lock()

    def register(self, hotkey_text: str) -> Tuple[bool, str]:
        spec, error = parse_hotkey_string(hotkey_text)
        if not spec:
            return False, error

        with self._lock:
            # Fully stop the old hotkey before trying to register the new one.
            self.unregister(wait=True)

            # Small pause gives Windows time to release the previous global hotkey.
            time.sleep(0.10)

            self.hotkey_spec = spec
            self._registered = False
            self._stop_event.clear()

            self.listener_thread = threading.Thread(target=self._message_loop, daemon=True)
            self.listener_thread.start()

            deadline = time.time() + 3.0
            while time.time() < deadline:
                if self._registered:
                    return True, spec.display()

                if self._stop_event.is_set() and not self._registered:
                    break

                time.sleep(0.02)

            self.unregister(wait=True)
            return False, f"Failed to register hotkey: {spec.display()}"

    def _message_loop(self):
        spec = self.hotkey_spec
        if not spec:
            self._stop_event.set()
            return

        self.listener_thread_id = kernel32.GetCurrentThreadId()

        modifiers, vk = spec.register_parts()

        if not user32.RegisterHotKey(None, self.hotkey_id, modifiers, vk):
            self._registered = False
            self.listener_thread_id = None
            self._stop_event.set()
            return

        self._registered = True

        msg = ctypes.wintypes.MSG()

        while not self._stop_event.is_set():
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)

            if result == 0 or msg.message == WM_QUIT:
                break

            if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                threading.Thread(target=self.callback, daemon=True).start()

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        try:
            user32.UnregisterHotKey(None, self.hotkey_id)
        except Exception:
            pass

        self._registered = False
        self.listener_thread_id = None
        self._stop_event.set()

    def unregister(self, wait: bool = False):
        thread = self.listener_thread
        thread_id = self.listener_thread_id

        if thread_id:
            self._stop_event.set()
            user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)

        if wait and thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

        self._registered = False
        self.listener_thread_id = None
        self.listener_thread = None
        self.hotkey_spec = None

    def stop(self):
        self.unregister(wait=True)


class CaptureAutomation:
    def __init__(self):
        self.tab_vk = KEY_NAME_TO_VK["TAB"]

        # Faster timing profile
        self.key_press_delay = 0.01
        self.click_hold_delay = 0.01
        self.after_open_delay = 0.08
        self.after_move_delay = 0.01
        self.after_click_delay = 0.05
        self.after_close_delay = 0.03

    def get_cursor_pos(self) -> Tuple[int, int]:
        point = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def set_cursor_pos(self, x: int, y: int) -> None:
        user32.SetCursorPos(int(x), int(y))

    def left_click(self) -> None:
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(self.click_hold_delay)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def press_key(self, vk: int) -> None:
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(self.key_press_delay)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def perform_capture(
        self,
        x: int,
        y: int,
        close_overlay: bool = True,
        restore_mouse: bool = True,
    ) -> Tuple[bool, str]:
        try:
            original_x, original_y = self.get_cursor_pos()

            self.press_key(self.tab_vk)
            time.sleep(self.after_open_delay)

            self.set_cursor_pos(x, y)
            time.sleep(self.after_move_delay)

            self.left_click()
            time.sleep(self.after_click_delay)

            if close_overlay:
                self.press_key(self.tab_vk)
                time.sleep(self.after_close_delay)

            if restore_mouse:
                self.set_cursor_pos(original_x, original_y)

            return True, "Capture input sent"
        except Exception as e:
            return False, f"Capture failed: {e}"


def current_modifier_names() -> Tuple[str, ...]:
    pressed = []
    if user32.GetAsyncKeyState(VK_CONTROL) & 0x8000:
        pressed.append("CTRL")
    if user32.GetAsyncKeyState(VK_MENU) & 0x8000:
        pressed.append("ALT")
    if user32.GetAsyncKeyState(VK_SHIFT) & 0x8000:
        pressed.append("SHIFT")
    if (user32.GetAsyncKeyState(VK_LWIN) & 0x8000) or (user32.GetAsyncKeyState(VK_RWIN) & 0x8000):
        pressed.append("WIN")
    return tuple(mod for mod in MODIFIER_ORDER if mod in pressed)
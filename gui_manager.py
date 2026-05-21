"""
Themed GUI management for Isle Map Updater.
Uses the generated dinosaur-style assets while keeping the existing app behavior.
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont, ImageTk

from hotkey_capture import current_modifier_names, normalize_key_name


class GUIManager:
    def __init__(self, app_instance):
        self.app = app_instance
        self.gui = None
        self.status_text = None
        self.map_var = None
        self.map_dropdown = None
        self.save_map_button = None
        self.setup_button = None
        self.refresh_button = None
        self.capture_button = None
        self.calibrate_button = None
        self.hotkey_button = None
        self.hotkey_label = None
        self.coord_label = None
        self.last_coords_label = None
        self.close_overlay_button = None
        self.restore_mouse_button = None
        self.open_map_startup_button = None
        self.close_overlay_var = None
        self.restore_mouse_var = None
        self.open_map_startup_var = None
        self.filtered_maps = []
        self._ui_queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._map_switch_in_progress = False
        self._hotkey_dialog: Optional[tk.Toplevel] = None
        self._browser_state_logged_dead = False
        self._setup_in_progress = False
        self._browser_was_opened_this_session = False
        self._images = {}
        self._text_image_cache = {}
        self._button_image_cache = {}
        self._checkbox_image_cache = {}
        self._asset_dir = Path(__file__).resolve().parent / "assets"
        self._surface_bg = "#17130f"
        self._surface_bg_2 = "#1d1712"
        self._text_main = "#eadfcb"
        self._text_muted = "#cbbfa8"
        self._text_logs = "#f1e7cf"

    def create_gui(self):
        self.gui = tk.Tk()
        self.gui.title("Isle Map Updater")
        self.gui.geometry("700x620")
        self.gui.resizable(False, False)
        self.gui.configure(bg="#110e0b")

        self._load_assets()
        self._apply_window_icon()
        self._apply_dark_title_bar()
        self._draw_static_text_layers()
        self._build_styles()

        bg_label = tk.Label(self.gui, image=self._images["background"], bd=0, highlightthickness=0)
        bg_label.place(x=0, y=0)

        header_panel = tk.Label(self.gui, image=self._resized_image("header_panel", 660, 95), bd=0, highlightthickness=0)
        header_panel.place(x=20, y=8)

        dropdown_bg = tk.Label(self.gui, image=self._resized_image("dropdown_bg", 510, 44), bd=0, highlightthickness=0)
        dropdown_bg.place(x=18, y=145)

        self.map_var = tk.StringVar()
        self.map_dropdown = ttk.Combobox(
            self.gui,
            textvariable=self.map_var,
            state="readonly",
            width=40,
            font=self._pick_font(16, bold=True, decorative=True),
            style="Themed.TCombobox",
        )
        self.map_dropdown.place(x=30, y=152, width=465, height=30)

        saved_map = self.app.config_manager.get_selected_map()
        if saved_map:
            self.map_dropdown.set(f"Saved default: {saved_map}")
        else:
            self.map_dropdown.set("Load browser first to see available maps...")

        self.map_dropdown.bind("<<ComboboxSelected>>", self.on_map_selected)

        self.save_map_button = self._make_image_button(
            self.gui,
            image_key="button_green",
            text="SAVE AS DEFAULT",
            command=self.save_current_map,
            width=145,
            font_size=15,
            decorative=True,
        )
        self.save_map_button.place(x=523, y=146)
        self.save_map_button.config(state=tk.DISABLED)

        setup_button_text = "OPEN MAP" if self.app.config_manager.get_selected_map() else "SETUP MAP"
        self.setup_button = self._make_image_button(
            self.gui,
            image_key="button_green",
            text=setup_button_text,
            command=self.setup_browser_gui,
            width=165,
            font_size=15,
            decorative=True,
        )
        self.setup_button.place(x=18, y=195)
        self._set_setup_button_state(setup_button_text, enabled=True)

        self.refresh_button = self._make_image_button(
            self.gui,
            image_key="button_green",
            text="REFRESH MAPS",
            command=self.refresh_maps_gui,
            width=165,
            font_size=15,
            decorative=True,
        )
        self.refresh_button.place(x=195, y=195)
        self.refresh_button.config(state=tk.DISABLED)

        self.open_map_startup_var = tk.BooleanVar(value=self.app.config_manager.get_open_map_on_startup())
        self.open_map_startup_button = self._make_checkbox_button(
            self.gui,
            variable=self.open_map_startup_var,
            command=self.on_open_map_startup_toggled,
        )
        self.open_map_startup_button.place(x=372, y=202)

        quick_panel = tk.Label(self.gui, image=self._resized_image("quick_panel", 680, 210), bd=0, highlightthickness=0)
        quick_panel.place(x=10, y=240)
        self.hotkey_label = tk.Label(
            self.gui,
            bg="#221912",
            bd=0,
            padx=0,
            pady=0,
            highlightthickness=0,
        )
        self.hotkey_label.place(x=235, y=300, width=90, height=30)

        self.hotkey_button = self._make_image_button(
            self.gui,
            image_key="button_bronze",
            text="SET HOTKEY",
            command=self.open_hotkey_dialog,
            width=190,
            font_size=16,
            decorative=True,
        )
        self.hotkey_button.place(x=400, y=292)
        self.coord_label = tk.Label(self.gui, bg=self._surface_bg, bd=0, padx=0, pady=0, highlightthickness=0)
        self.coord_label.place(x=240, y=356, width=120)

        self.calibrate_button = self._make_image_button(
            self.gui,
            image_key="button_bronze",
            text="CALIBRATE CLICK POINT",
            command=self.calibrate_click_point_gui,
            width=190,
            font_size=16,
            decorative=True,
        )
        self.calibrate_button.place(x=400, y=338)

        self.capture_button = self._make_image_button(
            self.gui,
            image_key="button_green",
            text="CAPTURE COORDINATES",
            command=self.capture_now_gui,
            width=195,
            font_size=10,
        )

        self.close_overlay_var = tk.BooleanVar(value=self.app.config_manager.get_close_overlay_after_capture())
        self.close_overlay_button = self._make_checkbox_button(
            self.gui,
            variable=self.close_overlay_var,
            command=self.on_close_overlay_toggled,
            panel_x=125,
            panel_y=158,
        )
        self.close_overlay_button.place(x=135, y=398)

        self.restore_mouse_var = tk.BooleanVar(value=self.app.config_manager.get_restore_mouse_after_capture())
        self.restore_mouse_button = self._make_checkbox_button(
            self.gui,
            variable=self.restore_mouse_var,
            command=self.on_restore_mouse_toggled,
            panel_x=368,
            panel_y=158,
        )
        self.restore_mouse_button.place(x=378, y=398)

        logs_panel = tk.Label(self.gui, image=self._resized_image("logs_panel", 680, 160), bd=0, highlightthickness=0)
        logs_panel.place(x=10, y=456)

        self.status_text = tk.Text(
            self.gui,
            height=7,
            width=72,
            font=("Consolas", 10),
            bg="#24150d",
            fg=self._text_logs,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
            insertbackground=self._text_logs,
        )
        self.status_text.place(x=26, y=485, width=640, height=115)

        self.gui.update_idletasks()
        width = self.gui.winfo_width()
        height = self.gui.winfo_height()
        x = (self.gui.winfo_screenwidth() // 2) - (width // 2)
        y = (self.gui.winfo_screenheight() // 2) - (height // 2)
        self.gui.geometry(f"{width}x{height}+{x}+{y}")
        self._apply_dark_title_bar()
        self.gui.after(50, self._apply_dark_title_bar)
        self.gui.protocol("WM_DELETE_WINDOW", self.stop_gui)

        self.gui.after(100, self._process_ui_queue)
        self.gui.after(1000, self._monitor_browser_state)

        self.update_capture_settings_display()
        if self.app.config_manager.get_selected_map():
            self.log_to_gui(f"Saved map: {self.app.config_manager.get_selected_map()}")


    def _apply_window_icon(self):
        if not self.gui:
            return

        icon_candidates = [
            self._asset_dir / "green_dino.ico",
            self._asset_dir / "green_dinosaur.ico",
            self._asset_dir / "app_icon.ico",
            self._asset_dir / "green_dino.png",
            self._asset_dir / "green_dinosaur.png",
            self._asset_dir / "app_icon.png",
        ]

        for icon_path in icon_candidates:
            try:
                if not icon_path.exists():
                    continue
                suffix = icon_path.suffix.lower()
                if suffix == ".ico":
                    self.gui.iconbitmap(str(icon_path))
                else:
                    icon_image = ImageTk.PhotoImage(Image.open(icon_path).convert("RGBA"))
                    self._images["window_icon"] = icon_image
                    self.gui.iconphoto(True, icon_image)
                return
            except Exception:
                pass

        try:
            generated_icon = self._generate_green_dino_icon(32)
            icon_photo = ImageTk.PhotoImage(generated_icon)
            self._images["window_icon"] = icon_photo
            self.gui.iconphoto(True, icon_photo)
        except Exception:
            pass

    def _generate_green_dino_icon(self, size: int = 32):
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        green_main = "#4DCC63"
        green_dark = "#246D33"
        eye = "#E8F7B0"

        # Tail/body/head silhouette.
        draw.polygon([
            (3, 22), (9, 18), (13, 15), (18, 11), (23, 8), (27, 9),
            (29, 12), (27, 15), (25, 16), (23, 20), (20, 21), (16, 22),
            (14, 26), (11, 27), (10, 23), (7, 24)
        ], fill=green_main)

        # Belly/leg shapes.
        draw.polygon([(13, 22), (16, 21), (16, 28), (12, 28)], fill=green_dark)
        draw.polygon([(19, 21), (22, 20), (23, 28), (19, 28)], fill=green_dark)

        # Back spikes.
        draw.polygon([(11, 16), (13, 11), (15, 16)], fill=green_dark)
        draw.polygon([(15, 14), (17, 9), (19, 14)], fill=green_dark)
        draw.polygon([(19, 12), (21, 7), (23, 12)], fill=green_dark)

        # Eye and outline accents.
        draw.ellipse((23, 11, 25, 13), fill=eye)
        draw.line([(4, 22), (9, 18), (13, 15), (18, 11), (23, 8), (27, 9)], fill=green_dark, width=2)
        draw.line([(16, 22), (14, 26)], fill=green_dark, width=2)
        draw.line([(20, 21), (21, 28)], fill=green_dark, width=2)
        return image

    def _apply_dark_title_bar(self):
        if not self.gui:
            return
        try:
            self.gui.update_idletasks()
            import ctypes

            hwnd = self.gui.winfo_id()
            try:
                parent = ctypes.windll.user32.GetParent(hwnd)
                if parent:
                    hwnd = parent
            except Exception:
                pass

            value = ctypes.c_int(1)
            size = ctypes.sizeof(value)

            dwmapi = ctypes.windll.dwmapi

            # Windows builds vary between 19 and 20 for immersive dark mode.
            for attr in (20, 19):
                try:
                    dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), size)
                except Exception:
                    pass

            # Nudge a repaint so the caption updates.
            try:
                SWP_NOSIZE = 0x0001
                SWP_NOMOVE = 0x0002
                SWP_NOZORDER = 0x0004
                SWP_FRAMECHANGED = 0x0020
                ctypes.windll.user32.SetWindowPos(
                    hwnd, 0, 0, 0, 0, 0,
                    SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
                )
            except Exception:
                pass
        except Exception:
            pass

    def _load_assets(self):
        self._pil_assets = {}
        assets = {
            "background": "background.png",
            "header_panel": "header_panel.png",
            "dropdown_bg": "dropdown_bg.png",
            "quick_panel": "quick_panel.png",
            "logs_panel": "logs_panel.png",
            "button_green": "button_green.png",
            "button_bronze": "button_bronze.png",
            "checkbox_off": "checkbox_off.png",
            "checkbox_on": "checkbox_on.png",
        }
        for key, filename in assets.items():
            image = Image.open(self._asset_dir / filename).convert("RGBA")
            self._pil_assets[key] = image
            self._images[key] = ImageTk.PhotoImage(image)

    def _resized_image(self, asset_key: str, width: int, height: int):
        cache_key = f"{asset_key}_{width}x{height}"
        if cache_key not in self._images:
            image = self._pil_assets[asset_key].resize((width, height), Image.LANCZOS)
            self._images[cache_key] = ImageTk.PhotoImage(image)
        return self._images[cache_key]

    def _draw_static_text_layers(self):
        """Bake static heading text directly into the artwork so no label background shows."""
        # Header panel text
        header = self._pil_assets["header_panel"].copy()
        title_text = "ISLE MAP UPDATER"
        title_size = 54
        font_path = self._find_font_path(decorative=True, bold=True)
        try:
            title_font = ImageFont.truetype(font_path, size=title_size) if font_path else ImageFont.load_default()
        except Exception:
            title_font = ImageFont.load_default()
        title_draw = ImageDraw.Draw(header)
        title_bbox = title_draw.textbbox((0, 0), title_text, font=title_font, stroke_width=2)
        title_x = max(0, (header.width - (title_bbox[2] - title_bbox[0])) // 2 - title_bbox[0])
        self._draw_text_on_image(
            header,
            text=title_text,
            x=title_x,
            y=24,
            size=title_size,
            decorative=True,
            color="#E8D7B0",
            stroke_fill="#2A160C",
            shadow_fill="#6E4A24",
        )
        self._pil_assets["header_panel"] = header
        self._images["header_panel"] = ImageTk.PhotoImage(header)

        # Background static labels
        background = self._pil_assets["background"].copy()
        self._draw_text_on_image(
            background,
            text="Active Region",
            x=190,
            y=120,
            size=24,
            decorative=True,
            color="#E8D7B0",
            stroke_fill="#2A160C",
            shadow_fill="#6E4A24",
        )
        self._draw_text_on_image(
            background,
            text="Open map on startup",
            x=405,
            y=202,
            size=20,
            decorative=True,
            color="#E8D7B0",
            stroke_fill="#2A160C",
            shadow_fill="#6E4A24",
        )
        self._pil_assets["background"] = background
        self._images["background"] = ImageTk.PhotoImage(background)

        # Quick panel labels
        quick = self._pil_assets["quick_panel"].copy()
        static_quick_labels = [
            ("Quick Capture", 275, 22, 17, True),
            ("Hotkey", 105, 61, 14, True),
            ("Coord Click Point", 90, 104, 14, True),
            ("Last Coords", 32, 189, 14, True),
            ("Close overlay after click", 162, 140, 13, True),
            ("Restore mouse position", 405, 140, 13, True),
        ]
        for label_text, x, y, size, decorative in static_quick_labels:
            self._draw_text_on_image(
                quick,
                text=label_text,
                x=x,
                y=y,
                size=size,
                decorative=decorative,
                color="#f1dfbd",
                stroke_fill="#1f1209",
                shadow_fill="#3a2413",
            )
        self._pil_assets["quick_panel"] = quick
        self._images["quick_panel"] = ImageTk.PhotoImage(quick)

    def _draw_text_on_image(
        self,
        image,
        text: str,
        x: int,
        y: int,
        size: int,
        decorative: bool = False,
        color: str = "#E8D7B0",
        stroke_fill: str = "#2A160C",
        shadow_fill: str = "#6E4A24",
    ):
        draw = ImageDraw.Draw(image)
        font_path = self._find_font_path(decorative=decorative, bold=True)
        try:
            font = ImageFont.truetype(font_path, size=size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        draw.text((x + 2, y + 2), text, font=font, fill=shadow_fill)
        draw.text((x, y), text, font=font, fill=color, stroke_width=2, stroke_fill=stroke_fill)

    def _build_styles(self):
        style = ttk.Style(self.gui)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        cave_font = self._pick_font(16, bold=True, decorative=True)

        style.configure(
            "Themed.TCombobox",
            fieldbackground="#231a13",
            background="#231a13",
            foreground="#efe2c8",
            bordercolor="#231a13",
            lightcolor="#231a13",
            darkcolor="#231a13",
            arrowcolor="#d7c5a3",
            insertcolor="#efe2c8",
            relief="flat",
            padding=4,
            font=cave_font,
        )
        style.map(
            "Themed.TCombobox",
            fieldbackground=[("readonly", "#231a13")],
            foreground=[("readonly", "#efe2c8")],
            selectbackground=[("readonly", "#231a13")],
            selectforeground=[("readonly", "#efe2c8")],
        )

        try:
            self.gui.option_add("*TCombobox*Listbox.font", cave_font)
        except Exception:
            pass

    def _pick_font(self, size: int, bold: bool = False, decorative: bool = False):
        if decorative:
            family = "Cave Stone"
        else:
            family = "Georgia"
        return (family, size, "bold") if bold else (family, size)

    def _find_font_path(self, decorative: bool = False, bold: bool = True):
        candidates = []
        win_dir = os.environ.get("WINDIR", r"C:\Windows")
        windows_fonts = Path(win_dir) / "Fonts"

        if decorative:
            candidates.extend([
                self._asset_dir / "fonts" / "Cave Stone.otf",
                self._asset_dir / "fonts" / "CaveStone.otf",
                self._asset_dir / "fonts" / "Cave Stone.ttf",
                self._asset_dir / "fonts" / "CaveStone.ttf",
                Path.home() / "Downloads" / "Cave Stone.otf",
                Path.home() / "Downloads" / "CaveStone.otf",
                windows_fonts / "Cave Stone.otf",
                windows_fonts / "CaveStone.otf",
                windows_fonts / "Cave Stone.ttf",
                windows_fonts / "CaveStone.ttf",
                windows_fonts / "georgiab.ttf",
                windows_fonts / "timesbd.ttf",
                windows_fonts / "GARA.TTF",
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
                Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf"),
            ])
        else:
            candidates.extend([
                windows_fonts / "georgia.ttf",
                windows_fonts / "times.ttf",
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
                Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf"),
            ])

        for candidate in candidates:
            try:
                if Path(candidate).exists():
                    return str(candidate)
            except Exception:
                pass
        return None

    def _render_text_image(
        self,
        text: str,
        size: int,
        decorative: bool = False,
        color: str = "#E8D7B0",
        stroke_fill: str = "#2A160C",
        shadow_fill: str = "#6E4A24",
    ):
        key = (text, size, decorative, color, stroke_fill, shadow_fill)
        if key in self._text_image_cache:
            return self._text_image_cache[key]

        font_path = self._find_font_path(decorative=decorative, bold=True)
        try:
            font = ImageFont.truetype(font_path, size=size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        dummy = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        width = max(1, bbox[2] - bbox[0] + 8)
        height = max(1, bbox[3] - bbox[1] + 8)

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        x = 4 - bbox[0]
        y = 4 - bbox[1]
        draw.text((x + 2, y + 2), text, font=font, fill=shadow_fill)
        draw.text((x, y), text, font=font, fill=color, stroke_width=2, stroke_fill=stroke_fill)
        photo = ImageTk.PhotoImage(image)
        self._text_image_cache[key] = photo
        return photo

    def _make_text_label(
        self,
        parent,
        text: str,
        x: int,
        y: int,
        size: int,
        decorative: bool = False,
        color: str = "#E8D7B0",
        stroke_fill: str = "#2A160C",
        shadow_fill: str = "#6E4A24",
        bg: Optional[str] = None,
    ):
        image = self._render_text_image(text, size=size, decorative=decorative, color=color, stroke_fill=stroke_fill, shadow_fill=shadow_fill)
        label = tk.Label(
            parent,
            image=image,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
            padx=0,
            pady=0,
            bg=bg or self.gui.cget("bg"),
            activebackground=bg or self.gui.cget("bg"),
        )
        label.image = image
        label.place(x=x, y=y)
        return label

    def _label_text(self, value: str) -> str:
        return value

    def _make_image_button(self, parent, image_key: str, text: str, command, width: int = 170, font_size: int = 10, decorative: bool = False):
        if decorative:
            base_image = self._pil_assets[image_key].resize((width, 42), Image.LANCZOS)
            composed = self._compose_button_text_image(base_image, text, font_size=max(8, font_size - 1), decorative=True)
            photo = ImageTk.PhotoImage(composed)
            cache_key = f"_btn_{image_key}_{width}_{text}_{font_size}_{decorative}"
            self._images[cache_key] = photo
            button = tk.Button(
                parent,
                image=photo,
                text="",
                compound="center",
                command=command,
                bg="#0f0d0a",
                activebackground="#0f0d0a",
                bd=0,
                highlightthickness=0,
                relief=tk.FLAT,
                padx=0,
                pady=0,
                cursor="hand2",
                width=width,
                anchor="center",
            )
            button.image = photo
            button._decorative = True
            button._image_key = image_key
            button._image_width = width
            button._font_size = font_size
            return button

        button = tk.Button(
            parent,
            image=self._resized_image(image_key, width, 42),
            text=text,
            compound="center",
            command=command,
            font=self._pick_font(max(8, font_size - 1), bold=True, decorative=decorative),
            fg="#F3E7CE",
            activeforeground="#fff7e8",
            bg="#0f0d0a",
            activebackground="#0f0d0a",
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
            padx=0,
            pady=0,
            cursor="hand2",
            width=width,
            anchor="center",
            disabledforeground="#d8c7a3",
        )
        return button

    def _compose_button_text_image(self, base_image, text: str, font_size: int = 10, decorative: bool = False):
        img = base_image.copy().convert("RGBA")
        draw = ImageDraw.Draw(img)
        font_path = self._find_font_path(decorative=decorative, bold=True)
        try:
            font = ImageFont.truetype(font_path, size=font_size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=1)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (img.width - text_w) // 2 - bbox[0]
        y = (img.height - text_h) // 2 - bbox[1] - (1 if decorative else 0)
        draw.text((x + 1, y + 1), text, font=font, fill="#5a3419")
        draw.text((x, y), text, font=font, fill="#F3E7CE", stroke_width=1, stroke_fill="#2A160C")
        return img

    def _make_checkbox_button(self, parent, variable: tk.BooleanVar, command, panel_x: int = 0, panel_y: int = 0):
        off_photo = self._images["checkbox_off"]
        on_photo = self._images["checkbox_on"]
        button = tk.Button(
            parent,
            image=on_photo if variable.get() else off_photo,
            text="",
            compound="left",
            command=lambda: self._toggle_checkbox(variable, button, command),
            bg=self._surface_bg,
            activebackground=self._surface_bg,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT,
            cursor="hand2",
            anchor="w",
            padx=0,
            pady=0,
        )
        button._checkbox_on_image = on_photo
        button._checkbox_off_image = off_photo
        return button

    def _render_pil_text_image(self, text: str, size: int, decorative: bool = False, color: str = "#E8D7B0", stroke_fill: str = "#2A160C", shadow_fill: str = "#6E4A24"):
        font_path = self._find_font_path(decorative=decorative, bold=True)
        try:
            font = ImageFont.truetype(font_path, size=size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        dummy = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=1)
        width = max(1, bbox[2] - bbox[0] + 4)
        height = max(1, bbox[3] - bbox[1] + 4)
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        x = 2 - bbox[0]
        y = 2 - bbox[1]
        draw.text((x + 1, y + 1), text, font=font, fill=shadow_fill)
        draw.text((x, y), text, font=font, fill=color, stroke_width=1, stroke_fill=stroke_fill)
        return img

    def _toggle_checkbox(self, variable: tk.BooleanVar, button: tk.Button, command):
        variable.set(not variable.get())
        button.config(image=button._checkbox_on_image if variable.get() else button._checkbox_off_image)
        command()

    def _update_button_text(self, button: tk.Button, text: str):
        if not button:
            return

        if getattr(button, "_decorative", False):
            image_key = getattr(button, "_image_key", "button_green")
            width = getattr(button, "_image_width", 170)
            font_size = getattr(button, "_font_size", 10)
            base_image = self._pil_assets[image_key].resize((width, 42), Image.LANCZOS)
            composed = self._compose_button_text_image(
                base_image,
                text,
                font_size=max(8, font_size - 1),
                decorative=True,
            )
            photo = ImageTk.PhotoImage(composed)
            cache_key = f"_btn_runtime_{image_key}_{width}_{text}_{font_size}"
            self._images[cache_key] = photo
            button.config(image=photo, text="")
            button.image = photo
        else:
            button.config(text=text)

    def _set_setup_button_state(self, text: str, enabled: bool):
        if not self.setup_button:
            return
        self.setup_button.config(state=tk.NORMAL)
        self._update_button_text(self.setup_button, text)
        self.setup_button.config(state=(tk.NORMAL if enabled else tk.DISABLED))

    def _run_on_ui(self, func: Callable[[], None]) -> None:
        self._ui_queue.put(func)

    def _process_ui_queue(self):
        while True:
            try:
                func = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                func()
            except Exception as e:
                print(f"[GUI] UI task failed: {e}")

        if self.gui:
            self.gui.after(100, self._process_ui_queue)

    def _monitor_browser_state(self):
        try:
            if not self.gui:
                return

            browser_alive = self.app.browser_manager.is_browser_alive()
            has_saved_map = bool(self.app.config_manager.get_selected_map())

            if not self._setup_in_progress:
                if browser_alive:
                    self._set_setup_button_state("OPEN MAP", enabled=False)
                    self.refresh_button.config(state=tk.NORMAL)
                    self._browser_state_logged_dead = False
                else:
                    if self._browser_was_opened_this_session:
                        button_text = "REOPEN MAP"
                    else:
                        button_text = "OPEN MAP" if has_saved_map else "SETUP MAP"

                    self._set_setup_button_state(button_text, enabled=True)
                    self.refresh_button.config(state=tk.DISABLED)

                    if self._browser_was_opened_this_session and not self._browser_state_logged_dead:
                        self.log_to_gui("[INFO] Browser was closed. Click 'Reopen Map' to open it again.")
                        self._browser_state_logged_dead = True
        except Exception as e:
            print(f"[GUI] Browser state monitor failed: {e}")
        finally:
            if self.gui:
                self.gui.after(1000, self._monitor_browser_state)

    def update_capture_settings_display(self):
        def update():
            if self.hotkey_label:
                self._set_dynamic_text_label(self.hotkey_label, self.app.config_manager.get_capture_hotkey(), size=13, decorative=True)
            coord_pos = self.app.config_manager.get_coord_click_position()
            if self.coord_label:
                self._set_dynamic_text_label(self.coord_label, f"({coord_pos[0]}, {coord_pos[1]})" if coord_pos else "Not calibrated", size=12, decorative=True)
            if self.close_overlay_var is not None and self.close_overlay_button is not None:
                self.close_overlay_var.set(self.app.config_manager.get_close_overlay_after_capture())
                self.close_overlay_button.config(image=self.close_overlay_button._checkbox_on_image if self.close_overlay_var.get() else self.close_overlay_button._checkbox_off_image)
            if self.restore_mouse_var is not None and self.restore_mouse_button is not None:
                self.restore_mouse_var.set(self.app.config_manager.get_restore_mouse_after_capture())
                self.restore_mouse_button.config(image=self.restore_mouse_button._checkbox_on_image if self.restore_mouse_var.get() else self.restore_mouse_button._checkbox_off_image)
            if self.open_map_startup_var is not None and self.open_map_startup_button is not None:
                self.open_map_startup_var.set(self.app.config_manager.get_open_map_on_startup())
                self.open_map_startup_button.config(image=self.open_map_startup_button._checkbox_on_image if self.open_map_startup_var.get() else self.open_map_startup_button._checkbox_off_image)

        self._run_on_ui(update)

    def _set_dynamic_text_label(self, label: tk.Label, text: str, size: int = 12, decorative: bool = False):
        img = self._render_text_image(text, size=size, decorative=decorative, color=self._text_main, stroke_fill="#2A160C", shadow_fill="#5a3419")
        label.configure(image=img, text="")
        label.image = img

    def update_last_coords_label(self, coords_text: str):
        def update():
            if self.last_coords_label:
                self.last_coords_label.config(text=coords_text)

        self._run_on_ui(update)

    def setup_browser_gui(self):
        self._setup_in_progress = True
        self.setup_button.config(state=tk.DISABLED)
        self._update_button_text(self.setup_button, "CONNECTING...")
        self.log_to_gui("Setting up browser...")

        def setup_thread():
            try:
                self.log_to_gui("Opening Chrome browser...")
                self.log_to_gui(f"Loading: {self.app.browser_manager.vulnona_url}")
                success = self.app.browser_manager.setup_browser()
                if success:
                    maps = self.app.browser_manager.get_available_maps()
                    self._run_on_ui(lambda: self._finish_setup_success(maps))
                else:
                    error_text = self.app.browser_manager.get_last_error() or "Browser setup failed"
                    self._run_on_ui(lambda: self._finish_setup_failure(error_text))
            except Exception as e:
                self._run_on_ui(lambda: self._finish_setup_failure(str(e)))

        threading.Thread(target=setup_thread, daemon=True).start()

    def _finish_setup_success(self, maps):
        self._setup_in_progress = False
        self._browser_state_logged_dead = False
        self._browser_was_opened_this_session = True
        self.log_to_gui("[OK] Browser opened successfully!")
        self.log_to_gui("[SCAN] Scanning available maps...")
        if maps:
            self.update_map_dropdown()
            self.log_to_gui(f"[OK] Found {len(maps)} available maps!")
            self.save_map_button.config(state=tk.NORMAL)
            self.refresh_button.config(state=tk.NORMAL)
            self._set_setup_button_state("OPEN MAP", enabled=False)
            if self.app.config_manager.get_selected_map():
                self.log_to_gui(f"[RESTORE] Restoring saved map: {self.app.config_manager.get_selected_map()}")
                self.apply_saved_map()
        else:
            self.log_to_gui("[WARN] No maps found!")
            self.refresh_button.config(state=tk.NORMAL)
            self._set_setup_button_state("REOPEN MAP", enabled=True)

    def _finish_setup_failure(self, error_text: str):
        self._setup_in_progress = False
        self.log_to_gui(f"[ERROR] Browser setup failed: {error_text}")
        self._set_setup_button_state("REOPEN MAP", enabled=True)

    def refresh_maps_gui(self):
        self.refresh_button.config(state=tk.DISABLED)
        self._update_button_text(self.refresh_button, "REFRESHING...")
        self.log_to_gui("Refreshing available maps...")

        def refresh_thread():
            maps = self.app.browser_manager.get_available_maps()
            self._run_on_ui(lambda: self._finish_refresh(maps))

        threading.Thread(target=refresh_thread, daemon=True).start()

    def _finish_refresh(self, maps):
        self.update_map_dropdown()
        self.log_to_gui(f"Maps refreshed! ({len(maps)} found)")
        self.refresh_button.config(state=tk.NORMAL)
        self._update_button_text(self.refresh_button, "REFRESH MAPS")

    def update_map_dropdown(self):
        available_maps = self.app.browser_manager.available_maps
        if not available_maps:
            self.map_dropdown["values"] = ["No maps available"]
            self.map_dropdown.set("No maps available")
            self.filtered_maps = []
            return

        self.filtered_maps = list(available_maps)
        map_labels = [map_info["label"] for map_info in self.filtered_maps]
        self.map_dropdown["values"] = map_labels

        selected_map = self.app.config_manager.get_selected_map()
        current_selection = None
        if selected_map:
            for i, map_info in enumerate(self.filtered_maps):
                if map_info["value"] == selected_map:
                    current_selection = map_labels[i]
                    break

        self.map_dropdown.set(current_selection or "Select a map...")

    def on_map_selected(self, event=None):
        selected_label = self.map_var.get()
        ignored = {
            "",
            "No maps available",
            "Load browser first to see available maps...",
            f"Saved default: {self.app.config_manager.get_selected_map()}",
        }
        if selected_label in ignored:
            return
        if self._map_switch_in_progress:
            return

        selected_map_value = None
        for map_info in self.filtered_maps:
            if map_info["label"] == selected_label:
                selected_map_value = map_info["value"]
                break

        if not selected_map_value:
            self.log_to_gui(f"[ERROR] Could not resolve map: {selected_label}")
            return

        self._map_switch_in_progress = True
        self.map_dropdown.configure(state="disabled")
        self.log_to_gui(f"[MAP] Switching to: {selected_label}")

        def select_thread():
            success = self.app.browser_manager.select_map(selected_map_value)
            self._run_on_ui(lambda: self._finish_map_switch(success, selected_map_value, selected_label))

        threading.Thread(target=select_thread, daemon=True).start()

    def _finish_map_switch(self, success: bool, selected_map_value: str, selected_label: str):
        self._map_switch_in_progress = False
        self.map_dropdown.configure(state="readonly")
        if success:
            self.app.config_manager.set_selected_map(selected_map_value, selected_label)
            self.log_to_gui(f"[OK] Map active: {selected_label}")
            self.save_map_button.config(state=tk.NORMAL)
            if not self.app.running:
                self.app.start_monitoring()
        else:
            error_text = self.app.browser_manager.get_last_error() or selected_label
            self.log_to_gui(f"[ERROR] Failed to switch to: {error_text}")

    def capture_now_gui(self):
        success, message = self.app.trigger_coordinate_capture(source="Capture Now button")
        if not success:
            self.log_to_gui(f"[CAPTURE] {message}")
        else:
            self.log_to_gui("[CAPTURE] Manual capture started")

    def calibrate_click_point_gui(self):
        success, message = self.app.calibrate_coordinate_click(countdown_seconds=5)
        if not success:
            self.log_to_gui(f"[CALIBRATE] {message}")
        else:
            self.log_to_gui("[CALIBRATE] Calibration started")

    def on_close_overlay_toggled(self):
        self.app.config_manager.set_close_overlay_after_capture(self.close_overlay_var.get())
        self.log_to_gui(f"[CAPTURE] Close overlay after click: {'On' if self.close_overlay_var.get() else 'Off'}")

    def on_restore_mouse_toggled(self):
        self.app.config_manager.set_restore_mouse_after_capture(self.restore_mouse_var.get())
        self.log_to_gui(f"[CAPTURE] Restore mouse position: {'On' if self.restore_mouse_var.get() else 'Off'}")

    def on_open_map_startup_toggled(self):
        self.app.config_manager.set_open_map_on_startup(self.open_map_startup_var.get())
        self.log_to_gui(f"[STARTUP] Open map on startup: {'On' if self.open_map_startup_var.get() else 'Off'}")

    def open_hotkey_dialog(self):
        if self._hotkey_dialog and self._hotkey_dialog.winfo_exists():
            self._hotkey_dialog.lift()
            self._hotkey_dialog.focus_force()
            return

        dialog = tk.Toplevel(self.gui)
        dialog.title("Set Capture Hotkey")
        dialog.geometry("430x170")
        dialog.resizable(False, False)
        dialog.transient(self.gui)
        dialog.grab_set()
        dialog.configure(bg="#16120e")
        self._hotkey_dialog = dialog

        tk.Label(dialog, text="Press the hotkey combination you want to use.", font=self._pick_font(11, bold=True, decorative=True), fg=self._text_main, bg="#16120e").pack(pady=(15, 8))
        tk.Label(dialog, text="Supported keys: A-Z, 0-9, F1-F12, arrows, Tab, Enter, Esc, Home/End, PgUp/PgDn", wraplength=380, font=self._pick_font(11, decorative=True), fg=self._text_muted, bg="#16120e").pack(pady=2)
        tk.Label(dialog, text="Example: Ctrl+Alt+F8 or Shift+F6", font=self._pick_font(11, decorative=True), fg="#b7aa92", bg="#16120e").pack(pady=2)
        preview_var = tk.StringVar(value="Waiting for key press...")
        tk.Label(dialog, textvariable=preview_var, font=("Consolas", 12), fg="#efe2c8", bg="#16120e").pack(pady=12)
        tk.Button(dialog, text="Cancel", command=lambda: self._close_hotkey_dialog(None), bg="#2a2119", fg=self._text_main, relief=tk.FLAT).pack(pady=6)

        def on_key_press(event):
            keysym = (event.keysym or "").upper()
            if keysym in {"CONTROL_L", "CONTROL_R", "SHIFT_L", "SHIFT_R", "ALT_L", "ALT_R", "WIN_L", "WIN_R", "SUPER_L", "SUPER_R"}:
                return "break"

            key_name = normalize_key_name(keysym)
            if not key_name:
                preview_var.set(f"Unsupported key: {event.keysym}")
                return "break"

            modifiers = current_modifier_names()
            parts = list(modifiers) + [key_name]
            hotkey_text = "+".join(parts)
            preview_var.set(hotkey_text)
            self._apply_hotkey_selection(hotkey_text)
            return "break"

        dialog.bind("<KeyPress>", on_key_press)
        dialog.bind("<Escape>", lambda event: self._close_hotkey_dialog(None))
        dialog.focus_force()

    def _apply_hotkey_selection(self, hotkey_text: str):
        success, message = self.app.update_capture_hotkey(hotkey_text)

        if success:
            self.log_to_gui(f"[HOTKEY] Capture hotkey set to: {message}")
            self.update_capture_settings_display()
            self._close_hotkey_dialog(None)
        else:
            self.log_to_gui(f"[HOTKEY] Failed to set hotkey: {message}")

            # Keep the dialog open so the user can press another key
            # instead of having to click Set Hotkey again.
            if self._hotkey_dialog and self._hotkey_dialog.winfo_exists():
                self._hotkey_dialog.focus_force()

    def _close_hotkey_dialog(self, _event):
        if self._hotkey_dialog and self._hotkey_dialog.winfo_exists():
            self._hotkey_dialog.destroy()
        self._hotkey_dialog = None

    def save_current_map(self):
        selected_map = self.app.config_manager.get_selected_map()
        if selected_map:
            self.app.config_manager.save_config()
            self.log_to_gui(f"Saved '{selected_map}' as default map!")
        else:
            self.log_to_gui("No map selected to save!")

    def apply_saved_map(self):
        selected_map = self.app.config_manager.get_selected_map()
        if not selected_map or not self.filtered_maps:
            return

        for i, map_info in enumerate(self.filtered_maps):
            if map_info["value"] == selected_map:
                self.map_dropdown.current(i)
                self.map_dropdown.event_generate("<<ComboboxSelected>>")
                return

        self.log_to_gui(f"Saved map not found in current list: {selected_map}")

    def log_to_gui(self, message: str):
        if not self.status_text:
            print(message)
            return

        def append_message():
            if self.status_text:
                self.status_text.insert(tk.END, message + "\n")
                self.status_text.see(tk.END)

        self._run_on_ui(append_message)

    def schedule_open_map_on_startup(self):
        if not self.gui:
            return
        if not self.app.config_manager.get_open_map_on_startup():
            return
        if not self.app.config_manager.get_selected_map():
            self.log_to_gui("[STARTUP] Auto-open skipped: no saved default map.")
            return

        self.log_to_gui("[STARTUP] Auto-opening saved map...")
        self.gui.after(400, self.setup_browser_gui)

    def stop_gui(self):
        self.app.running = False
        if self.gui:
            self.gui.destroy()
            self.gui = None
        self.app.stop()

    def start_mainloop(self):
        if self.gui:
            try:
                self.gui.mainloop()
            except Exception as e:
                print(f"GUI error: {e}")
            finally:
                self.app.stop()

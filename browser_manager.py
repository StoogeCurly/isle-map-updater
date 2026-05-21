"""
Browser management for Isle Map Updater.
Stable browser handling for vulnona.com while keeping the newer helper methods.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, UnexpectedAlertPresentException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class BrowserManager:
    def __init__(self, chrome_profile_dir: Optional[str] = None):
        self.driver = None
        self.vulnona_url = "https://vulnona.com/game/map/"
        self.available_maps: List[Dict[str, str]] = []
        self.last_error: str = ""
        self.wait_timeout = 20
        self.active_map_value: Optional[str] = None
        self.browser_open_flag: bool = False

        # ------------------------------------------------------------
        # AppData save location
        # C:\Users\YourName\AppData\Local\Isle Map Updater\
        # ------------------------------------------------------------
        appdata_base = os.getenv("LOCALAPPDATA")

        if appdata_base:
            self.appdata_dir = os.path.join(appdata_base, "Isle Map Updater")
        else:
            self.appdata_dir = os.path.join(
                os.path.expanduser("~"),
                "AppData",
                "Local",
                "Isle Map Updater",
            )

        os.makedirs(self.appdata_dir, exist_ok=True)

        self.chrome_profile_dir = chrome_profile_dir or os.path.join(self.appdata_dir, "chrome_profile")
        os.makedirs(self.chrome_profile_dir, exist_ok=True)

        self.wdm_cache_dir = os.path.join(self.appdata_dir, ".wdm")
        os.makedirs(self.wdm_cache_dir, exist_ok=True)

    def _set_error(self, message: str) -> None:
        self.last_error = message
        print(message)

    def get_last_error(self) -> str:
        return self.last_error

    def is_browser_alive(self) -> bool:
        if not self.driver or not self.browser_open_flag:
            return False

        # Check real browser windows, not just the ChromeDriver process.
        # If the user manually closes Chrome, Selenium will usually have no
        # window handles left or will raise an exception here.
        try:
            handles = self.driver.window_handles
            if not handles:
                self.browser_open_flag = False
                return False
            return True
        except Exception:
            self.browser_open_flag = False
            return False

    def _wait(self, timeout: Optional[int] = None) -> WebDriverWait:
        return WebDriverWait(self.driver, timeout or self.wait_timeout)

    def _wait_for_document_ready(self) -> None:
        self._wait().until(lambda d: d.execute_script("return document.readyState") == "complete")

    def _wait_for_map_controls(self) -> None:
        def condition(driver):
            map_list = driver.find_elements(By.CSS_SELECTOR, "input[type='radio'][name='map_list']")
            map_old = driver.find_elements(By.CSS_SELECTOR, "input[type='radio'][name='map']")
            return bool(map_list or map_old)

        self._wait(20).until(condition)

    def _get_persistent_base_dir(self) -> str:
        """
        Returns the AppData save folder.
        """
        os.makedirs(self.appdata_dir, exist_ok=True)
        return self.appdata_dir

    def _build_options(self) -> Options:
        chrome_options = Options()
        chrome_options.add_argument("--new-window")
        chrome_options.add_argument("--start-maximized")

        os.makedirs(self.chrome_profile_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={self.chrome_profile_dir}")

        return chrome_options

    def _create_driver(self):
        chrome_options = self._build_options()
        launch_errors = []

        # 1) Selenium Manager (built into modern Selenium). This avoids .wdm entirely.
        try:
            print("[INFO] Trying Selenium Manager startup")
            return webdriver.Chrome(options=chrome_options)
        except Exception as e:
            launch_errors.append(f"Selenium Manager failed: {e}")

        # 2) Bundled local chromedriver.exe from AppData.
        # If you ever want to manually place chromedriver.exe, put it here:
        # C:\Users\YourName\AppData\Local\Isle Map Updater\chromedriver.exe
        chromedriver_path = os.path.join(self._get_persistent_base_dir(), "chromedriver.exe")
        if os.path.exists(chromedriver_path):
            try:
                print(f"[INFO] Using bundled ChromeDriver: {chromedriver_path}")
                service = Service(chromedriver_path)
                return webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                launch_errors.append(f"Bundled ChromeDriver failed: {e}")

        # 3) webdriver-manager fallback.
        try:
            print("[INFO] Using webdriver-manager fallback with AppData cache")
            local_wdm = self.wdm_cache_dir
            os.makedirs(local_wdm, exist_ok=True)

            os.environ["WDM_LOCAL"] = "1"
            os.environ["WDM_CACHE_DIR"] = local_wdm

            try:
                # Older webdriver-manager versions support path=.
                service = Service(ChromeDriverManager(path=local_wdm).install())
            except TypeError:
                # Newer webdriver-manager versions removed path=.
                service = Service(ChromeDriverManager().install())

            return webdriver.Chrome(service=service, options=chrome_options)

        except Exception as e:
            launch_errors.append(f"webdriver-manager failed: {e}")

        raise RuntimeError(" | ".join(launch_errors) if launch_errors else "Unable to start Chrome")

    def setup_browser(self) -> bool:
        """Initialize Chrome browser with vulnona map."""
        self.last_error = ""
        try:
            if self.is_browser_alive():
                self.stop()

            print("[BROWSER] Starting Chrome...")
            self.driver = self._create_driver()
            self.browser_open_flag = True

            print(f"[BROWSER] Navigating to: {self.vulnona_url}")
            self.driver.get(self.vulnona_url)

            self._wait_for_document_ready()
            self._wait_for_map_controls()
            self._close_info_popup_if_present()

            print("[OK] Vulnona map ready for coordinates!")
            return True
        except Exception as e:
            self._set_error(f"[ERROR] Failed to setup browser: {e}")
            self.stop()
            return False

    def _close_info_popup_if_present(self) -> None:
        if not self.is_browser_alive():
            return
        try:
            close_button = self.driver.find_element(By.ID, "readme_close")
            self.driver.execute_script("arguments[0].click();", close_button)
            print("[OK] Info popup closed")
            time.sleep(0.5)
        except Exception:
            print("[INFO] No info popup to close")

    def _find_map_radios(self):
        radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio'][name='map_list']")
        if radios:
            return radios

        radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio'][name='map']")
        if radios:
            return radios
        return []

    def get_available_maps(self) -> List[Dict[str, str]]:
        """Get available maps from vulnona.com."""
        if not self.is_browser_alive():
            self._set_error("[ERROR] Browser not initialized")
            return []

        try:
            self._wait_for_document_ready()
            radios = self._find_map_radios()
            print(f"[MAP] Processing {len(radios)} radio buttons...")

            maps: List[Dict[str, str]] = []
            seen_values = set()

            for radio in radios:
                try:
                    map_value = (radio.get_attribute("value") or "").strip()
                    map_id = (radio.get_attribute("id") or "").strip()
                    if not map_value:
                        continue
                    if map_value in seen_values:
                        continue

                    label_text = map_value
                    game_type = "Unknown"
                    status = "Unknown"
                    status_text = ""

                    if map_id:
                        try:
                            label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{map_id}']")
                            full_label_text = (label.text or "").strip()
                            label_lines = [line.strip() for line in full_label_text.splitlines() if line.strip()]
                            if label_lines:
                                label_text = label_lines[0]

                            try:
                                game_icon = label.find_element(By.CSS_SELECTOR, "img.game_icon")
                                game_icon_src = game_icon.get_attribute("src") or ""
                                if "TI_icon.png" in game_icon_src:
                                    game_type = "The Isle"
                                elif "PoT_icon.png" in game_icon_src:
                                    game_type = "Path of Titans"
                            except Exception:
                                pass

                            try:
                                middle_div = label.find_element(By.CSS_SELECTOR, "div.middle")
                                status_text = (middle_div.text or "").strip()
                                if status_text.startswith("✅"):
                                    status = "Active"
                                elif status_text.startswith("❌"):
                                    status = "Outdated"
                                elif status_text.startswith("⚠️"):
                                    status = "Legacy"
                            except Exception:
                                pass
                        except NoSuchElementException:
                            pass

                    upper_name = label_text.upper()
                    upper_value = map_value.upper()

                    if game_type == "Path of Titans":
                        continue
                    if any(bad in upper_name or bad in upper_value for bad in ["OUTDATED", "SCRAPPED", "UNALIVED"]):
                        continue

                    seen_values.add(map_value)
                    maps.append(
                        {
                            "value": map_value,
                            "label": label_text,
                            "raw_name": label_text,
                            "game_type": game_type,
                            "status": status,
                            "status_text": status_text,
                        }
                    )
                except Exception as e:
                    print(f"[WARNING] Error processing map radio: {e}")

            self.available_maps = maps
            print(f"[MAP] Total maps found: {len(maps)}")
            return maps
        except Exception as e:
            self._set_error(f"[ERROR] Failed to get available maps: {e}")
            return []

    def _find_map_radio(self, map_value: str):
        selectors = [
            f"input[type='radio'][name='map_list'][value='{map_value}']",
            f"input[type='radio'][name='map'][value='{map_value}']",
            f"input[type='radio'][value='{map_value}']",
        ]
        for selector in selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                return elements[0]
        return None

    def select_map(self, map_value: str) -> bool:
        """Select a specific map on vulnona.com using the old stable click behavior."""
        if not self.is_browser_alive():
            self._set_error("[ERROR] Browser not initialized")
            return False

        try:
            print(f"[MAP] Selecting map: {map_value}")
            radio = self._find_map_radio(map_value)
            if radio is None:
                self._set_error(f"[ERROR] Could not find radio button for map: {map_value}")
                return False

            if not radio.is_selected():
                map_id = radio.get_attribute("id")
                clicked = False

                if map_id:
                    labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{map_id}']")
                    if labels:
                        self.driver.execute_script("arguments[0].click();", labels[0])
                        clicked = True

                if not clicked:
                    self.driver.execute_script("arguments[0].checked = true;", radio)
                    self.driver.execute_script("arguments[0].click();", radio)

                time.sleep(3)

            self.active_map_value = map_value
            print(f"[OK] Successfully selected map: {map_value}")
            return True
        except Exception as e:
            self._set_error(f"[ERROR] Failed to select map {map_value}: {e}")
            return False

    def _find_coordinate_input(self):
        selectors = [
            (By.ID, "current_pos"),
            (By.CSS_SELECTOR, "input#current_pos"),
            (By.CSS_SELECTOR, "input[name='current_pos']"),
        ]
        for by, selector in selectors:
            elements = self.driver.find_elements(by, selector)
            if elements:
                return elements[0]
        raise NoSuchElementException("Coordinate input not found")

    def _find_submit_button(self):
        selectors = [
            (By.CSS_SELECTOR, "input[type='submit'][value='Show']"),
            (By.XPATH, "//input[@type='submit' and @value='Show']"),
            (By.XPATH, "//button[normalize-space()='Show']"),
            (By.XPATH, "//input[@type='submit']"),
        ]
        for by, selector in selectors:
            elements = self.driver.find_elements(by, selector)
            if elements:
                return elements[0]
        raise NoSuchElementException("Show button not found")

    def update_map_position(self, raw_coordinates: str) -> bool:
        """Update position on vulnona map with raw Isle coordinates."""
        if not self.is_browser_alive():
            self._set_error("[ERROR] Browser is not running")
            return False

        try:
            coordinate_input = self._wait().until(lambda d: self._find_coordinate_input())
            coordinate_input.click()
            coordinate_input.send_keys(Keys.CONTROL, "a")
            coordinate_input.send_keys(Keys.BACKSPACE)
            coordinate_input.send_keys(raw_coordinates)

            current_value = coordinate_input.get_attribute("value") or ""
            if current_value.strip() != raw_coordinates.strip():
                self.driver.execute_script(
                    "arguments[0].value = arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                    "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                    coordinate_input,
                    raw_coordinates,
                )

            submit_button = self._find_submit_button()
            self.driver.execute_script("arguments[0].click();", submit_button)
            print(f"[MAP] Updated position: {raw_coordinates}")
            return True
        except Exception as e:
            self._set_error(f"[ERROR] Failed to update map: {e}")
            return False

    def stop(self) -> None:
        """Stop the browser."""
        if self.driver:
            try:
                print("[BROWSER] Closing browser...")
                self.driver.quit()
                print("[OK] Browser closed successfully")
            except Exception as e:
                print(f"[WARNING] Error closing browser: {e}")
            finally:
                self.driver = None
                self.active_map_value = None
                self.browser_open_flag = False
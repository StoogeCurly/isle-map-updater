"""
Coordinate parsing for Isle Map Updater.
Handles extraction and validation of coordinates from clipboard.
"""

from __future__ import annotations

import re
from typing import Optional


class CoordinateParser:
    def __init__(self):
        self.test_coordinates = [
            "88,879.526, -288,696.11, 21,112.882",
            "89,123.456, -289,123.45, 22,456.789",
            "87,654.321, -287,987.65, 20,789.123",
            "90,111.222, -290,333.44, 23,555.666",
            "86,999.888, -286,777.99, 19,444.333",
        ]
        self.test_index = 0
        self._skip_keywords = [
            "[DEBUG]",
            "[MAP]",
            "[OK]",
            "[ERROR]",
            "[WARNING]",
            "[INFO]",
            "DevTools listening",
            "USB:",
            "Created TensorFlow",
        ]
        self._number_pattern = self._create_number_pattern()
        self._legacy_pattern = re.compile(
            rf"(?:Lat|LAT):\s*({self._number_pattern})\s+"
            rf"(?:Long|LONG):\s*({self._number_pattern})\s+"
            rf"(?:Alt|ALT):\s*({self._number_pattern})",
            re.IGNORECASE,
        )
        self._evrima_pattern = re.compile(
            rf"(?:^|[^.\d])({self._number_pattern})\s*,\s*"
            rf"({self._number_pattern})\s*,\s*"
            rf"({self._number_pattern})(?:[^.\d]|$)"
        )
        self._evrima_fallback_pattern = re.compile(
            rf"({self._number_pattern})\s*,\s*"
            rf"({self._number_pattern})\s*,\s*"
            rf"({self._number_pattern})"
        )

    def parse_coordinates(self, text: Optional[str]) -> Optional[str]:
        """Extract raw Isle coordinates from clipboard text."""
        if not text:
            return None

        text = str(text).strip()
        if not text:
            return None

        if any(keyword in text for keyword in self._skip_keywords):
            return None

        if len(text) > 200:
            return None

        print(f"[DEBUG] Parsing clipboard text: '{text[:50]}...'")

        legacy_coords = self._parse_legacy_format(text)
        if legacy_coords:
            return legacy_coords

        evrima_coords = self._parse_evrima_format(text)
        if evrima_coords:
            return evrima_coords

        return None

    def _create_number_pattern(self) -> str:
        minus_signs = r"[-−]"
        thousands_seps = r"[,\.\s']"
        decimal_seps = r"[,.]"
        return (
            r"" + minus_signs + r"?"
            r"(?:"
            r"\d{1,3}(?:" + thousands_seps + r"\d{1,3})*"
            r"(?:" + decimal_seps + r"\d{1,6})?"
            r"|"
            r"\d{1,9}(?:" + decimal_seps + r"\d{1,6})?"
            r")"
        )

    def _parse_legacy_format(self, text: str) -> Optional[str]:
        match = self._legacy_pattern.search(text)
        if not match:
            return None

        lat, lon, alt = match.groups()
        if self._looks_zero(lat) and self._looks_zero(lon) and self._looks_zero(alt):
            print("[DEBUG] Skipping Legacy zero coordinates")
            return None

        normalized_coords = self._normalize_coordinates(lat, lon, alt)
        print(f"[DEBUG] Legacy coordinates found: {normalized_coords}")
        return normalized_coords

    def _parse_evrima_format(self, text: str) -> Optional[str]:
        match = self._evrima_pattern.search(text) or self._evrima_fallback_pattern.search(text)
        if not match:
            return None

        x, y, z = match.groups()
        stripped = text.strip()
        if (("0.0, 0.0" in stripped and len(stripped) < 20) or stripped == "0,0"):
            print("[DEBUG] Skipping 0,0 coordinates")
            return None

        normalized_coords = self._normalize_coordinates(x, y, z)
        print(f"[DEBUG] Evrima coordinates found: {normalized_coords}")
        return normalized_coords

    def _looks_zero(self, value: str) -> bool:
        cleaned = value.replace(" ", "").replace(",", "").replace(".", "").replace("'", "")
        cleaned = cleaned.replace("−", "").replace("-", "")
        return bool(cleaned) and set(cleaned) == {"0"}

    def _normalize_coordinates(self, x: str, y: str, z: str) -> str:
        return f"{self._normalize_number(x)}, {self._normalize_number(y)}, {self._normalize_number(z)}"

    def _normalize_number(self, num_str: str) -> str:
        clean_str = num_str.strip().replace("−", "-")
        is_negative = clean_str.startswith("-")
        if is_negative:
            clean_str = clean_str[1:]

        # Normalize thousands separators that are never decimal separators here.
        clean_str = clean_str.replace(" ", "").replace("'", "")

        decimal_sep = self._detect_decimal_separator(clean_str)
        if decimal_sep:
            integer_part, decimal_part = clean_str.rsplit(decimal_sep, 1)
            integer_digits = re.sub(r"[^\d]", "", integer_part)
            decimal_digits = re.sub(r"[^\d]", "", decimal_part)
            normalized = self._group_thousands(integer_digits)
            if decimal_digits:
                normalized = f"{normalized}.{decimal_digits}"
        else:
            digits_only = re.sub(r"[^\d]", "", clean_str)
            normalized = self._group_thousands(digits_only)

        if is_negative and normalized:
            normalized = f"-{normalized}"
        return normalized

    def _detect_decimal_separator(self, clean_str: str) -> Optional[str]:
        dot_count = clean_str.count(".")
        comma_count = clean_str.count(",")

        if dot_count and comma_count:
            return "." if clean_str.rfind(".") > clean_str.rfind(",") else ","

        if dot_count:
            tail = clean_str.rsplit(".", 1)[1]
            if 1 <= len(tail) <= 6 and tail.isdigit():
                return "."
            return None

        if comma_count:
            tail = clean_str.rsplit(",", 1)[1]
            if 1 <= len(tail) <= 6 and tail.isdigit() and comma_count == 1:
                return ","
            if 1 <= len(tail) <= 3 and tail.isdigit() and comma_count > 1:
                # Values like 88,879.526 use comma for thousands elsewhere; if comma is the
                # only separator and repeated, treat them as thousands separators.
                return None
            return None

        return None

    def _group_thousands(self, digits: str) -> str:
        digits = digits.lstrip("0") or "0"
        parts = []
        while len(digits) > 3:
            parts.append(digits[-3:])
            digits = digits[:-3]
        parts.append(digits)
        return ",".join(reversed(parts))

    def get_test_coordinates(self) -> str:
        """Get next test coordinates for demo purposes."""
        coords = self.test_coordinates[self.test_index]
        self.test_index = (self.test_index + 1) % len(self.test_coordinates)
        return coords

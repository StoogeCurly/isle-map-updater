# 🗺️ Isle Map Updater

A simple Windows tool for **The Isle** that captures your in-game coordinates and updates the [Vulnona map](https://vulnona.com/game/map/) in real time.

Reimagined and maintained by **StoogeCurly**.  
Inspired by **GitHub Muslix / the-isle-map-updater**.

![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)
![Map](https://img.shields.io/badge/map-Vulnona-green.svg)

---

## 🚀 Features

- 📋 **Clipboard Monitoring** - Detects copied Isle coordinates
- 🌐 **Vulnona Map Updates** - Sends coordinates to the Vulnona map automatically
- ⌨️ **Custom Hotkey** - Set your own capture hotkey
- 🎯 **Click Point Calibration** - Save where your in-game coords appear
- 💾 **Saved Settings** - Saves your map, hotkey, and calibration point
- 🖥️ **Simple GUI** - Easy-to-use desktop interface

---

## 📋 Requirements

### Packed EXE Version

- Windows PC
- Google Chrome
- Internet connection

Python is **not required** for the EXE.

### Source Version

- Windows PC
- Python 3.10+
- Google Chrome
- Internet connection

---

## 🛠️ Install / Run

### Option 1: Packed EXE

Download or copy:

```text
Isle Map Updater.exe
```

Double-click it to launch.

### Option 2: Source Files

Install requirements:

```bat
pip install -r requirements.txt
```

Run:

```bat
python isle_map_updater.py
```

---

## ⚠️ Windows SmartScreen / Antivirus

Windows may warn you because the EXE is not code-signed and is packed with PyInstaller.

This app opens Chrome, uses a hotkey, and watches the clipboard for copied coordinates, so some antivirus tools may flag it.

Recommended:

1. Right-click the EXE
2. Click **Scan with Microsoft Defender**
3. Optionally check it with VirusTotal
4. If SmartScreen appears, click **More info → Run anyway**

---

## 🎮 How to Use

### Step 1: Open the App

Start the EXE or run the Python script.

### Step 2: Open the Map

Click:

```text
Setup Map / Open Map
```

The app opens:

```text
https://vulnona.com/game/map/
```

### Step 3: Select Your Map

Pick your map from the dropdown, then click:

```text
Save as Default
```

### Step 4: Calibrate Click Point

Click:

```text
Calibrate Click Point
```

Then click your in-game coordinate text.

Calibration only saves when valid coordinates are copied. It cancels after 70 seconds if nothing valid is detected.

### Step 5: Set Hotkey

Click:

```text
Set Hotkey
```

Examples:

```text
`
F8
CTRL+ALT+F8
SHIFT+F6
```

### Step 6: Capture Coordinates

Press your hotkey in game.

The app clicks your saved coordinate spot, copies the coordinates, and updates the Vulnona map.

---

## 📊 Supported Coordinate Format

Example:

```text
88,879.526, -288,696.11, 21,112.882
```

The app supports common Legacy/Evrima coordinate variations and validates coordinates before sending them to Vulnona.

---

## 💾 Saved Data

Settings are saved here:

```text
C:\Users\YourName\AppData\Local\Isle Map Updater\
```

This may include:

```text
map_config.json
chrome_profile
.wdm
```

These are normal. They save your settings and browser profile between launches.

---

## 🗂️ Project Files

```text
isle-map-updater/
├── README.md
├── isle_map_updater.py
├── browser_manager.py
├── config_manager.py
├── coordinate_parser.py
├── gui_manager.py
├── hotkey_capture.py
├── requirements.txt
├── assets/
└── dist/
    └── Isle Map Updater.exe
```

---

## 🐛 Troubleshooting

### Browser does not open

- Make sure Chrome is installed
- Check your internet connection
- Make sure antivirus/firewall is not blocking the app

### Map does not update

- Make sure Vulnona is open
- Make sure the correct map is selected
- Recalibrate the coordinate click point
- Confirm coordinates are copying to your clipboard

### Hotkey does not work

- Try a different hotkey
- Avoid keys already used by Windows or another app
- Restart the app

### Calibration does not save

- Click directly on the in-game coordinate text
- Make sure the click copies valid coordinates
- Try again before the 70-second timeout

---

## 🙏 Credits

- **StoogeCurly** - Reimagined and maintained version
- **GitHub Muslix / the-isle-map-updater** - Original inspiration
- **Vulnona** - Map service
- **The Isle Community** - Testing and feedback
- **Selenium Team** - Browser automation

---

## 🔄 Version History

### v1.0.0

- Themed GUI
- Vulnona map integration
- Clipboard coordinate monitoring
- Custom hotkey support
- Click point calibration
- Packed EXE support

---

**Made with ❤️ for The Isle community**

> ⭐ If this tool helps you, please consider giving it a star on GitHub!

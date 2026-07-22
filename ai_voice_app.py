# Copyright (c) 2026 BluexDEV Softwares. All rights reserved.
# Use permitted. Modification and redistribution of source code prohibited.
# See LICENSE for full terms.

# =========================
# SELF INSTALL DEPENDENCIES
# =========================
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

REQUIRED = {
    "PyQt6": "PyQt6",
    "requests": "requests",
    "dotenv": "python-dotenv",
    "sounddevice": "sounddevice",
    "numpy": "numpy",
    "scipy": "scipy",
    "openai": "openai",
    "pyttsx3": "pyttsx3",
    "edge_tts": "edge-tts",
    "deep_translator": "deep-translator",
    "stftpitchshift": "stftpitchshift",
}
# keyboard requires root/accessibility permissions on macOS and crashes on import without them
if sys.platform != "darwin":
    REQUIRED["keyboard"] = "keyboard"


def install_deps():
    if getattr(sys, "frozen", False):
        return  # All deps are bundled in the EXE — pip install not available
    for module_name, package_name in REQUIRED.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])


install_deps()

# =========================
# IMPORTS (AFTER INSTALL)
# =========================
import hashlib
import io
import json
import math
import threading
import time
import traceback
import uuid
import wave
import webbrowser

import edge_tts
try:
    import keyboard as _keyboard_mod
except Exception:
    _keyboard_mod = None
import numpy as np
import pyttsx3
import requests
import sounddevice as sd
from dotenv import load_dotenv
from openai import OpenAI

# macOS 26+ (Tahoe): Qt's static initializer (QLoggingRegistry) calls
# CFBundleGetMainBundle() which returns NULL before NSApplication is set up,
# causing a crash in __CFCheckCFInfoPACSignature (SIGSEGV at 0x8).
# Fix 1: Call [NSApplication sharedApplication] via Obj-C runtime before PyQt6 import.
# Fix 2: qt.conf (bundled) gives Qt an explicit DataPath so it never calls CFBundleGetMainBundle.
if sys.platform == "darwin":
    try:
        import ctypes as _ct, ctypes.util as _ctu
        _lib = _ctu.find_library("objc")
        if _lib:
            _objc = _ct.CDLL(_lib)
            _objc.objc_getClass.restype = _ct.c_void_p
            _objc.objc_getClass.argtypes = [_ct.c_char_p]
            _objc.sel_registerName.restype = _ct.c_void_p
            _objc.sel_registerName.argtypes = [_ct.c_char_p]
            _objc.objc_msgSend.restype = _ct.c_void_p
            _objc.objc_msgSend.argtypes = [_ct.c_void_p, _ct.c_void_p]
            _cls = _objc.objc_getClass(b"NSApplication")
            _sel = _objc.sel_registerName(b"sharedApplication")
            if _cls:
                _objc.objc_msgSend(_cls, _sel)
    except Exception:
        pass

from PyQt6.QtCore import QEvent, QMimeData, QObject, QPoint, QRectF, QSize, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDrag, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMenuBar,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSplashScreen,
    QStackedWidget,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

# =========================
# THEME — Neon Sci-Fi palette (kaikki värit yhdessä paikassa)
# =========================
THEME = {
    "BG_DEEP":       "#05070f",   # ikkunan tausta (lähes musta navy)
    "BG_PANEL":      "#0a0f1e",   # korttigradientti alku
    "BG_PANEL2":     "#0d1630",   # korttigradientti loppu
    "BG_RAISED":     "#101a36",   # napit idle
    "BG_INPUT":      "#070b16",   # tekstikentät, mittarien tausta
    "BORDER":        "#1c2c52",   # oletuspaneelireuna (himmeä navy)
    "BORDER_GLOW":   "#2e7fff",   # neon-sininen pääaksentti
    "BLUE":          "#2e7fff",
    "BLUE_BRIGHT":   "#6aa8ff",
    "BLUE_DIM":      "#173a75",
    "PURPLE":        "#7b2fff",
    "PURPLE_BRIGHT": "#a678ff",
    "PURPLE_DIM":    "#41208a",
    "GOLD":          "#ffb830",   # suosikit / kansiot
    "GOLD_BRIGHT":   "#ffd060",
    "GOLD_DIM":      "#7a5510",
    "GREEN":         "#00ff88",   # Live Listen / play
    "GREEN_DIM":     "#0a3d24",
    "RED":           "#ff2e4d",   # STOP / record
    "RED_DIM":       "#8a1020",
    "CYAN":          "#00e5ff",   # HA-napit
    "TEXT":          "#dce6ff",
    "TEXT_DIM":      "#8a9bc4",
    "TEXT_FAINT":    "#546a94",
    "GRAD_ACCENT":   "qlineargradient(x1:0,y1:1,x2:1,y2:0, stop:0 #2e7fff, stop:1 #7b2fff)",
    "GRAD_PANEL":    "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0a0f1e, stop:1 #0d1630)",
    "GRAD_BTN":      "qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #14204a, stop:1 #0c1226)",
    "GRAD_METER":    "qlineargradient(x1:0, x2:1, stop:0 #00ff88, stop:0.6 #ffb830, stop:1 #ff2e4d)",
}


def T(qss: str) -> str:
    """Korvaa @TOKEN-nimet QSS-merkkijonossa THEME-arvoilla (pisin avain ensin)."""
    for k in sorted(THEME, key=len, reverse=True):
        qss = qss.replace("@" + k, THEME[k])
    return qss


METER_LABEL_STYLE = T("color: @BORDER_GLOW; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;")
METER_STYLE_MIC = T(
    "QProgressBar { background: @BG_INPUT; border: 1px solid @BORDER; border-radius: 4px; }"
    "QProgressBar::chunk { background: @GRAD_METER; border-radius: 3px; }"
)
METER_STYLE_OUT = T(
    "QProgressBar { background: @BG_INPUT; border: 1px solid @BORDER; border-radius: 4px; }"
    "QProgressBar::chunk { background: @GRAD_METER; border-radius: 3px; }"
)
LIST_STYLE = T("""
    QListWidget {
        background: @BG_INPUT;
        border: 1px solid @BORDER;
        border-radius: 8px;
        font-family: "Inter", "Segoe UI", sans-serif;
        font-size: 12px;
    }
    QListWidget::item {
        background: @BG_RAISED;
        border: 1px solid @BORDER;
        border-radius: 6px;
        margin: 2px 4px;
        padding: 4px 7px;
        color: @TEXT_DIM;
    }
    QListWidget::item:hover {
        background: @BLUE_DIM;
        border-color: @PURPLE;
        color: #ffffff;
    }
    QListWidget::item:selected {
        background: @GRAD_ACCENT;
        border-color: @BLUE;
        color: #ffffff;
    }
""")

# =========================
# CONFIG
# =========================
def get_base_path():
    if getattr(sys, "frozen", False):
        # Store user data in %APPDATA%\Voice Royale — writable without admin rights,
        # survives reinstalls/upgrades since the installer never touches AppData.
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        user_dir = os.path.join(appdata, "Voice Royale")
        os.makedirs(user_dir, exist_ok=True)
        return user_dir
    return os.path.dirname(os.path.abspath(__file__))

def get_assets_path():
    # Bundled read-only assets (splash image etc.) — inside _MEIPASS for frozen, else same as BASE_PATH
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
ASSETS_PATH = get_assets_path()
# Load API keys first, then .env (signing vars) without overriding
load_dotenv(os.path.join(BASE_PATH, "credentials.env"))
load_dotenv(os.path.join(BASE_PATH, ".env"), override=False)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY", "")
VOICE_ID = os.getenv("VOICE_ID", "")
HISTORY_FILE = os.path.join(BASE_PATH, "speech_history.json")

DEFAULT_TTS_BACKEND = "Edge TTS (free)"

client: OpenAI | None = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

LANGS = {
    "Auto": "auto",
    "English": "English",
    "German": "German",
    "Swedish": "Swedish",
    "Finnish": "Finnish",
    "Russian": "Russian",
    "Italian": "Italian",
    "Dutch": "Dutch",
    "Norwegian": "Norwegian",
    "Danish": "Danish",
    "Romanian": "Romanian",
    "Latvian": "Latvian",
    "Lithuanian": "Lithuanian",
    "Japanese": "Japanese",
    "Chinese": "Chinese",
    "Hungarian": "Hungarian",
    "Polish": "Polish",
    "Czech": "Czech",
    "Catalan": "Catalan",
    "Belarusian": "Belarusian",
    "Spanish": "Spanish",
    "French": "French",
    "Turkish": "Turkish",
    "Hindi": "Hindi",
    "Hebrew": "Hebrew",
    "Greek": "Greek",
    "Croatian": "Croatian",
    "Arabic": "Arabic",
}

LANG_FLAG_CODES = {
    "English": "us",
    "German": "de",
    "Swedish": "se",
    "Finnish": "fi",
    "Russian": "ru",
    "Italian": "it",
    "Dutch": "nl",
    "Norwegian": "no",
    "Danish": "dk",
    "Romanian": "ro",
    "Latvian": "lv",
    "Lithuanian": "lt",
    "Japanese": "jp",
    "Chinese": "cn",
    "Hungarian": "hu",
    "Polish": "pl",
    "Czech": "cz",
    "Catalan": "ca",
    "Belarusian": "by",
    "Spanish": "es",
    "French": "fr",
    "Turkish": "tr",
    "Hindi": "in",
    "Hebrew": "il",
    "Greek": "gr",
    "Croatian": "hr",
    "Arabic": "sa",
}

# Edge TTS voices mapping
EDGE_VOICES = {
    "English": "en-US-AriaNeural",
    "German": "de-DE-KatjaNeural",
    "Swedish": "sv-SE-SofieNeural",
    "Finnish": "fi-FI-NooraNeural",
    "Russian": "ru-RU-SvetlanaNeural",
    "Italian": "it-IT-ElsaNeural",
    "Dutch": "nl-NL-ColetteNeural",
    "Norwegian": "nb-NO-PernilleNeural",
    "Danish": "da-DK-ChristelNeural",
    "Romanian": "ro-RO-AlinaNeural",
    "Latvian": "lv-LV-EveritaNeural",
    "Lithuanian": "lt-LT-OnaNeural",
    "Japanese": "ja-JP-NanamiNeural",
    "Chinese": "zh-CN-XiaoxiaoNeural",
    "Hungarian": "hu-HU-NoemiNeural",
    "Polish": "pl-PL-ZofiaNeural",
    "Czech": "cs-CZ-VlastaNeural",
    "Catalan": "ca-ES-JoanaNeural",
    "Belarusian": "ru-RU-SvetlanaNeural",
    "Spanish": "es-ES-ElviraNeural",
    "French": "fr-FR-DeniseNeural",
    "Turkish": "tr-TR-EmelNeural",
    "Hindi": "hi-IN-SwaraNeural",
    "Hebrew": "he-IL-HilaNeural",
    "Greek": "el-GR-AthinaNeural",
    "Croatian": "hr-HR-GabrijelaNeural",
    "Arabic": "ar-SA-ZariyahNeural",
}

APP_VERSION = "1.3.88"
GITHUB_REPO = "JuhaFIN1/voice-royale"

# =========================
# APP SETTINGS (separate from credentials/history)
# =========================
SETTINGS_FILE = os.path.join(BASE_PATH, "app_settings.json")

DEFAULT_SETTINGS = {
    "wake_keyword": "jarvis",
    "wake_custom_ppn_path": "",
    "picovoice_access_key": os.getenv("PICOVOICE_ACCESS_KEY", ""),
    "hotkey": "ctrl+alt+space",
    "default_target_lang": "Auto",
    "default_tts_backend": DEFAULT_TTS_BACKEND,
    "translation_backend": "Google (free)",
    "stt_backend": "OpenAI Whisper API",
    "deepl_api_key": "",
    "pixabay_api_key": "",
    "wake_command_seconds": 6.0,
    "custom_languages": [],
    "soundboard_pages": [
        {"name": "Peli aloitus", "slots": [{"name": f"Slot {i+1}", "file": "", "image": ""} for i in range(56)]}
    ],
    "stream_deck_enabled": True,
    "stream_deck_mapping": {},   # tyhjä = käytä DEFAULT_MAPPING
    "soundboard_volume": 1.0,
    "sb_icon_size": "large",
    "ha_url": "",
    "ha_token": "",
    "ha_players": [],
    "voice_fx_output_device": None,
    "voice_fx_monitor_device": None,
    "voice_fx_hear_myself": False,
    "voice_fx_enabled": False,
    "start_with_windows": False,
    "start_minimized": False,
}


def load_settings() -> dict:
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = {**DEFAULT_SETTINGS, **data}
            return merged
    except Exception:
        pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[DEBUG] Failed to save settings: {e}")


_REG_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_APP_NAME = "Voice Royale"


def _get_autostart_state() -> tuple:
    """Returns (start_with_windows: bool, start_minimized: bool)."""
    if sys.platform != "win32":
        return False, False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, _REG_APP_NAME)
        winreg.CloseKey(key)
        return True, "--minimized" in val
    except Exception:
        return False, False


def _apply_autostart(enabled: bool, minimized: bool) -> None:
    """Write or remove the Windows autostart registry key."""
    if sys.platform != "win32":
        return
    if not getattr(sys, "frozen", False):
        return  # dev mode: don't touch registry
    try:
        import winreg
        exe = sys.executable
        cmd = f'"{exe}"' + (" --minimized" if (enabled and minimized) else "")
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN, 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, _REG_APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, _REG_APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[autostart] registry error: {e}")


_CUSTOM_LANG_NAMES: set = set()


def _apply_custom_languages_to_globals(custom_langs: list) -> None:
    global _CUSTOM_LANG_NAMES
    for name in _CUSTOM_LANG_NAMES:
        LANGS.pop(name, None)
        LANG_FLAG_CODES.pop(name, None)
        EDGE_VOICES.pop(name, None)
    _CUSTOM_LANG_NAMES = set()
    for entry in custom_langs:
        name = entry.get("name", "").strip()
        code = entry.get("country_code", "").strip().lower()
        voice = entry.get("edge_voice", "").strip()
        if not name:
            continue
        LANGS[name] = name
        if code:
            LANG_FLAG_CODES[name] = code
        if voice:
            EDGE_VOICES[name] = voice
        _CUSTOM_LANG_NAMES.add(name)


# =========================
# VIRTUAL AUDIO (VB-Cable)
# =========================

def _windows_disabled_audio_names() -> set:
    """Palauttaa Windowsissa disabloitujen / irti olevien äänilaitteiden nimet
    (pienillä kirjaimilla). PortAudio voi silti enumeroida ne WDM-KS-reittiä
    pitkin ohi Windowsin Disable-asetuksen — tällä listalla ne suodatetaan
    pois käyttäjälle näytettävistä laitelistoista.

    Rekisteri: HKLM\\...\\MMDevices\\Audio\\{Capture,Render}\\{guid}\\DeviceState
    (1=aktiivinen, 2=disabloitu, 4=ei läsnä, 8=irti). Properties-avaimesta
    luetaan laitteen näyttönimet vertailua varten."""
    names = set()
    if sys.platform != "win32":
        return names
    try:
        import winreg
    except Exception:
        return names
    _NAME_PROPS = (
        "{a45c254e-df1c-4efd-8020-67d146a850e0},14",  # PKEY_Device_DeviceDesc
        "{b3f8fa53-0004-438e-9003-51a46e139bfc},6",   # PKEY_DeviceInterface_FriendlyName
        "{026e516e-b814-414b-83cd-856d6fef4822},2",   # endpoint FriendlyName
    )
    for flow in ("Capture", "Render"):
        base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio" + "\\" + flow
        try:
            hk = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
        except OSError:
            continue
        i = 0
        while True:
            try:
                guid = winreg.EnumKey(hk, i)
                i += 1
            except OSError:
                break
            try:
                dk = winreg.OpenKey(hk, guid)
                state, _ = winreg.QueryValueEx(dk, "DeviceState")
                if state == 1:  # DEVICE_STATE_ACTIVE — ei suodateta
                    continue
                pk = winreg.OpenKey(dk, "Properties")
                for prop in _NAME_PROPS:
                    try:
                        val, _ = winreg.QueryValueEx(pk, prop)
                        if isinstance(val, str) and val.strip():
                            names.add(val.strip().lower())
                    except OSError:
                        pass
            except OSError:
                pass
    return names


def _matches_disabled_name(device_name: str, disabled_names: set) -> bool:
    """Törmäyttää PortAudio-laitenimen Windowsin disabloitujen nimiin.
    MME katkaisee nimet ~31 merkkiin, joten pelkkä == ei riitä — hyväksytään
    myös substring- ja pitkä prefix-osuma kumpaan suuntaan tahansa."""
    n = device_name.lower().strip()
    for d in disabled_names:
        if d in n or n in d:
            return True
        cmp = min(len(n), len(d))
        if cmp >= 16 and n[:cmp] == d[:cmp]:
            return True
    return False


def _is_vbcable_installed() -> bool:
    try:
        return any(
            any(kw in d["name"].lower() for kw in ("cable", "voicemod"))
            for d in sd.query_devices()
        )
    except Exception:
        return False


def _get_vbcable_download_url() -> str:
    import urllib.request, re
    try:
        with urllib.request.urlopen("https://vb-audio.com/Cable/index.htm", timeout=8) as r:
            html = r.read().decode("utf-8", errors="ignore")
        m = re.search(r'(https?://[^"\']*VBCABLE_Driver_Pack[\w]+\.zip)', html)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack43.zip"


def _install_vbcable(status_cb) -> None:
    """Download, extract and install VB-Cable. Runs in a background thread."""
    import platform
    import subprocess
    import tempfile
    import urllib.request
    import zipfile

    try:
        status_cb("Looking up download link...")
        url = _get_vbcable_download_url()

        status_cb("Downloading VB-Cable (~1 MB)...")
        tmp_dir = tempfile.mkdtemp(prefix="vbcable_")
        zip_path = os.path.join(tmp_dir, "vbcable.zip")
        urllib.request.urlretrieve(url, zip_path)

        status_cb("Extracting...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        setup_name = "VBCABLE_Setup_x64.exe" if platform.machine().endswith("64") else "VBCABLE_Setup.exe"
        setup_path = None
        for root, _, files in os.walk(tmp_dir):
            for f in files:
                if f.lower() == setup_name.lower():
                    setup_path = os.path.join(root, f)
                    break

        if not setup_path:
            status_cb(f"Error: {setup_name} not found in the package.")
            return

        status_cb("Installing — approve the UAC admin prompt that appears...")
        subprocess.run(
            ["powershell", "-Command",
             f"Start-Process -FilePath '{setup_path}' -Verb RunAs -Wait"],
            capture_output=True, timeout=180,
        )

        if _is_vbcable_installed():
            status_cb("✅ VB-Cable installed! CABLE Input now visible in output device list.")
        else:
            status_cb("Install ran — if CABLE doesn't appear, restart the app once.")

    except urllib.error.URLError as exc:
        status_cb(f"Download failed: {exc}\nManual download: vb-audio.com/Cable")
    except Exception as exc:
        status_cb(f"Error: {exc}")


# =========================
# VOICEMEETER BANANA
# =========================

_VM_REG_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
_VM_REMOTE_DLL = "VoicemeeterRemote64.dll"


def _is_voicemeeter_installed() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, _VM_REG_PATH) as base:
                    i = 0
                    while True:
                        try:
                            sub = winreg.EnumKey(base, i)
                            if "voicemeeter" in sub.lower():
                                return True
                        except OSError:
                            break
                        i += 1
            except OSError:
                pass
    except Exception:
        pass
    # Fallback: check if any sounddevice has Voicemeeter
    try:
        return any("voicemeeter" in d["name"].lower() for d in sd.query_devices())
    except Exception:
        return False


def _ensure_voicemeeter_running() -> bool:
    """Start Voicemeeter Banana if installed but not running. Returns True if running."""
    if sys.platform != "win32":
        return False
    import subprocess as _sp, time as _t
    # Voicemeeter Banana exe names: old installer=voicemeeterb.exe, new installer=voicemeeterpro_x64.exe
    # voicemeeter.exe/voicemeeter_x64.exe are basic Voicemeeter — do NOT start those
    _vm_exe_names = ["voicemeeterb.exe", "voicemeeterpro_x64.exe", "voicemeeterpro.exe"]
    try:
        r = _sp.run(["tasklist", "/NH"], capture_output=True, text=True, timeout=5,
                        creationflags=_sp.CREATE_NO_WINDOW)
        if any(name in r.stdout.lower() for name in _vm_exe_names):
            return True
    except Exception:
        pass
    search_dirs = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "VB", "Voicemeeter"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "VB", "Voicemeeter"),
    ]
    # Find actual install path from registry (handles non-standard install locations)
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for wow in ("", r"WOW6432Node\\"):
                reg_path = rf"SOFTWARE\{wow}Microsoft\Windows\CurrentVersion\Uninstall"
                try:
                    with winreg.OpenKey(hive, reg_path) as base:
                        i = 0
                        while True:
                            try:
                                sub = winreg.EnumKey(base, i)
                                if "voicemeeter" in sub.lower():
                                    try:
                                        with winreg.OpenKey(base, sub) as key:
                                            for val in ("InstallLocation", "UninstallString", "DisplayIcon"):
                                                try:
                                                    v, _ = winreg.QueryValueEx(key, val)
                                                    d = os.path.dirname(v.strip('"')) if val != "InstallLocation" else v
                                                    if d and os.path.isdir(d) and d not in search_dirs:
                                                        search_dirs.append(d)
                                                except OSError:
                                                    pass
                                    except OSError:
                                        pass
                            except OSError:
                                break
                            i += 1
                except OSError:
                    pass
    except Exception:
        pass
    for d in search_dirs:
        for name in _vm_exe_names:
            exe = os.path.join(d, name)
            if os.path.isfile(exe):
                try:
                    si = _sp.STARTUPINFO()
                    si.dwFlags |= _sp.STARTF_USESHOWWINDOW
                    si.wShowWindow = 2  # SW_SHOWMINIMIZED
                    _sp.Popen([exe], startupinfo=si)
                    _t.sleep(2.5)
                    return True
                except Exception:
                    pass
    return False


def _get_voicemeeter_dll_path() -> str | None:
    """Return path to VoicemeeterRemote64.dll or None."""
    search_dirs = [
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "VB", "Voicemeeter"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "VB", "Voicemeeter"),
        r"C:\Program Files\VB\Voicemeeter",
        r"C:\Program Files (x86)\VB\Voicemeeter",
    ]
    for d in search_dirs:
        p = os.path.join(d, _VM_REMOTE_DLL)
        if os.path.isfile(p):
            return p
    return None


def _get_voicemeeter_download_url() -> str:
    """Scrape banana.htm for the latest installer URL, fall back to a known CDN path."""
    import urllib.request, re as _re
    candidates = []
    try:
        req = urllib.request.Request(
            "https://vb-audio.com/Voicemeeter/banana.htm",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")
        for pat in [
            r'(https?://[^"\']*[Vv]oicemeeter[^"\']*\.(zip|exe))',
            r'href="(/[^"\']*[Vv]oicemeeter[^"\']*\.(zip|exe))"',
        ]:
            for m in _re.finditer(pat, html):
                url = m.group(1)
                if not url.startswith("http"):
                    url = "https://vb-audio.com" + url
                if url not in candidates:
                    candidates.append(url)
    except Exception:
        pass
    # Prefer zip over exe, prefer "Banana" in name
    for url in candidates:
        if "banana" in url.lower() or "Banana" in url:
            return url
    if candidates:
        return candidates[0]
    # Hard-coded CDN fallback — NSIS installer, supports /S silent flag
    return "https://download.vb-audio.com/Download_CABLE/VoicemeeterBananaSetup_v2.0.9.0.zip"


def _install_voicemeeter(status_cb) -> None:
    """Download and silent-install Voicemeeter Banana. Runs in a background thread."""
    import tempfile
    import subprocess
    import zipfile

    try:
        status_cb("Haetaan latauspaikka...")
        url = _get_voicemeeter_download_url()

        tmp_dir = tempfile.mkdtemp(prefix="voicemeeter_")
        is_zip = url.lower().endswith(".zip")
        dest = os.path.join(tmp_dir, "vm.zip" if is_zip else "VoicemeeterSetup.exe")

        # Stream download with progress so the UI knows we're alive
        status_cb("Ladataan Voicemeeter Banana...")
        try:
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(65536):
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded * 100 / total)
                        status_cb(f"Ladataan... {pct}%")
        except Exception as exc:
            status_cb(f"Latausvirhe: {exc}\nManuaalisesti: vb-audio.com/Voicemeeter")
            return

        setup_path = None
        if is_zip:
            status_cb("Puretaan...")
            try:
                with zipfile.ZipFile(dest, "r") as zf:
                    zf.extractall(tmp_dir)
                for root, _, files in os.walk(tmp_dir):
                    for f in files:
                        if f.lower().endswith(".exe") and "voicemeeter" in f.lower():
                            setup_path = os.path.join(root, f)
                            break
                    if setup_path:
                        break
            except Exception as exc:
                status_cb(f"Purkuvirhe: {exc}")
                return
        else:
            setup_path = dest

        if not setup_path:
            status_cb("Asennustiedostoa ei löydy paketista. Yritä manuaalisesti: vb-audio.com/Voicemeeter")
            return

        status_cb("Asennetaan — hyväksy UAC-pyyntö joka ilmestyy...")
        # Quote the path to handle spaces; NSIS /S = silent, /SD = default answers
        ps_cmd = (
            f'Start-Process -FilePath \'"{setup_path}"\' '
            f'-ArgumentList \'/S\' -Verb RunAs -Wait'
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, timeout=300,
        )

        if _is_voicemeeter_installed():
            status_cb("✅ Voicemeeter Banana asennettu! Käynnistä PC uudelleen viimeistelläksesi ajuriasennuksen.")
            _disable_unused_voicemeeter_endpoints(lambda _msg: None)
        else:
            stderr = result.stderr.decode("utf-8", errors="ignore").strip()
            if "cancel" in stderr.lower() or "declined" in stderr.lower() or result.returncode != 0:
                status_cb(f"Asennus peruutettu tai epäonnistui (koodi {result.returncode}).\nKokeile manuaalisesti: vb-audio.com/Voicemeeter")
            else:
                status_cb("Asennus suoritettu. Jos Voicemeeter ei näy, käynnistä PC uudelleen.")

    except subprocess.TimeoutExpired:
        status_cb("Asennus kesti liian kauan — tarkista tehtävienhallinnasta onko asennus kesken.")
    except Exception as exc:
        status_cb(f"Virhe: {exc}")


def _disable_unused_voicemeeter_endpoints(status_cb) -> None:
    """Disable all Voicemeeter virtual audio endpoints except Input and Out B1.

    Voice Royale's chat routing only ever uses "Voicemeeter Input" (TTS playback
    target) and "Voicemeeter Out B1" (virtual mic for Discord/games). Voicemeeter
    Potato registers 16 endpoints total (In1-5, AUX/VAIO3 Input, Out A1-A5, Out B2-B3
    are all unused by this app) which clutters Windows' sound device lists. Disabling
    via Device Manager keeps Voicemeeter itself fully functional and is reversible.
    Requires admin — triggers a UAC prompt.
    """
    if sys.platform != "win32":
        return
    import tempfile

    # The PnP-filter script is written to its own .ps1 file and invoked with -File +
    # an array -ArgumentList, instead of embedding it as a nested -Command string
    # (avoids the quote-nesting that used to break the outer Start-Process call
    # silently before the UAC prompt could even appear).
    #
    # Device MATCHING is registry-based, not PnP FriendlyName-based. Verified directly
    # on real hardware: Get-PnpDevice -Class AudioEndpoint reports every Voicemeeter
    # endpoint's Status as "Error" (never "OK") and its FriendlyName as a generic,
    # indistinguishable string ("Speakers (VB-Audio Voicemeeter VAIO)", "Voicemeeter
    # Out 1..8") that does NOT match the names Windows/sd.query_devices() actually show
    # ("Voicemeeter Input", "Voicemeeter Out B1", etc). The real, distinguishable name
    # lives in the registry (same property _set_windows_default_recording() already
    # reads), and that registry GUID appears verbatim inside Get-PnpDevice's InstanceId
    # (SWD\MMDEVAPI\{0.0.1.00000000}.{GUID} for capture, {0.0.0.00000000}.{GUID} for
    # render) — so endpoints are identified by GUID lookup instead of by name/status.
    tmp_dir = tempfile.mkdtemp(prefix="vr_vmcleanup_")
    script_path = os.path.join(tmp_dir, "cleanup.ps1")
    result_path = os.path.join(tmp_dir, "result.txt")
    ps_script = (
        "try {\n"
        "  $renderBase = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\MMDevices\\Audio\\Render'\n"
        "  $captureBase = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\MMDevices\\Audio\\Capture'\n"
        "  $keep = @('Voicemeeter Input', 'Voicemeeter Out B1')\n"
        "  $guids = @()\n"
        "  foreach ($base in @($renderBase, $captureBase)) {\n"
        "    Get-ChildItem $base -ErrorAction SilentlyContinue | ForEach-Object {\n"
        "      $propPath = Join-Path $_.PSPath 'Properties'\n"
        "      $name = (Get-ItemProperty -Path $propPath -Name '{a45c254e-df1c-4efd-8020-67d146a850e0},2' -ErrorAction SilentlyContinue).'{a45c254e-df1c-4efd-8020-67d146a850e0},2'\n"
        "      if ($name -like '*Voicemeeter*' -and ($keep -notcontains $name)) {\n"
        "        $guids += $_.PSChildName\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "  $disabledCount = 0\n"
        "  foreach ($guid in $guids) {\n"
        "    Get-PnpDevice -Class AudioEndpoint -PresentOnly | Where-Object { $_.InstanceId -like \"*$guid*\" } | ForEach-Object {\n"
        "      Disable-PnpDevice -InstanceId $_.InstanceId -Confirm:$false -ErrorAction SilentlyContinue\n"
        "      $disabledCount++\n"
        "    }\n"
        "  }\n"
        f"  \"OK:$disabledCount\" | Out-File -FilePath '{result_path}' -Encoding utf8\n"
        "} catch {\n"
        f"  \"ERROR: $_\" | Out-File -FilePath '{result_path}' -Encoding utf8\n"
        "}\n"
    )
    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(ps_script)
        status_cb("Siivotaan turhat Voicemeeter-virtuaalilaitteet — hyväksy UAC-pyyntö...")
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Start-Process -FilePath powershell -Verb RunAs -Wait -ArgumentList "
             f"@('-NoProfile','-ExecutionPolicy','Bypass','-File','{script_path}')"],
            capture_output=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        result_text = ""
        if os.path.isfile(result_path):
            with open(result_path, "r", encoding="utf-8") as f:
                result_text = f.read().strip()
        if result_text.startswith("OK:"):
            count = result_text.split(":", 1)[1]
            if count != "0":
                status_cb(
                    f"✅ {count} turhaa Voicemeeter-virtuaalilaitetta piilotettu "
                    "(Voicemeeter Input + Out B1 jäivät käyttöön)."
                )
            else:
                status_cb("⚠ Ei löytynyt piilotettavia Voicemeeter-laitteita.")
        elif result_text.startswith("ERROR"):
            status_cb(f"Laitteiden siivous epäonnistui: {result_text}")
        else:
            status_cb("⚠ UAC-pyyntöä ei hyväksytty tai se peruttiin — laitteita ei siivottu.")
    except Exception as exc:
        status_cb(f"Laitteiden siivous epäonnistui: {exc}")
    finally:
        import shutil as _sh_cleanup
        _sh_cleanup.rmtree(tmp_dir, ignore_errors=True)


def _check_voicemeeter_routing() -> tuple[str, bool]:
    """Check that a Voicemeeter virtual B1 output and CABLE Input exist in the device list."""
    try:
        devices = sd.query_devices()
        # Match both Banana ("Voicemeeter Output") and Potato ("Voicemeeter Out B1")
        vm_out_dev = next(
            (d for d in devices
             if ("voicemeeter output" in d["name"].lower()
                 or "voicemeeter out b1" in d["name"].lower())
             and d["max_input_channels"] > 0),
            None,
        )
        vm_in_dev = next(
            (d for d in devices
             if d["name"].lower() == "voicemeeter input (vb-audio voicemeeter vaio)"
             and d["max_output_channels"] > 0),
            None,
        )
        if vm_out_dev and vm_in_dev:
            return (
                "✅ Reititys valmis!\n"
                f"  • Voice Royale lähtölaite → '{vm_in_dev['name']}'\n"
                f"  • Windows oletusmikrofoni → '{vm_out_dev['name']}'\n"
                "  • Discord, Fortnite ym. käyttävät sitä automaattisesti.",
                True,
            )
        parts = []
        if not vm_in_dev:
            parts.append("Voicemeeter Input ei löydy — käynnistä Voicemeeter uudelleen")
        if not vm_out_dev:
            parts.append("Voicemeeter Out B1 ei löydy — käynnistä Voicemeeter uudelleen tai PC:n uudelleenkäynnistys")
        return "⚠ " + "\n  • ".join(parts), False
    except Exception as exc:
        return f"Virhe laitetarkistuksessa: {exc}", False


def _set_windows_default_recording(name_contains: str) -> tuple[bool, str]:
    """Set Windows default recording device.
    Reads device names from registry (reliable), sets default via IPolicyConfig COM.
    """
    if sys.platform != "win32":
        return False, "Ei Windows"
    import subprocess as _sp
    # Registry: PKEY_Device_DeviceDesc = {a45c254e...},2
    # C# helper does the COM vtable cast natively (PowerShell -as fails for IUnknown interfaces)
    ps = f"""
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
[ComImport, Guid("F8679F50-850A-41CF-9C72-430F290290C8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPolicyConfigVR {{
  [PreserveSig] int _1();[PreserveSig] int _2();[PreserveSig] int _3();
  [PreserveSig] int _4();[PreserveSig] int _5();[PreserveSig] int _6();
  [PreserveSig] int _7();[PreserveSig] int _8();[PreserveSig] int _9();[PreserveSig] int _10();
  [PreserveSig] int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string id, uint role);
  [PreserveSig] int _12();
}}
[ComImport, Guid("870AF99C-171D-4F9E-AF0D-E63DF40C2BC9"), ClassInterface(ClassInterfaceType.None)]
public class PolicyConfigClientVR {{}}
public static class PolicyConfigHelperVR {{
  public static void SetDefault(string epId) {{
    var pc = (IPolicyConfigVR)new PolicyConfigClientVR();
    pc.SetDefaultEndpoint(epId, 0);
    pc.SetDefaultEndpoint(epId, 1);
    pc.SetDefaultEndpoint(epId, 2);
  }}
}}
'@ -ErrorAction SilentlyContinue
$regBase = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\MMDevices\\Audio\\Capture'
$found = $false
foreach ($key in Get-ChildItem $regBase -ErrorAction SilentlyContinue) {{
  $propPath = Join-Path $key.PSPath 'Properties'
  $nm = (Get-ItemProperty -Path $propPath -Name '{{a45c254e-df1c-4efd-8020-67d146a850e0}},2' -ErrorAction SilentlyContinue).'{{a45c254e-df1c-4efd-8020-67d146a850e0}},2'
  if ($nm -and $nm -like '*{name_contains}*') {{
    $epId = '{{0.0.1.00000000}}.' + $key.PSChildName
    [PolicyConfigHelperVR]::SetDefault($epId)
    Write-Output "OK:$nm"
    $found = $true
    break
  }}
}}
if (-not $found) {{ Write-Output "NOTFOUND" }}
"""
    try:
        r = _sp.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=25,
        )
        out = r.stdout.strip()
        if out.startswith("OK:"):
            return True, f"✅ Windows oletusmikrofoni asetettu: {out[3:]}"
        return False, f"Laitetta ei löydy ('{name_contains}') — käynnistä Voicemeeter ja yritä uudelleen"
    except Exception as e:
        return False, str(e)


def _open_windows_sound_recording():
    """Open Windows Sound settings to the Recording tab."""
    import subprocess as _sp
    _sp.Popen(["rundll32", "shell32.dll,Control_RunDLL", "mmsys.cpl", ",", "1"])


def _get_voicemeeter_output_device_indices() -> list[int]:
    """Return [Voicemeeter Input index, headphones index] from list_output_devices()."""
    devices = list_output_devices()
    # Must be exactly "Voicemeeter Input" (Strip[2] → B1), not "Voicemeeter In 2" etc.
    vm_idx = next(
        (idx for idx, n in reversed(devices)
         if n.lower() == "voicemeeter input (vb-audio voicemeeter vaio)"),
        None,
    )
    headphone_idx = next(
        (idx for idx, n in devices if "headphones" in n.lower() and "realtek" in n.lower()),
        None,
    )
    if headphone_idx is None:
        headphone_idx = next(
            (idx for idx, n in devices
             if any(k in n.lower() for k in ("headphone", "headset", "kuuloke"))
             and not any(k in n.lower() for k in ("voicemeeter", "cable", "virtual"))),
            None,
        )
    return [i for i in [vm_idx, headphone_idx] if i is not None]


def _voicemeeter_configure(mic_device_name: str, status_cb) -> None:
    """Configure Voicemeeter Banana routing via VoicemeeterRemote64.dll.

    Routes:
      - Hardware Input 1 → selected recording device (RodeCaster Chat / Mix Minus)
      - Virtual Input (VB-Cable Out) → VR TTS audio
      Both → B1 virtual output bus (becomes Windows default mic for games)
    """
    import ctypes
    import ctypes.wintypes

    dll_path = _get_voicemeeter_dll_path()
    if not dll_path:
        status_cb("VoicemeeterRemote64.dll not found. Is Voicemeeter Banana installed?")
        return

    try:
        vm = ctypes.WinDLL(dll_path)
        # Login
        res = vm.VBVMR_Login()
        if res not in (0, 1):  # 0=OK, 1=OK+launch
            status_cb(f"Voicemeeter login failed (code {res}). Is Voicemeeter running?")
            return

        import time
        time.sleep(1.5)  # Let Voicemeeter start if it just launched

        # Helper: set parameter string
        def set_param_str(param: str, value: str):
            vm.VBVMR_SetParameterStringA(param.encode(), value.encode())

        # Helper: set parameter float
        def set_param_float(param: str, value: float):
            vm.VBVMR_SetParameterFloat(param.encode(), ctypes.c_float(value))

        # Hardware Input 1 (Strip[0]): route RodeCaster/physical mic → B1
        # Try WDM first, then MME — Voicemeeter may accept either format
        if mic_device_name:
            set_param_str("Strip[0].device.wdm", mic_device_name)
            time.sleep(0.3)
            set_param_str("Strip[0].device.mme", mic_device_name)
        set_param_float("Strip[0].A1", 0.0)
        set_param_float("Strip[0].A2", 0.0)
        set_param_float("Strip[0].B1", 1.0)   # → B1 bus
        set_param_float("Strip[0].B2", 0.0)

        # Virtual Input Strip[2] (= "Voicemeeter Input" VAIO) → B1
        # Voice Royale sends TTS/soundboard here
        set_param_float("Strip[2].A1", 0.0)
        set_param_float("Strip[2].A2", 0.0)
        set_param_float("Strip[2].B1", 1.0)   # → B1
        set_param_float("Strip[2].B2", 0.0)

        # Bus B1 on
        set_param_float("Bus[3].On", 1.0)

        time.sleep(0.8)
        vm.VBVMR_Logout()
        status_cb(
            "✅ Reititys asetettu: Strip[0] → B1 ja Strip[2] → B1.\n"
            "⚠ Tarkista Voicemeeter Banana: Hardware Input 1 -kohtaan pitää näkyä "
            f"'{mic_device_name}'. Jos se on tyhjä, valitse se manuaalisesti.\n"
            "Varmista myös että B1-nappi palaa Hardware Input 1 -stripissä."
        )
    except Exception as exc:
        status_cb(f"Configuration error: {exc}")


# =========================
# OPTIONAL: Picovoice Porcupine wake-word
# =========================
try:
    import pvporcupine  # type: ignore
    PORCUPINE_AVAILABLE = True
except Exception:
    pvporcupine = None
    PORCUPINE_AVAILABLE = False


# =========================
# OPTIONAL: stftPitchShift (proper phase-vocoder pitch shifting)
# =========================
try:
    from stftpitchshift import StftPitchShift  # type: ignore
    STFTPITCHSHIFT_AVAILABLE = True
except Exception:
    StftPitchShift = None
    STFTPITCHSHIFT_AVAILABLE = False


# =========================
# VOICE EFFECT PROCESSOR
# =========================
class VoiceEffectProcessor:
    """Real-time mic → DSP effects → virtual output (e.g. VB-Cable).

    Effects run inline in the audio callback (single bidirectional sd.Stream).
    Pitch shifting uses overlap-add across large Hann-windowed grains
    (_PITCH_BLOCK/_PITCH_HOP) so it can stay fast enough for the callback
    while avoiding the clicking a naive per-tiny-chunk resample would cause.
    """

    # "pitches" is a list of simultaneous semitone shifts — stftPitchShift's
    # `factors` supports shifting by several amounts at once and mixing the
    # results ("poly pitch shift"), which is what the Chorus/Octave/5th/Duet/
    # PowerChord/Alien presets below use for real harmony/doubling effects
    # instead of a single pitch move. Verified via FFT/peak-amplitude testing
    # (no clipping/NaN across all presets at typical AND near-full-scale input).
    PRESETS = {
        "Normal":     {"pitches": [0],             "robot": False},
        "Pitch +4":   {"pitches": [4],              "robot": False},
        "Pitch +8":   {"pitches": [8],              "robot": False},
        "Pitch -4":   {"pitches": [-4],             "robot": False},
        "Pitch -8":   {"pitches": [-8],             "robot": False},
        "Robot":      {"pitches": [0],              "robot": True},
        "Deep":       {"pitches": [-6],             "robot": False},
        "Helium":     {"pitches": [10],             "robot": False},
        "Chorus":     {"pitches": [0, 0.15, -0.15], "robot": False},
        "Octave":     {"pitches": [0, 12],          "robot": False},
        "5th":        {"pitches": [0, 7],           "robot": False},
        "Duet":       {"pitches": [0, 4],           "robot": False},
        "PowerChord": {"pitches": [-12, 0, 7],      "robot": False},
        "Alien":      {"pitches": [-5, 5, 12],      "robot": False},
    }

    _SAMPLE_RATE = 48000  # matches USB audio interfaces (RodeCaster etc.)
    _BLOCKSIZE = 512     # ~10ms latency, same callback-driven approach as Voicemod

    # Pitch-shift analysis window: independently resampling each 512-sample
    # driver callback (old approach) clicks at every ~10ms block boundary —
    # audible as constant crackle/warble. Processing much larger overlapping
    # (50%) Hann-windowed grains and cross-fading them via overlap-add removes
    # the boundary discontinuity entirely. Hann @ 50% overlap is COLA-exact
    # (overlapped windows sum to a constant), so no extra normalization pass
    # is needed. Costs ~(_PITCH_BLOCK-_PITCH_HOP)/_SAMPLE_RATE extra latency
    # (~43ms) — a normal trade-off for realtime pitch shifting.
    _PITCH_BLOCK = 4096
    _PITCH_HOP = 2048  # must divide evenly by _BLOCKSIZE

    # Internal STFT frame/hop for stftpitchshift's phase vocoder. Must match
    # _PITCH_BLOCK — measured that a smaller internal frame (2048) makes the
    # library's formant/cepstral path return wildly wrong frequencies for
    # pitch-DOWN shifts specifically (verified via FFT: "Deep" -6 semitones
    # came out ~2x HIGHER, not lower). At framesize=4096 that failure mode
    # goes away for a single whole-buffer call, but still reappears once
    # wired into our streaming/overlap-add grain loop — root cause not fully
    # isolated, so formant preservation (quefrency) is left at 0 (disabled)
    # until that's understood; plain (non-formant) shifting measured reliable
    # across all presets and loudness levels in both cases.
    _SPS_FRAMESIZE = 4096
    _SPS_HOPSIZE = 1024

    def __init__(self, status_cb):
        self._status = status_cb
        self._active = False
        self._pitches = [0]
        self._robot = False
        self._robot_phase = 0
        self._current_preset = "Normal"
        self._lock = threading.Lock()
        self._stream = None       # single bidirectional sd.Stream
        self._monitor_stream = None
        self._hear_myself = False
        self._monitor_device = None
        self._pv_window = np.hanning(self._PITCH_BLOCK).astype(np.float32)
        self._sps = (
            StftPitchShift(
                framesize=self._SPS_FRAMESIZE,
                hopsize=self._SPS_HOPSIZE,
                samplerate=int(self._SAMPLE_RATE),
            )
            if STFTPITCHSHIFT_AVAILABLE else None
        )
        self._reset_pitch_state()

    def _reset_pitch_state(self):
        self._pv_stage = np.zeros(0, dtype=np.float32)          # raw input not yet a full hop
        self._pv_history = np.zeros(self._PITCH_BLOCK, dtype=np.float32)  # last BLOCK raw samples
        self._pv_out_accum = np.zeros(self._PITCH_BLOCK, dtype=np.float32)  # OLA accumulator
        self._pv_out_ready = np.zeros(0, dtype=np.float32)      # processed samples awaiting output

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_preset(self) -> str:
        return self._current_preset

    def set_preset(self, name: str):
        p = self.PRESETS.get(name, self.PRESETS["Normal"])
        with self._lock:
            self._pitches = p["pitches"]
            self._robot = p["robot"]
            self._current_preset = name

    def _callback(self, indata, outdata, frames, time_info, status):
        """Audio callback — runs in real-time audio thread, must be fast."""
        with self._lock:
            pitches = self._pitches
            robot = self._robot
        chunk = indata[:, 0].copy()
        if robot or pitches != [0]:
            try:
                chunk = self._apply(chunk, pitches, robot)
            except Exception:
                pass  # on error: pass through unmodified
        outdata[:, 0] = chunk
        if self._monitor_stream and self._hear_myself:
            try:
                self._monitor_stream.write(chunk.reshape(-1, 1))
            except Exception:
                pass

    def start(self, input_device, output_device):
        if self._active:
            self.stop()
        self._reset_pitch_state()
        try:
            # Verify both devices use the same host API — mixed APIs cause -9993
            try:
                in_info = sd.query_devices(input_device)
                out_info = sd.query_devices(output_device)
                if in_info["hostapi"] != out_info["hostapi"]:
                    apis = sd.query_hostapis()
                    in_api = apis[in_info["hostapi"]]["name"]
                    out_api = apis[out_info["hostapi"]]["name"]
                    self._status(
                        f"Voice FX error: mic '{in_info['name']}' käyttää {in_api}, "
                        f"mutta output '{out_info['name']}' käyttää {out_api}. "
                        f"Valitse laitteet samalta API:lta (molemmat WASAPI)."
                    )
                    return
            except Exception:
                pass
            self._stream = sd.Stream(
                samplerate=self._SAMPLE_RATE,
                blocksize=self._BLOCKSIZE,
                device=(input_device, output_device),
                channels=(1, 1),
                dtype="float32",
                callback=self._callback,
                latency="low",
            )
            self._stream.start()
            self._active = True
            if self._hear_myself and self._monitor_device is not None:
                self._start_monitor_stream(self._monitor_device)
            self._status(f"Voice FX: stream ON [{self._current_preset}]")
        except Exception as e:
            self._active = False
            if self._stream:
                try: self._stream.stop(); self._stream.close()
                except Exception: pass
                self._stream = None
            self._status(f"Voice FX error: {e}")

    def stop(self):
        self._active = False
        if self._stream:
            try: self._stream.stop(); self._stream.close()
            except Exception: pass
            self._stream = None
        if self._monitor_stream:
            try: self._monitor_stream.stop(); self._monitor_stream.close()
            except Exception: pass
            self._monitor_stream = None
        self._status("Voice FX: stream OFF")

    def _apply(self, chunk: np.ndarray, pitches: list, robot: bool) -> np.ndarray:
        if robot:
            n = len(chunk)
            t = np.arange(self._robot_phase, self._robot_phase + n) / self._SAMPLE_RATE
            self._robot_phase = (self._robot_phase + n) % (self._SAMPLE_RATE * 100)
            chunk = chunk * np.sin(2 * np.pi * 40 * t).astype(np.float32)
        if pitches != [0]:
            chunk = self._pitch_shift(chunk, pitches)
        return chunk

    def _pitch_shift(self, chunk: np.ndarray, semitones_list: list) -> np.ndarray:
        """Overlap-add granular pitch shift, decoupled from the driver's small
        callback size — see _PITCH_BLOCK/_PITCH_HOP comment above for why.
        semitones_list can hold several simultaneous shifts ("poly pitch
        shift") for the Chorus/Octave/5th/Duet/PowerChord/Alien presets."""
        HOP = self._PITCH_HOP
        BLOCK = self._PITCH_BLOCK
        factors = [2.0 ** (s / 12.0) for s in semitones_list]
        n = len(chunk)
        self._pv_stage = np.concatenate([self._pv_stage, chunk])
        while len(self._pv_stage) >= HOP:
            hop_samples, self._pv_stage = self._pv_stage[:HOP], self._pv_stage[HOP:]
            self._pv_history = np.concatenate([self._pv_history[HOP:], hop_samples])
            if self._sps is not None:
                # Proper phase-vocoder pitch shift (github.com/jurihock/stftPitchShift,
                # MIT). It windows/frames internally, so pass it the RAW history and
                # apply our own outer Hann window to its output afterwards — that's
                # only for cross-fading this grain smoothly against its neighbours
                # below, not a second analysis window on the input. Handles multiple
                # simultaneous factors natively, mixing them into one output.
                shifted_raw = self._sps.shiftpitch(
                    self._pv_history, factors=factors, quefrency=0
                ).astype(np.float32)
                shifted = shifted_raw * self._pv_window
            else:
                # Fallback if the dependency failed to install: cruder single-
                # resample-and-tile shift per factor, summed (still correct,
                # verified via FFT, just without the phase vocoder's transient/
                # timbre quality). Resample ONCE per factor only — a second
                # resample back to BLOCK mathematically cancels the pitch shift
                # out (verified empirically).
                from scipy.signal import resample
                grain = self._pv_history * self._pv_window
                shifted = np.zeros(BLOCK, dtype=np.float32)
                for factor in factors:
                    n_mid = max(1, int(round(BLOCK / factor)))
                    shifted_raw = resample(grain, n_mid).astype(np.float32)
                    shifted += np.resize(shifted_raw, BLOCK)
            self._pv_out_accum += shifted
            ready = self._pv_out_accum[:HOP].copy()
            self._pv_out_accum = np.concatenate(
                [self._pv_out_accum[HOP:], np.zeros(HOP, dtype=np.float32)]
            )
            self._pv_out_ready = np.concatenate([self._pv_out_ready, ready])
        if len(self._pv_out_ready) >= n:
            out, self._pv_out_ready = self._pv_out_ready[:n], self._pv_out_ready[n:]
        else:
            # startup transient only — not enough processed audio buffered yet
            out = np.concatenate(
                [self._pv_out_ready, np.zeros(n - len(self._pv_out_ready), dtype=np.float32)]
            )
            self._pv_out_ready = np.zeros(0, dtype=np.float32)
        # Overlap-add of tiled/truncated grains can occasionally push loud/hot
        # mic input over 0 dBFS (measured up to ~1.15 peak on a hot signal with
        # "Pitch +8") — tanh is a smooth, always-bounded (-1,1) soft limiter that
        # is near-identity at normal levels, so this only engages on the rare
        # loud peak instead of hard-clipping into a crackle.
        out = np.tanh(out).astype(np.float32)
        return out

    def set_monitor(self, device, enabled: bool):
        self._hear_myself = enabled
        self._monitor_device = device
        if enabled and device is not None and self._active:
            self._start_monitor_stream(device)
        else:
            self._stop_monitor_stream()

    def _start_monitor_stream(self, device):
        self._stop_monitor_stream()
        try:
            self._monitor_stream = sd.OutputStream(
                device=device,
                samplerate=self._SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=self._BLOCKSIZE,
                latency="low",
            )
            self._monitor_stream.start()
        except Exception as e:
            self._status(f"Hear Myself error: {e}")
            self._monitor_stream = None

    def _stop_monitor_stream(self):
        if self._monitor_stream:
            try:
                self._monitor_stream.stop()
                self._monitor_stream.close()
            except Exception:
                pass
            self._monitor_stream = None


# =========================
# STREAM DECK HTTP SERVER
# =========================
class StreamDeckHttpServer:
    """HTTP server for the official Elgato Stream Deck plugin.

    Voice Royale listens on localhost:17842.  The companion .streamDeckPlugin
    (in streamdeck-plugin/) connects to Stream Deck software via WebSocket and
    forwards button-press events here as HTTP POST /action/{name} requests.

    Endpoints:
      GET  /health         → {"status":"ok","app":"Voice Royale"}
      GET  /state          → current app state (recording, lang, FX, soundboard…)
      GET  /actions        → list of callable action names
      POST /action/{name}  → trigger named action, returns {"ok":true}
    """

    PORT = 17842

    ACTIONS = [
        "record_toggle", "wake_listen_toggle", "speak", "stop_recording",
        "tts_toggle", "settings", "overlay_toggle",
        "lang_Auto", "lang_English", "lang_Finnish", "lang_Swedish",
        "lang_German", "lang_Russian", "lang_Italian", "lang_Dutch",
        "lang_Norwegian", "lang_Danish", "lang_Romanian", "lang_Latvian",
        "lang_Lithuanian", "lang_Japanese", "lang_Chinese", "lang_Hungarian",
        "lang_French", "lang_Spanish", "lang_Portuguese",
        "sb_page_goto_0",
        "fx_Normal", "fx_Pitch +4", "fx_Pitch -4", "fx_Robot", "fx_Deep", "fx_Helium",
    ]

    def __init__(self, status_cb):
        self._status = status_cb
        self._app = None
        self._server = None
        self._thread = None

    def start(self, app_ref):
        self._app = app_ref
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None

    def is_running(self):
        return self._server is not None

    def _run(self):
        import http.server
        import urllib.parse
        app = self._app
        status_cb = self._status
        server_ref = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # suppress access log spam

            def do_OPTIONS(self):
                self.send_response(200)
                self._cors()
                self.end_headers()

            def do_GET(self):
                if self.path == "/health":
                    self._json({"status": "ok", "app": "Voice Royale",
                                "port": StreamDeckHttpServer.PORT})
                elif self.path == "/state":
                    self._json(app._get_sd_state())
                elif self.path == "/actions":
                    self._json({"actions": StreamDeckHttpServer.ACTIONS})
                elif self.path.startswith("/action/"):
                    import urllib.parse as _up
                    action = _up.unquote(self.path[8:].strip("/"))
                    app._sd_action_queue.put(action)
                    self._json({"ok": True, "action": action})
                elif self.path.startswith("/soundboard/image/"):
                    parts = self.path[18:].strip("/").split("/")
                    img_b64 = None
                    if len(parts) == 2:
                        try:
                            pi = int(parts[0])
                            slot_str = parts[1]
                            st = app._get_sd_state()
                            pages_st = st.get("soundboard_pages", [])
                            ip = ""
                            if pi < len(pages_st):
                                sl = pages_st[pi].get("slots", [])
                                if slot_str.startswith("f"):
                                    sub_parts = slot_str[1:].split("_")
                                    fi, si = int(sub_parts[0]), int(sub_parts[1])
                                    if fi < len(sl):
                                        fs_list = sl[fi].get("folder_slots", [])
                                        fs = next((x for x in fs_list if x.get("index") == si), None)
                                        ip = fs.get("image_path", "") if fs else ""
                                else:
                                    si = int(slot_str)
                                    if si < len(sl):
                                        ip = sl[si].get("image_path", "")
                            if ip and os.path.exists(ip):
                                import base64 as _b64
                                with open(ip, "rb") as _f:
                                    raw = _b64.b64encode(_f.read()).decode()
                                _ext = os.path.splitext(ip)[1].lower()
                                _mime = "image/jpeg" if _ext in (".jpg", ".jpeg") else "image/png"
                                img_b64 = f"data:{_mime};base64,{raw}"
                        except Exception:
                            pass
                    self._json({"image": img_b64})
                elif self.path.startswith("/soundboard/audio/"):
                    # Serve raw audio file for HA media_player playback
                    parts = self.path[18:].strip("/").split("/")
                    if len(parts) == 2:
                        try:
                            pi, si = int(parts[0]), int(parts[1])
                            page_slots = app._get_page_root_slots(pi)
                            file_path = page_slots[si].get("file", "") if si < len(page_slots) else ""
                            if file_path and os.path.exists(file_path):
                                with open(file_path, "rb") as _af:
                                    body = _af.read()
                                _ext = os.path.splitext(file_path)[1].lower().lstrip(".")
                                _mime = {"mp3": "audio/mpeg", "wav": "audio/wav",
                                         "ogg": "audio/ogg", "flac": "audio/flac"}.get(_ext, "audio/mpeg")
                                self.send_response(200)
                                self.send_header("Content-Type", _mime)
                                self.send_header("Content-Length", str(len(body)))
                                self._cors()
                                self.end_headers()
                                self.wfile.write(body)
                                return
                        except Exception:
                            pass
                    self.send_response(404)
                    self._cors()
                    self.end_headers()
                elif self.path == "/ha_test_audio":
                    body = _ha_serve_test_beep()
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(body)))
                    self._cors()
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self._cors()
                    self.end_headers()

            def do_POST(self):
                if self.path.startswith("/action/"):
                    import urllib.parse as _up
                    action = _up.unquote(self.path[8:].strip("/"))
                    app._sd_action_queue.put(action)
                    self._json({"ok": True, "action": action})
                else:
                    self.send_response(404)
                    self._cors()
                    self.end_headers()

            def _cors(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

            def _json(self, data):
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._cors()
                self.end_headers()
                self.wfile.write(body)

        try:
            import http.server as _hs
            self._server = server_ref._server = _hs.HTTPServer(
                ("0.0.0.0", self.PORT), _Handler
            )
            status_cb(f"Stream Deck: HTTP ready on port {self.PORT}")
            self._server.serve_forever()
        except OSError:
            status_cb(f"Stream Deck: port {self.PORT} busy — plugin won't connect")
        except Exception as e:
            status_cb(f"Stream Deck HTTP: {e}")


# =========================
# HOME ASSISTANT HELPERS
# =========================

def _get_local_ip() -> str:
    """Return the machine's LAN IP (the address HA can reach us on)."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _make_test_beep_wav() -> bytes:
    """Generate a short 440 Hz beep as WAV bytes."""
    import math, struct, io as _io, wave as _wave
    sr, dur, freq = 44100, 0.8, 440
    n = int(sr * dur)
    samples = [int(32767 * 0.5 * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)]
    buf = _io.BytesIO()
    with _wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{n}h", *samples))
    return buf.getvalue()


def _ha_api(method: str, path: str, settings: dict, json_data: dict = None) -> dict:
    """Make an authenticated Home Assistant REST API call."""
    ha_url = settings.get("ha_url", "").rstrip("/")
    ha_token = settings.get("ha_token", "")
    if not ha_url:
        raise RuntimeError("HA URL ei asetettu")
    if not ha_token:
        raise RuntimeError("HA token ei asetettu")
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }
    url = f"{ha_url}/api{path}"
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    if method.upper() == "GET":
        r = requests.get(url, headers=headers, timeout=10, verify=False)
    else:
        r = requests.post(url, headers=headers, json=json_data or {}, timeout=10, verify=False)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {}


_HA_TEST_BEEP: bytes = b""   # cached lazily


def _ha_serve_test_beep() -> bytes:
    global _HA_TEST_BEEP
    if not _HA_TEST_BEEP:
        _HA_TEST_BEEP = _make_test_beep_wav()
    return _HA_TEST_BEEP


# =========================
# SOUNDBOARD IMPORT HELPERS
# =========================

def _sb_import_audio(src_path: str, page_index: int, slot_index: int) -> tuple[str, int, int]:
    """Convert and copy audio into soundboard data dir. Returns (dest_path, orig_bytes, new_bytes)."""
    out_dir = os.path.join(BASE_PATH, "soundboard", "audio")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{uuid.uuid4().hex}.wav")
    orig_size = os.path.getsize(src_path)

    ext = os.path.splitext(src_path)[1].lower()
    target_sr = 22050

    if ext == ".wav":
        with wave.open(src_path, "rb") as wf:
            ch, sw, sr = wf.getnchannels(), wf.getsampwidth(), wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        if sw == 1:
            data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif sw == 2:
            data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sw == 4:
            data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            data = data.reshape(-1, ch).mean(axis=1)
        if sr != target_sr:
            from scipy.signal import resample as _resamp
            data = _resamp(data, int(len(data) * target_sr / sr))
    else:
        # Use ffmpeg (already required by Edge TTS) to convert any audio format
        tmp_wav = out_path + ".tmp.wav"
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", src_path,
                 "-ac", "1", "-ar", str(target_sr), "-sample_fmt", "s16",
                 "-f", "wav", tmp_wav],
                capture_output=True, timeout=60,
                creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0),
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode(errors="ignore").strip()[-300:])
            with wave.open(tmp_wav, "rb") as wf:
                raw = wf.readframes(wf.getnframes())
            data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpeg ei löydy — asenna ffmpeg ja lisää se PATH:iin\n"
                "(sama kuin Edge TTS tarvitsee)"
            )
        finally:
            try:
                os.remove(tmp_wav)
            except OSError:
                pass

    out_int16 = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(target_sr)
        wf.writeframes(out_int16.tobytes())

    return out_path, orig_size, os.path.getsize(out_path)


def _sb_import_image(src_path: str, page_index: int, slot_index: int) -> tuple[str, int, int]:
    """Scale and JPEG-compress image into soundboard data dir. Returns (dest_path, orig_bytes, new_bytes)."""
    out_dir = os.path.join(BASE_PATH, "soundboard", "images")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{uuid.uuid4().hex}.jpg")
    orig_size = os.path.getsize(src_path)

    px = QPixmap(src_path)
    if px.isNull():
        raise RuntimeError(f"Kuvaa ei voi avata: {src_path}")
    px = px.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio,
                   Qt.TransformationMode.SmoothTransformation)
    if not px.save(out_path, "JPEG", 55):
        raise RuntimeError(f"Kuvan tallennus epäonnistui: {out_path}")

    return out_path, orig_size, os.path.getsize(out_path)


# SOUNDBOARD BUTTON WIDGET
# =========================
class SoundboardButton(QWidget):
    """One soundboard slot — big icon centered, name below, right-click to assign."""

    clicked_play = pyqtSignal(int)
    data_changed = pyqtSignal(int)
    swap_requested = pyqtSignal(int, int, int, int)   # src_page, src_slot, dst_page, dst_slot
    bulk_import_requested = pyqtSignal(int, list)     # start_slot, [paths]

    _edit_mode: bool = False
    _pixabay_api_key: str = ""

    @classmethod
    def set_edit_mode(cls, enabled: bool):
        cls._edit_mode = enabled

    @classmethod
    def set_pixabay_key(cls, key: str):
        cls._pixabay_api_key = key

    @staticmethod
    def _wrap_label(name: str) -> str:
        """Break name into max 2 lines of ~12 chars each."""
        if len(name) <= 12:
            return name
        words = name.split()
        if len(words) == 1:
            return name[:11] + "…"
        line1 = ""
        split_idx = len(words)
        for i, w in enumerate(words):
            test = (line1 + (" " if line1 else "") + w)
            if len(test) <= 12:
                line1 = test
            else:
                split_idx = i
                break
        if not line1:
            return name[:11] + "…"
        if split_idx == len(words):
            return line1
        line2 = " ".join(words[split_idx:])
        if len(line2) > 13:
            line2 = line2[:12] + "…"
        return line1 + "\n" + line2

    # Size class vars — updated by set_size_mode()
    _BTN_W: int = 74
    _BTN_H: int = 70
    _ICON_W: int = 48
    _ICON_H: int = 36
    _FONT_SIZE: int = 9

    _STYLE_IDLE = T(
        "QToolButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #131c3a, stop:1 #0a0f22);"
        " border: 2px solid @BORDER; border-radius: 10px;"
        " color: @TEXT_DIM; font-size: 10px; font-weight: 700;"
        " padding-bottom: 2px; }"
        "QToolButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #1b2850, stop:1 #101830);"
        " border: 2px solid @PURPLE; color: #e0e8ff; }"
        "QToolButton:pressed { background: @BG_INPUT; border: 2px solid @BLUE; }"
        "QToolButton:focus { border: 2px solid @BORDER; outline: none; }"
    )
    _STYLE_PLAY = T(
        "QToolButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #0a2818, stop:1 #06160c);"
        " border: 2px solid @GREEN; border-radius: 10px;"
        " color: @GREEN; font-size: 10px; font-weight: 700; padding-bottom: 2px; }"
        "QToolButton:focus { outline: none; }"
    )
    _STYLE_DRAG = T(
        "QToolButton { background: @BG_INPUT; border: 2px dashed @BLUE; border-radius: 10px;"
        " color: @BLUE; font-size: 10px; font-weight: 700; padding-bottom: 2px; }"
        "QToolButton:focus { outline: none; }"
    )
    _STYLE_LINK = T(
        "QToolButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #0a1428, stop:1 #060c18);"
        " border: 2px solid @BLUE_DIM; border-radius: 10px;"
        " color: @BLUE; font-size: 10px; font-weight: 700;"
        " padding-bottom: 2px; }"
        "QToolButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #142040, stop:1 #0a1828);"
        " border: 2px solid @BLUE; color: @BLUE_BRIGHT; }"
        "QToolButton:pressed { background: #060c18; border: 2px solid @PURPLE; }"
        "QToolButton:focus { outline: none; }"
    )
    _STYLE_FOLDER = T(
        "QToolButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #1a1400, stop:1 #0e0a00);"
        " border: 2px solid @GOLD_DIM; border-radius: 10px;"
        " color: @GOLD; font-size: 10px; font-weight: 700;"
        " padding-bottom: 2px; }"
        "QToolButton:hover { border: 2px solid @GOLD; color: @GOLD_BRIGHT; }"
        "QToolButton:pressed { background: #0e0a00; border: 2px solid @GOLD; }"
        "QToolButton:focus { outline: none; }"
    )
    _STYLE_FOLDER_DRAG = T(
        "QToolButton { background: #1a1400; border: 2px dashed @GOLD; border-radius: 10px;"
        " color: @GOLD_BRIGHT; font-size: 10px; font-weight: 700; padding-bottom: 2px; }"
        "QToolButton:focus { outline: none; }"
    )
    _STYLE_BACK = T(
        "QToolButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #171232, stop:1 #0c0a1e);"
        " border: 2px solid @PURPLE_DIM; border-radius: 10px;"
        " color: @PURPLE_BRIGHT; font-size: 10px; font-weight: 700;"
        " padding-bottom: 2px; }"
        "QToolButton:hover { border: 2px solid @PURPLE; color: #d0c0ff; }"
        "QToolButton:pressed { background: #0c0a1e; border: 2px solid @BLUE; }"
        "QToolButton:focus { outline: none; }"
    )
    _STYLE_HA = T(
        "QToolButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #001a1a, stop:1 #000e0e);"
        " border: 2px solid #00b3b3; border-radius: 10px;"
        " color: @CYAN; font-size: 10px; font-weight: 700;"
        " padding-bottom: 2px; }"
        "QToolButton:hover { border: 2px solid #00ffff; color: #80ffff; }"
        "QToolButton:pressed { background: #000e0e; border: 2px solid #009999; }"
        "QToolButton:focus { outline: none; }"
    )

    @classmethod
    def set_size_mode(cls, mode: str):
        if mode == "small":
            cls._BTN_W, cls._BTN_H = 82, 58
            cls._ICON_W, cls._ICON_H = 52, 34
            cls._FONT_SIZE = 8
        else:
            cls._BTN_W, cls._BTN_H = 74, 70
            cls._ICON_W, cls._ICON_H = 48, 36
            cls._FONT_SIZE = 9
        fs = cls._FONT_SIZE
        for attr in ("_STYLE_IDLE", "_STYLE_PLAY", "_STYLE_DRAG", "_STYLE_LINK",
                     "_STYLE_FOLDER", "_STYLE_FOLDER_DRAG", "_STYLE_BACK", "_STYLE_HA"):
            s = getattr(cls, attr)
            for old in (7, 8, 9, 10, 11):
                s = s.replace(f"font-size: {old}px", f"font-size: {fs}px")
            setattr(cls, attr, s)

    def __init__(self, page_index: int, slot_index: int, parent=None):
        super().__init__(parent)
        self.page_index = page_index
        self.slot_index = slot_index
        self._data = {"name": f"Slot {slot_index + 1}", "file": "", "image": "", "link_page_name": ""}
        self._drag_start: QPoint | None = None
        self.setFixedSize(self._BTN_W, self._BTN_H)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._btn = QToolButton()
        self._btn.setFixedSize(self._BTN_W, self._BTN_H)
        self._btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._btn.setIconSize(QSize(self._ICON_W, self._ICON_H))
        self._btn.setStyleSheet(self._STYLE_IDLE)
        self._btn.clicked.connect(lambda: self.clicked_play.emit(self.slot_index))
        self._btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._btn.customContextMenuRequested.connect(self._ctx_menu)
        self._btn.setAcceptDrops(True)
        self._btn.installEventFilter(self)
        lay.addWidget(self._btn)
        self.setAcceptDrops(True)

        self._refresh()

    def set_data(self, d: dict):
        self._data = dict(d)
        if "link_page_name" not in self._data:
            self._data["link_page_name"] = ""
        self._refresh()
        # Back-button slots are not draggable or context-menu editable
        _is_back = bool(self._data.get("_back"))
        self._btn.setContextMenuPolicy(
            Qt.ContextMenuPolicy.NoContextMenu if _is_back
            else Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._btn.setAcceptDrops(not _is_back)
        self.setAcceptDrops(not _is_back)

    def get_data(self) -> dict:
        return dict(self._data)

    def set_playing(self, playing: bool):
        if not self._data.get("link_page_name"):
            self._btn.setStyleSheet(self._STYLE_PLAY if playing else self._STYLE_IDLE)

    # ---- drag-and-drop ----

    _IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
    _AUDIO_EXTS = {'.wav', '.mp3', '.ogg', '.flac', '.aiff', '.aif'}
    _SLOT_MIME = "application/x-soundboard-slot"

    def eventFilter(self, obj, event):
        if obj is self._btn:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress:
                if SoundboardButton._edit_mode and event.button() == Qt.MouseButton.LeftButton:
                    self._drag_start = event.position().toPoint()
                return False
            if t == QEvent.Type.MouseMove:
                if (SoundboardButton._edit_mode and self._drag_start is not None
                        and event.buttons() & Qt.MouseButton.LeftButton):
                    dist = (event.position().toPoint() - self._drag_start).manhattanLength()
                    if dist >= QApplication.startDragDistance():
                        self._drag_start = None
                        self._start_slot_drag()
                        return True
                return False
            if t == QEvent.Type.MouseButtonRelease:
                self._drag_start = None
                return False
            if t == QEvent.Type.DragEnter:
                self._on_drag_enter(event)
                return True
            if t == QEvent.Type.DragMove:
                if SoundboardButton._edit_mode:
                    event.acceptProposedAction()
                else:
                    event.ignore()
                return True
            if t == QEvent.Type.DragLeave:
                self._restore_style()
                return True
            if t == QEvent.Type.Drop:
                self._on_drop(event)
                return True
        return super().eventFilter(obj, event)

    # Override drag methods on the outer QWidget so EXE OLE drops work even
    # when Qt's hit-testing lands on this widget instead of _btn.
    def dragEnterEvent(self, event):
        self._on_drag_enter(event)

    def dragMoveEvent(self, event):
        if SoundboardButton._edit_mode:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._restore_style()

    def dropEvent(self, event):
        self._on_drop(event)

    def _restore_style(self):
        if self._data.get("_back"):
            self._btn.setStyleSheet(self._STYLE_BACK)
        elif self._data.get("subfolder"):
            self._btn.setStyleSheet(self._STYLE_FOLDER)
        elif self._data.get("link_page_name"):
            self._btn.setStyleSheet(self._STYLE_LINK)
        else:
            self._btn.setStyleSheet(self._STYLE_IDLE)

    def _start_slot_drag(self):
        mime = QMimeData()
        payload = json.dumps({"page": self.page_index, "slot": self.slot_index}).encode()
        mime.setData(self._SLOT_MIME, payload)
        drag = QDrag(self._btn)
        drag.setMimeData(mime)
        px = self._btn.grab().scaled(54, 51, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        drag.setPixmap(px)
        drag.setHotSpot(QPoint(px.width() // 2, px.height() // 2))
        drag.exec(Qt.DropAction.MoveAction)

    def _on_drag_enter(self, event):
        if not SoundboardButton._edit_mode:
            event.ignore()
            return
        mime = event.mimeData()
        if mime.hasFormat(self._SLOT_MIME):
            try:
                info = json.loads(bytes(mime.data(self._SLOT_MIME)).decode())
                if info["page"] == self.page_index and info["slot"] == self.slot_index:
                    event.ignore()
                    return
            except Exception:
                pass
            event.acceptProposedAction()
            self._btn.setStyleSheet(self._STYLE_DRAG)
            return
        # Accept unconditionally in edit mode — mime.hasUrls() is unreliable at
        # DragEnter time for Windows OLE file drags in frozen EXE (lazy loading).
        # File type is validated in _on_drop where mime.urls() is always populated.
        style = self._STYLE_DRAG
        if self._data.get("subfolder") and mime.hasUrls():
            for url in mime.urls():
                if os.path.splitext(url.toLocalFile())[1].lower() in self._IMAGE_EXTS:
                    style = self._STYLE_FOLDER_DRAG
                    break
        event.acceptProposedAction()
        self._btn.setStyleSheet(style)

    def _on_drop(self, event):
        self._restore_style()
        if not SoundboardButton._edit_mode:
            event.ignore()
            return
        mime = event.mimeData()
        if mime.hasFormat(self._SLOT_MIME):
            try:
                info = json.loads(bytes(mime.data(self._SLOT_MIME)).decode())
                src_p, src_s = info["page"], info["slot"]
                if src_p == self.page_index and src_s == self.slot_index:
                    event.ignore()
                    return
                self.swap_requested.emit(src_p, src_s, self.page_index, self.slot_index)
                event.acceptProposedAction()
            except Exception:
                event.ignore()
            return
        if mime.hasUrls():
            audio_files = []
            image_file = None
            for url in mime.urls():
                path = url.toLocalFile()
                if os.path.isdir(path):
                    for fn in sorted(os.listdir(path)):
                        if os.path.splitext(fn)[1].lower() in self._AUDIO_EXTS:
                            audio_files.append(os.path.join(path, fn))
                else:
                    ext = os.path.splitext(path)[1].lower()
                    if ext in self._AUDIO_EXTS:
                        audio_files.append(path)
                    elif ext in self._IMAGE_EXTS and image_file is None:
                        image_file = path
            if len(audio_files) > 1:
                self.bulk_import_requested.emit(self.slot_index, audio_files)
            elif len(audio_files) == 1:
                self._drop_sound(audio_files[0])
            if image_file and not audio_files:
                self._drop_image(image_file)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drop_image(self, path: str):
        try:
            dest, _, _ = _sb_import_image(path, self.page_index, self.slot_index)
            self._data["image"] = dest
            self._notify_status(f"Soundboard {self.slot_index+1}: kuva pudotettu")
        except Exception:
            self._data["image"] = path
        self._refresh()
        self.data_changed.emit(self.slot_index)

    def _drop_sound(self, path: str):
        try:
            dest, _, _ = _sb_import_audio(path, self.page_index, self.slot_index)
            self._data["file"] = dest
            self._notify_status(f"Soundboard {self.slot_index+1}: ääni pudotettu")
        except Exception:
            self._data["file"] = path
        if not self._data.get("name") or self._data["name"].startswith("Slot "):
            self._data["name"] = os.path.splitext(os.path.basename(path))[0]
        self._refresh()
        self.data_changed.emit(self.slot_index)

    def _make_icon_pixmap(self, size: int) -> QPixmap:
        img_path = self._data.get("image", "")
        px = QPixmap(size, size)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 8
        inner = QRectF(2, 2, size - 4, size - 4)
        has_img = bool(img_path and os.path.exists(img_path))
        if has_img:
            src = QPixmap(img_path)
            has_img = not src.isNull()
        if has_img:
            scaled = src.scaled(size - 4, size - 4,
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation)
            ox = (scaled.width() - (size - 4)) // 2
            oy = (scaled.height() - (size - 4)) // 2
            cropped = scaled.copy(ox, oy, size - 4, size - 4)
            clip = QPainterPath()
            clip.addRoundedRect(inner, r, r)
            p.setClipPath(clip)
            p.drawPixmap(2, 2, cropped)
            p.setClipping(False)
            pen = QPen(QColor(THEME["PURPLE"]))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.drawRoundedRect(inner, r, r)
        else:
            clip = QPainterPath()
            clip.addRoundedRect(inner, r, r)
            p.setClipPath(clip)
            p.fillRect(inner.toRect(), QColor("#0a0f22"))
            p.setClipping(False)
            p.setPen(QColor(THEME["BLUE"]))
            p.setFont(QFont("Segoe UI", size // 3))
            p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "♪")
            pen = QPen(QColor(THEME["BORDER"]))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.drawRoundedRect(inner, r, r)
        p.end()
        return px

    def _make_folder_pixmap(self, size: int) -> QPixmap:
        px = QPixmap(size, size)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        inner = QRectF(2, 2, size - 4, size - 4)
        clip = QPainterPath()
        clip.addRoundedRect(inner, 8, 8)
        p.setClipPath(clip)
        p.fillRect(inner.toRect(), QColor("#0E0A00"))
        p.setClipping(False)
        p.setPen(QColor(THEME["GOLD"]))
        p.setFont(QFont("Segoe UI", size // 3))
        p.drawText(QRectF(0, 0, size, size - 4), Qt.AlignmentFlag.AlignCenter, "📁")
        pen = QPen(QColor(THEME["GOLD_DIM"]))
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.drawRoundedRect(inner, 8, 8)
        p.end()
        return px

    def _make_link_pixmap(self, size: int) -> QPixmap:
        px = QPixmap(size, size)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        inner = QRectF(2, 2, size - 4, size - 4)
        clip = QPainterPath()
        clip.addRoundedRect(inner, 8, 8)
        p.setClipPath(clip)
        p.fillRect(inner.toRect(), QColor("#060C18"))
        p.setClipping(False)
        p.setPen(QColor(THEME["BLUE"]))
        p.setFont(QFont("Segoe UI", size // 3))
        p.drawText(QRectF(0, 0, size, size - 4), Qt.AlignmentFlag.AlignCenter, "▶")
        pen = QPen(QColor(THEME["BLUE_DIM"]))
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.drawRoundedRect(inner, 8, 8)
        p.end()
        return px

    def _refresh(self):
        link_name = self._data.get("link_page_name", "")
        name = self._data.get("name") or f"Slot {self.slot_index + 1}"
        display = self._wrap_label(name)
        _isz = self._ICON_H
        if self._data.get("_back"):
            self._btn.setIcon(QIcon())
            self._btn.setText("◀ Takaisin")
            self._btn.setToolTip("Palaa edelliselle sivulle")
            self._btn.setStyleSheet(self._STYLE_BACK)
        elif self._data.get("subfolder"):
            _img = self._data.get("image", "")
            if _img and os.path.exists(_img):
                self._btn.setIcon(QIcon(self._make_icon_pixmap(_isz)))
            else:
                self._btn.setIcon(QIcon(self._make_folder_pixmap(_isz)))
            self._btn.setText(display)
            self._btn.setToolTip(f"📁 Kansio: {name}")
            self._btn.setStyleSheet(self._STYLE_FOLDER)
        elif link_name:
            self._btn.setIcon(QIcon(self._make_link_pixmap(_isz)))
            self._btn.setText(display)
            self._btn.setToolTip(f"→ Sivu: {link_name}")
            self._btn.setStyleSheet(self._STYLE_LINK)
        elif self._data.get("ha_players"):
            self._btn.setIcon(QIcon(self._make_icon_pixmap(_isz)))
            self._btn.setText(display)
            ha_names = ", ".join(self._data.get("ha_players", []))
            self._btn.setToolTip(f"HA: {ha_names}\n{name}")
            self._btn.setStyleSheet(self._STYLE_HA)
        else:
            self._btn.setIcon(QIcon(self._make_icon_pixmap(_isz)))
            self._btn.setText(display)
            self._btn.setToolTip(name + ("\n" + self._data["file"] if self._data.get("file") else ""))
            self._btn.setStyleSheet(self._STYLE_IDLE)

    def _ctx_menu(self, pos):
        if not SoundboardButton._edit_mode:
            return
        menu = QMenu(self)
        menu.addAction("Assign Sound…", self._assign_sound)
        menu.addAction("Generoi TTS-ääni…", self._generate_tts_sound)
        menu.addAction("Assign Image…", self._assign_image)
        menu.addAction("Etsi kuva netistä…", self._search_image_online)
        menu.addAction("Rename…", self._rename)
        menu.addAction("Volume…", self._set_volume)
        menu.addSeparator()
        menu.addAction("Bulk Import — tiedostot…", self._bulk_import_files)
        menu.addAction("Bulk Import — kansio…", self._bulk_import_folder)
        menu.addSeparator()
        menu.addAction("Link to Page…", self._assign_page_link)
        if not self._data.get("_back") and not self._data.get("subfolder"):
            menu.addAction("Kansioksi…", self._set_as_folder)
        if not self._data.get("_back"):
            menu.addSeparator()
            ha_label = "HA Media Players… (aktiivinen)" if self._data.get("ha_players") else "HA Media Players…"
            menu.addAction(ha_label, self._assign_ha_players)
        _name = self._data.get("name", "")
        has_content = bool(self._data.get("file") or self._data.get("image")
                          or self._data.get("link_page_name") or self._data.get("subfolder")
                          or self._data.get("ha_players")
                          or (_name and not _name.startswith("Slot ")))
        if has_content:
            menu.addSeparator()
            menu.addAction("Clear", self._clear)
        menu.exec(self.mapToGlobal(pos))

    def _assign_ha_players(self):
        """Open dialog to assign HA media_player entities to this soundboard slot."""
        # Walk up widget tree to find App and get settings
        p = self.parent()
        app = None
        while p is not None:
            if hasattr(p, "settings"):
                app = p
                break
            p = p.parent()
        ha_players_cfg = app.settings.get("ha_players", []) if app else []
        if not ha_players_cfg:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "HA ei konfiguroitu",
                "Määritä ensin Home Assistant -yhteys Asetukset → Home Assistant -välilehdellä."
            )
            return

        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QCheckBox, QLabel
        dlg = QDialog(self)
        dlg.setWindowTitle(f"HA Media Players — {self._data.get('name', 'Slot')}")
        dlg.resize(380, 300)
        dlg.setStyleSheet(
            "QDialog { background: #05070f; color: #b9c5e6; }"
            "QCheckBox { color: #b9c5e6; font-size: 13px; padding: 4px; }"
            "QPushButton { background: #101a36; border: 1px solid #1c2c52; border-radius: 5px;"
            " color: #b9c5e6; padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #6aa8ff; border-color: #6aa8ff; }"
            "QLabel { color: #8a9bc4; font-size: 11px; }"
        )
        vbox = QVBoxLayout(dlg)
        vbox.setContentsMargins(16, 12, 16, 12)
        vbox.setSpacing(6)
        lbl = QLabel("Valitse HA media_player -laitteet joille ääni lähetetään:")
        lbl.setStyleSheet("color: #b9c5e6; font-size: 12px; font-weight: 600; padding-bottom: 4px;")
        vbox.addWidget(lbl)

        current_players = set(self._data.get("ha_players", []))
        checkboxes = []
        for cfg in ha_players_cfg:
            eid = cfg.get("entity_id", "")
            friendly = cfg.get("name", "") or eid
            cb = QCheckBox(f"{friendly}  ({eid})")
            cb.setChecked(eid in current_players)
            cb.setProperty("entity_id", eid)
            vbox.addWidget(cb)
            checkboxes.append(cb)

        vbox.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        vbox.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = [cb.property("entity_id") for cb in checkboxes if cb.isChecked()]
            self._data["ha_players"] = selected
            self._refresh()
            self.data_changed.emit(self.slot_index)

    def _generate_tts_sound(self):
        """Open a dialog to generate TTS audio and save it to this soundboard slot."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
            QComboBox as _QCB, QPushButton as _QPB,
        )
        import threading as _thr

        # Walk up to find App instance for settings
        p = self.parent()
        app = None
        while p is not None:
            if hasattr(p, "settings"):
                app = p
                break
            p = p.parent()

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Generoi TTS-ääni — {self._data.get('name', 'Slot')}")
        dlg.resize(460, 300)
        dlg.setStyleSheet(
            "QDialog { background: #05070f; color: #b9c5e6; font-family: 'Segoe UI', sans-serif; }"
            "QLabel { color: #b9c5e6; font-size: 12px; }"
            "QTextEdit { background: #0a0f1e; border: 1px solid #1c2c52; border-radius: 5px;"
            " color: #dce6ff; font-size: 13px; padding: 4px; }"
            "QComboBox { background: #101a36; border: 1px solid #1c2c52; border-radius: 5px;"
            " color: #dce6ff; padding: 4px 8px; min-height: 22px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #0a0f1e; color: #dce6ff; }"
            "QPushButton { background: #101a36; border: 1px solid #1c2c52; border-radius: 5px;"
            " color: #b9c5e6; padding: 6px 18px; font-size: 12px; }"
            "QPushButton:hover { background: #2e7fff; border-color: #2e7fff; color: #fff; }"
            "QPushButton:disabled { background: #0a0f1e; color: #546a94; border-color: #101a36; }"
        )

        vbox = QVBoxLayout(dlg)
        vbox.setContentsMargins(16, 14, 16, 14)
        vbox.setSpacing(8)

        vbox.addWidget(QLabel("Teksti puhuttavaksi:"))
        text_edit = QTextEdit()
        text_edit.setMaximumHeight(80)
        text_edit.setPlaceholderText("Kirjoita teksti…")
        vbox.addWidget(text_edit)

        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)
        backend_combo = _QCB()
        backend_combo.addItems(["Edge TTS (free)", "ElevenLabs", "OpenAI TTS"])
        if app:
            backend_combo.setCurrentText(app.settings.get("default_tts_backend", "Edge TTS (free)"))
        lang_combo = _QCB()
        for _l in LANGS:
            if _l != "Auto":
                lang_combo.addItem(_l)
        if app and hasattr(app, "langbox"):
            cur = app.langbox.currentText()
            if lang_combo.findText(cur) >= 0:
                lang_combo.setCurrentText(cur)
        opt_row.addWidget(QLabel("Backend:"))
        opt_row.addWidget(backend_combo, 1)
        opt_row.addWidget(QLabel("Kieli:"))
        opt_row.addWidget(lang_combo, 1)
        vbox.addLayout(opt_row)

        status_lbl = QLabel("")
        status_lbl.setStyleSheet("color: #8a9bc4; font-size: 11px;")
        vbox.addWidget(status_lbl)

        btn_row = QHBoxLayout()
        preview_btn = _QPB("Generoi & Esikatselu")
        save_btn = _QPB("Tallenna napille")
        save_btn.setEnabled(False)
        btn_row.addWidget(preview_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        vbox.addLayout(btn_row)

        _wav = [None]

        def _do_generate(then_save=False):
            text = text_edit.toPlainText().strip()
            if not text:
                status_lbl.setText("Kirjoita ensin teksti.")
                return
            backend = backend_combo.currentText()
            lang = lang_combo.currentText()
            preview_btn.setEnabled(False)
            save_btn.setEnabled(False)
            status_lbl.setText("Generoidaan…")

            def _worker():
                try:
                    if backend == "ElevenLabs":
                        wav_bytes = request_tts_wav(text)
                    elif backend.startswith("Edge TTS"):
                        import asyncio as _aio
                        wav_bytes = _aio.run(request_edge_tts_wav(text, lang))
                    else:
                        if not client:
                            raise RuntimeError("OpenAI API-avain puuttuu asetuksista.")
                        resp = client.audio.speech.create(
                            model="tts-1", voice="alloy", input=text
                        )
                        mp3_bytes = resp.content
                        import tempfile as _tf
                        with _tf.NamedTemporaryFile(suffix=".mp3", delete=False) as _m:
                            _m.write(mp3_bytes)
                            _mp3 = _m.name
                        with _tf.NamedTemporaryFile(suffix=".wav", delete=False) as _w:
                            _wp = _w.name
                        try:
                            subprocess.run(
                                ["ffmpeg", "-y", "-i", _mp3,
                                 "-ar", "22050", "-ac", "1", "-f", "wav", _wp],
                                capture_output=True, timeout=30,
                                creationflags=(subprocess.CREATE_NO_WINDOW
                                               if sys.platform == "win32" else 0),
                            )
                            with open(_wp, "rb") as _f:
                                wav_bytes = _f.read()
                        finally:
                            for _pp in (_mp3, _wp):
                                try: os.remove(_pp)
                                except: pass
                    _wav[0] = wav_bytes
                    QTimer.singleShot(0, lambda wb=wav_bytes: _on_done(wb, then_save))
                except Exception as exc:
                    QTimer.singleShot(0, lambda e=str(exc): _on_err(e))

            _thr.Thread(target=_worker, daemon=True).start()

        def _on_done(wav_bytes, then_save):
            kb = len(wav_bytes) // 1024
            status_lbl.setText(f"Valmis — {kb} KB. Kuunnellaan…")
            preview_btn.setEnabled(True)
            save_btn.setEnabled(True)
            _thr.Thread(target=lambda: play_wav_bytes(wav_bytes), daemon=True).start()
            if then_save:
                _do_save()

        def _on_err(msg):
            status_lbl.setText(f"Virhe: {msg[:100]}")
            preview_btn.setEnabled(True)

        def _do_save():
            if not _wav[0]:
                _do_generate(then_save=True)
                return
            import tempfile as _tf
            with _tf.NamedTemporaryFile(suffix=".wav", delete=False) as _t:
                _t.write(_wav[0])
                _tmp = _t.name
            try:
                dest, _, _ = _sb_import_audio(_tmp, self.page_index, self.slot_index)
                self._data["file"] = dest
                self._data["link_page_name"] = ""
                txt = text_edit.toPlainText().strip()
                if not self._data.get("name") or self._data["name"].startswith("Slot "):
                    self._data["name"] = txt[:20] if txt else "TTS"
                self._refresh()
                self.data_changed.emit(self.slot_index)
                status_lbl.setText("Tallennettu napille!")
                save_btn.setEnabled(False)
            except Exception as exc:
                status_lbl.setText(f"Tallennusvirhe: {exc}")
            finally:
                try: os.remove(_tmp)
                except: pass

        preview_btn.clicked.connect(lambda: _do_generate(then_save=False))
        save_btn.clicked.connect(_do_save)
        dlg.exec()

    def _assign_sound(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Assign Sound", "",
            "Audio files (*.wav *.mp3 *.ogg *.flac *.aiff)"
        )
        if not path:
            return
        try:
            dest, orig, new = _sb_import_audio(path, self.page_index, self.slot_index)
            self._data["file"] = dest
            self._data["link_page_name"] = ""
            ratio = (1 - new / orig) * 100 if orig > 0 else 0
            self._notify_status(
                f"Soundboard {self.slot_index+1}: ääni tuotu "
                f"({orig//1024} KB → {new//1024} KB, -{ratio:.0f}%)"
            )
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Tuontivirhe", str(e))
            self._data["file"] = path
            self._data["link_page_name"] = ""
        if not self._data.get("name") or self._data["name"].startswith("Slot "):
            self._data["name"] = os.path.splitext(os.path.basename(path))[0]
        self._refresh()
        self.data_changed.emit(self.slot_index)

    def _assign_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Assign Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if not path:
            return
        try:
            dest, orig, new = _sb_import_image(path, self.page_index, self.slot_index)
            self._data["image"] = dest
            ratio = (1 - new / orig) * 100 if orig > 0 else 0
            self._notify_status(
                f"Soundboard {self.slot_index+1}: kuva tuotu "
                f"({orig//1024} KB → {new//1024} KB, -{ratio:.0f}%)"
            )
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Tuontivirhe", str(e))
            self._data["image"] = path
        self._refresh()
        self.data_changed.emit(self.slot_index)

    def _assign_page_link(self):
        p = self.parent()
        app = None
        while p is not None:
            if hasattr(p, "_sb_tabs"):
                app = p
                break
            p = p.parent()
        if app is None:
            return
        all_pages = [app._sb_tabs.tabText(i) for i in range(app._sb_tabs.count())]
        own_name = all_pages[self.page_index] if self.page_index < len(all_pages) else ""
        choices = [pg for pg in all_pages if pg != own_name]
        if not choices:
            return
        current = self._data.get("link_page_name", "")
        idx = choices.index(current) if current in choices else 0
        choice, ok = QInputDialog.getItem(
            self, "Linkki sivulle", "Valitse sivu:", choices, idx, False
        )
        if ok and choice:
            self._data["link_page_name"] = choice
            self._data["file"] = ""
            if not self._data.get("name") or self._data["name"].startswith("Slot "):
                self._data["name"] = f"→ {choice}"
            self._refresh()
            self.data_changed.emit(self.slot_index)

    def _notify_status(self, msg: str):
        p = self.parent()
        while p is not None:
            if isinstance(p, QWidget) and hasattr(p, "append_status"):
                p.append_status(msg)
                return
            p = p.parent()

    def _rename(self):
        text, ok = QInputDialog.getText(
            self, "Rename Slot", "Button name:",
            text=self._data.get("name", f"Slot {self.slot_index + 1}")
        )
        if ok and text.strip():
            self._data["name"] = text.strip()
            self._refresh()
            self.data_changed.emit(self.slot_index)

    def _set_volume(self):
        current = int(self._data.get("volume", 1.0) * 100)
        val, ok = QInputDialog.getInt(
            self, "Slot volyymi", "Volyymi % (10–200):", current, 10, 200, 5
        )
        if ok:
            self._data["volume"] = val / 100.0
            self.data_changed.emit(self.slot_index)

    def _clear(self):
        sb_dir = os.path.realpath(os.path.join(BASE_PATH, "soundboard"))
        for key in ("file", "image"):
            path = self._data.get(key, "")
            if path and os.path.isfile(path):
                try:
                    if os.path.realpath(path).startswith(sb_dir):
                        os.remove(path)
                except Exception:
                    pass
        self._data = {"name": f"Slot {self.slot_index + 1}", "file": "", "image": "", "link_page_name": "", "volume": 1.0}
        self._refresh()
        self.data_changed.emit(self.slot_index)

    def _set_as_folder(self):
        name = self._data.get("name", "")
        if not name or name.startswith("Slot "):
            name, ok = QInputDialog.getText(self, "Kansion nimi", "Nimi kansiolle:")
            if not ok or not name.strip():
                return
            name = name.strip()
        self._data["subfolder"] = True
        self._data["name"] = name
        self._data["file"] = ""
        self._data["link_page_name"] = ""
        if "folder_slots" not in self._data:
            self._data["folder_slots"] = [
                {"name": f"Slot {i+1}", "file": "", "image": "", "link_page_name": ""}
                for i in range(55)
            ]
        self._refresh()
        self.data_changed.emit(self.slot_index)

    def _bulk_import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Valitse äänitiedostot", "",
            "Audio files (*.wav *.mp3 *.ogg *.flac *.aiff)"
        )
        if paths:
            self.bulk_import_requested.emit(self.slot_index, sorted(paths))

    def _bulk_import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Valitse kansio")
        if not folder:
            return
        paths = sorted(
            os.path.join(folder, fn) for fn in os.listdir(folder)
            if os.path.splitext(fn)[1].lower() in self._AUDIO_EXTS
        )
        if paths:
            self.bulk_import_requested.emit(self.slot_index, paths)

    def _search_image_online(self):
        import re as _re
        import queue as _q

        query_init = self._data.get("name", "")
        if query_init.startswith("Slot "):
            query_init = ""

        dlg = QDialog(self)
        dlg.setWindowTitle("Etsi kuva netistä")
        dlg.resize(740, 580)
        dlg.setStyleSheet(
            "QDialog { background: #070b16; }"
            "QScrollArea { background: #070b16; border: 1px solid #222; border-radius: 6px; }"
            "QWidget#grid_bg { background: #070b16; }"
        )

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        # ── Search bar ──────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        query_edit = QLineEdit(query_init)
        query_edit.setPlaceholderText("Hakusana…")
        query_edit.setStyleSheet(
            "QLineEdit { background: #101a36; color: #dce6ff; border: 1px solid #333;"
            " border-radius: 5px; padding: 6px 10px; font-size: 13px; }"
            "QLineEdit:focus { border-color: #2e7fff; }"
        )
        search_btn = QPushButton("Hae")
        search_btn.setFixedWidth(70)
        search_btn.setStyleSheet(
            "QPushButton { background: #2e7fff; color: #fff; border: none; border-radius: 5px;"
            " padding: 6px 12px; font-weight: 700; }"
            "QPushButton:hover { background: #5090FF; }"
            "QPushButton:disabled { background: #333; color: #666; }"
        )
        search_row.addWidget(query_edit)
        search_row.addWidget(search_btn)
        outer.addLayout(search_row)

        status_lbl = QLabel("Kirjoita hakusana ja paina Hae")
        status_lbl.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        outer.addWidget(status_lbl)

        # ── Thumbnail grid ───────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_bg = QWidget()
        grid_bg.setObjectName("grid_bg")
        grid_lay = QGridLayout(grid_bg)
        grid_lay.setSpacing(6)
        grid_lay.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(grid_bg)
        outer.addWidget(scroll, 1)

        # ── Bottom buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        use_btn = QPushButton("Käytä valittua kuvaa")
        use_btn.setEnabled(False)
        use_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #2e7fff,stop:1 #7b2fff);"
            " color: #fff; border: none; border-radius: 5px; padding: 8px 20px; font-weight: 700; }"
            "QPushButton:hover { background: #7b2fff; }"
            "QPushButton:disabled { background: #222; color: #555; }"
        )
        cancel_btn = QPushButton("Peruuta")
        cancel_btn.setStyleSheet(
            "QPushButton { background: #101a36; color: #999; border: 1px solid #333;"
            " border-radius: 5px; padding: 8px 16px; }"
            "QPushButton:hover { border-color: #666; color: #CCC; }"
        )
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(use_btn)
        outer.addLayout(btn_row)
        cancel_btn.clicked.connect(dlg.reject)

        # ── State ────────────────────────────────────────────────────────
        THUMB_W, THUMB_H, COLS = 130, 100, 5
        SEL_STYLE  = "border: 3px solid #2e7fff; border-radius: 6px; background: #0a1428;"
        IDLE_STYLE = "border: 2px solid #1c2c52; border-radius: 6px; background: #111;"

        thumb_labels: list[QLabel] = []
        full_urls: list[str] = []
        sel_lbl   = [None]
        sel_url   = [None]

        def _clear_grid():
            for w in thumb_labels:
                grid_lay.removeWidget(w)
                w.deleteLater()
            thumb_labels.clear()
            full_urls.clear()
            sel_lbl[0] = None
            sel_url[0] = None
            use_btn.setEnabled(False)

        def _add_thumb(full_url: str, pixmap: "QPixmap"):
            idx = len(thumb_labels)
            lbl = QLabel()
            lbl.setFixedSize(THUMB_W, THUMB_H)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(IDLE_STYLE)
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            px = pixmap.scaled(THUMB_W - 6, THUMB_H - 6,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(px)
            thumb_labels.append(lbl)
            full_urls.append(full_url)
            row, col = divmod(idx, COLS)
            grid_lay.addWidget(lbl, row, col)

            def _click(_=None, _l=lbl, _u=full_url):
                if sel_lbl[0]:
                    sel_lbl[0].setStyleSheet(IDLE_STYLE)
                sel_lbl[0] = _l
                sel_url[0] = _u
                _l.setStyleSheet(SEL_STYLE)
                use_btn.setEnabled(True)

            lbl.mousePressEvent = _click

        # ── Search ───────────────────────────────────────────────────────
        def _do_search():
            q = query_edit.text().strip()
            if not q:
                return
            _clear_grid()
            status_lbl.setText("Haetaan…")
            search_btn.setEnabled(False)

            rq: _q.Queue = _q.Queue()

            def _worker():
                try:
                    api_key = SoundboardButton._pixabay_api_key
                    if not api_key:
                        rq.put(("err", "Pixabay API-avain puuttuu — lisää se Asetuksista (Käännös & TTS -välilehti)"))
                        return
                    import urllib.parse
                    url = (
                        f"https://pixabay.com/api/?key={api_key}"
                        f"&q={urllib.parse.quote(q)}&image_type=photo"
                        f"&per_page=24&safesearch=true"
                    )
                    r = requests.get(url, timeout=10)
                    r.raise_for_status()
                    hits = r.json().get("hits", [])
                    pairs = [
                        (h["largeImageURL"], h["webformatURL"])
                        for h in hits
                        if h.get("largeImageURL") and h.get("webformatURL")
                    ]
                    if not pairs:
                        rq.put(("err", "Ei kuvatuloksia — kokeile eri hakusanaa"))
                        return
                    rq.put(("ok", pairs))
                except Exception as e:
                    rq.put(("err", str(e)))

            threading.Thread(target=_worker, daemon=True).start()

            def _poll_search():
                try:
                    msg = rq.get_nowait()
                except _q.Empty:
                    return
                _t_search.stop()
                search_btn.setEnabled(True)
                if msg[0] == "err":
                    status_lbl.setText(f"Virhe: {msg[1]}")
                    return
                pairs = msg[1]
                status_lbl.setText(f"Ladataan {len(pairs)} kuvaa…")
                _load_thumbs(pairs)

            _t_search = QTimer(dlg)
            _t_search.timeout.connect(_poll_search)
            _t_search.start(200)

        # ── Thumbnail loader ─────────────────────────────────────────────
        def _load_thumbs(pairs: list):
            tq: _q.Queue = _q.Queue()
            pending = [len(pairs)]

            def _fetch(idx, full, thumb):
                for url in (thumb, full):
                    try:
                        r = requests.get(url, timeout=8)
                        px = QPixmap()
                        px.loadFromData(r.content)
                        if not px.isNull():
                            tq.put(("ok", full, px))
                            return
                    except Exception:
                        pass
                tq.put(("skip",))

            for i, (full, thumb) in enumerate(pairs):
                threading.Thread(target=_fetch, args=(i, full, thumb), daemon=True).start()

            added = [0]

            def _drain():
                try:
                    while True:
                        item = tq.get_nowait()
                        pending[0] -= 1
                        if item[0] == "ok":
                            _add_thumb(item[1], item[2])
                            added[0] += 1
                except _q.Empty:
                    pass
                if pending[0] <= 0:
                    _t_drain.stop()
                    status_lbl.setText(f"{added[0]} kuvaa — valitse ja paina 'Käytä'")

            _t_drain = QTimer(dlg)
            _t_drain.timeout.connect(_drain)
            _t_drain.start(100)

        # ── Download & save ───────────────────────────────────────────────
        def _use_selected():
            url = sel_url[0]
            if not url:
                return
            use_btn.setEnabled(False)
            use_btn.setText("Ladataan…")

            dq: _q.Queue = _q.Queue()

            def _dl():
                try:
                    r = requests.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=20,
                    )
                    r.raise_for_status()
                    ct = r.headers.get("content-type", "")
                    ext = ".png" if "png" in ct else ".gif" if "gif" in ct else ".jpg"
                    fd, tmp = tempfile.mkstemp(suffix=ext)
                    with os.fdopen(fd, "wb") as f:
                        f.write(r.content)
                    dq.put(("ok", tmp))
                except Exception as e:
                    dq.put(("err", str(e)))

            threading.Thread(target=_dl, daemon=True).start()

            def _poll_dl():
                try:
                    msg = dq.get_nowait()
                except _q.Empty:
                    return
                _t_dl.stop()
                use_btn.setEnabled(True)
                use_btn.setText("Käytä valittua kuvaa")
                if msg[0] == "err":
                    status_lbl.setText(f"Latausvirhe: {msg[1]}")
                    return
                tmp_path = msg[1]
                try:
                    dest, _, _ = _sb_import_image(tmp_path, self.page_index, self.slot_index)
                    self._data["image"] = dest
                except Exception:
                    self._data["image"] = tmp_path
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                self._refresh()
                self.data_changed.emit(self.slot_index)
                dlg.accept()

            _t_dl = QTimer(dlg)
            _t_dl.timeout.connect(_poll_dl)
            _t_dl.start(200)

        search_btn.clicked.connect(_do_search)
        query_edit.returnPressed.connect(_do_search)
        use_btn.clicked.connect(_use_selected)

        if query_init:
            _do_search()

        dlg.exec()


# =========================
# VOICE COMMAND PARSER (uses OpenAI to detect target language + translate)
# =========================
def parse_voice_command(transcript: str, default_lang: str) -> tuple[str, str]:
    """Parse a voice command transcript and return (target_language, translated_text).

    The user may say things like "translate to German, hello how are you" or
    "saksaksi mitä kuuluu" — GPT extracts the target language and translates the rest.
    If no language is specified, falls back to default_lang.
    """
    supported = ", ".join(k for k in LANGS.keys() if k != "Auto")
    prompt = (
        "You are a voice command parser for a translator app.\n"
        f"Supported target languages: {supported}.\n"
        f"Default target language (when not specified): {default_lang}.\n\n"
        "Input: a transcribed voice command that may begin with a target-language hint "
        "(in any language, e.g. 'translate to German', 'in German', 'saksaksi', 'auf Deutsch'). "
        "Detect the target language, strip the language hint, and translate the remaining "
        "message text into that target language.\n\n"
        "Respond with ONLY a JSON object: {\"language\": \"<lang>\", \"translated\": \"<translation>\"}.\n"
        "No code fences, no extra prose.\n\n"
        f"Input: {transcript}"
    )
    response = client.responses.create(model="gpt-4.1-mini", input=prompt)
    text = (getattr(response, "output_text", None) or "").strip()
    # Strip code fences if model added them anyway
    if text.startswith("```"):
        text = text.strip("`")
        # remove possible leading "json"
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        data = json.loads(text)
        lang = data.get("language", default_lang)
        translated = data.get("translated", "")
        if lang not in LANGS or lang == "Auto":
            lang = default_lang if default_lang in LANGS else "English"
        return lang, translated.strip()
    except Exception:
        return default_lang, text  # fallback: treat raw as translation


# =========================
# AUDIO DEVICE HELPERS
# =========================

def _fit_combo_dropdown(combo) -> None:
    """Widen the combo's dropdown popup so long device names are not truncated."""
    fm = combo.fontMetrics()
    if combo.count() == 0:
        return
    w = max(fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())) + 60
    combo.view().setMinimumWidth(max(w, 300))


def _best_audio_devices(channel_key: str) -> list:
    """Return one entry per device name: prefer WASAPI > DirectSound > MME > WDM-KS.
    WDM-KS is included only when no other API has the same device name (fallback).
    """
    try:
        host_apis = sd.query_hostapis()
        api_priority = {}
        wdmks_indices = set()
        for i, api in enumerate(host_apis):
            n = api["name"].lower()
            if "wdm-ks" in n or "wdm ks" in n or "kernel" in n:
                api_priority[i] = 99  # lowest priority; skip if better exists
                wdmks_indices.add(i)
            elif "wasapi" in n:
                api_priority[i] = 0
            elif "directsound" in n:
                api_priority[i] = 1
            elif "mme" in n:
                api_priority[i] = 2
            else:
                api_priority[i] = 3

        devices = list(sd.query_devices())

        # Names that have at least one non-WDM-KS entry
        non_wdm_names = {
            d["name"] for d in devices
            if d[channel_key] > 0 and d.get("hostapi", 0) not in wdmks_indices
        }
        # Names reachable via non-truncated non-WDM entry
        full_names = {
            d["name"] for d in devices
            if d[channel_key] > 0
            and api_priority.get(d.get("hostapi", 0), 99) < 99
        }

        best = {}  # name -> (priority, index)
        for i, d in enumerate(devices):
            if d[channel_key] == 0:
                continue
            api_idx = d.get("hostapi", 0)
            pri = api_priority.get(api_idx, 3)
            name = d["name"]
            # Skip WDM-KS if a non-WDM version of this device exists
            if api_idx in wdmks_indices and name in non_wdm_names:
                continue
            # Skip MME-truncated (shorter name that is prefix of a longer full name)
            if any(other != name and other.startswith(name) for other in full_names):
                continue
            if name not in best or pri < best[name][0]:
                best[name] = (pri, i)

        return [(idx, name) for name, (_, idx) in sorted(best.items())]
    except Exception:
        return []


def list_output_devices():
    return _best_audio_devices("max_output_channels")


def list_input_devices():
    return _best_audio_devices("max_input_channels")


def find_voicemeeter_device(devices):
    for index, name in devices:
        if "voicemeeter" in name.lower():
            return index
    for index, name in devices:
        if "virtual" in name.lower():
            return index
    return None


def load_history_data():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Migrate old display_lang values to plain language names
            migration_map = {
                "🇺🇸 English": "English",
                "🇩🇪 German": "German",
                "🇸🇪 Swedish": "Swedish",
                "🇫🇮 Finnish": "Finnish",
                "🇷🇺 Russian": "Russian",
                "🇮🇹 Italian": "Italian",
                "[EN] English": "English",
                "[DE] German": "German",
                "[SE] Swedish": "Swedish",
                "[FI] Finnish": "Finnish",
                "[RU] Russian": "Russian",
                "[IT] Italian": "Italian",
            }

            if "history" in data:
                for item in data["history"]:
                    if isinstance(item, dict) and "display_lang" in item:
                        item["display_lang"] = migration_map.get(item["display_lang"], item["display_lang"])
            if "favorites" in data:
                for item in data["favorites"]:
                    if isinstance(item, dict) and "display_lang" in item:
                        item["display_lang"] = migration_map.get(item["display_lang"], item["display_lang"])

            # Migrate old single device selection to multiple device selection
            if "selected_output_device" in data and "selected_output_devices" not in data:
                old_device = data["selected_output_device"]
                if isinstance(old_device, int) and old_device >= 0:
                    data["selected_output_devices"] = [old_device]
                del data["selected_output_device"]

            save_history_data(data)
            return data
    except Exception:
        pass
    return {"history": [], "favorites": []}


def save_history_data(data):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# =========================
# TRANSLATION (multi-backend)
# =========================

_GOOGLE_LANG_MAP = {
    "auto": "en", "English": "en", "German": "de", "Swedish": "sv",
    "Finnish": "fi", "Russian": "ru", "Italian": "it", "Dutch": "nl",
    "Norwegian": "no", "Danish": "da", "Romanian": "ro", "Latvian": "lv",
    "Lithuanian": "lt", "Japanese": "ja", "Chinese": "zh-CN", "Hungarian": "hu",
    "Polish": "pl", "Czech": "cs", "Catalan": "ca", "Belarusian": "be",
    "Spanish": "es", "French": "fr",
    "Turkish": "tr", "Hindi": "hi", "Hebrew": "iw",
    "Greek": "el", "Croatian": "hr", "Arabic": "ar",
}

_DEEPL_LANG_MAP = {
    "auto": "EN-US", "English": "EN-US", "German": "DE", "Swedish": "SV",
    "Finnish": "FI", "Russian": "RU", "Italian": "IT", "Dutch": "NL",
    "Norwegian": "NB", "Danish": "DA", "Romanian": "RO", "Latvian": "LV",
    "Lithuanian": "LT", "Japanese": "JA", "Chinese": "ZH", "Hungarian": "HU",
    "Polish": "PL", "Czech": "CS", "Spanish": "ES", "French": "FR",
    "Turkish": "TR", "Greek": "EL", "Arabic": "AR",
    # DeepL ei tue: Hindi, Hebrew, Croatian
}

# Whisper ISO 639-1 language codes (None = auto-detect)
_WHISPER_LANG_MAP = {
    "English": "en", "German": "de", "Swedish": "sv", "Finnish": "fi",
    "Russian": "ru", "Italian": "it", "Dutch": "nl", "Norwegian": "no",
    "Danish": "da", "Romanian": "ro", "Latvian": "lv", "Lithuanian": "lt",
    "Japanese": "ja", "Chinese": "zh", "Hungarian": "hu", "Polish": "pl",
    "Czech": "cs", "Catalan": "ca", "Belarusian": "be", "Spanish": "es",
    "French": "fr", "Turkish": "tr", "Hindi": "hi", "Hebrew": "he",
    "Greek": "el", "Croatian": "hr", "Arabic": "ar",
}


def translate_text(text: str, lang: str,
                   backend: str = "Google (free)", deepl_key: str = "") -> str:
    if backend == "Google (free)":
        from deep_translator import GoogleTranslator
        target = _GOOGLE_LANG_MAP.get(lang, lang.lower())
        try:
            return GoogleTranslator(source="auto", target=target).translate(text) or ""
        except Exception as e:
            raise RuntimeError(f"Google Translate error: {e}") from e

    if backend == "DeepL":
        if not deepl_key:
            raise RuntimeError("DeepL API-avain puuttuu. Lisää se Asetuksiin.")
        target = _DEEPL_LANG_MAP.get(lang)
        if not target:
            raise RuntimeError(f"DeepL ei tue kieltä '{lang}'. Käytä Google (free) tai OpenAI.")
        from deep_translator import DeepLTranslator
        try:
            return DeepLTranslator(api_key=deepl_key, source="auto", target=target).translate(text) or ""
        except Exception as e:
            raise RuntimeError(f"DeepL error: {e}") from e

    # OpenAI (default fallback)
    if not client:
        raise RuntimeError("OpenAI API-avain puuttuu. Lisää se Asetuksiin tai vaihda käännösmoottori.")
    if lang == "auto":
        prompt = (
            "Detect the language of the following text and translate it to natural English. "
            "Output ONLY the translated text.\n\n"
            f"{text}"
        )
    else:
        prompt = (
            f"Translate the following text to {lang}. "
            "Output ONLY the translated text.\n\n"
            f"{text}"
        )
    response = client.responses.create(model="gpt-4.1-mini", input=prompt)
    translated = getattr(response, "output_text", None)
    if translated:
        return translated.strip()
    output = getattr(response, "output", None)
    if output and len(output) > 0:
        content_items = output[0].get("content", [])
        if content_items and len(content_items) > 0:
            return content_items[0].get("text", "").strip()
    return ""


# =========================
# ELEVENLABS TTS
# =========================

def request_tts_wav(text: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.75,
        },
        "audio_format": "wav",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.content


def request_local_tts_wav(text: str) -> bytes:
    engine = pyttsx3.init()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        temp_path = tmp.name

    try:
        engine.save_to_file(text, temp_path)
        engine.runAndWait()
        with open(temp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


async def request_edge_tts_wav(text: str, lang: str) -> bytes:
    voice = EDGE_VOICES.get(lang, "en-US-AriaNeural")  # Default to English if not found
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_tmp:
        mp3_path = mp3_tmp.name
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_tmp:
        wav_path = wav_tmp.name

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(mp3_path)

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            mp3_path,
            "-ar",
            "16000",
            "-ac",
            "1",
            "-f",
            "wav",
            wav_path,
        ]
        try:
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0),
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "ffmpeg is required to convert Edge TTS MP3 output to WAV. "
                "Install ffmpeg and ensure it is on your PATH."
            ) from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to convert Edge TTS output to WAV with ffmpeg: {result.stderr.strip()}"
            )

        with open(wav_path, "rb") as f:
            wav_bytes = f.read()

        if not wav_bytes or not wav_bytes.startswith(b"RIFF"):
            raise RuntimeError("Edge TTS returned invalid WAV data after ffmpeg conversion.")

        return wav_bytes
    finally:
        for path in (mp3_path, wav_path):
            try:
                os.remove(path)
            except OSError:
                pass


def record_wav_from_mic(duration: float = 5.0, samplerate: int = 16000, channels: int = 1, device_index=None) -> bytes:
    try:
        frames = int(duration * samplerate)
        recording = sd.rec(frames, samplerate=samplerate, channels=channels, dtype="int16", device=device_index)
        sd.wait()
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(samplerate)
                wf.writeframes(recording.tobytes())
            return buffer.getvalue()
    except Exception as e:
        raise RuntimeError(f"Failed to record audio: {e}") from e


_local_whisper_model = None
_local_whisper_model_name: str = ""

def _load_local_whisper(model_name: str):
    global _local_whisper_model, _local_whisper_model_name
    if _local_whisper_model is not None and _local_whisper_model_name == model_name:
        return _local_whisper_model
    from faster_whisper import WhisperModel
    _sizes = {"tiny": "75MB", "base": "145MB", "small": "460MB"}
    print(f"[Whisper] Loading faster-whisper model '{model_name}'… (first use downloads ~{_sizes.get(model_name, '?')})")
    _local_whisper_model = WhisperModel(model_name, device="cpu", compute_type="int8")
    _local_whisper_model_name = model_name
    return _local_whisper_model


def transcribe_audio_wav(wav_bytes: bytes, language: str = None, stt_backend: str = "OpenAI Whisper API") -> str:
    try:
        if len(wav_bytes) < 100:
            return ""
        if not wav_bytes.startswith(b"RIFF"):
            return ""

        if stt_backend.startswith("Local Whisper"):
            # e.g. "Local Whisper (base)" → "base"
            model_name = "base"
            if "(" in stt_backend and ")" in stt_backend:
                model_name = stt_backend.split("(")[1].rstrip(")")
            import tempfile, os as _os
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(wav_bytes)
                tmp_path = tmp.name
            try:
                model = _load_local_whisper(model_name)
                kwargs = {}
                if language:
                    kwargs["language"] = language
                segments, _info = model.transcribe(tmp_path, **kwargs)
                text = " ".join(seg.text for seg in segments)
            finally:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass
            return text.strip() if text else ""

        # OpenAI Whisper API (default)
        with io.BytesIO(wav_bytes) as buffer:
            buffer.name = "speech.wav"
            kwargs = {"model": "whisper-1", "file": buffer}
            if language:
                kwargs["language"] = language
            response = client.audio.transcriptions.create(**kwargs)

        text = getattr(response, "text", None)
        if not text:
            text = getattr(response, "transcription", None)
        return text.strip() if text else ""
    except Exception as e:
        print(f"[DEBUG] Transcription error: {e}")
        raise


# =========================
# PLAYBACK
# =========================

def play_wav_bytes(wav_bytes: bytes, device_indices=None, level_callback=None, volume: float = 1.0,
                   stop_event: "threading.Event | None" = None):
    """Play WAV audio to one or multiple output devices simultaneously."""
    try:
        with io.BytesIO(wav_bytes) as buffer:
            with wave.open(buffer, "rb") as wf:
                channels = wf.getnchannels()
                samplerate = wf.getframerate()
                sample_width = wf.getsampwidth()
                raw_frames = wf.readframes(wf.getnframes())

        if sample_width == 1:
            audio_data = np.frombuffer(raw_frames, dtype=np.uint8).astype(np.int16) - 128
        elif sample_width == 2:
            audio_data = np.frombuffer(raw_frames, dtype=np.int16)
        elif sample_width == 4:
            audio_data = np.frombuffer(raw_frames, dtype=np.int32)
        else:
            raise ValueError(f"Unsupported WAV sample width: {sample_width}")

        if channels > 1:
            audio_data = audio_data.reshape(-1, channels)

        if volume != 1.0:
            audio_data = np.clip(audio_data.astype(np.float32) * volume, -32768, 32767).astype(np.int16)

        # Handle single device or multiple devices
        if device_indices is None:
            device_indices = []
        elif isinstance(device_indices, int):
            device_indices = [device_indices]
        elif not isinstance(device_indices, list):
            device_indices = []

        # Use sd.OutputStream per device — thread-safe, no global stream conflicts
        # Level callback is driven from inside the write loop (primary device only)
        # so it stays in sync with actual audio output instead of a free-running timer.
        device_errors: list[str] = []
        device_ok: list[bool] = []
        results_lock = threading.Lock()

        def play_to_device(device_index, report_level=False):
            ok = False
            err_msg = None
            try:
                info = sd.query_devices(device_index) if device_index is not None else sd.query_devices(sd.default.device[1])
                dev_name = info.get("name", str(device_index))
                if info['max_output_channels'] == 0:
                    err_msg = f"'{dev_name}' ei ole toistolaiteet (max_output_channels=0)"
                else:
                    sr = samplerate
                    data = audio_data
                    native_sr = int(info.get('default_samplerate') or 48000)
                    if native_sr != sr:
                        import scipy.signal
                        fa = data.astype(np.float32)
                        n_frames = fa.shape[0] if fa.ndim > 1 else len(fa)
                        new_len = max(1, int(n_frames * native_sr / sr))
                        resampled = scipy.signal.resample(fa, new_len, axis=0) if fa.ndim > 1 else scipy.signal.resample(fa, new_len)
                        data = np.clip(resampled, -32768, 32767).astype(np.int16)
                        sr = native_sr
                    n_ch = min(int(info['max_output_channels']), 2)
                    out = data.reshape(-1, 1) if data.ndim == 1 else data[:, :n_ch]
                    if out.shape[1] < n_ch:
                        out = np.column_stack([out[:, 0]] * n_ch)
                    _CHUNK = 4096  # frames per write — short enough to respond to stop quickly
                    with sd.OutputStream(device=device_index, samplerate=sr,
                                         channels=n_ch, dtype='int16', latency='low') as stream:
                        offset = 0
                        while offset < len(out):
                            if stop_event is not None and stop_event.is_set():
                                break
                            end = min(offset + _CHUNK, len(out))
                            chunk = out[offset:end]
                            stream.write(chunk)
                            if report_level and level_callback is not None:
                                flat_chunk = chunk.flatten().astype(np.float32) / 32768.0
                                level_callback(float(np.max(np.abs(flat_chunk))))
                            offset = end
                    if report_level and level_callback is not None:
                        level_callback(0.0)
                    ok = True
            except Exception as e:
                try:
                    dev_name = sd.query_devices(device_index)["name"]
                except Exception:
                    dev_name = str(device_index)
                err_msg = f"'{dev_name}': {e}"
            with results_lock:
                device_ok.append(ok)
                if err_msg:
                    device_errors.append(err_msg)

        targets = device_indices if device_indices else [None]
        threads = []
        for i, dev_idx in enumerate(targets):
            t = threading.Thread(target=play_to_device, args=(dev_idx, i == 0), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        # Only raise if every device failed — single-device errors are silent warnings
        if device_errors and not any(device_ok):
            raise RuntimeError("Äänen toisto epäonnistui:\n" + "\n".join(device_errors))

    except Exception as e:
        raise RuntimeError(f"Audio playback failed: {e}") from e


class _OctagonStopButton(QPushButton):
    """Soundboard stop button rendered as a red octagon (stop-sign shape)."""

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cut = min(w, h) // 5
        pts = [QPoint(x, y) for x, y in [
            (cut, 0), (w - cut, 0),
            (w, cut), (w, h - cut),
            (w - cut, h), (cut, h),
            (0, h - cut), (0, cut),
        ]]
        poly = QPolygon(pts)
        if self.isDown():
            fill = QColor("#ff3355")
        elif self.underMouse():
            fill = QColor("#cc1030")
        else:
            fill = QColor("#7a0f1f")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawPolygon(poly)
        pen = QPen(QColor("#ff6070"), 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(poly)
        font = QFont("Arial", 9, QFont.Weight.Black)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "STOP")
        p.end()


# =========================
# WAKE-WORD LISTENER (Picovoice Porcupine with Whisper fallback)
# =========================
class WakeListener:
    """Background wake-word detector. Uses Porcupine if available, otherwise Whisper VAD."""

    def __init__(self, on_wake_callback, on_status_callback):
        self.on_wake = on_wake_callback
        self.on_status = on_status_callback
        self._thread = None
        self._stop_flag = threading.Event()
        self._porcupine = None
        self._device_index = None
        self._mode = None
        self._keyword = "jarvis"
        self._level_callback = None
        self._stt_backend = "OpenAI Whisper API"

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, access_key: str, keyword: str, custom_ppn_path: str, device_index, level_callback=None, stt_backend: str = "OpenAI Whisper API"):
        self._keyword = keyword.lower()
        self._device_index = device_index
        self._level_callback = level_callback
        self._stt_backend = stt_backend

        # Try Picovoice Porcupine first
        if PORCUPINE_AVAILABLE and access_key:
            try:
                if custom_ppn_path and os.path.exists(custom_ppn_path):
                    self._porcupine = pvporcupine.create(
                        access_key=access_key, keyword_paths=[custom_ppn_path]
                    )
                else:
                    self._porcupine = pvporcupine.create(
                        access_key=access_key, keywords=[keyword]
                    )
                self._mode = "porcupine"
            except Exception as e:
                self.on_status(f"Porcupine init failed ({e}) — switching to Whisper mode")
                self._porcupine = None
                self._mode = "whisper"
        else:
            if not PORCUPINE_AVAILABLE:
                self.on_status("pvporcupine not installed — using Whisper wake-word mode")
            else:
                self.on_status("No Picovoice key — using Whisper wake-word mode (add key in Settings for better efficiency)")
            self._mode = "whisper"

        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._thread = None
        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None
        self._mode = None

    def _run(self):
        if self._mode == "porcupine":
            self._run_porcupine()
        else:
            self._run_whisper()

    def _run_porcupine(self):
        porcupine_sr = self._porcupine.sample_rate  # always 16000
        frame_length = self._porcupine.frame_length
        device = self._device_index

        def _get_native_sr(dev):
            try:
                idx = dev if dev is not None else sd.default.device[0]
                return int(sd.query_devices(idx).get("default_samplerate", porcupine_sr))
            except Exception:
                return porcupine_sr

        native_sr = _get_native_sr(device)

        for _attempt in range(2):
            try:
                need_resample = native_sr != porcupine_sr
                if need_resample:
                    import scipy.signal
                    native_frame = int(np.ceil(frame_length * native_sr / porcupine_sr))
                    with sd.InputStream(
                        device=device, channels=1, samplerate=native_sr,
                        blocksize=native_frame, dtype="float32",
                    ) as stream:
                        self.on_status(f"👂 Porcupine listening (native={native_sr}→{porcupine_sr} Hz)")
                        while not self._stop_flag.is_set():
                            data, _overflow = stream.read(native_frame)
                            samples = data[:, 0] if data.ndim > 1 else data.flatten()
                            if self._level_callback is not None:
                                self._level_callback(float(np.max(np.abs(samples))))
                            resampled = scipy.signal.resample(samples, frame_length).astype(np.float32)
                            pcm = (np.clip(resampled, -1.0, 1.0) * 32767).astype(np.int16)
                            result = self._porcupine.process(pcm.tolist())
                            if result >= 0:
                                self.on_status("✨ Wake-word detected!")
                                self.on_wake()
                                time.sleep(0.3)
                else:
                    with sd.InputStream(
                        device=device, channels=1, samplerate=porcupine_sr,
                        blocksize=frame_length, dtype="int16",
                    ) as stream:
                        self.on_status(f"👂 Porcupine listening (sr={porcupine_sr})")
                        while not self._stop_flag.is_set():
                            data, _overflow = stream.read(frame_length)
                            pcm = data[:, 0] if data.ndim > 1 else data
                            if self._level_callback is not None:
                                peak = float(np.max(np.abs(pcm))) / 32768.0
                                self._level_callback(peak)
                            result = self._porcupine.process(pcm.tolist())
                            if result >= 0:
                                self.on_status("✨ Wake-word detected!")
                                self.on_wake()
                                time.sleep(0.3)
                return
            except Exception as e:
                if _attempt == 0 and device is not None and "out of range" in str(e).lower():
                    self.on_status("Wake: mic not found — trying default device")
                    device = None
                    native_sr = _get_native_sr(device)
                else:
                    self.on_status(f"Wake listener stopped: {e}")
                    return

    def _run_whisper(self):
        """Streams mic continuously in 2.5s chunks, transcribes, checks for wake keyword."""
        target_sr = 16000
        chunk_duration = 2.5
        silence_threshold = 0.008
        device = self._device_index

        def _get_native_sr(dev):
            try:
                idx = dev if dev is not None else sd.default.device[0]
                return int(sd.query_devices(idx).get("default_samplerate", target_sr))
            except Exception:
                return target_sr

        native_sr = _get_native_sr(device)
        self.on_status(f"👂 Whisper mode listening for: '{self._keyword}'")

        while not self._stop_flag.is_set():
            try:
                frames = []
                peak_ref = [0.0]

                def _cb(indata, _fc, _ti, _st):
                    peak = float(np.max(np.abs(indata)))
                    if peak > peak_ref[0]:
                        peak_ref[0] = peak
                    if self._level_callback is not None:
                        self._level_callback(peak)
                    frames.append(indata.copy())

                with sd.InputStream(
                    device=device,
                    channels=1,
                    samplerate=native_sr,
                    blocksize=1024,
                    dtype="float32",
                    callback=_cb,
                ):
                    start = time.time()
                    while time.time() - start < chunk_duration and not self._stop_flag.is_set():
                        time.sleep(0.05)

                if self._stop_flag.is_set():
                    break

                if not frames:
                    continue

                audio = np.concatenate(frames, axis=0).flatten()

                if native_sr != target_sr:
                    import scipy.signal
                    new_len = int(len(audio) * target_sr / native_sr)
                    audio = scipy.signal.resample(audio, new_len).astype(np.float32)

                rms = float(np.sqrt(np.mean(audio ** 2)))
                if rms < silence_threshold:
                    continue

                audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
                wav_buf = io.BytesIO()
                with wave.open(wav_buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(target_sr)
                    wf.writeframes(audio_int16.tobytes())

                try:
                    transcript = transcribe_audio_wav(wav_buf.getvalue(), stt_backend=getattr(self, "_stt_backend", "OpenAI Whisper API"))
                    if transcript:
                        self.on_status(f"Wake heard: \"{transcript}\"")
                        if self._keyword in transcript.lower():
                            self.on_status(f"✨ Wake-word '{self._keyword}' detected!")
                            self.on_wake()
                            time.sleep(1.0)
                    else:
                        self.on_status(f"👂 Listening for: '{self._keyword}'")
                except Exception as e:
                    self.on_status(f"Wake: transcription error — {e}")
                    time.sleep(1.0)

            except Exception as e:
                if not self._stop_flag.is_set():
                    if device is not None and "out of range" in str(e).lower():
                        self.on_status("Wake: mic not found — using default device")
                        device = None
                        native_sr = _get_native_sr(device)
                    else:
                        self.on_status(f"Wake listener error: {e}")
                        time.sleep(1.0)


# =========================
class _TextboxOverlayFilter(QObject):
    """Repositions floating overlay buttons inside the textbox on resize."""
    def __init__(self, btn_right: "QPushButton", btn_left: "QPushButton" = None):
        super().__init__()
        self._right = btn_right
        self._left = btn_left

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            w, h = obj.width(), obj.height()
            if self._right:
                self._right.move(w - self._right.width() - 6, h - self._right.height() - 6)
            if self._left:
                self._left.move(6, h - self._left.height() - 6)
        return False


class SoundboardPageContainer(QWidget):
    """Soundboard page container — paints colored group backgrounds behind buttons."""

    _COLS = 19
    _BTN_W = 74
    _BTN_H = 70
    _SPACING = 6
    _MARGIN = 6
    _TOP = 6         # top margin (matches grid.setContentsMargins top)
    _MAX_ROW = 2     # 0-indexed max row index (3 rows → max=2)

    @classmethod
    def set_size_mode(cls, mode: str):
        if mode == "small":
            cls._COLS = 11
            cls._BTN_W = 82
            cls._BTN_H = 58
            cls._SPACING = 3
            cls._MAX_ROW = 4  # 5 rows → max=4
        else:
            cls._COLS = 19
            cls._BTN_W = 74
            cls._BTN_H = 70
            cls._SPACING = 6
            cls._MAX_ROW = 2  # 3 rows → max=2

    _PRESET_COLORS = [
        ("#2e7fff", "Sininen"),
        ("#7b2fff", "Violetti"),
        ("#FF4D4D", "Punainen"),
        ("#00CC6A", "Vihreä"),
        ("#FFB800", "Keltainen"),
        ("#FF7A00", "Oranssi"),
        ("#00CCCC", "Sinivihreä"),
        ("#FF4DA6", "Pinkki"),
    ]

    def __init__(self, page_index: int, groups: list, save_callback):
        super().__init__()
        self._page_index = page_index
        self._groups: list[dict] = list(groups)
        self._save_cb = save_callback
        self._group_labels: list = []

    def set_groups(self, groups: list):
        self._groups = list(groups)
        self._rebuild_group_labels()
        self.update()

    def get_groups(self) -> list:
        return list(self._groups)

    def init_group_labels(self):
        """Call once after all button children have been added to the grid."""
        self._rebuild_group_labels()

    def _slot_to_rect(self, slot_s: int, slot_e: int):
        """Return (row_s, row_e, col_s, col_e) for a slot range, layout-aware."""
        slot_s = max(0, min(54, slot_s))
        slot_e = max(slot_s, min(54, slot_e))
        r_s = slot_s // self._COLS
        r_e = slot_e // self._COLS
        if r_s == r_e:
            return r_s, r_e, slot_s % self._COLS, slot_e % self._COLS
        return r_s, r_e, 0, self._COLS - 1

    def _get_slot_range(self, grp: dict):
        if "slot_start" in grp:
            return grp["slot_start"], grp.get("slot_end", grp["slot_start"])
        # Legacy row/col → slot index (best effort)
        r_s = grp.get("row_start", 0)
        c_s = grp.get("col_start", 0)
        r_e = grp.get("row_end", r_s)
        c_e = grp.get("col_end", self._COLS - 1)
        return r_s * self._COLS + c_s, r_e * self._COLS + c_e

    def _rebuild_group_labels(self):
        from PyQt6.QtWidgets import QLabel as _QL
        from PyQt6.QtGui import QColor as _QC
        for lbl in self._group_labels:
            lbl.hide()
            lbl.deleteLater()
        self._group_labels = []
        for grp in self._groups:
            name = grp.get("name", "")
            if not name:
                continue
            slot_s, slot_e = self._get_slot_range(grp)
            r_s, r_e, c_s, c_e = self._slot_to_rect(slot_s, slot_e)
            color_str = grp.get("color", THEME["BLUE"])
            rect = self._row_rect(r_s, r_e, c_s, c_e)
            c = _QC(color_str)
            lbl = _QL(name, self)
            lbl.setStyleSheet(
                f"background: rgba({c.red()},{c.green()},{c.blue()},210);"
                " color: #fff; font-weight: bold; font-size: 7px;"
                " border-radius: 3px; padding: 0 4px;"
            )
            lbl.adjustSize()
            lbl.move(rect.x() + 2, rect.y() + 2)
            lbl.raise_()
            lbl.show()
            self._group_labels.append(lbl)

    def _row_rect(self, row_start: int, row_end: int,
                  col_start: int = 0, col_end: int = -1) -> "QRect":
        from PyQt6.QtCore import QRect as _QRect
        if col_end < 0:
            col_end = self._COLS - 1
        pad = 4
        x = self._MARGIN + col_start * (self._BTN_W + self._SPACING) - pad // 2
        y = self._TOP + row_start * (self._BTN_H + self._SPACING) - pad // 2
        w = (col_end - col_start + 1) * (self._BTN_W + self._SPACING) - self._SPACING + pad
        h = (row_end - row_start + 1) * (self._BTN_H + self._SPACING) - self._SPACING + pad
        return _QRect(max(0, x), max(0, y), w, h)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._groups:
            return
        from PyQt6.QtGui import QPainter, QColor, QPen
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for grp in self._groups:
            slot_s, slot_e = self._get_slot_range(grp)
            r_s, r_e, c_s, c_e = self._slot_to_rect(slot_s, slot_e)
            color_str = grp.get("color", THEME["BLUE"])
            rect = self._row_rect(r_s, r_e, c_s, c_e)
            color = QColor(color_str)
            bg = QColor(color.red(), color.green(), color.blue(), 38)
            painter.fillRect(rect, bg)
            pen = QPen(QColor(color.red(), color.green(), color.blue(), 130))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawRect(rect)

    def open_groups_dialog(self):
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                                      QDialogButtonBox, QLabel, QLineEdit,
                                      QComboBox, QListWidgetItem)
        dlg = QDialog(self)
        dlg.setWindowTitle("Soundboard ryhmät")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(
            "QDialog { background: #1a1a2a; color: #ccc; }"
            "QLabel { color: #aaa; font-size: 11px; }"
        )
        lay = QVBoxLayout(dlg)
        lay.setSpacing(8)

        list_w = QListWidget()
        list_w.setStyleSheet(
            "QListWidget { background: #111; color: #ccc; border: 1px solid #333;"
            " border-radius: 4px; padding: 2px; }"
            "QListWidget::item:selected { background: #101a36; }"
        )
        lay.addWidget(QLabel("Ryhmät (värikoodit soundboardin taustalle):"))
        lay.addWidget(list_w)

        _btn_ss = ("QPushButton { background: #252535; color: #ccc; border: 1px solid #333;"
                   " border-radius: 4px; padding: 4px 10px; }"
                   "QPushButton:hover { background: #353545; color: #fff; }")
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Lisää")
        edit_btn = QPushButton("Muokkaa")
        del_btn = QPushButton("Poista")
        for b in (add_btn, edit_btn, del_btn):
            b.setStyleSheet(_btn_ss)
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.accept)
        lay.addWidget(bb)

        def _refresh_list():
            list_w.clear()
            for grp in self._groups:
                s_s, s_e = self._get_slot_range(grp)
                item = QListWidgetItem(f"Slotit {s_s+1}–{s_e+1}: {grp['name']}")
                item.setForeground(QColor(grp.get("color", THEME["BLUE"])))
                list_w.addItem(item)

        _refresh_list()

        _input_ss = ("QLineEdit,QComboBox { background: #111; color: #eee;"
                     " border: 1px solid #333; padding: 4px; border-radius: 3px; }")

        def _grp_editor(existing=None):
            sub = QDialog(dlg)
            sub.setWindowTitle("Muokkaa ryhmää" if existing else "Uusi ryhmä")
            sub.setStyleSheet("QDialog { background: #1a1a2a; color: #ccc; }"
                              "QLabel { color: #aaa; font-size: 11px; }")
            sl = QVBoxLayout(sub)
            sl.setSpacing(6)

            name_ed = QLineEdit(existing.get("name", "") if existing else "")
            name_ed.setStyleSheet(_input_ss)
            name_ed.setPlaceholderText("Ryhmän nimi")
            sl.addWidget(QLabel("Nimi:"))
            sl.addWidget(name_ed)

            from PyQt6.QtWidgets import QSpinBox as _QSpinBox
            _cur_s, _cur_e = self._get_slot_range(existing) if existing else (0, 54)
            slot_s_spin = _QSpinBox()
            slot_s_spin.setRange(1, 55)
            slot_s_spin.setValue(_cur_s + 1)
            slot_s_spin.setStyleSheet(_input_ss)
            slot_e_spin = _QSpinBox()
            slot_e_spin.setRange(1, 55)
            slot_e_spin.setValue(_cur_e + 1)
            slot_e_spin.setStyleSheet(_input_ss)
            sl.addWidget(QLabel("Alku-slotti (1–55):"))
            sl.addWidget(slot_s_spin)
            sl.addWidget(QLabel("Loppu-slotti (1–55):"))
            sl.addWidget(slot_e_spin)

            color_combo = QComboBox()
            for hex_c, lbl in self._PRESET_COLORS:
                color_combo.addItem(lbl, hex_c)
            cur_color = existing.get("color", THEME["BLUE"]) if existing else THEME["BLUE"]
            idx = next((i for i, (h, _) in enumerate(self._PRESET_COLORS) if h == cur_color), 0)
            color_combo.setCurrentIndex(idx)
            color_combo.setStyleSheet(_input_ss)
            sl.addWidget(QLabel("Väri:"))
            sl.addWidget(color_combo)

            sbb = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            sbb.accepted.connect(sub.accept)
            sbb.rejected.connect(sub.reject)
            sl.addWidget(sbb)

            if sub.exec() == QDialog.DialogCode.Accepted:
                s_s = slot_s_spin.value() - 1
                s_e = max(s_s, slot_e_spin.value() - 1)
                return {
                    "name": name_ed.text().strip() or "Ryhmä",
                    "color": color_combo.currentData(),
                    "slot_start": s_s,
                    "slot_end": s_e,
                }
            return None

        def _on_add():
            g = _grp_editor()
            if g:
                self._groups.append(g)
                self.update()
                _refresh_list()
                if self._save_cb:
                    self._save_cb()

        def _on_edit():
            idx = list_w.currentRow()
            if 0 <= idx < len(self._groups):
                g = _grp_editor(self._groups[idx])
                if g:
                    self._groups[idx] = g
                    self.update()
                    _refresh_list()
                    if self._save_cb:
                        self._save_cb()

        def _on_del():
            idx = list_w.currentRow()
            if 0 <= idx < len(self._groups):
                self._groups.pop(idx)
                self.update()
                _refresh_list()
                if self._save_cb:
                    self._save_cb()

        add_btn.clicked.connect(_on_add)
        edit_btn.clicked.connect(_on_edit)
        del_btn.clicked.connect(_on_del)
        dlg.exec()


# =========================
# SUBTITLE OVERLAY
# =========================
class SubtitleOverlay(QWidget):
    """Frameless always-on-top floating subtitle widget. Drag to reposition."""

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._drag_pos = None

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(16, 10, 16, 10)
        vbox.setSpacing(3)

        self._orig_lbl = QLabel("")
        self._orig_lbl.setWordWrap(True)
        self._orig_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self._orig_lbl)

        self._trans_lbl = QLabel("")
        self._trans_lbl.setWordWrap(True)
        self._trans_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self._trans_lbl)

        self.setMinimumWidth(360)
        self.setMaximumWidth(960)
        self.set_font_size(16)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        p.fillPath(path, QColor(10, 14, 20, 215))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def set_transcription(self, text: str):
        self._orig_lbl.setText(text)
        self.adjustSize()

    def set_translation(self, text: str):
        self._trans_lbl.setText(text)
        self.adjustSize()

    def set_font_size(self, size: int):
        self._orig_lbl.setStyleSheet(
            f"color: #dce6ff; font-size: {size}px; font-weight: 600;"
            " background: transparent; padding: 0;"
        )
        self._trans_lbl.setStyleSheet(
            f"color: #6aa8ff; font-size: {size}px; font-weight: 600;"
            " background: transparent; padding: 0;"
        )


class CompactWidget(QWidget):
    """Small floating always-on-top control panel — REC/TARGET/Speak/status.
    Meant to replace the full window while gaming. Double-click to restore."""

    def __init__(self, app: "App"):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._app = app
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag_pos = None
        self.setFixedSize(320, 84)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(6)

        btn_style = T(
            "QPushButton { background: @BG_RAISED; border: 1px solid @BORDER; border-radius: 6px;"
            " color: @TEXT; font-size: 14px; }"
            "QPushButton:hover { border-color: @PURPLE; }"
        )

        self.rec_btn = QPushButton("🎤")
        self.rec_btn.setFixedSize(36, 32)
        self.rec_btn.setToolTip("Record — dupla-klikkaa tausta palataksesi täyteen ikkunaan")
        self.rec_btn.setStyleSheet(btn_style)
        self.rec_btn.clicked.connect(lambda: self._app.on_record_toggle())
        row.addWidget(self.rec_btn)

        self.lang_combo = QComboBox()
        for lang in LANGS.keys():
            self.lang_combo.addItem(lang)
        self.lang_combo.setFixedWidth(120)
        self.lang_combo.setStyleSheet(T(
            "QComboBox { background: @BG_RAISED; border: 1px solid @BORDER; border-radius: 6px;"
            " color: @TEXT; font-size: 11px; padding: 2px 6px; }"
        ))
        self.lang_combo.currentTextChanged.connect(self._on_lang_changed)
        row.addWidget(self.lang_combo)

        self.speak_btn = QPushButton("🔊")
        self.speak_btn.setFixedSize(36, 32)
        self.speak_btn.setToolTip("Speak")
        self.speak_btn.setStyleSheet(btn_style)
        self.speak_btn.clicked.connect(lambda: self._app.on_speak())
        row.addWidget(self.speak_btn)

        self.restore_btn = QPushButton("🗗")
        self.restore_btn.setFixedSize(28, 32)
        self.restore_btn.setToolTip("Palaa täyteen ikkunaan")
        self.restore_btn.setStyleSheet(btn_style)
        self.restore_btn.clicked.connect(lambda: self._app.toggle_compact_mode())
        row.addWidget(self.restore_btn)

        outer.addLayout(row)

        self.status_lbl = QLabel("Ready — dupla-klikkaa palataksesi")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(T("color: @TEXT_DIM; font-size: 10px; background: transparent;"))
        self.status_lbl.installEventFilter(self)
        outer.addWidget(self.status_lbl)

    def _on_lang_changed(self, text: str):
        if text and self._app.langbox.currentText() != text:
            self._app.langbox.setCurrentText(text)

    def sync_lang(self, text: str):
        self.lang_combo.blockSignals(True)
        self.lang_combo.setCurrentText(text)
        self.lang_combo.blockSignals(False)

    def set_rec_state(self, recording: bool):
        self.rec_btn.setText("🔴" if recording else "🎤")

    def set_status(self, text: str):
        line = text.strip().splitlines()[-1] if text.strip() else ""
        self.status_lbl.setText(line[:70])

    def eventFilter(self, obj, event):
        if obj is self.status_lbl and event.type() == QEvent.Type.MouseButtonDblClick:
            self._app.toggle_compact_mode()
            return True
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)
        p.fillPath(path, QColor(5, 7, 15, 240))
        pen = QPen(QColor(46, 127, 255, 160))
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._app.toggle_compact_mode()


# CUSTOM TITLEBAR (frameless main window)
# =========================
class TitleBar(QWidget):
    HEIGHT = 42

    def __init__(self, app_window: QWidget, file_menu):
        super().__init__(app_window)
        self._win = app_window
        self.setFixedHeight(self.HEIGHT)
        self.setStyleSheet(T(
            "TitleBar { background: @GRAD_PANEL; border: none;"
            " border-bottom: 1px solid @BORDER_GLOW; }"
        ))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(6)

        # Vasen: appi-ikoni + File-menu
        icon_lbl = QLabel()
        icon_path = os.path.join(ASSETS_PATH, "iconimage.ico")
        if os.path.exists(icon_path):
            icon_lbl.setPixmap(QIcon(icon_path).pixmap(20, 20))
        lay.addWidget(icon_lbl)

        menu_btn = QToolButton()
        menu_btn.setText("☰  File")
        menu_btn.setMenu(file_menu)
        menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_btn.setStyleSheet(T(
            "QToolButton { background: transparent; border: 1px solid transparent;"
            " border-radius: 6px; color: @TEXT_DIM; font-size: 12px; font-weight: 600;"
            " padding: 4px 10px; }"
            "QToolButton:hover { background: @BLUE_DIM; border-color: @BLUE; color: #ffffff; }"
            "QToolButton::menu-indicator { image: none; }"
        ))
        lay.addWidget(menu_btn)

        lay.addStretch(1)

        # Keski: neon-logo
        logo = QLabel(
            '<span style="color:{b};">VOICE</span>'
            '&nbsp;<span style="color:{p};">ROYALE</span>'.format(
                b=THEME["BLUE_BRIGHT"], p=THEME["PURPLE_BRIGHT"])
        )
        logo.setStyleSheet(T(
            "background: rgba(46,127,255,0.10); border: 1px solid @BLUE_DIM;"
            " border-radius: 10px; padding: 3px 22px;"
            " font-size: 17px; font-weight: 900; letter-spacing: 4px;"
        ))
        lay.addWidget(logo)

        lay.addStretch(1)

        # Oikea: ikkunanapit
        btn_ss = T(
            "QToolButton { background: transparent; border: none; border-radius: 6px;"
            " color: @TEXT_DIM; font-size: 13px; font-weight: 400; padding: 0; }"
            "QToolButton:hover { background: @BLUE_DIM; color: #ffffff; }"
        )
        close_ss = T(
            "QToolButton { background: transparent; border: none; border-radius: 6px;"
            " color: @TEXT_DIM; font-size: 13px; font-weight: 400; padding: 0; }"
            "QToolButton:hover { background: @RED; color: #ffffff; }"
        )
        self._btn_min = QToolButton()
        self._btn_min.setText("—")
        self._btn_min.setFixedSize(38, 28)
        self._btn_min.setStyleSheet(btn_ss)
        self._btn_min.clicked.connect(lambda: self._win.showMinimized())
        self._btn_max = QToolButton()
        self._btn_max.setText("▢")
        self._btn_max.setFixedSize(38, 28)
        self._btn_max.setStyleSheet(btn_ss)
        self._btn_max.clicked.connect(self._toggle_max)
        self._btn_close = QToolButton()
        self._btn_close.setText("✕")
        self._btn_close.setFixedSize(38, 28)
        self._btn_close.setStyleSheet(close_ss)
        self._btn_close.clicked.connect(lambda: self._win.close())
        for b in (self._btn_min, self._btn_max, self._btn_close):
            lay.addWidget(b)

    def _toggle_max(self):
        if self._win.isMaximized():
            self._win.showNormal()
            self._btn_max.setText("▢")
        else:
            self._win.showMaximized()
            self._btn_max.setText("❐")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            wh = self._win.windowHandle()
            if wh is not None:
                wh.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_max()


# APPLICATION
# =========================
class App(QWidget):
    sig_mic_level = pyqtSignal(int)
    sig_out_level = pyqtSignal(int)
    sig_status = pyqtSignal(str)
    sig_set_textbox = pyqtSignal(str)

    def create_flag_icon(self, country_code: str):
        pixmap = QPixmap(20, 14)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if country_code == "us":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.red)
            painter.fillRect(0, 0, 12, 8, Qt.GlobalColor.blue)
            painter.fillRect(0, 2, 20, 2, Qt.GlobalColor.white)
            painter.fillRect(0, 6, 20, 2, Qt.GlobalColor.white)
            painter.fillRect(0, 10, 20, 2, Qt.GlobalColor.white)
        elif country_code == "de":
            painter.fillRect(0, 0, 20, 5, Qt.GlobalColor.black)
            painter.fillRect(0, 5, 20, 5, Qt.GlobalColor.red)
            painter.fillRect(0, 10, 20, 4, Qt.GlobalColor.yellow)
        elif country_code == "se":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.blue)
            painter.fillRect(5, 0, 4, 14, Qt.GlobalColor.yellow)
            painter.fillRect(0, 5, 20, 4, Qt.GlobalColor.yellow)
        elif country_code == "fi":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.white)
            painter.fillRect(5, 0, 4, 14, Qt.GlobalColor.blue)
            painter.fillRect(0, 5, 20, 4, Qt.GlobalColor.blue)
        elif country_code == "ru":
            painter.fillRect(0, 0, 20, 4, Qt.GlobalColor.white)
            painter.fillRect(0, 4, 20, 5, Qt.GlobalColor.blue)
            painter.fillRect(0, 9, 20, 5, Qt.GlobalColor.red)
        elif country_code == "it":
            painter.fillRect(0, 0, 7, 14, Qt.GlobalColor.green)
            painter.fillRect(7, 0, 6, 14, Qt.GlobalColor.white)
            painter.fillRect(13, 0, 7, 14, Qt.GlobalColor.red)
        elif country_code == "nl":
            painter.fillRect(0, 0, 20, 5, Qt.GlobalColor.red)
            painter.fillRect(0, 5, 20, 4, Qt.GlobalColor.white)
            painter.fillRect(0, 9, 20, 5, Qt.GlobalColor.blue)
        elif country_code == "no":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.red)
            painter.fillRect(4, 0, 4, 14, Qt.GlobalColor.white)
            painter.fillRect(0, 5, 20, 4, Qt.GlobalColor.white)
            painter.fillRect(5, 0, 2, 14, Qt.GlobalColor.blue)
            painter.fillRect(0, 6, 20, 2, Qt.GlobalColor.blue)
        elif country_code == "dk":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.red)
            painter.fillRect(5, 0, 3, 14, Qt.GlobalColor.white)
            painter.fillRect(0, 5, 20, 4, Qt.GlobalColor.white)
        elif country_code == "ro":
            painter.fillRect(0, 0, 7, 14, Qt.GlobalColor.blue)
            painter.fillRect(7, 0, 6, 14, Qt.GlobalColor.yellow)
            painter.fillRect(13, 0, 7, 14, Qt.GlobalColor.red)
        elif country_code == "lv":
            painter.fillRect(0, 0, 20, 5, Qt.GlobalColor.darkRed)
            painter.fillRect(0, 5, 20, 4, Qt.GlobalColor.white)
            painter.fillRect(0, 9, 20, 5, Qt.GlobalColor.darkRed)
        elif country_code == "lt":
            painter.fillRect(0, 0, 20, 5, Qt.GlobalColor.yellow)
            painter.fillRect(0, 5, 20, 4, Qt.GlobalColor.green)
            painter.fillRect(0, 9, 20, 5, Qt.GlobalColor.red)
        elif country_code == "jp":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.white)
            painter.fillRect(7, 3, 6, 8, Qt.GlobalColor.red)
        elif country_code == "cn":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.red)
            painter.fillRect(2, 2, 4, 4, Qt.GlobalColor.yellow)
        elif country_code == "hu":
            painter.fillRect(0, 0, 20, 5, Qt.GlobalColor.red)
            painter.fillRect(0, 5, 20, 4, Qt.GlobalColor.white)
            painter.fillRect(0, 9, 20, 5, Qt.GlobalColor.green)
        elif country_code == "pl":
            painter.fillRect(0, 0, 20, 7, Qt.GlobalColor.white)
            painter.fillRect(0, 7, 20, 7, Qt.GlobalColor.red)
        elif country_code == "cz":
            painter.fillRect(0, 0, 20, 7, Qt.GlobalColor.white)
            painter.fillRect(0, 7, 20, 7, Qt.GlobalColor.red)
            painter.fillRect(0, 0, 8, 14, Qt.GlobalColor.blue)
        elif country_code == "ca":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.yellow)
            painter.fillRect(0, 2, 20, 2, Qt.GlobalColor.red)
            painter.fillRect(0, 5, 20, 2, Qt.GlobalColor.red)
            painter.fillRect(0, 8, 20, 2, Qt.GlobalColor.red)
            painter.fillRect(0, 11, 20, 2, Qt.GlobalColor.red)
        elif country_code == "by":
            painter.fillRect(0, 0, 20, 10, Qt.GlobalColor.red)
            painter.fillRect(0, 10, 20, 4, Qt.GlobalColor.green)
            painter.fillRect(0, 0, 3, 14, Qt.GlobalColor.white)
        elif country_code == "es":
            painter.fillRect(0, 0, 20, 4, Qt.GlobalColor.red)
            painter.fillRect(0, 4, 20, 6, Qt.GlobalColor.yellow)
            painter.fillRect(0, 10, 20, 4, Qt.GlobalColor.red)
        elif country_code == "fr":
            painter.fillRect(0, 0, 7, 14, Qt.GlobalColor.blue)
            painter.fillRect(7, 0, 6, 14, Qt.GlobalColor.white)
            painter.fillRect(13, 0, 7, 14, Qt.GlobalColor.red)
        elif country_code == "tr":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.red)
            painter.fillRect(5, 2, 6, 10, Qt.GlobalColor.white)   # crescent outer
            painter.fillRect(7, 3, 6, 8, Qt.GlobalColor.red)      # crescent inner cutout
            painter.fillRect(13, 5, 2, 4, Qt.GlobalColor.white)   # star
        elif country_code == "in":
            painter.fillRect(0, 0, 20, 5, QColor(255, 153, 51))   # saffron
            painter.fillRect(0, 5, 20, 4, Qt.GlobalColor.white)
            painter.fillRect(0, 9, 20, 5, QColor(19, 136, 8))     # green
            painter.fillRect(8, 6, 4, 2, QColor(0, 0, 128))       # Ashoka Chakra (simplified)
        elif country_code == "il":
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.white)
            painter.fillRect(0, 1, 20, 2, QColor(0, 56, 184))     # blue stripe top
            painter.fillRect(0, 11, 20, 2, QColor(0, 56, 184))    # blue stripe bottom
            painter.fillRect(7, 4, 2, 6, QColor(0, 56, 184))      # Star of David left edge
            painter.fillRect(11, 4, 2, 6, QColor(0, 56, 184))     # right edge
            painter.fillRect(7, 4, 6, 2, QColor(0, 56, 184))      # top edge
            painter.fillRect(7, 8, 6, 2, QColor(0, 56, 184))      # bottom edge
        elif country_code == "gr":
            painter.fillRect(0, 0, 20, 14, QColor(0, 80, 160))    # blue
            painter.fillRect(0, 2, 20, 2, Qt.GlobalColor.white)
            painter.fillRect(0, 6, 20, 2, Qt.GlobalColor.white)
            painter.fillRect(0, 10, 20, 2, Qt.GlobalColor.white)
            painter.fillRect(0, 0, 8, 6, QColor(0, 80, 160))      # canton
            painter.fillRect(3, 0, 2, 6, Qt.GlobalColor.white)    # vertical cross
            painter.fillRect(0, 2, 8, 2, Qt.GlobalColor.white)    # horizontal cross
        elif country_code == "hr":
            painter.fillRect(0, 0, 7, 14, Qt.GlobalColor.red)
            painter.fillRect(7, 0, 6, 14, Qt.GlobalColor.white)
            painter.fillRect(13, 0, 7, 14, Qt.GlobalColor.blue)
            painter.fillRect(7, 3, 3, 3, Qt.GlobalColor.red)      # checkerboard
            painter.fillRect(10, 3, 3, 3, Qt.GlobalColor.white)
            painter.fillRect(7, 6, 3, 3, Qt.GlobalColor.white)
            painter.fillRect(10, 6, 3, 3, Qt.GlobalColor.red)
        elif country_code == "sa":
            painter.fillRect(0, 0, 20, 14, QColor(0, 106, 78))    # dark green
            painter.fillRect(3, 5, 12, 2, Qt.GlobalColor.white)   # sword blade
            painter.fillRect(3, 7, 2, 3, Qt.GlobalColor.white)    # sword handle
            painter.fillRect(3, 9, 5, 1, Qt.GlobalColor.white)    # crossguard
        else:
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.lightGray)

        painter.end()
        return QIcon(pixmap)

    def build_language_icons(self):
        icons = {}
        for lang, country_code in LANG_FLAG_CODES.items():
            icons[lang] = self.create_flag_icon(country_code)
        return icons

    def rebuild_langbox(self):
        self.lang_icons = self.build_language_icons()
        current = self.langbox.currentText()
        self.langbox.clear()
        for lang in LANGS.keys():
            icon = self.lang_icons.get(lang)
            if icon:
                self.langbox.addItem(icon, lang)
            else:
                self.langbox.addItem(lang)
        if self.langbox.findText(current) >= 0:
            self.langbox.setCurrentText(current)
        if hasattr(self, "source_langbox"):
            cur_src = self.source_langbox.currentText()
            self.source_langbox.clear()
            self.source_langbox.addItem("Auto (tunnistaa)")
            for lang in LANGS.keys():
                if lang == "Auto":
                    continue
                icon = self.lang_icons.get(lang)
                if icon:
                    self.source_langbox.addItem(icon, lang)
                else:
                    self.source_langbox.addItem(lang)
            if self.source_langbox.findText(cur_src) >= 0:
                self.source_langbox.setCurrentText(cur_src)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Royale")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setGeometry(100, 100, 1560, 900)
        self.setMinimumWidth(1200)
        icon_path = os.path.join(ASSETS_PATH, "iconimage.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setStyleSheet(T("""
            QWidget {
                background: @BG_DEEP;
                color: @TEXT;
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QFrame {
                background: @GRAD_PANEL;
                border: 1px solid @BORDER;
                border-radius: 10px;
            }
            QLabel { background: transparent; border: none; color: @TEXT; }

            QPushButton {
                background: @GRAD_BTN;
                border: 1px solid @BLUE_DIM;
                border-radius: 8px;
                color: @TEXT;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
                min-height: 30px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1b2c5e,stop:1 #121a36);
                border-color: @BLUE;
                color: #ffffff;
            }
            QPushButton:pressed { background: @BG_INPUT; border-color: @PURPLE; }
            QPushButton:checked {
                background: @GRAD_ACCENT;
                border-color: @BLUE_BRIGHT;
                color: #ffffff;
            }
            QPushButton:disabled { background: @BG_PANEL; color: @TEXT_FAINT; border-color: @BORDER; }

            QToolButton {
                background: @GRAD_BTN;
                border: 1px solid @BORDER;
                border-radius: 8px;
                color: @TEXT_DIM;
                font-size: 11px;
                font-weight: 700;
            }
            QToolButton:hover { background: @BLUE_DIM; border-color: @BLUE; color: #ffffff; }
            QToolButton:pressed { background: @BG_INPUT; border-color: @PURPLE; }

            QComboBox {
                background: @BG_RAISED;
                border: 1px solid @BORDER;
                border-radius: 8px;
                color: @TEXT;
                padding: 5px 10px;
                min-height: 30px;
            }
            QComboBox:hover { border-color: @BLUE; }
            QComboBox::drop-down { border: none; width: 22px; }
            QComboBox QAbstractItemView {
                background: @BG_PANEL;
                border: 1px solid @BORDER_GLOW;
                selection-background-color: @BLUE;
                color: @TEXT;
            }

            QTextEdit {
                background: @BG_INPUT;
                border: 1px solid @BORDER;
                border-radius: 8px;
                color: @TEXT;
                padding: 6px;
                selection-background-color: @BLUE;
            }
            QTextEdit:focus { border-color: @BORDER_GLOW; }
            QLineEdit {
                background: @BG_INPUT;
                border: 1px solid @BORDER;
                border-radius: 8px;
                color: @TEXT;
                padding: 5px 10px;
                min-height: 30px;
            }
            QLineEdit:focus { border-color: @BORDER_GLOW; }

            QCheckBox { color: @TEXT; background: transparent; spacing: 8px; }
            QCheckBox::indicator {
                width: 17px; height: 17px; border-radius: 5px;
                border: 1px solid @BLUE_DIM; background: @BG_INPUT;
            }
            QCheckBox::indicator:hover { border-color: @BLUE; }
            QCheckBox::indicator:checked {
                background: @GRAD_ACCENT;
                border-color: @BLUE_BRIGHT;
            }

            QScrollBar:vertical { background: @BG_DEEP; width: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:vertical {
                background: @GRAD_ACCENT;
                border-radius: 4px; min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: @PURPLE_BRIGHT; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { background: @BG_DEEP; height: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:horizontal {
                background: @GRAD_ACCENT;
                border-radius: 4px; min-width: 24px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

            QTabWidget::pane {
                border: 1px solid @BORDER_GLOW;
                border-radius: 10px;
                background: @GRAD_PANEL;
            }
            QTabBar::tab {
                background: @BG_RAISED;
                color: @TEXT_FAINT;
                padding: 9px 20px;
                font-weight: 700;
                font-size: 12px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                border: 1px solid @BORDER;
                border-bottom: none;
                border-radius: 8px 8px 0 0;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: @GRAD_ACCENT;
                color: #ffffff;
                border-color: @BLUE_BRIGHT;
            }
            QTabBar::tab:hover:!selected { background: @BLUE_DIM; color: @TEXT; border-color: @BLUE; }

            QListWidget { background: @BG_INPUT; border: 1px solid @BORDER; border-radius: 8px; }
            QListWidget::item {
                background: @BG_RAISED; border: 1px solid @BORDER;
                border-radius: 6px; margin: 2px 4px; padding: 5px 8px; color: @TEXT;
            }
            QListWidget::item:hover { background: @BLUE_DIM; border-color: @PURPLE; }
            QListWidget::item:selected {
                background: @GRAD_ACCENT;
                border-color: @BLUE_BRIGHT; color: #fff;
            }

            QScrollArea { background: transparent; border: 1px solid @BORDER; border-radius: 8px; }
            QProgressBar { background: @BG_INPUT; border: 1px solid @BORDER; border-radius: 4px; }
            QProgressBar::chunk {
                background: @GRAD_ACCENT;
                border-radius: 3px;
            }

            QMenu {
                background: @BG_PANEL;
                border: 1px solid @BORDER_GLOW;
                border-radius: 8px;
                color: @TEXT;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected {
                background: @GRAD_ACCENT;
                color: #ffffff;
            }
        """))

        # Last Whisper STT call round-trip time, shown in Settings dialog
        self._last_stt_latency_ms = None

        # Load app settings first so custom languages are available for icon building
        self.settings = load_settings()
        _apply_custom_languages_to_globals(self.settings.get("custom_languages", []))
        SoundboardButton.set_pixabay_key(self.settings.get("pixabay_api_key", ""))

        # Build language icons (used by langbox AND history list)
        self.lang_icons = self.build_language_icons()

        # Per-device row widgets — keyed by device index
        # Each entry: {"checkbox", "name_label", "meter", "db_label", "container", "full_name"}
        self._device_widgets = {}

        # Wake listener (created later; status callback uses sig_status)
        self._registered_hotkey = None
        self.wake_listener = WakeListener(
            on_wake_callback=self._on_wake_detected,
            on_status_callback=self.append_status,
        )

        # Auto-start Voicemeeter Banana if installed (always try; _ensure handles missing gracefully)
        QTimer.singleShot(1200, lambda: threading.Thread(
            target=_ensure_voicemeeter_running, daemon=True
        ).start())

        # System tray icon — app minimizes/closes to tray instead of taskbar
        self._tray_icon = QSystemTrayIcon(self)
        _icon_path = os.path.join(ASSETS_PATH, "iconimage.ico")
        self._tray_icon.setIcon(QIcon(_icon_path) if os.path.exists(_icon_path) else QIcon())
        self._tray_icon.setToolTip("Voice Royale")
        _tray_menu = QMenu()
        _show_action = _tray_menu.addAction("Avaa Voice Royale")
        _show_action.triggered.connect(self._restore_from_tray)
        _tray_menu.addSeparator()
        _quit_action = _tray_menu.addAction("Sulje ohjelma")
        _quit_action.triggered.connect(self._quit_from_tray)
        self._tray_icon.setContextMenu(_tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

        # Voice FX + soundboard state
        self._voice_fx = VoiceEffectProcessor(self.append_status)
        self._current_fx_preset = "Normal"
        self._soundboard_buttons: list[list[SoundboardButton]] = []
        self._sb_page_containers: list["SoundboardPageContainer"] = []
        self._sb_back_btns: list = []   # pinned Back button per page
        self._sb_nav_stack: dict[int, list] = {}  # page_index -> [(parent_slots, folder_slot_idx), ...]
        self._fx_preset_buttons: dict[str, QPushButton] = {}
        self._mb_bars: dict[int, tuple] = {}  # device_index -> (bar, db_lbl)
        self._sb_play_id: int = 0
        self._sb_playing_btn: "SoundboardButton | None" = None
        self._sb_stop_event: threading.Event = threading.Event()
        self._play_stop_event: threading.Event = threading.Event()  # stops TTS/speak/favorites

        # Stream Deck HTTP server (for official Elgato plugin)
        self._stream_deck = StreamDeckHttpServer(self.append_status)

        # ============ File menu (custom-titlebarin ☰-napille) ============
        file_menu = QMenu(self)
        file_menu.setStyleSheet(T(
            "QMenu { background: @BG_PANEL; border: 1px solid @BORDER_GLOW; color: @TEXT; }"
            "QMenu::item { padding: 7px 20px; }"
            "QMenu::item:selected { background: @GRAD_ACCENT; color: #fff; }"
            "QMenu::separator { height: 1px; background: @BORDER; margin: 4px 0; }"
        ))
        file_menu.addAction("⚙  Settings", lambda: open_settings_dialog(self))
        file_menu.addSeparator()
        file_menu.addAction("ℹ  About Voice Royale", self._show_app_info)
        file_menu.addSeparator()
        file_menu.addAction("✕  Exit", QApplication.instance().quit)
        self._titlebar = TitleBar(self, file_menu)

        # ============ Top row: Speech card (left) + History card (right) ============
        top_row = QHBoxLayout()
        top_row.addWidget(self._build_speech_card(), 2)
        top_row.addWidget(self._build_history_card(), 1)

        # ============ Bottom tab widget: Outputs / Soundboard / Voice FX ============
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.addTab(self._build_soundboard_card(), "  Soundboard  ")
        self._bottom_tabs.addTab(self._build_voice_fx_card(), "  Voice FX  ")
        # Output devices and input mic moved to Settings → Asennus.
        # Build the card to keep _device_rows_layout and input_device_combo alive,
        # but do not add it as a visible tab.
        self._hidden_outputs_card = self._build_outputs_card()

        # ============ Root layout ============
        content = QVBoxLayout()
        content.setContentsMargins(8, 4, 8, 8)
        content.setSpacing(6)
        content.addLayout(top_row, 1)
        content.addWidget(self._bottom_tabs, 1)
        content.addWidget(self._build_meters_bar())

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._titlebar)
        root.addLayout(content, 1)
        self.setLayout(root)

        # Wire signals — safe cross-thread UI updates
        self.sig_mic_level.connect(self._update_mic_meter)
        self.sig_out_level.connect(self._update_output_meters)
        self.sig_status.connect(self._on_status)
        self.sig_set_textbox.connect(self.textbox.setPlainText)
        self.sig_set_textbox.connect(self._overlay_on_transcription)

        # Subtitle overlay
        self._overlay = SubtitleOverlay()
        _op = self.settings.get("overlay_pos")
        if _op and len(_op) == 2:
            self._overlay.move(_op[0], _op[1])
        else:
            _scr = QApplication.primaryScreen().geometry()
            self._overlay.move(_scr.center().x() - 200, _scr.bottom() - 160)
        _ofs = int(self.settings.get("overlay_font_size", 16))
        self._overlay.set_font_size(_ofs)

        # Compact / mini mode — small always-on-top control panel for gaming
        self._compact = CompactWidget(self)
        _cp = self.settings.get("compact_pos")
        if _cp and len(_cp) == 2:
            self._compact.move(_cp[0], _cp[1])
        else:
            _scr2 = QApplication.primaryScreen().geometry()
            self._compact.move(_scr2.right() - 340, _scr2.top() + 40)
        self.langbox.currentTextChanged.connect(self._compact.sync_lang)
        self._compact.sync_lang(self.langbox.currentText())

        # Recording state + mic monitor (must be set before populate_input_devices)
        self.is_recording = False
        self.recording_thread = None
        self._mic_peak_ref = [0.0]
        self._mic_monitor_stream = None
        self._mic_timer = QTimer(self)
        self._mic_timer.setInterval(40)
        self._mic_timer.timeout.connect(self._tick_mic_meter)
        self._mic_timer.start()

        # Load data + populate devices
        self.history_data = load_history_data()
        self.history = self.history_data.get("history", [])
        self.favorites = self.history_data.get("favorites", [])
        self.refresh_history_views()

        self.populate_output_devices()
        self.populate_input_devices()
        self.register_hotkey()

        # Start always-on mic monitor after devices are populated
        self._start_mic_monitor()

        # Start Stream Deck HTTP server (used by the Elgato plugin)
        import queue as _queue
        self._sd_state: dict = {}
        self._sd_action_queue: _queue.Queue = _queue.Queue()
        self._sd_state_timer = QTimer(self)
        self._sd_state_timer.timeout.connect(self._refresh_sd_state)
        self._sd_state_timer.start(1500)
        self._sd_action_timer = QTimer(self)
        self._sd_action_timer.timeout.connect(self._drain_sd_action_queue)
        self._sd_action_timer.start(50)

        # Voicemeeter Banana running check — poll every 5s, update warning label
        self._vm_check_timer = QTimer(self)
        self._vm_check_timer.timeout.connect(self._check_voicemeeter_running)
        self._vm_check_timer.start(60000)
        QTimer.singleShot(3000, self._check_voicemeeter_running)
        self._stream_deck.start(self)
        QTimer.singleShot(600, self._autostart_voice_fx)

    # ============ Card builders ============

    def _make_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(T(
            "QFrame { background: @GRAD_PANEL;"
            " border: 1px solid @BORDER_GLOW; border-radius: 10px; }"
        ))
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        if title:
            title_lbl = QLabel(title.upper())
            title_lbl.setStyleSheet(T(
                "font-weight: 700; font-size: 12px; color: @BLUE_BRIGHT; border: none;"
                " letter-spacing: 1px; padding-bottom: 2px;"
            ))
            layout.addWidget(title_lbl)
        return frame, layout

    def _build_speech_card(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(T(
            "QFrame { background: @GRAD_PANEL;"
            " border: 1px solid @BORDER_GLOW; border-radius: 10px; }"
        ))
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)

        # Card title
        title_lbl = QLabel("SPEECH")
        title_lbl.setStyleSheet(T(
            "font-weight: 700; font-size: 12px; color: @BLUE_BRIGHT; border: none; letter-spacing: 1px;"
        ))
        layout.addWidget(title_lbl)

        # Voicemeeter Banana warning banner (hidden when Banana is running)
        self._vm_warning_label = QLabel("VAROITUS: Voicemeeter Banana ei ole käynnissä — mikrofoni ei kuulu!")
        self._vm_warning_label.setWordWrap(True)
        self._vm_warning_label.setStyleSheet(T(
            "color: @RED; background: #1a0510; border: 1px solid @RED;"
            " border-radius: 6px; padding: 4px 8px; font-size: 11px; font-weight: 600;"
        ))
        self._vm_warning_label.setVisible(False)
        layout.addWidget(self._vm_warning_label)

        # Status log — 5 rows
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setPlainText("Ready. Type or record. Hotkey: Ctrl+Alt+Space")
        self.status_text.setMinimumHeight(90)
        self.status_text.setMaximumHeight(115)
        self.status_text.setStyleSheet(T(
            "QTextEdit { background: @BG_INPUT; border: 1px solid @BORDER; border-radius: 8px;"
            " color: @TEXT_FAINT; font-size: 11px; padding: 5px; }"
        ))
        layout.addWidget(self.status_text)

        # Translated text label
        self.translated_label = QLabel("Translated text will appear here.")
        self.translated_label.setWordWrap(True)
        self.translated_label.setMinimumHeight(32)
        self.translated_label.setStyleSheet(T(
            "color: @BLUE_BRIGHT; padding: 5px 10px; background: @BG_INPUT;"
            "border: 1px solid @BORDER_GLOW; border-radius: 8px; font-size: 12px;"
        ))
        layout.addWidget(self.translated_label)

        # Source + Target selectors (left narrow columns) + textbox (right)
        text_row = QHBoxLayout()
        text_row.setSpacing(6)
        text_row.setContentsMargins(0, 0, 0, 0)

        src_lang_col = QVBoxLayout()
        src_lang_col.setSpacing(2)
        src_lang_col.setContentsMargins(0, 0, 0, 0)
        lbl_source = QLabel("SOURCE")
        lbl_source.setStyleSheet(T(
            "color: @TEXT_FAINT; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;"
        ))
        src_lang_col.addWidget(lbl_source)
        self.source_langbox = QComboBox()
        self.source_langbox.addItem("Auto (tunnistaa)")
        for _sl in LANGS.keys():
            if _sl == "Auto":
                continue
            _icon = self.lang_icons.get(_sl)
            if _icon:
                self.source_langbox.addItem(_icon, _sl)
            else:
                self.source_langbox.addItem(_sl)
        _saved_src = self.settings.get("stt_source_language", "Finnish")
        if self.source_langbox.findText(_saved_src) >= 0:
            self.source_langbox.setCurrentText(_saved_src)
        self.source_langbox.setFixedWidth(118)
        self.source_langbox.setToolTip("Kieli, jolla puhut mikrofoniin. Auto = Whisper tunnistaa itse.")
        src_lang_col.addWidget(self.source_langbox)
        src_lang_col.addStretch()
        text_row.addLayout(src_lang_col)

        lang_col = QVBoxLayout()
        lang_col.setSpacing(2)
        lang_col.setContentsMargins(0, 0, 0, 0)
        lbl_target = QLabel("TARGET")
        lbl_target.setStyleSheet(T(
            "color: @TEXT_FAINT; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;"
        ))
        lang_col.addWidget(lbl_target)
        self.langbox = QComboBox()
        for lang in LANGS.keys():
            icon = self.lang_icons.get(lang)
            if icon:
                self.langbox.addItem(icon, lang)
            else:
                self.langbox.addItem(lang)
        default_lang = self.settings.get("default_target_lang", "Auto")
        if self.langbox.findText(default_lang) >= 0:
            self.langbox.setCurrentText(default_lang)
        self.langbox.setFixedWidth(118)
        lang_col.addWidget(self.langbox)
        lang_col.addStretch()
        text_row.addLayout(lang_col)

        self.textbox = QTextEdit()
        self.textbox.setPlaceholderText("Type the phrase to speak…\nOr press 🎤 Listen to record.")
        self.textbox.setMinimumHeight(90)
        text_row.addWidget(self.textbox, 1)
        layout.addLayout(text_row, 1)

        # Speak button — floating overlay inside textbox, bottom-right
        self.speak_button = QPushButton("🔊  Speak", self.textbox)
        self.speak_button.setFixedSize(92, 32)
        self.speak_button.setToolTip("Speak this text (Ctrl+Enter)")
        self.speak_button.clicked.connect(self.on_speak)
        self.speak_button.setStyleSheet(T(
            "QPushButton { background: rgba(16,26,54,220); border: 1px solid @BORDER_GLOW;"
            " border-radius: 8px; color: @BLUE_BRIGHT; font-size: 12px; font-weight: 700; padding: 0; }"
            "QPushButton:hover { background: rgba(46,127,255,180); color: #fff; border-color: @PURPLE; }"
            "QPushButton:pressed { background: @BG_INPUT; }"
            "QPushButton:disabled { background: rgba(10,15,30,180); color: @TEXT_FAINT; border-color: @BORDER; }"
        ))
        self.speak_button.move(self.textbox.width() - 98, self.textbox.height() - 38)

        # Favorite button — floating overlay inside textbox, bottom-left
        self.favorite_button = QPushButton("⭐  Favorite", self.textbox)
        self.favorite_button.setFixedSize(98, 32)
        self.favorite_button.setToolTip("Save as favorite")
        self.favorite_button.clicked.connect(self.toggle_favorite)
        self.favorite_button.setStyleSheet(T(
            "QPushButton { background: rgba(26,18,0,215); border: 1px solid @GOLD_DIM;"
            " border-radius: 8px; color: @GOLD; font-size: 12px; font-weight: 700; padding: 0; }"
            "QPushButton:hover { border-color: @GOLD; color: @GOLD_BRIGHT; background: rgba(60,40,0,200); }"
        ))
        self.favorite_button.move(6, self.textbox.height() - 38)

        # Install resize filter for both textbox overlay buttons
        self._rec_filter = _TextboxOverlayFilter(self.speak_button, self.favorite_button)
        self.textbox.installEventFilter(self._rec_filter)
        self.speak_button.raise_()
        self.favorite_button.raise_()

        # Hidden widgets — needed by app logic but not shown in this card
        self.backend_combo = QComboBox()
        for backend in ("ElevenLabs", "Edge TTS (free)"):
            self.backend_combo.addItem(backend)
        self.backend_combo.setCurrentText(self.settings.get("default_tts_backend", DEFAULT_TTS_BACKEND))

        self.test_audio_button = QPushButton("🧪  Test")
        self.test_audio_button.clicked.connect(self.on_test_audio)

        # Button row: 🎤 Listen | 👂 Live Listen
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.record_button = QPushButton("🎤  Listen")
        self.record_button.setToolTip("Record from mic — Whisper transcribes and translates")
        self.record_button.clicked.connect(self.on_record_toggle)
        self.record_button.setStyleSheet(T(
            "QPushButton { background: @GRAD_ACCENT;"
            " border: 2px solid @BLUE_BRIGHT; border-radius: 8px; color: #fff;"
            " font-size: 13px; font-weight: 700; padding: 8px 18px; letter-spacing: 0.5px; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,"
            " stop:0 #5590ff, stop:1 #a052ff); border-color: @PURPLE_BRIGHT; }"
            "QPushButton:pressed { background: @BG_INPUT; border-color: @BLUE; }"
            "QPushButton:disabled { background: @BG_PANEL; color: @TEXT_FAINT; border-color: @BORDER; }"
        ))
        button_row.addWidget(self.record_button, 2)

        self.listen_button = QPushButton("👂  Live Listen")
        self.listen_button.setCheckable(True)
        self.listen_button.clicked.connect(self.toggle_wake_listener)
        self.listen_button.setStyleSheet(T(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            " stop:0 #0a1a12, stop:1 #06110b);"
            " border: 1px solid @GREEN_DIM; border-radius: 8px; color: @GREEN; font-weight: 600; }"
            "QPushButton:hover { border-color: @GREEN; color: #5affaa; background: #0c2417; }"
            "QPushButton:checked { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            " stop:0 #0a2e18, stop:1 #071e0f);"
            " border: 2px solid @GREEN; color: @GREEN; }"
        ))
        button_row.addWidget(self.listen_button, 1)

        self._overlay_btn = QPushButton("CC")
        self._overlay_btn.setCheckable(True)
        self._overlay_btn.setFixedWidth(40)
        self._overlay_btn.setToolTip("Subtitle Overlay — kelluva tekstitys (raahaa kohdalle)")
        self._overlay_btn.clicked.connect(self.toggle_overlay)
        self._overlay_btn.setStyleSheet(T(
            "QPushButton { background: @BG_RAISED; border: 1px solid @BORDER; border-radius: 8px;"
            " color: @TEXT_FAINT; font-size: 11px; font-weight: 700; padding: 0; }"
            "QPushButton:hover { border-color: @BLUE; color: @BLUE_BRIGHT; }"
            "QPushButton:checked { background: @BLUE_DIM; border: 2px solid @BLUE; color: @BLUE_BRIGHT; }"
        ))
        button_row.addWidget(self._overlay_btn)

        self._compact_btn = QPushButton("▭")
        self._compact_btn.setCheckable(True)
        self._compact_btn.setFixedWidth(40)
        self._compact_btn.setToolTip("Compact-tila — pieni kelluva widget pelaamisen ajaksi")
        self._compact_btn.clicked.connect(self.toggle_compact_mode)
        self._compact_btn.setStyleSheet(T(
            "QPushButton { background: @BG_RAISED; border: 1px solid @BORDER; border-radius: 8px;"
            " color: @TEXT_FAINT; font-size: 11px; font-weight: 700; padding: 0; }"
            "QPushButton:hover { border-color: @BLUE; color: @BLUE_BRIGHT; }"
            "QPushButton:checked { background: @BLUE_DIM; border: 2px solid @BLUE; color: @BLUE_BRIGHT; }"
        ))
        button_row.addWidget(self._compact_btn)
        layout.addLayout(button_row)

        # Status + hotkey compact row
        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        self.wake_status_label = QLabel("Wake-word: off")
        self.wake_status_label.setStyleSheet(T("color: @TEXT_FAINT; font-size: 10px; border: none;"))
        info_row.addWidget(self.wake_status_label, 1)
        self.hotkey_label = QLabel(f"Hotkey: {self.settings.get('hotkey', 'ctrl+alt+space')}")
        self.hotkey_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.hotkey_label.setStyleSheet(T("color: @TEXT_FAINT; font-size: 10px; border: none;"))
        info_row.addWidget(self.hotkey_label)
        layout.addLayout(info_row)

        # Wake-word usage instructions — shown only when listening is active
        self.wake_instructions_label = QLabel()
        self.wake_instructions_label.setWordWrap(True)
        self.wake_instructions_label.setStyleSheet(T(
            "QLabel { background: #06180f; border: 1px solid @GREEN_DIM; border-radius: 6px;"
            " color: @GREEN; font-size: 11px; padding: 8px 10px; }"
        ))
        self.wake_instructions_label.setVisible(False)
        layout.addWidget(self.wake_instructions_label)

        return frame

    def _build_history_card(self) -> QWidget:
        frame, layout = self._make_card("History (last 10)")

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_history_item_selected)
        self.history_list.setMinimumHeight(100)
        self.history_list.setStyleSheet(LIST_STYLE)
        layout.addWidget(self.history_list, 1)

        fav_title = QLabel("FAVORITES")
        fav_title.setStyleSheet(T("font-weight: 700; font-size: 11px; color: @GOLD; border: none; margin-top: 6px; letter-spacing: 1px;"))
        layout.addWidget(fav_title)

        self.favorites_list = QListWidget()
        self.favorites_list.itemClicked.connect(self.on_history_item_selected)
        self.favorites_list.setMinimumHeight(100)
        self.favorites_list.setStyleSheet(LIST_STYLE)
        layout.addWidget(self.favorites_list, 1)

        return frame

    # ---- Soundboard group overlay container ----

    def _sb_rebuild(self, mode: str):
        """Rebuild soundboard grid with new icon size mode."""
        self._sb_stop_playback()
        SoundboardButton.set_size_mode(mode)
        SoundboardPageContainer.set_size_mode(mode)
        sb_idx = next(
            (i for i in range(self._bottom_tabs.count())
             if "Soundboard" in self._bottom_tabs.tabText(i)), None)
        if sb_idx is None:
            return
        self._soundboard_buttons.clear()
        self._sb_page_containers.clear()
        self._bottom_tabs.removeTab(sb_idx)
        new_card = self._build_soundboard_card()
        self._bottom_tabs.insertTab(sb_idx, new_card, "  Soundboard  ")
        self._bottom_tabs.setCurrentIndex(sb_idx)

    def _build_soundboard_card(self) -> QWidget:
        _mode = self.settings.get("sb_icon_size", "large")
        SoundboardButton.set_size_mode(_mode)
        SoundboardPageContainer.set_size_mode(_mode)
        frame = QWidget()
        frame.setObjectName("card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        self._sb_tabs = QTabWidget()
        self._sb_tabs.setTabsClosable(False)
        self._sb_tabs.setStyleSheet(T(
            "QTabWidget::pane { border: 1px solid @BORDER; border-radius: 8px; background: @BG_DEEP; }"
            "QTabBar { margin-right: 232px; }"
            "QTabBar::tab { background: @BG_RAISED; color: @TEXT_FAINT; padding: 7px 14px;"
            " font-size: 11px; font-weight: 700; letter-spacing: 0.5px;"
            " border: 1px solid @BORDER; border-bottom: none; border-radius: 4px 4px 0 0; margin-right: 2px; }"
            "QTabBar::tab:selected { background: @GRAD_ACCENT;"
            " color: #fff; border-color: @BLUE_BRIGHT; }"
            "QTabBar::tab:hover:!selected { background: @BLUE_DIM; color: @TEXT; border-color: @BLUE; }"
        ))

        # Right-click context menu on tab bar
        self._sb_tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._sb_tabs.tabBar().customContextMenuRequested.connect(self._sb_tab_ctx_menu)

        # Drag-over-tab auto-navigation and tab reordering
        self._sb_tabs.tabBar().setAcceptDrops(True)
        self._sb_tabs.tabBar().installEventFilter(self)
        self._sb_tabs.tabBar().tabMoved.connect(self._sb_tab_moved)
        self._sb_hover_tab = -1
        self._sb_tab_hover_timer = QTimer(self)
        self._sb_tab_hover_timer.setSingleShot(True)
        self._sb_tab_hover_timer.timeout.connect(self._sb_do_tab_switch)

        # Corner buttons — height locked to tab bar height so they don't overflow
        _corner_wrap = QWidget()
        _corner_wrap.setFixedHeight(28)
        _corner_lay = QHBoxLayout(_corner_wrap)
        _corner_lay.setContentsMargins(0, 2, 4, 2)
        _corner_lay.setSpacing(4)

        self._sb_edit_btn = QPushButton("Edit")
        self._sb_edit_btn.setCheckable(True)
        self._sb_edit_btn.setFixedSize(44, 24)
        self._sb_edit_btn.setToolTip("Muokkaustila: vedä kuva/ääni napin päälle tai oikeaklikkaa")
        self._sb_edit_btn.setStyleSheet(T(
            "QPushButton { background: @BG_RAISED; color: @TEXT_FAINT; border: 1px solid @BORDER;"
            " border-radius: 4px; font-size: 10px; font-weight: 700; padding: 0; }"
            "QPushButton:hover:!checked { background: @BLUE_DIM; border-color: @PURPLE; color: @TEXT_DIM; }"
            "QPushButton:checked { background: #1a0e00; color: @GOLD; border: 2px solid @GOLD; padding: 0; }"
        ))
        self._sb_edit_btn.toggled.connect(self._sb_toggle_edit_mode)
        _corner_lay.addWidget(self._sb_edit_btn)

        from PyQt6.QtWidgets import QSlider as _QSlider
        self._sb_vol_slider = _QSlider(Qt.Orientation.Horizontal)
        self._sb_vol_slider.setRange(10, 200)
        self._sb_vol_slider.setValue(int(self.settings.get("soundboard_volume", 1.0) * 100))
        self._sb_vol_slider.setFixedWidth(72)
        self._sb_vol_slider.setToolTip("Soundboard volyymi (kaikki slotet)")
        self._sb_vol_slider.setStyleSheet(T(
            "QSlider::groove:horizontal { height:4px; background:@BORDER; border-radius:2px; }"
            "QSlider::handle:horizontal { width:12px; height:12px; margin:-4px 0;"
            " background:@PURPLE_BRIGHT; border-radius:6px; }"
            "QSlider::sub-page:horizontal { background:@GRAD_ACCENT; border-radius:2px; }"
        ))
        self._sb_vol_label = QLabel(f"{self._sb_vol_slider.value()}%")
        self._sb_vol_label.setFixedWidth(34)
        self._sb_vol_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._sb_vol_label.setStyleSheet(T("color:@TEXT_DIM; font-size:10px; background:transparent;"))

        def _on_sb_vol(v):
            self._sb_vol_label.setText(f"{v}%")
            self.settings["soundboard_volume"] = v / 100.0
            save_settings(self.settings)

        self._sb_vol_slider.valueChanged.connect(_on_sb_vol)
        _corner_lay.addWidget(self._sb_vol_slider)
        _corner_lay.addWidget(self._sb_vol_label)

        _sb_sz_mode = _mode
        _sb_sz_btn = QPushButton("L" if _sb_sz_mode != "small" else "S")
        _sb_sz_btn.setFixedHeight(24)
        _sb_sz_btn.setMinimumWidth(28)
        _sb_sz_btn.setToolTip(
            "Soundboard kuvakkeiden koko\n"
            "L = Suuret (19×3 riviä)\n"
            "S = Pienet (11×5 riviä, mahtuu kaikki 55)\n"
            "Klikkaa vaihtaaksesi"
        )
        _sb_sz_btn.setStyleSheet(T(
            "QPushButton { background: @BG_RAISED; color: @TEXT; border: 1px solid @BORDER;"
            " border-radius: 4px; font-size: 10px; font-weight: 700; padding: 0 6px; }"
            "QPushButton:hover { background: @BLUE_DIM; border-color: @PURPLE; color: #ffffff; }"
            "QPushButton:pressed { background: @BG_INPUT; }"
        ))

        def _toggle_sb_size():
            cur = self.settings.get("sb_icon_size", "large")
            new_mode = "small" if cur == "large" else "large"
            self.settings["sb_icon_size"] = new_mode
            save_settings(self.settings)
            self._sb_rebuild(new_mode)

        _sb_sz_btn.clicked.connect(_toggle_sb_size)
        _corner_lay.addWidget(_sb_sz_btn)

        add_page_btn = QPushButton("+")
        add_page_btn.setFixedWidth(26)
        add_page_btn.setToolTip("Lisää sivu (max 10)")
        add_page_btn.setStyleSheet(T(
            "QPushButton { background: @GRAD_ACCENT;"
            " color: #fff; border: none; border-radius: 4px; font-size: 15px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background: @PURPLE; }"
            "QPushButton:pressed { background: @BG_INPUT; border: 1px solid @BLUE; }"
        ))
        add_page_btn.clicked.connect(self._sb_add_page)
        _corner_lay.addWidget(add_page_btn)
        self._sb_tabs.setCornerWidget(_corner_wrap, Qt.Corner.TopRightCorner)

        # Migrate old flat soundboard_slots to pages format
        pages = self.settings.get("soundboard_pages")
        if not pages:
            old_slots = self.settings.get("soundboard_slots", [])
            pages = [{"name": "Peli aloitus", "slots": old_slots}]

        for page_data in pages:
            self._sb_add_page_widget(page_data)

        outer.addWidget(self._sb_tabs)
        return frame

    def _sb_add_page_widget(self, page_data: dict):
        pi = len(self._soundboard_buttons)
        name = page_data.get("name", f"Sivu {pi + 1}")
        slots = list(page_data.get("slots", []))
        while len(slots) < 55:
            slots.append({"name": f"Slot {len(slots)+1}", "file": "", "image": ""})

        page_btns: list[SoundboardButton] = []
        container = SoundboardPageContainer(pi, page_data.get("groups", []), self._save_soundboard)
        grid = QGridLayout(container)
        grid.setSpacing(SoundboardPageContainer._SPACING)
        grid.setContentsMargins(6, 6, 6, 6)

        for i in range(55):
            btn = SoundboardButton(pi, i)
            if slots[i]:
                btn.set_data(slots[i])
            btn.clicked_play.connect(self._sb_play_handler)
            btn.data_changed.connect(self._sb_data_handler)
            btn.swap_requested.connect(self._sb_swap_handler)
            btn.bulk_import_requested.connect(self._sb_bulk_import_handler)
            page_btns.append(btn)
            row, col = divmod(i, SoundboardPageContainer._COLS)
            grid.addWidget(btn, row, col)

        # Minimum width forces the grid to keep full size so QScrollArea can scroll horizontally
        _sp = SoundboardPageContainer
        _min_w = _sp._COLS * (_sp._BTN_W + _sp._SPACING) - _sp._SPACING + 2 * _sp._MARGIN
        container.setMinimumWidth(_min_w)
        container.init_group_labels()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(container)
        scroll.setStyleSheet(T(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:horizontal { height: 16px; background: @BG_INPUT; border-radius: 8px; margin: 0 18px; }"
            "QScrollBar::handle:horizontal { background: @BLUE_DIM; border-radius: 7px; min-width: 40px; }"
            "QScrollBar::handle:horizontal:hover { background: @BLUE; }"
            "QScrollBar::add-line:horizontal { width: 18px; background: @BG_RAISED;"
            " border-left: 1px solid @BORDER; border-radius: 0 8px 8px 0; }"
            "QScrollBar::sub-line:horizontal { width: 18px; background: @BG_RAISED;"
            " border-right: 1px solid @BORDER; border-radius: 8px 0 0 8px; }"
            "QScrollBar::add-line:horizontal:hover, QScrollBar::sub-line:horizontal:hover"
            " { background: @BLUE_DIM; }"
        ))

        # Fixed toolbar below scroll: [Takaisin] [stretch] [Soita random] [STOP]
        _tb = QWidget()
        _tb.setFixedHeight(36)
        _tb.setStyleSheet(T("background: @BG_INPUT; border-top: 1px solid @BORDER;"))
        _tb_lay = QHBoxLayout(_tb)
        _tb_lay.setContentsMargins(6, 3, 6, 3)
        _tb_lay.setSpacing(6)

        _back_btn = QPushButton("◀ Takaisin")
        _back_btn.setFixedHeight(28)
        _back_btn.setEnabled(False)
        _back_btn.setStyleSheet(T(
            "QPushButton { background: @BG_RAISED; color: @PURPLE_BRIGHT; border: 1px solid @BORDER;"
            " border-radius: 4px; font-size: 10px; font-weight: 700; padding: 0 10px; }"
            "QPushButton:hover:enabled { border-color: @PURPLE; color: #d0c0ff; }"
            "QPushButton:pressed:enabled { background: @BG_INPUT; }"
            "QPushButton:disabled { color: @TEXT_FAINT; border-color: @BORDER; background: @BG_INPUT; }"
        ))
        _back_btn.clicked.connect(lambda: self._sb_go_back(self._sb_tabs.currentIndex()))

        _rand_btn = QPushButton("▶ Soita random")
        _rand_btn.setFixedHeight(28)
        _rand_btn.setStyleSheet(T(
            "QPushButton { background: @BG_RAISED; color: @TEXT_DIM; border: 1px solid @BLUE_DIM;"
            " border-radius: 4px; font-size: 10px; font-weight: 700; padding: 0 10px; }"
            "QPushButton:hover { border-color: @BLUE; color: @BLUE_BRIGHT; }"
            "QPushButton:pressed { background: @BG_INPUT; }"
        ))
        _rand_btn.clicked.connect(lambda: self._sb_play_random(self._sb_tabs.currentIndex()))

        _stop_btn = _OctagonStopButton()
        _stop_btn.setFixedSize(72, 28)
        _stop_btn.setToolTip("Pysäytä soitto heti")
        _stop_btn.clicked.connect(self._sb_stop_playback)

        _tb_lay.addWidget(_back_btn)
        _tb_lay.addStretch()
        _tb_lay.addWidget(_rand_btn)
        _tb_lay.addWidget(_stop_btn)

        # Wrap scroll + toolbar in a single widget for the tab
        _page_wrap = QWidget()
        _pw_lay = QVBoxLayout(_page_wrap)
        _pw_lay.setContentsMargins(0, 0, 0, 0)
        _pw_lay.setSpacing(0)
        _pw_lay.addWidget(scroll)
        _pw_lay.addWidget(_tb)

        self._soundboard_buttons.append(page_btns)
        self._sb_page_containers.append(container)
        self._sb_back_btns.append(_back_btn)
        self._sb_nav_stack[pi] = []
        self._sb_tabs.addTab(_page_wrap, name)

    def _sb_add_page(self):
        if self._sb_tabs.count() >= 10:
            return
        new_data = {"name": f"Sivu {self._sb_tabs.count() + 1}", "slots": []}
        self._sb_add_page_widget(new_data)
        self._save_soundboard()
        self._sb_tabs.setCurrentIndex(self._sb_tabs.count() - 1)

    def _sb_remove_page(self, index: int):
        if self._sb_tabs.count() <= 1:
            return
        self._sb_tabs.removeTab(index)
        self._soundboard_buttons.pop(index)
        if index < len(self._sb_page_containers):
            self._sb_page_containers.pop(index)
        if index < len(self._sb_back_btns):
            self._sb_back_btns.pop(index)
        # Rebuild nav stack with corrected indices
        new_stack = {}
        for old_pi, entries in self._sb_nav_stack.items():
            if old_pi == index:
                continue
            new_pi = old_pi if old_pi < index else old_pi - 1
            new_stack[new_pi] = entries
        self._sb_nav_stack = new_stack
        # Update page_index on buttons of remaining pages
        for pi, page_btns in enumerate(self._soundboard_buttons):
            for btn in page_btns:
                btn.page_index = pi
        self._save_soundboard()

    def _sb_tab_ctx_menu(self, pos):
        index = self._sb_tabs.tabBar().tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        rename_act = menu.addAction("Nimeä uudelleen…")
        grp_act = menu.addAction("Muokkaa ryhmiä…")
        menu.addSeparator()
        delete_act = menu.addAction("Poista sivu")
        delete_act.setEnabled(self._sb_tabs.count() > 1)
        act = menu.exec(self._sb_tabs.tabBar().mapToGlobal(pos))
        if act == rename_act:
            current = self._sb_tabs.tabText(index)
            text, ok = QInputDialog.getText(self, "Nimeä sivu", "Sivun nimi:", text=current)
            if ok and text.strip():
                self._sb_tabs.setTabText(index, text.strip())
                self._save_soundboard()
        elif act == grp_act:
            if index < len(self._sb_page_containers):
                self._sb_page_containers[index].open_groups_dialog()
        elif act == delete_act:
            self._sb_remove_page(index)

    def _sb_play_handler(self, slot_index: int):
        if SoundboardButton._edit_mode:
            return
        sender_btn = self.sender()
        for pi, page_btns in enumerate(self._soundboard_buttons):
            if sender_btn in page_btns:
                data = sender_btn.get_data()
                if data.get("_back"):
                    self._sb_go_back(pi)
                    return
                if data.get("subfolder"):
                    self._sb_enter_folder(pi, slot_index)
                    return
                self._play_soundboard_slot(pi, slot_index)
                return

    def _sb_data_handler(self, slot_index: int):
        sender_btn = self.sender()
        for pi, page_btns in enumerate(self._soundboard_buttons):
            if sender_btn in page_btns:
                self._save_soundboard()
                return

    def _sb_swap_handler(self, src_page: int, src_slot: int, dst_page: int, dst_slot: int):
        if src_page >= len(self._soundboard_buttons) or dst_page >= len(self._soundboard_buttons):
            return
        src_btns = self._soundboard_buttons[src_page]
        dst_btns = self._soundboard_buttons[dst_page]
        if src_slot >= len(src_btns) or dst_slot >= len(dst_btns):
            return
        src_btn = src_btns[src_slot]
        dst_btn = dst_btns[dst_slot]
        src_data = src_btn.get_data()
        dst_data = dst_btn.get_data()
        if src_data.get("_back") or dst_data.get("_back"):
            return
        src_btn.set_data(dst_data)
        dst_btn.set_data(src_data)
        self._save_soundboard()

    def _get_page_root_slots(self, page_index: int) -> list:
        """Return root-level slot data for page, unwinding any subfolder navigation."""
        stack = self._sb_nav_stack.get(page_index, [])
        cur_slots = [btn.get_data() for btn in self._soundboard_buttons[page_index]]
        if not stack:
            return cur_slots
        # Strip the back-button placeholder before storing subfolder contents
        clean = []
        for i, d in enumerate(cur_slots):
            if d.get("_back"):
                clean.append({"name": f"Slot {i+1}", "file": "", "image": "", "link_page_name": ""})
            else:
                clean.append(dict(d))
        # Walk up the stack: stack[0] = outermost, stack[-1] = deepest
        for entry in reversed(stack):
            parent_slots, folder_slot_idx = entry[0], entry[1]
            parent_copy = [dict(s) for s in parent_slots]
            parent_copy[folder_slot_idx] = dict(parent_copy[folder_slot_idx])
            parent_copy[folder_slot_idx]["folder_slots"] = clean
            clean = parent_copy
        return clean

    def _sb_enter_folder(self, page_index: int, slot_index: int):
        """Navigate into a folder slot, replacing the page's buttons with folder contents."""
        page_btns = self._soundboard_buttons[page_index]
        cur_slots = [btn.get_data() for btn in page_btns]
        folder_data = cur_slots[slot_index]
        sub_slots = list(folder_data.get("folder_slots", []))
        while len(sub_slots) < 55:
            sub_slots.append({"name": f"Slot {len(sub_slots)+1}", "file": "", "image": "", "link_page_name": ""})
        # Push current state onto nav stack (include current tab name for restoration)
        prev_tab_name = self._sb_tabs.tabText(page_index)
        self._sb_nav_stack[page_index].append((cur_slots, slot_index, prev_tab_name))
        # Show pinned back button in toolbar
        if page_index < len(self._sb_back_btns):
            self._sb_back_btns[page_index].setEnabled(True)
        # Load subfolder content into buttons
        for i, btn in enumerate(page_btns):
            btn.set_data(sub_slots[i])
        self._sb_tabs.setTabText(page_index, f"📁 {folder_data.get('name', 'Kansio')}")

    def _sb_go_back(self, page_index: int):
        """Navigate back to the parent level from a subfolder."""
        stack = self._sb_nav_stack.get(page_index)
        if not stack:
            return
        # Capture current subfolder contents (without back button)
        page_btns = self._soundboard_buttons[page_index]
        cur_slots = [btn.get_data() for btn in page_btns]
        clean = []
        for i, d in enumerate(cur_slots):
            if d.get("_back"):
                clean.append({"name": f"Slot {i+1}", "file": "", "image": "", "link_page_name": ""})
            else:
                clean.append(dict(d))
        # Pop the stack (3-tuple: parent_slots, folder_slot_idx, prev_tab_name)
        entry = stack.pop()
        parent_slots, folder_slot_idx, prev_tab_name = entry[0], entry[1], entry[2]
        # Save current subfolder contents back into the folder slot
        parent_slots = [dict(s) for s in parent_slots]
        parent_slots[folder_slot_idx] = dict(parent_slots[folder_slot_idx])
        parent_slots[folder_slot_idx]["folder_slots"] = clean
        # Restore parent slots
        for i, btn in enumerate(page_btns):
            btn.set_data(parent_slots[i])
        # Restore tab name to what it was before entering this folder
        self._sb_tabs.setTabText(page_index, prev_tab_name)
        # Hide pinned back button if we're back at root level
        if not stack and page_index < len(self._sb_back_btns):
            self._sb_back_btns[page_index].setEnabled(False)
        self._save_soundboard()

    def _sb_stop_playback(self):
        self._sb_play_id += 1
        self._sb_stop_event.set()
        self._sb_stop_event = threading.Event()
        self._play_stop_event.set()
        self._play_stop_event = threading.Event()
        self.update_output_level(0.0)
        if self._sb_playing_btn:
            btn = self._sb_playing_btn
            self._sb_playing_btn = None
            btn.set_playing(False)

    def _sb_tab_moved(self, from_idx: int, to_idx: int):
        page = self._soundboard_buttons.pop(from_idx)
        self._soundboard_buttons.insert(to_idx, page)
        if from_idx < len(self._sb_page_containers):
            cont = self._sb_page_containers.pop(from_idx)
            self._sb_page_containers.insert(to_idx, cont)
        if from_idx < len(self._sb_back_btns):
            back = self._sb_back_btns.pop(from_idx)
            self._sb_back_btns.insert(to_idx, back)
        # Remap nav stack keys to reflect new indices
        new_stack = {}
        for old_pi, entries in self._sb_nav_stack.items():
            if old_pi == from_idx:
                new_stack[to_idx] = entries
            elif from_idx < to_idx and from_idx < old_pi <= to_idx:
                new_stack[old_pi - 1] = entries
            elif from_idx > to_idx and to_idx <= old_pi < from_idx:
                new_stack[old_pi + 1] = entries
            else:
                new_stack[old_pi] = entries
        self._sb_nav_stack = new_stack
        for pi, page_btns in enumerate(self._soundboard_buttons):
            for btn in page_btns:
                btn.page_index = pi

    def _sb_play_random(self, page_index: int):
        """Play a random sound from the current page (or subfolder)."""
        if SoundboardButton._edit_mode:
            return
        if page_index >= len(self._soundboard_buttons):
            return
        page_btns = self._soundboard_buttons[page_index]
        available = [
            btn for btn in page_btns
            if btn.get_data().get("file")
            and os.path.exists(btn.get_data().get("file", ""))
            and not btn.get_data().get("_back")
            and not btn.get_data().get("subfolder")
        ]
        if not available:
            self.append_status("Soundboard: ei soitettavia ääniä tällä sivulla")
            return
        import random as _rand
        chosen = _rand.choice(available)
        self._play_soundboard_slot(page_index, chosen.slot_index)

    def _sb_do_tab_switch(self):
        if self._sb_hover_tab >= 0:
            self._sb_tabs.setCurrentIndex(self._sb_hover_tab)

    def eventFilter(self, obj, event):
        if hasattr(self, '_sb_tabs') and obj is self._sb_tabs.tabBar():
            t = event.type()
            if t == QEvent.Type.DragEnter:
                if SoundboardButton._edit_mode and event.mimeData().hasFormat(SoundboardButton._SLOT_MIME):
                    event.acceptProposedAction()
                else:
                    event.ignore()
                return True
            if t == QEvent.Type.DragMove:
                if SoundboardButton._edit_mode and event.mimeData().hasFormat(SoundboardButton._SLOT_MIME):
                    tab = self._sb_tabs.tabBar().tabAt(event.position().toPoint())
                    if tab >= 0 and tab != self._sb_hover_tab:
                        self._sb_hover_tab = tab
                        self._sb_tab_hover_timer.start(700)
                    event.acceptProposedAction()
                else:
                    event.ignore()
                return True
            if t == QEvent.Type.DragLeave:
                self._sb_tab_hover_timer.stop()
                self._sb_hover_tab = -1
                return True
            if t == QEvent.Type.Drop:
                self._sb_tab_hover_timer.stop()
                self._sb_hover_tab = -1
                event.ignore()
                return True
        return super().eventFilter(obj, event)

    def _sb_bulk_import_handler(self, start_slot: int, paths: list):
        sender_btn = self.sender()
        page_idx = None
        for pi, page_btns in enumerate(self._soundboard_buttons):
            if sender_btn in page_btns:
                page_idx = pi
                break
        if page_idx is None:
            return
        page_btns = self._soundboard_buttons[page_idx]
        imported = 0
        for i, path in enumerate(paths):
            slot_idx = start_slot + i
            if slot_idx >= len(page_btns):
                break
            btn = page_btns[slot_idx]
            try:
                dest, _, _ = _sb_import_audio(path, page_idx, slot_idx)
                data = btn.get_data()
                data["file"] = dest
                data["link_page_name"] = ""
                if not data.get("name") or data["name"].startswith("Slot "):
                    data["name"] = os.path.splitext(os.path.basename(path))[0]
                btn.set_data(data)
                imported += 1
            except Exception as e:
                self.append_status(f"Bulk import slot {slot_idx+1}: {e}")
        if imported:
            self._save_soundboard()
            self.append_status(
                f"Bulk import: {imported}/{len(paths)} ääntä tuotu sivulle {page_idx+1}, "
                f"slotit {start_slot+1}–{start_slot+imported}"
            )

    def _sb_toggle_edit_mode(self, enabled: bool):
        SoundboardButton.set_edit_mode(enabled)
        self._sb_tabs.tabBar().setMovable(enabled)
        if enabled:
            self.append_status("Soundboard muokkaustila ON — vedä nappi toiselle sivulle/slotille; vedä otsikko järjestyksen muuttamiseksi; oikeaklikkaa muokataksesi")
        else:
            self._save_soundboard()
            self.append_status("Soundboard muokkaustila OFF — tallennettu")

    def _build_voice_fx_card(self) -> QWidget:
        frame, layout = self._make_card("Voice FX — real-time voice morphing via virtual output")

        # Top row: FX ON/OFF + Hear Myself ON/OFF side by side (saves vertical space)
        top_row = QHBoxLayout()
        self._fx_toggle = QPushButton("Voice FX: OFF")
        self._fx_toggle.setCheckable(True)
        self._fx_toggle.setChecked(self.settings.get("voice_fx_enabled", False))
        self._fx_toggle.setToolTip("Kytkee koko äänivirran päälle/pois")
        self._fx_toggle.setStyleSheet(T(
            "QPushButton { background: @BG_RAISED; border: 1px solid @BORDER; color: @TEXT_FAINT; }"
            "QPushButton:hover { border-color: @BLUE; color: @TEXT; }"
            "QPushButton:checked { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #003a1e,stop:1 #002712);"
            " border: 1px solid @GREEN; color: @GREEN; }"
        ))
        if self.settings.get("voice_fx_enabled", False):
            self._fx_toggle.setText("Voice FX: ON")
        self._fx_toggle.clicked.connect(self._toggle_voice_fx)
        top_row.addWidget(self._fx_toggle, 1)

        self._hear_myself_btn = QPushButton("Hear Myself: OFF")
        self._hear_myself_btn.setCheckable(True)
        self._hear_myself_btn.setChecked(self.settings.get("voice_fx_hear_myself", False))
        self._hear_myself_btn.setStyleSheet(T(
            "QPushButton { background: @BG_RAISED; border: 1px solid @BORDER; color: @TEXT_FAINT;"
            " font-size: 11px; font-weight: 700; padding: 5px 10px; }"
            "QPushButton:hover { border-color: @GOLD; color: @TEXT; }"
            "QPushButton:checked { background: #2a1a00; border: 1px solid @GOLD; color: @GOLD; }"
        ))
        if self.settings.get("voice_fx_hear_myself", False):
            self._hear_myself_btn.setText("Hear Myself: ON")
        self._hear_myself_btn.clicked.connect(self._toggle_hear_myself)
        top_row.addWidget(self._hear_myself_btn, 1)
        layout.addLayout(top_row)

        # Hear Myself monitor device — omat kuulokkeet/kaiuttimet, oletuksena Windowsin
        # oletus-toistolaite (ei tarvitse etsiä käsin)
        mon_row = QHBoxLayout()
        mon_lbl = QLabel("KUULEN ITSENI:")
        mon_lbl.setStyleSheet(T("border: none; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; color: @TEXT_FAINT;"))
        mon_row.addWidget(mon_lbl)
        self._fx_monitor_combo = QComboBox()
        self._populate_fx_monitor_combo()
        self._fx_monitor_combo.activated.connect(self._on_fx_monitor_device_changed)
        mon_row.addWidget(self._fx_monitor_combo, 1)
        layout.addLayout(mon_row)

        # FX Output — ei enää käsivalikkoa, aina sama chat-virtuaalikaapeli joka on jo
        # valittuna Output-laitteissa (TTS/soundboard käyttävät samaa listaa)
        self._fx_output_status_lbl = QLabel()
        self._fx_output_status_lbl.setWordWrap(True)
        layout.addWidget(self._fx_output_status_lbl)
        self._refresh_fx_output_status()

        # Preset buttons — 5 pientä saraketta niin kaikki 14 (perus pitch +
        # stftPitchShiftin poly-pitch-presetit) mahtuvat näkyviin ilman vierittämistä
        presets_lbl = QLabel("PRESET:")
        presets_lbl.setStyleSheet(T("font-size: 11px; font-weight: 700; letter-spacing: 0.5px; color: @BLUE_BRIGHT; border: none; margin-top: 6px;"))
        layout.addWidget(presets_lbl)

        preset_grid = QGridLayout()
        preset_grid.setSpacing(4)
        preset_items = list(VoiceEffectProcessor.PRESETS.keys())
        _FX_PRESET_COLS = 5
        for i, preset in enumerate(preset_items):
            btn = QPushButton(preset)
            btn.setCheckable(True)
            btn.setChecked(preset == "Normal")
            btn.setMinimumHeight(26)
            btn.setStyleSheet(T(
                "QPushButton { background: @BG_RAISED; border: 1px solid @BORDER;"
                " border-radius: 6px; color: @TEXT_DIM; font-weight: 600; padding: 4px 2px; font-size: 10px; }"
                "QPushButton:hover { background: @BLUE_DIM; border-color: @PURPLE; color: @TEXT; }"
                "QPushButton:checked { background: @GRAD_ACCENT; border: 2px solid @BLUE_BRIGHT; color: #fff; }"
            ))
            btn.clicked.connect(lambda checked, p=preset: self._select_fx_preset(p))
            preset_grid.addWidget(btn, i // _FX_PRESET_COLS, i % _FX_PRESET_COLS)
            self._fx_preset_buttons[preset] = btn
        layout.addLayout(preset_grid)

        layout.addStretch()

        hint = QLabel("FX Output on aina sama chat-virtuaalikaapeli (esim. Voicemeeter Input) jonka olet valinnut Output-laitteissa — ei erillistä valintaa. \"Voice FX: ON\" käynnistää koko äänivirran, \"OFF\" pysäyttää sen kokonaan.")
        hint.setStyleSheet(T("color: @TEXT_FAINT; font-size: 11px; border: none; margin-top: 4px;"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return frame

    def _refresh_fx_output_status(self):
        if not hasattr(self, "_fx_output_status_lbl"):
            return
        out_dev = self._get_auto_fx_output_device()
        if out_dev is not None:
            try:
                name = sd.query_devices(out_dev)["name"]
            except Exception:
                name = str(out_dev)
            self._fx_output_status_lbl.setText(f"✅ FX Output (automaattinen): {name}")
            self._fx_output_status_lbl.setStyleSheet(T("border: none; font-size: 11px; color: @GREEN; margin-top: 2px;"))
        else:
            self._fx_output_status_lbl.setText(
                "⚠️ Ei chat-virtuaalikaapelia valittuna Output-laitteissa — valitse esim. "
                "\"Voicemeeter Input\" Laitteet-listasta jotta Voice FX voi käynnistyä."
            )
            self._fx_output_status_lbl.setStyleSheet(T("border: none; font-size: 11px; color: @GOLD; margin-top: 2px;"))

    def _populate_fx_monitor_combo(self):
        self._fx_monitor_combo.clear()
        saved = self.settings.get("voice_fx_monitor_device")
        virtual_kw = ("cable", "voicemeeter", "voicemod", "virtual")
        junk_kw = ("microsoft sound mapper", "primary sound", "bthhfenum")
        disabled_names = _windows_disabled_audio_names()
        for i, n in list_output_devices():
            nl = n.lower()
            if (not n.startswith("{") and not any(k in nl for k in virtual_kw)
                    and not any(k in nl for k in junk_kw)
                    and not _matches_disabled_name(n, disabled_names)):
                self._fx_monitor_combo.addItem(f"🎧 {n}", i)
        target_idx = saved
        target_name = None
        if target_idx is None:
            # sd.default.device -indeksi elää eri ajuri-indeksiavaruudessa kuin
            # list_output_devices() (joka dedupplikoi nimen perusteella ja pitää
            # parhaan ajurin indeksin) — täsmäytys täytyy siis tehdä NIMELLÄ,
            # ei indeksillä, tai oletusvalinta ei koskaan osu mihinkään ja jää
            # ensimmäiseen listan laitteeseen.
            try:
                target_name = sd.query_devices(sd.default.device[1])["name"].lower().strip()
            except Exception:
                target_name = None
        if target_idx is not None:
            for idx in range(self._fx_monitor_combo.count()):
                if self._fx_monitor_combo.itemData(idx) == target_idx:
                    self._fx_monitor_combo.setCurrentIndex(idx)
                    break
        elif target_name is not None:
            # Tarkka osuma ensin, sitten prefix-vertailu — Windowsin oletuslaitenimi
            # voi tulla MME-rajapinnan katkaisemana (~31 merkkiin).
            _fallback_idx = None
            for idx in range(self._fx_monitor_combo.count()):
                item_dev_idx = self._fx_monitor_combo.itemData(idx)
                try:
                    item_name = sd.query_devices(item_dev_idx)["name"].lower().strip()
                except Exception:
                    continue
                if item_name == target_name:
                    self._fx_monitor_combo.setCurrentIndex(idx)
                    break
                cmp = min(len(item_name), len(target_name))
                if _fallback_idx is None and cmp >= 16 and item_name[:cmp] == target_name[:cmp]:
                    _fallback_idx = idx
            else:
                if _fallback_idx is not None:
                    self._fx_monitor_combo.setCurrentIndex(_fallback_idx)
        _fit_combo_dropdown(self._fx_monitor_combo)

    def _on_fx_monitor_device_changed(self):
        mon_dev = self._fx_monitor_combo.currentData()
        if mon_dev is None:
            return
        self.settings["voice_fx_monitor_device"] = mon_dev
        save_settings(self.settings)
        if self._hear_myself_btn.isChecked():
            self._voice_fx.set_monitor(mon_dev, True)

    def _toggle_hear_myself(self):
        enabled = self._hear_myself_btn.isChecked()
        self._hear_myself_btn.setText("Hear Myself: ON" if enabled else "Hear Myself: OFF")
        mon_dev = self._fx_monitor_combo.currentData()
        self.settings["voice_fx_hear_myself"] = enabled
        self.settings["voice_fx_monitor_device"] = mon_dev
        save_settings(self.settings)
        self._voice_fx.set_monitor(mon_dev, enabled)

    def _build_outputs_card(self) -> QWidget:
        frame, layout = self._make_card("")

        # Header row: title + action buttons
        header = QHBoxLayout()
        title_lbl = QLabel("OUTPUT DEVICES & LEVELS")
        title_lbl.setStyleSheet("font-weight: 700; font-size: 12px; color: #2e7fff; letter-spacing: 0.5px; border: none;")
        header.addWidget(title_lbl)
        header.addStretch()
        self.refresh_devices_button = QPushButton("🔄 Refresh")
        self.refresh_devices_button.clicked.connect(self.refresh_all_devices)
        header.addWidget(self.refresh_devices_button)
        self.device_info_button = QPushButton("ℹ️ Info")
        self.device_info_button.clicked.connect(self.on_device_info)
        header.addWidget(self.device_info_button)
        layout.addLayout(header)

        # Scrollable container for per-device rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(80)
        scroll.setMaximumHeight(160)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #1c2c52; border-radius: 8px; background: #0a0f1e; }"
        )
        container = QWidget()
        container.setStyleSheet("background: #0a0f1e;")
        self._device_rows_layout = QVBoxLayout(container)
        self._device_rows_layout.setSpacing(2)
        self._device_rows_layout.setContentsMargins(4, 4, 4, 4)
        self._device_rows_layout.addStretch()  # push items up
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Input device row at the bottom
        input_row = QHBoxLayout()
        input_lbl = QLabel("INPUT MIC:")
        input_lbl.setStyleSheet("border: none; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; color: #546a94;")
        input_row.addWidget(input_lbl)
        self.input_device_combo = QComboBox()
        self.input_device_combo.currentIndexChanged.connect(self.on_input_device_changed)
        input_row.addWidget(self.input_device_combo, 1)
        layout.addLayout(input_row)

        return frame

    def _build_meters_bar(self) -> QWidget:
        """Always-visible compact mic + output meters strip at the bottom of the window."""
        frame = QFrame()
        frame.setFixedHeight(36)
        frame.setStyleSheet(T(
            "QFrame { background: @BG_INPUT; border: 1px solid @BORDER; border-radius: 8px; }"
        ))
        outer = QHBoxLayout(frame)
        outer.setContentsMargins(10, 4, 10, 4)
        outer.setSpacing(0)

        # MIC section (always visible)
        mic_lbl = QLabel("MIC")
        mic_lbl.setStyleSheet(T("color: @GREEN; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; border: none; min-width: 26px;"))
        outer.addWidget(mic_lbl)
        outer.addSpacing(4)

        self.mic_level_bar = QProgressBar()
        self.mic_level_bar.setRange(0, 1000)
        self.mic_level_bar.setValue(0)
        self.mic_level_bar.setTextVisible(False)
        self.mic_level_bar.setFixedHeight(6)
        self.mic_level_bar.setMinimumWidth(80)
        self.mic_level_bar.setMaximumWidth(140)
        self.mic_level_bar.setStyleSheet(METER_STYLE_MIC)
        outer.addWidget(self.mic_level_bar)
        outer.addSpacing(4)

        self.mic_db_label = QLabel("-∞")
        self.mic_db_label.setStyleSheet(T(
            "color: @TEXT_FAINT; font-size: 9px; font-family: Consolas; border: none;"
        ))
        self.mic_db_label.setFixedWidth(34)
        self.mic_db_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        outer.addWidget(self.mic_db_label)

        sep0 = QFrame()
        sep0.setFrameShape(QFrame.Shape.VLine)
        sep0.setFixedWidth(1)
        sep0.setStyleSheet(T("background: @BORDER; border: none;"))
        outer.addSpacing(6)
        outer.addWidget(sep0)
        outer.addSpacing(6)

        lbl = QLabel("OUT")
        lbl.setStyleSheet(T("color: @BLUE_BRIGHT; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; border: none; min-width: 26px;"))
        outer.addWidget(lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(T("background: @BORDER; border: none;"))
        outer.addWidget(sep)
        outer.addSpacing(8)

        # Inner container rebuilt by _refresh_bottom_meters
        self._mb_inner = QWidget()
        self._mb_inner.setStyleSheet("background: transparent;")
        self._mb_inner_lay = QHBoxLayout(self._mb_inner)
        self._mb_inner_lay.setContentsMargins(0, 0, 0, 0)
        self._mb_inner_lay.setSpacing(14)
        self._mb_placeholder = QLabel("No output devices selected")
        self._mb_placeholder.setStyleSheet(T("color: @TEXT_FAINT; font-size: 11px; border: none;"))
        self._mb_inner_lay.addWidget(self._mb_placeholder)
        self._mb_inner_lay.addStretch()
        outer.addWidget(self._mb_inner, 1)

        # Resize-kahva frameless-ikkunalle (oikea alakulma)
        grip = QSizeGrip(frame)
        grip.setFixedSize(16, 16)
        grip.setStyleSheet("background: transparent; border: none;")
        outer.addSpacing(4)
        outer.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        return frame

    def _refresh_bottom_meters(self):
        """Rebuild the always-visible meters to match currently selected devices."""
        # Clear existing device widgets
        for bar, db_lbl, container in self._mb_bars.values():
            container.setParent(None)
            container.deleteLater()
        self._mb_bars.clear()

        selected = [(idx, w) for idx, w in self._device_widgets.items()
                    if w["checkbox"].isChecked()]
        self._mb_placeholder.setVisible(len(selected) == 0)

        for idx, w in selected:
            name = w["full_name"]
            short = (name[:15] + "…") if len(name) > 15 else name

            name_lbl = QLabel(short)
            name_lbl.setStyleSheet(T("color: @TEXT_FAINT; font-size: 9px; border: none;"))

            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setMinimumWidth(70)
            bar.setStyleSheet(METER_STYLE_OUT)

            db_lbl = QLabel("-∞")
            db_lbl.setStyleSheet(T(
                "color: @TEXT_FAINT; font-size: 9px; font-family: Consolas; border: none;"
            ))
            db_lbl.setFixedWidth(34)
            db_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            col = QVBoxLayout()
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(1)
            col.addWidget(name_lbl)
            col.addWidget(bar)

            row_lay = QHBoxLayout()
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(4)
            row_lay.addLayout(col, 1)
            row_lay.addWidget(db_lbl)

            container = QWidget()
            container.setStyleSheet("background: transparent;")
            container.setLayout(row_lay)
            container.setMinimumWidth(110)

            # Insert before the stretch (last item)
            insert_pos = self._mb_inner_lay.count() - 1
            self._mb_inner_lay.insertWidget(insert_pos, container, 1)
            self._mb_bars[idx] = (bar, db_lbl, container)

    # ============ Per-device row helpers ============

    def _add_device_row(self, device_index: int, display_name: str, full_name: str, was_selected: bool):
        container = QWidget()
        container.setStyleSheet(
            "QWidget { background: #0a0f1e; border: 1px solid #1c2c52; border-radius: 8px; }"
        )
        row = QHBoxLayout(container)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(8)

        cb = QCheckBox()
        cb.setChecked(was_selected)
        cb.stateChanged.connect(self.on_output_device_changed)

        name_lbl = QLabel(display_name)
        name_lbl.setStyleSheet("color: #b9c5e6; font-size: 12px; border: none;")
        name_lbl.setMinimumWidth(180)
        name_lbl.setMaximumWidth(500)
        name_lbl.setToolTip(full_name)

        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(12)
        bar.setStyleSheet(METER_STYLE_OUT)

        db_lbl = QLabel("-∞ dB")
        db_lbl.setStyleSheet("color: #546a94; font-family: 'Consolas', monospace; font-size: 11px; border: none;")
        db_lbl.setMinimumWidth(64)
        db_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(cb)
        row.addWidget(name_lbl)
        row.addWidget(bar, 1)
        row.addWidget(db_lbl)

        # Insert before the trailing stretch
        insert_index = max(0, self._device_rows_layout.count() - 1)
        self._device_rows_layout.insertWidget(insert_index, container)

        self._device_widgets[device_index] = {
            "checkbox": cb,
            "name_label": name_lbl,
            "meter": bar,
            "db_label": db_lbl,
            "container": container,
            "full_name": full_name,
        }

    def _clear_device_rows(self):
        for idx, w in list(self._device_widgets.items()):
            container = w["container"]
            container.setParent(None)
            container.deleteLater()
        self._device_widgets = {}

    # ============ Meter helpers ============

    @staticmethod
    def _level_to_db(value_int: int) -> str:
        """Convert 0-1000 meter value to a dB string. Floor at -60 dB."""
        if value_int <= 0:
            return "-∞ dB"
        linear = value_int / 1000.0
        db = 20.0 * math.log10(max(linear, 1e-6))
        if db < -60:
            return "-∞ dB"
        return f"{db:+.1f} dB"

    def _update_mic_meter(self, value: int):
        self.mic_level_bar.setValue(value)
        self.mic_db_label.setText(self._level_to_db(value))

    def _update_output_meters(self, value: int):
        """Broadcast the output level to every checked device's meter."""
        db_text = self._level_to_db(value)
        db_short = db_text.replace(" dB", "")
        for idx, w in self._device_widgets.items():
            if w["checkbox"].isChecked():
                w["meter"].setValue(value)
                w["db_label"].setText(db_text)
            else:
                w["meter"].setValue(0)
                w["db_label"].setText("-∞ dB")
        # Update always-visible bottom meters
        for idx, (bar, db_lbl, _) in self._mb_bars.items():
            bar.setValue(value)
            db_lbl.setText(db_short)

    def _check_voicemeeter_running(self):
        """Poll tasklist for Voicemeeter Banana; show/hide warning label on main thread."""
        def _poll():
            try:
                import subprocess as _sp
                r = _sp.run(["tasklist", "/NH"], capture_output=True, text=True, timeout=5,
                        creationflags=_sp.CREATE_NO_WINDOW)
                running = any(
                    name in r.stdout.lower()
                    for name in ("voicemeeterb.exe", "voicemeeterpro_x64.exe", "voicemeeterpro.exe")
                )
            except Exception:
                running = True  # assume ok on error, avoid false alarm
            QTimer.singleShot(0, lambda: self._vm_warning_label.setVisible(not running))
        threading.Thread(target=_poll, daemon=True).start()

    def append_status(self, message: str):
        self.sig_status.emit(message)

    def _on_status(self, message: str):
        current_text = self.status_text.toPlainText()
        lines = current_text.split('\n')
        if len(lines) > 8:
            lines = lines[-7:]
        lines.append(message)
        self.status_text.setPlainText('\n'.join(lines))
        cursor = self.status_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.status_text.setTextCursor(cursor)
        self._compact.set_status(message)

    def update_translated(self, text: str):
        self.sig_status.emit(f"→ {text}")
        QTimer.singleShot(0, lambda: self.translated_label.setText(f"Translated: {text}"))
        QTimer.singleShot(0, lambda: self._overlay.set_translation(text))

    def _overlay_on_transcription(self, text: str):
        self._overlay.set_transcription(text)
        self._overlay.set_translation("")

    def toggle_overlay(self):
        if self._overlay.isVisible():
            pos = self._overlay.pos()
            self.settings["overlay_pos"] = [pos.x(), pos.y()]
            save_settings(self.settings)
            self._overlay.hide()
        else:
            self._overlay.show()
        self._overlay_btn.setChecked(self._overlay.isVisible())

    def toggle_compact_mode(self):
        if self._compact.isVisible():
            pos = self._compact.pos()
            self.settings["compact_pos"] = [pos.x(), pos.y()]
            save_settings(self.settings)
            self._compact.hide()
            self.show()
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
            self.activateWindow()
            self.raise_()
        else:
            self._compact.sync_lang(self.langbox.currentText())
            self._compact.set_rec_state(self.is_recording)
            self._compact.show()
            self.hide()
        self._compact_btn.setChecked(self._compact.isVisible())

    def set_controls_enabled(self, enabled: bool):
        QTimer.singleShot(0, lambda: self._set_controls_enabled_main(enabled))

    def _set_controls_enabled_main(self, enabled: bool):
        self.speak_button.setEnabled(enabled)
        self.test_audio_button.setEnabled(enabled)
        self.favorite_button.setEnabled(enabled)
        if not self.is_recording:
            self.record_button.setEnabled(enabled)

    def refresh_history_views(self):
        self.history_list.clear()
        for item_data in self.history:
            if isinstance(item_data, dict):
                display_lang = item_data.get("display_lang", "Auto")
                text = item_data.get("text", "")
                display_text = f"{display_lang} | {text}"
            else:
                # Backward compatibility for old string entries
                display_text = item_data

            icon = self.lang_icons.get(display_lang)
            if icon:
                item = QListWidgetItem(icon, display_text)
            else:
                item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, item_data)  # Store full data
            self.history_list.addItem(item)

        self.favorites_list.clear()
        for item_data in self.favorites:
            if isinstance(item_data, dict):
                display_lang = item_data.get("display_lang", "Auto")
                text = item_data.get("text", "")
                display_text = f"⭐ {display_lang} | {text}"
            else:
                # Backward compatibility for old string entries
                display_text = f"⭐ {item_data}"

            icon = self.lang_icons.get(display_lang)
            if icon:
                item = QListWidgetItem(icon, display_text)
            else:
                item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, item_data)  # Store full data
            self.favorites_list.addItem(item)

    def add_to_history(self, text: str):
        text = text.strip()
        if not text:
            return

        # Get current language
        current_lang = self.langbox.currentText()
        lang_code = LANGS.get(current_lang, "auto")

        # Create history entry with text and language
        history_entry = {
            "text": text,
            "language": lang_code,
            "display_lang": current_lang
        }

        # Remove if already exists
        self.history = [h for h in self.history if not (isinstance(h, dict) and h.get("text") == text)]
        self.history.insert(0, history_entry)
        self.history = self.history[:10]
        self.history_data["history"] = self.history
        save_history_data(self.history_data)
        self.refresh_history_views()

    def toggle_favorite(self):
        text = self.textbox.toPlainText().strip()
        if not text:
            self.append_status("Cannot favorite empty text.")
            return

        current_lang = self.langbox.currentText()
        lang_code = LANGS.get(current_lang, "auto")

        existing_fav = next((f for f in self.favorites if isinstance(f, dict) and f.get("text") == text), None)
        if existing_fav:
            audio_file = existing_fav.get("audio_file", "")
            if audio_file and os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                except Exception:
                    pass
            self.favorites.remove(existing_fav)
            self.append_status("Removed from favorites.")
        else:
            favorite_entry = {
                "text": text,
                "language": lang_code,
                "display_lang": current_lang,
                "audio_file": "",
                "translated_text": "",
            }
            self.favorites.insert(0, favorite_entry)
            self.append_status("Added to favorites. Caching audio...")
            threading.Thread(target=self._generate_favorite_audio, args=(favorite_entry,), daemon=True).start()

        self.history_data["favorites"] = self.favorites
        save_history_data(self.history_data)
        self.refresh_history_views()

    def _generate_favorite_audio(self, entry: dict):
        text = entry.get("text", "")
        lang_code = entry.get("language", "auto")
        display_lang = entry.get("display_lang", "Auto")
        try:
            translated = translate_text(
                text, lang_code,
                backend=self.settings.get("translation_backend", "Google (free)"),
                deepl_key=self.settings.get("deepl_api_key", ""),
            )
            if not translated:
                return
            tts_backend = self.backend_combo.currentText()
            if tts_backend == "ElevenLabs" and ELEVEN_API_KEY and VOICE_ID:
                wav_bytes = request_tts_wav(translated)
            elif tts_backend.startswith("Edge TTS"):
                import asyncio
                wav_bytes = asyncio.run(request_edge_tts_wav(translated, lang_code))
            else:
                wav_bytes = request_local_tts_wav(translated)
            audio_dir = os.path.join(BASE_PATH, "favorites_audio")
            os.makedirs(audio_dir, exist_ok=True)
            audio_hash = hashlib.md5(f"{text}|{lang_code}".encode()).hexdigest()[:16]
            audio_path = os.path.join(audio_dir, f"{audio_hash}.wav")
            with open(audio_path, "wb") as f:
                f.write(wav_bytes)
            entry["audio_file"] = audio_path
            entry["translated_text"] = translated
            self.history_data["favorites"] = self.favorites
            save_history_data(self.history_data)
            self.append_status(f"Audio cached for favorite ({display_lang}).")
        except Exception as e:
            self.append_status(f"Failed to cache favorite audio: {e}")

    def _play_favorite_audio(self, audio_file: str):
        try:
            with open(audio_file, "rb") as f:
                wav_bytes = f.read()
            play_wav_bytes(
                wav_bytes,
                device_indices=self.get_selected_devices(),
                level_callback=self.update_output_level,
                stop_event=self._play_stop_event,
            )
            self.update_output_level(0.0)
        except Exception as e:
            self.append_status(f"Failed to play cached audio: {e}")

    def on_history_item_selected(self, item):
        item_data = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(item_data, dict):
            text = item_data.get("text", "")
            display_lang = item_data.get("display_lang", "Auto")
            audio_file = item_data.get("audio_file", "")
            translated_text = item_data.get("translated_text", "")

            self.textbox.setPlainText(text)
            lang_index = self.langbox.findText(display_lang)
            if lang_index >= 0:
                self.langbox.setCurrentIndex(lang_index)

            if audio_file and os.path.exists(audio_file):
                if translated_text:
                    self.update_translated(translated_text)
                self.append_status(f"Playing cached audio ({display_lang})...")
                threading.Thread(target=self._play_favorite_audio, args=(audio_file,), daemon=True).start()
        else:
            # Backward compatibility for old string entries
            item_text = item.text()
            if item_text.startswith("⭐ "):
                item_text = item_text[2:]
            # Try to extract language if present in format "LANG | text"
            if " | " in item_text:
                lang_part, text_part = item_text.split(" | ", 1)
                self.textbox.setPlainText(text_part)
                lang_index = self.langbox.findText(lang_part)
                if lang_index >= 0:
                    self.langbox.setCurrentIndex(lang_index)
            else:
                self.textbox.setPlainText(item_text)

    def populate_output_devices(self):
        self._clear_device_rows()
        devices = list_output_devices()
        if not devices:
            self.append_status("No audio output devices detected")
            return

        saved_devices = self.history_data.get("selected_output_devices", []) or []
        # Nimipohjainen tallennus (kuten mikrofonivalinnalla jo) — PortAudio-indeksit
        # eivät pysy vakioina uudelleenkäynnistysten välillä (virtuaalikaapelit/USB-
        # laitteet siirtävät numerointia), joten pelkkä indeksivertailu voi jättää
        # tallennetun laitteen valitsematta TAI valita väärän laitteen jolla nyt
        # sattuu olemaan sama numero. Nimi on ainoa pysyvä tunniste istuntojen yli.
        saved_names = set(self.history_data.get("selected_output_device_names", []) or [])

        # Prioritize routing-capable devices (VoiceMeeter, virtual, Rodecaster, etc.)
        routing_devices = [
            (index, name) for index, name in devices
            if any(keyword in name.lower() for keyword in ["voicemeeter", "virtual", "vb-audio", "voice", "rodecaster", "rode caster"])
        ]
        other_devices = [
            (index, name) for index, name in devices
            if not any(keyword in name.lower() for keyword in ["voicemeeter", "virtual", "vb-audio", "voice", "rodecaster", "rode caster"])
        ]

        def _was_selected(index, name):
            if saved_names:
                return name in saved_names
            return index in saved_devices  # vanha data ilman nimiä — index-fallback

        for index, name in routing_devices:
            self._add_device_row(index, f"🎛️ {name}", name, was_selected=_was_selected(index, name))
        for index, name in other_devices[:8]:
            self._add_device_row(index, f"🔊 {name}", name, was_selected=_was_selected(index, name))

        device_count = len(routing_devices) + min(len(other_devices), 8)
        self.append_status(f"Found {device_count} output devices ({len(routing_devices)} routing-capable)")
        self._refresh_bottom_meters()
        # Checkbox stateChanged only fires for devices whose checked state actually
        # CHANGES during population — if nothing changed (or PortAudio re-enumerated
        # indices so a previously-saved device never got re-checked), the Voice FX
        # status label could otherwise be left showing a stale "not selected" warning
        # from before the list was populated. Refresh unconditionally here instead.
        if hasattr(self, "_fx_output_status_lbl"):
            self._refresh_fx_output_status()

    def refresh_all_devices(self):
        self.populate_output_devices()
        self.populate_input_devices()

    def populate_input_devices(self):
        # Read saved selection BEFORE modifying the combo — addItem fires currentIndexChanged
        # which calls on_input_device_changed and would overwrite history_data mid-population
        saved_input_device = self.history_data.get("selected_input_device")
        saved_input_name = self.history_data.get("selected_input_device_name", "")

        self.input_device_combo.blockSignals(True)
        self.input_device_combo.clear()
        devices = list_input_devices()
        if not devices:
            self.input_device_combo.addItem("No audio input devices detected", -1)
            self.input_device_combo.blockSignals(False)
            self.append_status("No audio input devices detected")
            return

        _virtual_kw = ["voicemeeter", "vb-audio", "voicemod"]
        _exclude_kw = ["bthhfenum", "microsoft sound mapper", "primary sound capture"]

        best: dict[str, tuple] = {}  # friendly_name -> (index, name, samplerate)
        for index, name in devices:
            n = name.lower()
            if name.startswith("{") or any(k in n for k in _exclude_kw):
                continue
            try:
                sr = sd.query_devices(index)["default_samplerate"]
            except Exception:
                sr = 0
            if name not in best or sr > best[name][2]:
                best[name] = (index, name, sr)

        physical = []
        virtual = []
        for name, (index, fullname, sr) in best.items():
            n = name.lower()
            if any(k in n for k in _virtual_kw):
                virtual.append((index, fullname))
            else:
                physical.append((index, fullname))

        physical.sort(key=lambda x: (0 if "rode" in x[1].lower() else 1, x[1]))

        for index, name in physical:
            self.input_device_combo.addItem(f"🎤 {name}", index)
        for index, name in virtual:
            self.input_device_combo.addItem(f"🔌 {name}", index)

        self.append_status(f"Found {self.input_device_combo.count()} input devices ({len(physical)} physical, {len(virtual)} virtual)")
        _fit_combo_dropdown(self.input_device_combo)
        self.input_device_combo.blockSignals(False)

        # Restore by name first (stable across PortAudio re-enumeration), then by index
        matched = False
        if saved_input_name:
            for i in range(self.input_device_combo.count()):
                if self.input_device_combo.itemText(i) == saved_input_name:
                    self.input_device_combo.setCurrentIndex(i)  # fires on_input_device_changed
                    matched = True
                    break
        if not matched and saved_input_device is not None:
            for i in range(self.input_device_combo.count()):
                if self.input_device_combo.itemData(i) == saved_input_device:
                    self.input_device_combo.setCurrentIndex(i)  # fires on_input_device_changed
                    matched = True
                    break
        if not matched:
            # No saved preference or device not found — combo is at 0, ensure monitor starts
            self.on_input_device_changed()

    def get_selected_devices(self):
        """Get list of selected output device indices (or None if none)."""
        selected_devices = [
            idx for idx, w in self._device_widgets.items() if w["checkbox"].isChecked()
        ]
        return selected_devices if selected_devices else None

    def get_selected_input_device(self):
        index = self.input_device_combo.currentData()
        return index if isinstance(index, int) and index >= 0 else None

    def on_output_device_changed(self):
        """Called when a device checkbox is toggled — persist selection by index
        AND by name (name is what survives PortAudio re-enumeration across restarts)."""
        selected_devices = self.get_selected_devices()
        self.history_data["selected_output_devices"] = selected_devices or []
        self.history_data["selected_output_device_names"] = [
            self._device_widgets[idx]["full_name"]
            for idx in (selected_devices or [])
            if idx in self._device_widgets
        ]
        save_history_data(self.history_data)
        for w in self._device_widgets.values():
            if not w["checkbox"].isChecked():
                w["meter"].setValue(0)
                w["db_label"].setText("-∞ dB")
        self._refresh_bottom_meters()
        self._refresh_fx_output_status()
        if hasattr(self, "_voice_fx"):
            self._restart_voice_fx_output()

    def on_input_device_changed(self):
        selected_device = self.get_selected_input_device()
        if selected_device is not None:
            self.history_data["selected_input_device"] = selected_device
            self.history_data["selected_input_device_name"] = self.input_device_combo.currentText()
            save_history_data(self.history_data)
        self._stop_mic_monitor()
        self._start_mic_monitor()

    def register_hotkey(self):
        if self._registered_hotkey:
            try:
                if _keyboard_mod:
                    _keyboard_mod.remove_hotkey(self._registered_hotkey)
            except Exception:
                pass
            self._registered_hotkey = None

        if _keyboard_mod is None:
            self.append_status("Global hotkey not available on this platform.")
            return

        hk = self.settings.get("hotkey", "ctrl+alt+space")
        try:
            self._registered_hotkey = _keyboard_mod.add_hotkey(hk, self.on_hotkey_triggered)
        except Exception as exc:
            self.append_status(f"Hotkey registration failed: {exc}")

    def apply_settings_changes(self):
        """Re-apply settings after the dialog saves them."""
        _apply_custom_languages_to_globals(self.settings.get("custom_languages", []))
        SoundboardButton.set_pixabay_key(self.settings.get("pixabay_api_key", ""))
        self.rebuild_langbox()
        new_lang = self.settings.get("default_target_lang", "Auto")
        if self.langbox.findText(new_lang) >= 0:
            self.langbox.setCurrentText(new_lang)
        new_src = self.settings.get("stt_source_language", "Finnish")
        if self.source_langbox.findText(new_src) >= 0:
            self.source_langbox.setCurrentText(new_src)
        new_backend = self.settings.get("default_tts_backend", DEFAULT_TTS_BACKEND)
        if self.backend_combo.findText(new_backend) >= 0:
            self.backend_combo.setCurrentText(new_backend)

        self.hotkey_label.setText(f"Global hotkey: {self.settings.get('hotkey', 'ctrl+alt+space')}")
        self.register_hotkey()
        self._overlay.set_font_size(int(self.settings.get("overlay_font_size", 16)))

        # If wake listener is running, restart it with new keyword/key
        if self.wake_listener.is_running():
            self.append_status("Restarting wake-word listener with new settings...")
            self.wake_listener.stop()
            self._start_wake_listener()

    # ============ Wake-word listener controls ============

    def toggle_wake_listener(self):
        if self.wake_listener.is_running():
            self.wake_listener.stop()
            self.listen_button.setText("👂  Listen")
            self.listen_button.setChecked(False)
            self.wake_status_label.setText("Wake-word: off")
            self.wake_instructions_label.setVisible(False)
            self._start_mic_monitor()
        else:
            self._stop_mic_monitor()
            ok = self._start_wake_listener()
            if ok:
                self.listen_button.setText("⏹  Stop")
                self.listen_button.setChecked(True)
                kw = self.settings.get("wake_keyword", "jarvis")
                custom = self.settings.get("wake_custom_ppn_path", "")
                kw_display = os.path.basename(custom) if custom else kw
                self.wake_status_label.setText(f"Listening: {kw_display}")
                self._mic_peak_ref[0] = 0.0
                secs = self.settings.get("wake_command_seconds", 6.0)
                self.wake_instructions_label.setText(
                    f'Say  "{kw_display}"  then within {secs:.0f}s:\n'
                    f'  "[target language]: [text to translate]"\n\n'
                    f'Examples:\n'
                    f'  "{kw_display}, in German: hello how are you"\n'
                    f'  "{kw_display}, saksaksi: mitä kuuluu"\n'
                    f'  "{kw_display}, auf Deutsch: guten Tag"\n\n'
                    f'Language hint works in any language. Source language auto-detected.\n'
                    f'No language = uses the language selected in the dropdown.'
                )
                self.wake_instructions_label.setVisible(True)
            else:
                self.listen_button.setChecked(False)

    def _on_wake_level(self, peak: float):
        if peak > self._mic_peak_ref[0]:
            self._mic_peak_ref[0] = peak

    def _start_wake_listener(self) -> bool:
        return self.wake_listener.start(
            access_key=self.settings.get("picovoice_access_key", ""),
            keyword=self.settings.get("wake_keyword", "jarvis"),
            custom_ppn_path=self.settings.get("wake_custom_ppn_path", ""),
            device_index=self.get_selected_input_device(),
            level_callback=self._on_wake_level,
            stt_backend=self.settings.get("stt_backend", "OpenAI Whisper API"),
        )

    def _on_wake_detected(self):
        """Invoked from the wake-listener thread when wake-word is heard."""
        # Hand off command capture to its own thread so the wake loop continues
        threading.Thread(target=self._capture_wake_command, daemon=True).start()

    def _capture_wake_command(self):
        """Record audio for wake_command_seconds, transcribe, parse language, translate, play."""
        try:
            seconds = float(self.settings.get("wake_command_seconds", 6.0))
            device_index = self.get_selected_input_device()
            if device_index is None:
                self.append_status("Wake command capture: no input device selected.")
                return

            device_info = sd.query_devices(device_index)
            sample_rate = int(device_info.get("default_samplerate", 16000))
            channels = 1
            self.append_status(f"🎙️ Listening for command ({seconds:.1f}s)...")

            frames = []

            def _cb(indata, frame_count, time_info, status):
                peak = float(np.max(np.abs(indata)))
                if peak > self._mic_peak_ref[0]:
                    self._mic_peak_ref[0] = peak
                frames.append(indata.copy())

            self._mic_peak_ref[0] = 0.0
            with sd.InputStream(
                device=device_index, channels=channels, samplerate=sample_rate,
                blocksize=1024, dtype="float32", callback=_cb,
            ):
                end_time = time.time() + seconds
                while time.time() < end_time:
                    time.sleep(0.05)

            if not frames:
                self.append_status("Wake command: no audio captured.")
                return

            audio_data = np.concatenate(frames, axis=0).flatten()
            max_val = float(np.max(np.abs(audio_data)))
            if max_val > 0:
                audio_data = audio_data / max_val
            target_sr = 16000
            if sample_rate != target_sr:
                import scipy.signal
                new_len = int(len(audio_data) * target_sr / sample_rate)
                audio_data = scipy.signal.resample(audio_data, new_len).astype(np.float32)
                sample_rate = target_sr
            audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)

            wav_buf = io.BytesIO()
            with wave.open(wav_buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())
            wav_bytes = wav_buf.getvalue()

            self.append_status("Transcribing wake command...")
            _stt_t0 = time.time()
            transcript = transcribe_audio_wav(wav_bytes, stt_backend=self.settings.get("stt_backend", "OpenAI Whisper API"))
            self._last_stt_latency_ms = (time.time() - _stt_t0) * 1000.0
            if not transcript:
                self.append_status("Wake command: empty transcription.")
                return
            self.append_status(f"Heard: {transcript}")

            default_lang = self.langbox.currentText()
            if default_lang == "Auto":
                default_lang = "English"
            self.append_status("Parsing language + translating...")
            target_lang, translated = parse_voice_command(transcript, default_lang)
            if not translated:
                self.append_status("Wake command: nothing to translate.")
                return

            self.update_translated(translated)
            self.append_status(f"→ ({target_lang}) {translated}")

            # TTS
            tts_backend = self.backend_combo.currentText()
            try:
                if tts_backend == "ElevenLabs":
                    if not ELEVEN_API_KEY or not VOICE_ID:
                        raise RuntimeError("ElevenLabs credentials missing.")
                    wav_out = request_tts_wav(translated)
                elif tts_backend.startswith("Edge TTS"):
                    import asyncio
                    wav_out = asyncio.run(request_edge_tts_wav(translated, target_lang))
                else:
                    wav_out = request_local_tts_wav(translated)
            except requests.HTTPError as exc:
                if tts_backend == "ElevenLabs" and exc.response is not None and exc.response.status_code == 402:
                    wav_out = request_local_tts_wav(translated)
                else:
                    raise

            self.add_to_history(translated)
            play_wav_bytes(
                wav_out,
                device_indices=self.get_selected_devices(),
                level_callback=self.update_output_level,
                stop_event=self._play_stop_event,
            )
            self.update_output_level(0.0)
            self.append_status("Wake-translate complete.")
        except Exception as exc:
            self.append_status(f"Wake command error: {exc}")
            traceback.print_exc()

    def on_speak(self):
        text = self.textbox.toPlainText().strip()
        if not text:
            self.append_status("Please enter text to speak.")
            return
        self.append_status("Speak clicked. Starting translation...")
        threading.Thread(target=self.run_pipeline, args=(text,), daemon=True).start()

    def on_record_toggle(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        input_device_index = self.get_selected_input_device()
        input_device_name = self.input_device_combo.currentText()
        if input_device_index is None:
            self.append_status("No valid audio input device selected.")
            return

        self.is_recording = True
        self._mic_peak_ref[0] = 0.0
        self._stop_mic_monitor()
        self.recording_thread = threading.Thread(
            target=self.do_recording, args=(input_device_index, input_device_name), daemon=True
        )
        self.recording_thread.start()

        self.record_button.setText("🔴  Stop")
        self.record_button.setStyleSheet(T(
            "QPushButton { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,"
            " stop:0 #b01530, stop:1 @RED);"
            " border: 2px solid #ff6070; border-radius: 8px; color: #fff;"
            " font-size: 13px; font-weight: 700; padding: 8px 18px; }"
        ))
        self._compact.set_rec_state(True)
        self.append_status(f"🎤 Recording from: {input_device_name}")

    def _stop_recording(self):
        self.is_recording = False
        self.record_button.setEnabled(False)
        self.record_button.setText("⏳  Processing…")
        self.record_button.setStyleSheet(T(
            "QPushButton { background: @BG_RAISED; border: 1px solid @BORDER;"
            " border-radius: 8px; color: @TEXT_FAINT; font-size: 13px; font-weight: 700; padding: 8px 18px; }"
        ))
        self._compact.set_rec_state(False)

    def do_recording(self, input_device_index: int, input_device_name: str):
        try:
            # Record until stopped
            frames = []
            device_info = sd.query_devices(input_device_index)
            if device_info["max_input_channels"] < 1:
                raise RuntimeError("Selected device has no input channels")

            sample_rate = int(device_info.get("default_samplerate", 16000))
            channels = min(1, int(device_info["max_input_channels"]))
            blocksize = 1024

            self.append_status(f"Recording from {input_device_name} at {sample_rate} Hz")

            max_peak_ref = [0.0]
            last_speech_ref = [time.time()]
            record_start = time.time()
            auto_stop_secs = float(self.settings.get("auto_stop_silence", 2.0))
            # Peak threshold for speech detection — kept low so it works even with low mic gain.
            # Noise gate separately handles whether to send to Whisper.
            speech_peak_threshold = 0.005

            def _audio_cb(indata, frame_count, time_info, status):
                # No Qt calls here — PortAudio thread must stay clean
                peak = float(np.max(np.abs(indata)))
                if peak > max_peak_ref[0]:
                    max_peak_ref[0] = peak
                if peak > self._mic_peak_ref[0]:
                    self._mic_peak_ref[0] = peak
                if peak > speech_peak_threshold:
                    last_speech_ref[0] = time.time()
                frames.append(indata.copy())

            with sd.InputStream(device=input_device_index, channels=channels,
                                samplerate=sample_rate, blocksize=blocksize,
                                dtype="float32", callback=_audio_cb):
                while self.is_recording:
                    time.sleep(0.05)
                    # Auto-stop after silence
                    if auto_stop_secs > 0 and (time.time() - record_start) > 0.4:
                        if (time.time() - last_speech_ref[0]) >= auto_stop_secs:
                            self.is_recording = False
                            QTimer.singleShot(0, self._stop_recording)

            if not frames:
                self.append_status("No audio data recorded")
                return

            total_seconds = (len(frames) * blocksize) / sample_rate

            # Concatenate and flatten to 1D float32
            audio_data = np.concatenate(frames, axis=0).flatten()

            # Noise gate: check raw amplitude BEFORE normalization
            max_val = np.max(np.abs(audio_data))
            noise_gate = float(self.settings.get("noise_gate_threshold", 0.0))
            if noise_gate > 0.0 and max_val < noise_gate:
                self.append_status(f"Liian hiljainen (max {max_val:.4f} < {noise_gate:.4f}) — ei lähetetä Whisperille.")
                return

            # Normalize to [-1, 1]
            if max_val > 0:
                audio_data = audio_data / max_val
            else:
                self.append_status("Warning: recorded audio is silent")

            # Resample to 16 kHz for Whisper
            target_sample_rate = 16000
            if sample_rate != target_sample_rate:
                import scipy.signal
                new_length = int(len(audio_data) * target_sample_rate / sample_rate)
                audio_data = scipy.signal.resample(audio_data, new_length).astype(np.float32)
                sample_rate = target_sample_rate

            audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)

            wav_bytes = io.BytesIO()
            with wave.open(wav_bytes, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())
            wav_bytes = wav_bytes.getvalue()

            # Source language hint for Whisper
            src_lang_name = self.source_langbox.currentText()
            whisper_lang = _WHISPER_LANG_MAP.get(src_lang_name)  # None = auto-detect

            self.append_status(f"Sending {total_seconds:.1f}s audio to Whisper...")
            _stt_t0 = time.time()
            try:
                transcribed = transcribe_audio_wav(wav_bytes, language=whisper_lang, stt_backend=self.settings.get("stt_backend", "OpenAI Whisper API"))
                self._last_stt_latency_ms = (time.time() - _stt_t0) * 1000.0
            except Exception as e:
                traceback.print_exc()
                self.append_status(f"Transcription failed: {e}")
                QTimer.singleShot(0, lambda err=str(e): __import__('PyQt6.QtWidgets', fromlist=['QMessageBox']).QMessageBox.critical(self, "Transcription Error", err))
                return

            if not transcribed:
                self.append_status("Whisper returned empty — try speaking louder or closer to the mic.")
                return

            self.sig_set_textbox.emit(transcribed)
            self.append_status(f"Transcribed: {transcribed}")

            # Auto-translate+play if target language is set (no confirmation dialog)
            target_lang = self.langbox.currentText()
            if target_lang and target_lang != "Auto":
                self.append_status(f"Translating to {target_lang} and playing...")
                threading.Thread(target=self.run_pipeline, args=(transcribed,), daemon=True).start()

        except Exception as exc:
            self.append_status(f"Error during recording: {exc}")
            traceback.print_exc()
        finally:
            # Reset recording state
            self.is_recording = False
            QTimer.singleShot(0, self.reset_recording_ui)

    def reset_recording_ui(self):
        if not self.wake_listener.is_running() and self.isVisible():
            self._start_mic_monitor()
        self.record_button.setEnabled(True)
        self.record_button.setText("🎤  Listen")
        self._compact.set_rec_state(False)
        self.record_button.setStyleSheet(T(
            "QPushButton { background: @GRAD_ACCENT;"
            " border: 2px solid @BLUE_BRIGHT; border-radius: 8px; color: #fff;"
            " font-size: 13px; font-weight: 700; padding: 8px 18px; letter-spacing: 0.5px; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,"
            " stop:0 #5590ff, stop:1 #a052ff); border-color: @PURPLE_BRIGHT; }"
            "QPushButton:pressed { background: @BG_INPUT; border-color: @BLUE; }"
            "QPushButton:disabled { background: @BG_PANEL; color: @TEXT_FAINT; border-color: @BORDER; }"
        ))

    def _tick_mic_meter(self):
        val = int(min(self._mic_peak_ref[0] * 1000, 1000))
        self.mic_level_bar.setValue(val)
        db = self._level_to_db(val)
        self.mic_db_label.setText(db.replace(" dB", ""))
        self._mic_peak_ref[0] *= 0.75  # decay between ticks

    def _start_mic_monitor(self):
        """Open a lightweight always-on InputStream just for level metering when idle."""
        if self._mic_monitor_stream is not None:
            return
        if getattr(self, "_voice_fx", None) is not None and self._voice_fx.is_active:
            # Voice FX already has its own stream open on the same mic —
            # opening a second one here would grab the device twice and
            # keep it captured continuously even when nobody is speaking.
            return
        dev = self.get_selected_input_device()
        if dev is None:
            return
        try:
            try:
                native_sr = int(sd.query_devices(dev).get("default_samplerate", 16000))
            except Exception:
                native_sr = 16000
            def _cb(indata, frames, time_info, status):
                peak = float(np.max(np.abs(indata)))
                if peak > self._mic_peak_ref[0]:
                    self._mic_peak_ref[0] = peak
            self._mic_monitor_stream = sd.InputStream(
                device=dev, channels=1, samplerate=native_sr,
                blocksize=1024, dtype="float32", callback=_cb, latency="low",
            )
            self._mic_monitor_stream.start()
        except Exception:
            self._mic_monitor_stream = None

    def _stop_mic_monitor(self):
        """Close the idle mic monitor stream (called before recording starts)."""
        s = self._mic_monitor_stream
        self._mic_monitor_stream = None
        if s:
            try:
                s.stop(); s.close()
            except Exception:
                pass

    def _show_main_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(T(
            "QMenu { background: @BG_PANEL; border: 1px solid @BORDER_GLOW; border-radius: 8px; color: @TEXT; }"
            "QMenu::item { padding: 7px 20px; }"
            "QMenu::item:selected { background: @GRAD_ACCENT; color: #fff; }"
            "QMenu::separator { height: 1px; background: @BORDER; margin: 4px 0; }"
        ))
        menu.addAction("⚙  Settings", lambda: open_settings_dialog(self))
        menu.addSeparator()
        menu.addAction("ℹ  About Voice Royale", self._show_app_info)
        menu.addAction("✕  Exit", QApplication.instance().quit)
        btn = self._hamburger_btn
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _show_app_info(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Voice Royale",
            "Voice Royale — AI Voice Translation\n"
            "© 2026 BluexDEV Softwares. All rights reserved.\n\n"
            "Speech-to-text: OpenAI Whisper\n"
            "Translation: GPT-4.1-mini\n"
            "TTS: Edge TTS (free) / ElevenLabs\n"
            "Voice FX: pyrubberband / scipy\n"
            "Stream Deck: Elgato StreamDeck SDK\n\n"
            "Tuki: asiakaspalvelu@selaa.fi"
        )

    def update_mic_level(self, peak: float):
        # Safe to call from any thread — just writes a float to a list slot
        if peak > self._mic_peak_ref[0]:
            self._mic_peak_ref[0] = peak

    def update_output_level(self, peak: float):
        self.sig_out_level.emit(int(min(peak * 1000, 1000)))

    # ============ Soundboard ============

    def _play_soundboard_slot(self, page_index: int, slot_index: int):
        if page_index >= len(self._soundboard_buttons):
            return
        page_btns = self._soundboard_buttons[page_index]
        if slot_index >= len(page_btns):
            return
        btn = page_btns[slot_index]
        data = btn.get_data()

        # Page-link button — navigate to target page (only in play mode)
        link_name = data.get("link_page_name", "")
        if link_name and not SoundboardButton._edit_mode:
            for i in range(self._sb_tabs.count()):
                if self._sb_tabs.tabText(i) == link_name:
                    self._sb_tabs.setCurrentIndex(i)
                    return
            self.append_status(f"Soundboard: sivu '{link_name}' ei löydy")
            return

        # ── HA Media Player path ──────────────────────────────────────────
        ha_entity_ids = data.get("ha_players", [])
        if ha_entity_ids:
            path = data.get("file", "")
            if not path or not os.path.exists(path):
                self.append_status(f"HA Soundboard p{page_index+1} slot {slot_index+1}: ei ääntä (oikeaklikkaa)")
                return
            local_ip = _get_local_ip()
            audio_url = (f"http://{local_ip}:{StreamDeckHttpServer.PORT}"
                         f"/soundboard/audio/{page_index}/{slot_index}")
            vol = max(0.0, self.settings.get("soundboard_volume", 1.0) * data.get("volume", 1.0))

            def _play_ha():
                QTimer.singleShot(0, lambda: btn.set_playing(True))
                errors = []
                for eid in ha_entity_ids:
                    try:
                        _ha_api("POST", "/services/media_player/play_media", self.settings, {
                            "entity_id": eid,
                            "media_content_id": audio_url,
                            "media_content_type": "music",
                        })
                    except Exception as e:
                        errors.append(f"{eid}: {e}")
                if errors:
                    self.append_status("HA virhe: " + "; ".join(errors))
                else:
                    self.append_status(f"HA: soitetaan {', '.join(ha_entity_ids)}")
                # Reset button after estimated play time + buffer
                try:
                    import wave as _w
                    with _w.open(path, "rb") as wf:
                        dur = wf.getnframes() / wf.getframerate()
                except Exception:
                    dur = 3.0
                QTimer.singleShot(int((dur + 1.0) * 1000), lambda: btn.set_playing(False))

            threading.Thread(target=_play_ha, daemon=True).start()
            return

        path = data.get("file", "")
        if not path or not os.path.exists(path):
            self.append_status(f"Soundboard p{page_index+1} slot {slot_index+1}: ei ääntä (oikeaklikkaa)")
            return

        # Stop any current playback immediately
        self._sb_stop_event.set()
        self._sb_stop_event = threading.Event()
        my_stop_event = self._sb_stop_event

        self._sb_play_id += 1
        my_play_id = self._sb_play_id
        if self._sb_playing_btn and self._sb_playing_btn is not btn:
            old_btn = self._sb_playing_btn
            QTimer.singleShot(0, lambda: old_btn.set_playing(False))
        self._sb_playing_btn = btn

        final_vol = max(0.0, self.settings.get("soundboard_volume", 1.0) * data.get("volume", 1.0))

        def _level_cb(level: float):
            self.update_output_level(level if self._sb_play_id == my_play_id else 0.0)

        def _play():
            try:
                QTimer.singleShot(0, lambda: btn.set_playing(True))
                wav = self._load_audio_as_wav(path)
                if self._sb_play_id == my_play_id:
                    play_wav_bytes(wav, device_indices=self.get_selected_devices(),
                                   level_callback=_level_cb, volume=final_vol,
                                   stop_event=my_stop_event)
                self.update_output_level(0.0)
            except Exception as e:
                if self._sb_play_id == my_play_id:
                    self.append_status(f"Soundboard error: {e}")
            finally:
                if self._sb_play_id == my_play_id:
                    QTimer.singleShot(0, lambda: btn.set_playing(False))

        threading.Thread(target=_play, daemon=True).start()

    def _play_soundboard_nested(self, page_idx: int, folder_slot_idx: int, sub_slot_idx: int):
        """Play a sub-slot inside a subfolder directly from settings (Stream Deck support)."""
        page_slots = self._get_page_root_slots(page_idx)
        if folder_slot_idx >= len(page_slots):
            return
        folder_slot = page_slots[folder_slot_idx]
        if not folder_slot.get("subfolder"):
            return
        folder_slots = folder_slot.get("folder_slots", [])
        if sub_slot_idx >= len(folder_slots):
            return
        sub_slot = folder_slots[sub_slot_idx]
        path = sub_slot.get("file", "")
        if not path or not os.path.exists(path):
            self.append_status(f"SD subfolder p{page_idx+1} f{folder_slot_idx+1} s{sub_slot_idx+1}: ei ääntä")
            return

        self._sb_stop_event.set()
        self._sb_stop_event = threading.Event()
        my_stop_event = self._sb_stop_event
        self._sb_play_id += 1
        my_play_id = self._sb_play_id

        final_vol = max(0.0, self.settings.get("soundboard_volume", 1.0) * sub_slot.get("volume", 1.0))

        def _level_cb(level: float):
            self.update_output_level(level if self._sb_play_id == my_play_id else 0.0)

        def _play():
            try:
                wav = self._load_audio_as_wav(path)
                if self._sb_play_id == my_play_id:
                    play_wav_bytes(wav, device_indices=self.get_selected_devices(),
                                   level_callback=_level_cb, volume=final_vol,
                                   stop_event=my_stop_event)
                self.update_output_level(0.0)
            except Exception as e:
                if self._sb_play_id == my_play_id:
                    self.append_status(f"SD subfolder error: {e}")

        threading.Thread(target=_play, daemon=True).start()

    def _load_audio_as_wav(self, path: str) -> bytes:
        if path.lower().endswith(".wav"):
            with open(path, "rb") as f:
                return f.read()
        try:
            from pydub import AudioSegment  # type: ignore
            seg = AudioSegment.from_file(path)
            buf = io.BytesIO()
            seg.export(buf, format="wav")
            return buf.getvalue()
        except ImportError:
            raise RuntimeError(
                f"Only WAV files are supported without pydub. "
                f"Install pydub (pip install pydub) for MP3/OGG support. File: {os.path.basename(path)}"
            )

    def _save_soundboard(self):
        pages = []
        for pi in range(len(self._soundboard_buttons)):
            stack = self._sb_nav_stack.get(pi, [])
            if stack:
                name = stack[0][2]
            else:
                name = self._sb_tabs.tabText(pi)
            slots = self._get_page_root_slots(pi)
            groups = (self._sb_page_containers[pi].get_groups()
                      if pi < len(self._sb_page_containers) else [])
            pages.append({"name": name, "slots": slots, "groups": groups})
        self.settings["soundboard_pages"] = pages
        save_settings(self.settings)

    # ============ Voice FX ============

    _FX_AUTO_OUTPUT_KEYWORDS = ("voicemeeter", "vb-audio", "vb cable", "cable")
    # Kanoniset laitenimet joihin wizard OIKEASTI reitittää chat-äänen
    # (_voicemeeter_configure: Strip[2] "Voicemeeter Input" -> B1; VB-Cable: "CABLE Input").
    # Jos käyttäjällä on useampi virtuaalikaapeli valittuna Output-laitteissa (esim.
    # Voicemeeter Potato -asennuksella "VAIO3 Input" + "Voicemeeter Input"), näiden
    # täsmällinen nimi käy AINA ennen löysää avainsanaosumaa, ettei Voice FX päädy
    # kanavaan jota mikään reititys ei oikeasti kuuntele.
    _FX_CANONICAL_OUTPUT_NAMES = (
        "voicemeeter input (vb-audio voicemeeter vaio)",
        "cable input (vb-audio virtual cable)",
    )

    def _get_auto_fx_output_device(self):
        """Voice FX always feeds the same chat-facing virtual cable already picked
        for TTS/soundboard output (get_selected_devices()) — never a separately
        hand-picked device. Only matches software virtual cables, never physical/
        hardware outputs (e.g. RodeCaster channels), to avoid mic->speaker->mic
        feedback loops on a continuous stream."""
        selected = self.get_selected_devices() or []
        if not selected:
            return None
        try:
            names = dict(list_output_devices())
        except Exception:
            return None
        # 1. Täsmällinen kanoninen nimi ensin — se johon Voicemeeter/VB-Cable-reititys
        #    on oikeasti kytketty, vaikka listalla olisi muitakin virtuaalikaapeleita.
        for idx in selected:
            if names.get(idx, "").lower() in self._FX_CANONICAL_OUTPUT_NAMES:
                return idx
        # 2. Fallback: löysä avainsanaosuma (esim. epätavallinen VB-Cable-laitenimi).
        for idx in selected:
            name = names.get(idx, "")
            if any(k in name.lower() for k in self._FX_AUTO_OUTPUT_KEYWORDS):
                return idx
        return None

    def _autostart_voice_fx(self):
        if not self.settings.get("voice_fx_enabled", False):
            # User has never turned "Voice FX: ON" (or explicitly turned it back
            # off) — don't silently start a mic passthrough stream in the background.
            return
        in_dev = self.get_selected_input_device()
        out_dev = self._get_auto_fx_output_device()
        if in_dev is not None and out_dev is not None:
            mon_dev = self._fx_monitor_combo.currentData()
            hear_on = self._hear_myself_btn.isChecked()
            self._stop_mic_monitor()
            self._voice_fx.set_monitor(mon_dev, hear_on)
            self._voice_fx.start(in_dev, out_dev)
            self._voice_fx.set_preset(self._current_fx_preset)
            self._fx_toggle.setChecked(True)
            self._fx_toggle.setText("Voice FX: ON")
            self.append_status("Voice FX: stream jatkettu (oli päällä edellisellä kerralla)")
        else:
            self.append_status("Voice FX: ei voitu jatkaa — valitse chat-virtuaalikaapeli (esim. Voicemeeter Input) output-laitteeksi")

    def _restart_voice_fx_output(self):
        """Called when the user's chat output selection (get_selected_devices())
        changes while Voice FX is running — follow the new device, or stop
        cleanly if no virtual cable is selected anymore."""
        if not self._voice_fx.is_active:
            return
        out_dev = self._get_auto_fx_output_device()
        in_dev = self.get_selected_input_device()
        if out_dev is None or in_dev is None:
            self._voice_fx.stop()
            self._start_mic_monitor()
            self._fx_toggle.setChecked(False)
            self._fx_toggle.setText("Voice FX: OFF")
            self.settings["voice_fx_enabled"] = False
            save_settings(self.settings)
            self.append_status("Voice FX: pysäytetty — chat-virtuaalikaapelia ei ole enää valittuna output-laitteissa")
            return
        preset = self._current_fx_preset
        mon_dev = self._fx_monitor_combo.currentData()
        hear_on = self._hear_myself_btn.isChecked()
        self._stop_mic_monitor()
        self._voice_fx.set_monitor(mon_dev, hear_on)
        self._voice_fx.start(in_dev, out_dev)
        self._voice_fx.set_preset(preset)

    def _toggle_voice_fx(self):
        if self._fx_toggle.isChecked():
            if not self._voice_fx.is_active:
                in_dev = self.get_selected_input_device()
                out_dev = self._get_auto_fx_output_device()
                if in_dev is None or out_dev is None:
                    self.append_status("Voice FX: valitse mikrofoni ja chat-virtuaalikaapeli (esim. Voicemeeter Input) output-laitteeksi ensin")
                    self._fx_toggle.setChecked(False)
                    return
                mon_dev = self._fx_monitor_combo.currentData()
                hear_on = self._hear_myself_btn.isChecked()
                self._stop_mic_monitor()
                self._voice_fx.set_monitor(mon_dev, hear_on)
                self._voice_fx.start(in_dev, out_dev)
            self._voice_fx.set_preset(self._current_fx_preset)
            self._fx_toggle.setText("Voice FX: ON")
            self.settings["voice_fx_enabled"] = True
            save_settings(self.settings)
        else:
            self._voice_fx.stop()
            self._start_mic_monitor()
            self._fx_toggle.setText("Voice FX: OFF")
            self.settings["voice_fx_enabled"] = False
            save_settings(self.settings)

    def _select_fx_preset(self, preset: str):
        self._current_fx_preset = preset
        for p, btn in self._fx_preset_buttons.items():
            btn.setChecked(p == preset)
        self._voice_fx.set_preset(preset)
        if self._voice_fx.is_active:
            self.append_status(f"Voice FX: preset → {preset}")

    # ============ Stream Deck ============

    def _drain_sd_action_queue(self):
        import queue as _q
        while True:
            try:
                action = self._sd_action_queue.get_nowait()
            except _q.Empty:
                break
            try:
                self._handle_sd_action_impl(action)
            except Exception as e:
                self.append_status(f"SD '{action}' virhe: {e}")

    def _handle_sd_action(self, action: str):
        try:
            self._handle_sd_action_impl(action)
        except Exception as e:
            self.append_status(f"SD action '{action}' error: {e}")

    def _handle_sd_action_impl(self, action: str):
        if action == "record_toggle":
            self.on_record_toggle()
        elif action == "wake_listen_toggle":
            self.toggle_wake_listener()
        elif action == "speak":
            self.on_speak()
        elif action == "stop_recording":
            if self.is_recording:
                self._stop_recording()
        elif action == "tts_toggle":
            # Cycle between ElevenLabs and Edge TTS
            current = self.backend_combo.currentText()
            nxt = "Edge TTS (free)" if current == "ElevenLabs" else "ElevenLabs"
            self.backend_combo.setCurrentText(nxt)
        elif action == "settings":
            open_settings_dialog(self)
        elif action == "overlay_toggle":
            self.toggle_overlay()
        elif action.startswith("lang_"):
            lang = action[5:]
            idx = self.langbox.findText(lang)
            if idx >= 0:
                self.langbox.setCurrentIndex(idx)
        elif action.startswith("sb_page_goto_"):
            try:
                idx = int(action[13:])
                if 0 <= idx < self._sb_tabs.count():
                    self._sb_tabs.setCurrentIndex(idx)
            except ValueError:
                pass
        elif action.startswith("soundboard_"):
            parts = action[11:].split("_")
            try:
                if len(parts) == 3:
                    # soundboard_{page}_{folder_slot}_{sub_slot}
                    self._play_soundboard_nested(int(parts[0]), int(parts[1]), int(parts[2]))
                elif len(parts) == 2:
                    self._play_soundboard_slot(int(parts[0]), int(parts[1]))
                else:
                    self._play_soundboard_slot(self._sb_tabs.currentIndex(), int(parts[0]))
            except (ValueError, IndexError):
                pass
        elif action.startswith("fx_"):
            self._select_fx_preset(action[3:])
        else:
            self.append_status(f"SD: tuntematon toiminto '{action}'")

    def _refresh_sd_state(self):
        """Update state cache from the main thread (called by QTimer every 1.5s).
        The HTTP server background thread reads _sd_state; Qt widgets must only
        be accessed here on the main thread to avoid crashes."""
        try:
            pages = []
            for pi, page_data in enumerate(self.settings.get("soundboard_pages", [])):
                slots = []
                for si, slot in enumerate(page_data.get("slots", [])):
                    img = slot.get("image", "")
                    is_folder = bool(slot.get("subfolder"))
                    folder_slots_info = []
                    if is_folder:
                        for fi, fs in enumerate(slot.get("folder_slots", [])):
                            if fs.get("file") or (
                                fs.get("name") and not fs.get("name", "").startswith("Slot ")
                            ):
                                fs_img = fs.get("image", "")
                                folder_slots_info.append({
                                    "index": fi,
                                    "name": fs.get("name", f"Slot {fi+1}"),
                                    "has_file": bool(fs.get("file")),
                                    "image_path": fs_img if fs_img and os.path.exists(fs_img) else "",
                                })
                    slots.append({
                        "name": slot.get("name", f"Slot {si+1}"),
                        "has_file": bool(slot.get("file")),
                        "has_image": bool(img and os.path.exists(img)),
                        "image_path": img if img and os.path.exists(img) else "",
                        "is_folder": is_folder,
                        "folder_slots": folder_slots_info,
                    })
                pages.append({"name": page_data.get("name", f"Page {pi+1}"), "slots": slots})
            self._sd_state = {
                "recording": self.is_recording,
                "listening": self.wake_listener.is_running(),
                "language": self.langbox.currentText(),
                "tts_backend": self.backend_combo.currentText(),
                "fx_preset": getattr(self, "_current_fx_preset", "Normal"),
                "fx_active": self._voice_fx.is_active,
                "soundboard_page": self._sb_tabs.currentIndex(),
                "soundboard_pages": pages,
            }
        except Exception:
            pass

    def _get_sd_state(self) -> dict:
        """Return cached state — safe to call from any thread."""
        return dict(self._sd_state)

    def _get_sd_button_state(self, action: str) -> tuple[str, bool]:
        """Return (label, is_active) for rendering a Stream Deck button."""
        if action == "record_toggle":
            return ("RECORD", self.is_recording)
        if action == "wake_listen_toggle":
            return ("LISTEN", self.wake_listener.is_running())
        if action == "speak":
            return ("SPEAK", False)
        if action == "stop_recording":
            return ("STOP", self.is_recording)
        if action == "tts_toggle":
            return (self.backend_combo.currentText()[:8], False)
        if action == "settings":
            return ("SETTINGS", False)
        if action.startswith("lang_"):
            lang = action[5:]
            return (lang[:8], self.langbox.currentText() == lang)
        if action.startswith("sb_page_goto_"):
            try:
                idx = int(action[13:])
                name = self._sb_tabs.tabText(idx).strip() if idx < self._sb_tabs.count() else f"P{idx+1}"
                cur = self._sb_tabs.currentIndex()
                return (name[:10], cur == idx)
            except ValueError:
                return ("GO", False)
        if action.startswith("soundboard_"):
            parts = action[11:].split("_")
            if len(parts) == 2:
                pi, si = int(parts[0]), int(parts[1])
            else:
                pi, si = self._sb_tabs.currentIndex(), int(parts[0])
            if pi < len(self._soundboard_buttons) and si < len(self._soundboard_buttons[pi]):
                name = self._soundboard_buttons[pi][si].get_data().get("name", f"SB{si+1}")
                return (name[:10], False)
            return (f"SB{si+1}", False)
        if action.startswith("fx_"):
            preset = action[3:]
            active = self._current_fx_preset == preset and self._voice_fx.is_active
            return (preset[:10], active)
        return (action[:10], False)

    # ============ App close / tray ============

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self.hide)
        super().changeEvent(event)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()
        if not self.wake_listener.is_running():
            self._start_mic_monitor()

    def _quit_from_tray(self):
        self._force_quit = True
        self.close()

    def closeEvent(self, event):
        if not getattr(self, "_force_quit", False):
            event.ignore()
            self.hide()
            self._stop_mic_monitor()
            return
        try:
            if self.wake_listener.is_running():
                self.wake_listener.stop()
        except Exception:
            pass
        try:
            if self._voice_fx.is_active:
                self._voice_fx.stop()
        except Exception:
            pass
        try:
            self._sd_state_timer.stop()
            self._sd_action_timer.stop()
        except Exception:
            pass
        try:
            self._stream_deck.stop()
        except Exception:
            pass
        try:
            pos = self._overlay.pos()
            self.settings["overlay_pos"] = [pos.x(), pos.y()]
            save_settings(self.settings)
            self._overlay.close()
        except Exception:
            pass
        try:
            pos = self._compact.pos()
            self.settings["compact_pos"] = [pos.x(), pos.y()]
            save_settings(self.settings)
            self._compact.close()
        except Exception:
            pass
        super().closeEvent(event)

    def ask_play_transcribed(self, transcribed: str):
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Play Recorded Text?",
            f"Do you want to translate and play this recorded text?\n\n\"{transcribed}\"",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            threading.Thread(target=self.run_pipeline, args=(transcribed,), daemon=True).start()

    def on_device_info(self):
        selected_devices = self.get_selected_devices()
        input_device = self.get_selected_input_device()

        if selected_devices:
            device_names = [
                self._device_widgets[idx]["full_name"]
                for idx in selected_devices
                if idx in self._device_widgets
            ]
            output_name = ", ".join(device_names)
        else:
            output_name = "None selected"

        input_name = self.input_device_combo.currentText() if input_device is not None else "None selected"
        info_msg = f"Selected Output: {output_name}\n"
        info_msg += f"Selected Input: {input_name} (ID: {input_device})\n\n"

        for device_index in (selected_devices or []):
            try:
                device_info = sd.query_devices(device_index)
                info_msg += f"Output Device [{device_index}] {device_info['name']}:\n"
                info_msg += f"  Output channels: {device_info['max_output_channels']}\n"
                info_msg += f"  Default sample rate: {device_info['default_samplerate']}\n"
            except Exception as e:
                info_msg += f"  Error getting output device info: {e}\n"

        if input_device is not None:
            try:
                device_info = sd.query_devices(input_device)
                info_msg += f"\nInput Device [{input_device}] {device_info['name']}:\n"
                info_msg += f"  Input channels: {device_info['max_input_channels']}\n"
                info_msg += f"  Default sample rate: {device_info['default_samplerate']}\n"
            except Exception as e:
                info_msg += f"  Error getting input device info: {e}\n"

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Device Information", info_msg)

    def on_test_audio(self):
        selected_devices = self.get_selected_devices()
        if not selected_devices:
            self.append_status("No valid audio output device selected.")
            return

        device_names = [
            self._device_widgets[idx]["full_name"]
            for idx in selected_devices
            if idx in self._device_widgets
        ]
        device_name = ", ".join(device_names) if device_names else "selected devices"

        self.append_status(f"Testing audio output to: {device_name}")
        threading.Thread(target=self.play_test_audio, args=(selected_devices, device_name), daemon=True).start()

    def play_test_audio(self, device_indices, device_name: str):
        try:
            duration = 1.0
            frequency = 440
            sample_rate = 16000
            num_samples = int(sample_rate * duration)

            t = np.linspace(0, duration, num_samples, False)
            audio_int16 = (np.sin(frequency * 2 * np.pi * t) * 32767).astype(np.int16)

            with io.BytesIO() as buf:
                with wave.open(buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_int16.tobytes())
                wav_bytes = buf.getvalue()

            play_wav_bytes(wav_bytes, device_indices=device_indices)
            self.append_status(f"✅ Test audio played successfully to: {device_name}")
        except Exception as exc:
            self.append_status(f"❌ Test audio failed: {exc}")
            traceback.print_exc()

    def on_hotkey_triggered(self):
        text = self.textbox.toPlainText().strip()
        if not text:
            self.append_status("Hotkey pressed, but no text was provided.")
            return
        self.append_status("Hotkey pressed. Generating speech...")
        threading.Thread(target=self.run_pipeline, args=(text,), daemon=True).start()

    def run_pipeline(self, text: str):
        self.set_controls_enabled(False)
        try:
            lang = LANGS[self.langbox.currentText()]
            self.append_status("Translating text...")
            translated = translate_text(
                text, lang,
                backend=self.settings.get("translation_backend", "Google (free)"),
                deepl_key=self.settings.get("deepl_api_key", ""),
            )
            if not translated or not translated.strip():
                raise RuntimeError("Käännös palautti tyhjän tuloksen. Tarkista asetukset.")

            self.update_translated(translated)
            self.append_status("Generating speech audio...")

            tts_backend = self.backend_combo.currentText()
            try:
                if tts_backend == "ElevenLabs":
                    if not ELEVEN_API_KEY or not VOICE_ID:
                        raise RuntimeError(
                            "ElevenLabs credentials are not configured. Choose a local backend or add ElevenLabs keys."
                        )
                    wav_bytes = request_tts_wav(translated)
                elif tts_backend.startswith("Edge TTS"):
                    import asyncio
                    wav_bytes = asyncio.run(request_edge_tts_wav(translated, lang))
                else:
                    wav_bytes = request_local_tts_wav(translated)
            except requests.HTTPError as exc:
                if tts_backend == "ElevenLabs" and exc.response is not None and exc.response.status_code == 402:
                    self.append_status("ElevenLabs requires payment. Falling back to local TTS.")
                    wav_bytes = request_local_tts_wav(translated)
                else:
                    raise

            self.add_to_history(text)
            selected_devices = self.get_selected_devices()
            if selected_devices:
                device_names = [
                    self._device_widgets[idx]["full_name"]
                    for idx in selected_devices
                    if idx in self._device_widgets
                ]
                device_name = ", ".join(device_names) if device_names else "multiple devices"
            else:
                device_name = "default device"
            self.append_status(f"Playing audio to output device(s): {device_name}")
            play_wav_bytes(
                wav_bytes,
                device_indices=self.get_selected_devices(),
                level_callback=self.update_output_level,
                stop_event=self._play_stop_event,
            )
            self.update_output_level(0.0)
            self.append_status("Playback complete.")
        except Exception as exc:
            error_message = str(exc)
            self.append_status(f"Error: {error_message}")
            traceback.print_exc()
        finally:
            self.set_controls_enabled(True)


# =========================
# SETTINGS DIALOG
# =========================
def open_settings_dialog(parent_app: "App") -> None:
    """Open the settings dialog and apply changes if the user clicks Save."""
    global OPENAI_API_KEY, client, ELEVEN_API_KEY, VOICE_ID
    from PyQt6.QtWidgets import (
        QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QFileDialog, QScrollArea,
        QComboBox as _QComboBox, QPushButton as _QPushButton, QHBoxLayout as _QHBoxLayout,
        QListWidget as _QListWidget,
    )

    dlg = QDialog(parent_app)
    dlg.setWindowTitle("Voice Royale — Asetukset")
    dlg.resize(900, 660)
    dlg.setMinimumSize(720, 520)
    dlg.setStyleSheet(parent_app.styleSheet() + T("""
        QTabWidget::pane { border: 1px solid @BORDER_GLOW; border-radius: 0 8px 8px 8px;
            background: @BG_PANEL; padding: 4px; }
        QTabBar::tab { background: @BG_RAISED; color: @TEXT_FAINT; padding: 5px 9px;
            font-size: 10px; font-weight: 700; letter-spacing: 0;
            border: 1px solid @BORDER; border-bottom: none;
            border-radius: 5px 5px 0 0; margin-right: 2px; }
        QTabBar::tab:selected { background: @GRAD_ACCENT; color: #fff; border-color: @BLUE_BRIGHT; }
        QTabBar::tab:hover:!selected { background: @BLUE_DIM; color: @TEXT;
            border-color: @BLUE; }
        QScrollArea { border: none; background: transparent; }
        QLineEdit { background: @BG_INPUT; border: 1px solid @BORDER;
            border-radius: 7px; color: @TEXT; padding: 7px 12px;
            font-size: 13px; min-height: 18px; }
        QLineEdit:focus { border-color: @PURPLE; background: @BG_RAISED; }
        QLineEdit:disabled { color: @TEXT_FAINT; background: @BG_PANEL; }
        QComboBox { background: @BG_INPUT; border: 1px solid @BORDER; border-radius: 7px;
            color: @TEXT; padding: 7px 12px; font-size: 13px; min-height: 18px; }
        QComboBox:focus { border-color: @PURPLE; }
        QComboBox::drop-down { border: none; width: 22px; }
        QComboBox QAbstractItemView { background: @BG_PANEL; border: 1px solid @BORDER_GLOW;
            color: @TEXT; selection-background-color: @BLUE; padding: 4px; }
        QPushButton { background: @GRAD_BTN; border: 1px solid @BORDER; border-radius: 7px;
            color: @TEXT_DIM; padding: 7px 16px; font-size: 12px; font-weight: 600; }
        QPushButton:hover { background: @BLUE_DIM; border-color: @BLUE; color: #e0e8ff; }
        QPushButton:pressed { background: @BG_INPUT; border-color: @PURPLE; }
        QListWidget { background: @BG_INPUT; border: 1px solid @BORDER; border-radius: 7px;
            color: @TEXT; font-size: 12px; padding: 4px; }
        QListWidget::item:selected { background: @BLUE; color: #fff; border-radius: 4px; }
        QDialogButtonBox QPushButton { min-width: 90px; padding: 8px 20px; font-size: 13px; }
    """))

    settings = dict(parent_app.settings)

    # ── shared helpers ────────────────────────────────────────────────
    LABEL_STYLE = T("color: @TEXT_DIM; font-size: 12px; font-weight: 600;")
    DESC_STYLE  = T("color: @TEXT_FAINT; font-size: 11px; padding: 2px 0 10px 0; line-height: 150%;")

    def _desc(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(DESC_STYLE)
        lbl.setWordWrap(True)
        return lbl

    def _header(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(T(
            "color: @BLUE_BRIGHT; font-size: 13px; font-weight: 700; letter-spacing: 0.4px;"
            " padding: 14px 0 6px 0; border-bottom: 1px solid @BORDER; margin-bottom: 2px;"
        ))
        return lbl

    def _make_form() -> QFormLayout:
        f = QFormLayout()
        f.setVerticalSpacing(6)
        f.setHorizontalSpacing(16)
        f.setContentsMargins(20, 12, 20, 20)
        f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return f

    def _scroll_tab(form: QFormLayout) -> QWidget:
        inner = QWidget()
        inner.setLayout(form)
        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        return scroll

    def _lbl(text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(LABEL_STYLE)
        return l

    def _secret_row(value: str, placeholder: str):
        row = _QHBoxLayout()
        row.setSpacing(6)
        edit = QLineEdit(value)
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText(placeholder)
        btn = _QPushButton("Näytä")
        btn.setFixedWidth(64)
        btn.setCheckable(True)
        def _toggle(checked, e=edit, b=btn):
            e.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
            b.setText("Piilota" if checked else "Näytä")
        btn.toggled.connect(_toggle)
        row.addWidget(edit, 1)
        row.addWidget(btn)
        w = QWidget()
        w.setLayout(row)
        return w, edit

    # ══════════════════════════════════════════════════════════════════
    # 5 välilehteä: Yleiset / API-avaimet / Puhe & Kielet / Stream Deck & HA / Huolto
    # ══════════════════════════════════════════════════════════════════
    f_general = _make_form()
    f_apikeys = _make_form()
    f_speech = _make_form()
    f_maint = _make_form()

    # ---- Yleiset: Kääntäminen ----
    f_general.addRow(_header("Kääntäminen"))

    trans_backend_combo = _QComboBox()
    for b in ("Google (free)", "DeepL", "OpenAI"):
        trans_backend_combo.addItem(b)
    trans_backend_combo.setCurrentText(settings.get("translation_backend", "Google (free)"))
    f_general.addRow(_lbl("Käännösmoottori:"), trans_backend_combo)
    f_general.addRow("", _desc(
        "Google (free) — ei tarvitse API-avainta, toimii heti.\n"
        "DeepL — laadukas käännös, vaatii ilmaisen avaimen (Asetukset → API-avaimet).\n"
        "OpenAI — GPT-4.1-mini, vaatii maksullisen OpenAI-avaimen (Asetukset → API-avaimet)."
    ))

    lang_combo = _QComboBox()
    for lang in LANGS.keys():
        lang_combo.addItem(lang)
    lang_combo.setCurrentText(settings.get("default_target_lang", "Auto"))
    f_general.addRow(_lbl("Oletuskohde­kieli:"), lang_combo)
    f_general.addRow("", _desc(
        "Kieli, jolle teksti tai puhe käännetään oletuksena. "
        "'Auto' tunnistaa puhutun kielen ja kääntää englanniksi. "
        "Voit vaihtaa kielen myös pääikkunassa lennossa."
    ))

    # ---- Yleiset: Puheentunnistus (STT) ----
    f_general.addRow(_header("Puheentunnistus (STT)"))

    stt_backend_combo = _QComboBox()
    for b in ("OpenAI Whisper API", "Local Whisper (tiny)", "Local Whisper (base)", "Local Whisper (small)"):
        stt_backend_combo.addItem(b)
    stt_backend_combo.setCurrentText(settings.get("stt_backend", "OpenAI Whisper API"))
    f_general.addRow(_lbl("STT-moottori:"), stt_backend_combo)
    f_general.addRow("", _desc(
        "OpenAI Whisper API — pilvipalvelu, hyvä laatu, vaatii maksullisen OpenAI-avaimen.\n"
        "Local Whisper — ilmainen, offline, CPU-pohjainen (faster-whisper). tiny=75MB, base=145MB, small=460MB.\n"
        "Paikallinen malli ladataan automaattisesti ensimmäisellä käyttökerralla."
    ))

    stt_src_lang_combo = _QComboBox()
    stt_src_lang_combo.addItem("Auto (tunnistaa)")
    for _sl in LANGS.keys():
        if _sl != "Auto":
            stt_src_lang_combo.addItem(_sl)
    stt_src_lang_combo.setCurrentText(settings.get("stt_source_language", "Finnish"))
    f_general.addRow(_lbl("Lähde­kieli:"), stt_src_lang_combo)
    f_general.addRow("", _desc(
        "Kieli, jolla puhut mikrofoniin.\n"
        "'Auto (tunnistaa)' — Whisper tunnistaa kielen automaattisesti (suositeltu).\n"
        "Aseta tietty kieli vain jos tunnistus on toistuvasti väärä."
    ))

    # ---- Yleiset: Puhesynteesi (TTS) ----
    f_general.addRow(_header("Puhesynteesi (TTS)"))

    backend_combo = _QComboBox()
    for b in ("Edge TTS (free)", "ElevenLabs"):
        backend_combo.addItem(b)
    backend_combo.setCurrentText(settings.get("default_tts_backend", DEFAULT_TTS_BACKEND))
    f_general.addRow(_lbl("TTS-moottori:"), backend_combo)
    f_general.addRow("", _desc(
        "Edge TTS (free) — Microsoftin neuraaliäänet, ei tiliä tarvita, hyvä laatu.\n"
        "ElevenLabs — erittäin realistinen AI-ääni, vaatii maksullisen tilin ja API-avaimen (Asetukset → API-avaimet)."
    ))

    # ---- Yleiset: Pikanäppäin ----
    f_general.addRow(_header("Pikanäppäin"))

    hotkey_edit = QLineEdit(settings.get("hotkey", "ctrl+alt+space"))
    hotkey_edit.setPlaceholderText("esim. ctrl+alt+space")
    hotkey_edit.setMaximumWidth(220)
    f_general.addRow(_lbl("Global hotkey:"), hotkey_edit)
    f_general.addRow("", _desc(
        "Pikanäppäin, joka toistaa tekstiruudun sisällön vaikka ikkuna on taustalla. "
        "Käytä nimiä: ctrl, alt, shift, space, f1–f12. Yhdistä +-merkillä (esim. ctrl+alt+space). "
        "Vältä OS:n tai pelin omia pikanäppäimiä."
    ))

    # ---- Yleiset: Käynnistys ----
    f_general.addRow(_header("Käynnistys"))

    if sys.platform == "win32":
        _is_frozen = getattr(sys, "frozen", False)
        _autostart_on, _minimized_on = _get_autostart_state()

        autostart_chk = QCheckBox("Käynnisty Windowsin mukana")
        autostart_chk.setChecked(_autostart_on)
        autostart_chk.setEnabled(_is_frozen)
        autostart_chk.setStyleSheet("color: #dce6ff; background: transparent;")

        minimized_chk = QCheckBox("Käynnisty pienennettynä")
        minimized_chk.setChecked(_minimized_on)
        minimized_chk.setEnabled(_is_frozen and _autostart_on)
        minimized_chk.setStyleSheet("color: #dce6ff; background: transparent;")

        def _on_autostart_chk(_state):
            enabled = autostart_chk.isChecked()
            minimized_chk.setEnabled(enabled)
            _apply_autostart(enabled, minimized_chk.isChecked())

        def _on_minimized_chk(_state):
            _apply_autostart(autostart_chk.isChecked(), minimized_chk.isChecked())

        autostart_chk.stateChanged.connect(_on_autostart_chk)
        minimized_chk.stateChanged.connect(_on_minimized_chk)

        f_general.addRow(_lbl("Autostart:"), autostart_chk)
        f_general.addRow("", minimized_chk)
        if not _is_frozen:
            f_general.addRow("", _desc("Autostart ei toimi kehitysmoodissa — rakenna ensin exe-tiedosto."))
        else:
            f_general.addRow("", _desc("Muutos astuu voimaan heti — tallentaminen ei tarvita."))

    # ══════════════════════════════════════════════════════════════════
    # API-avaimet
    # ══════════════════════════════════════════════════════════════════
    f_apikeys.addRow(_header("OpenAI"))

    api_key_widget, api_key_edit = _secret_row(OPENAI_API_KEY, "sk-...")
    f_apikeys.addRow(_lbl("API-avain:"), api_key_widget)
    f_apikeys.addRow("", _desc(
        "Tarvitaan puheentunnistukseen (Whisper) ja käännökseen kun moottori = OpenAI.\n"
        "Hae avain: platform.openai.com/api-keys  •  Tallennetaan credentials.env-tiedostoon."
    ))

    f_apikeys.addRow(_header("ElevenLabs"))

    eleven_key_widget, eleven_key_edit = _secret_row(ELEVEN_API_KEY, "ElevenLabs API-avain")
    f_apikeys.addRow(_lbl("API-avain:"), eleven_key_widget)
    voice_id_edit = QLineEdit(VOICE_ID)
    voice_id_edit.setPlaceholderText("Voice ID (elevenlabs.io → Voices → kopioi ID)")
    f_apikeys.addRow(_lbl("Voice ID:"), voice_id_edit)
    f_apikeys.addRow("", _desc(
        "Tarvitaan vain jos TTS-moottori = ElevenLabs (Asetukset → Yleiset).\n"
        "Hae avain ja Voice ID osoitteesta elevenlabs.io  •  Tallennetaan credentials.env-tiedostoon."
    ))

    f_apikeys.addRow(_header("DeepL"))

    deepl_key_widget, deepl_key_edit = _secret_row(
        settings.get("deepl_api_key", ""), "DeepL API-avain — päättyy :fx (ilmainen)"
    )
    f_apikeys.addRow(_lbl("API-avain:"), deepl_key_widget)
    f_apikeys.addRow("", _desc(
        "Ilmainen avain: rekisteröidy osoitteessa deepl.com/pro#developer → Authentication Key.\n"
        "Ilmainen tili: 500 000 merkkiä/kk. Avain päättyy :fx."
    ))

    def _update_deepl_visibility():
        is_deepl = trans_backend_combo.currentText() == "DeepL"
        deepl_key_widget.setVisible(is_deepl)
    trans_backend_combo.currentTextChanged.connect(lambda _: _update_deepl_visibility())
    _update_deepl_visibility()

    f_apikeys.addRow(_header("Pixabay"))

    pixabay_key_widget, pixabay_key_edit = _secret_row(
        settings.get("pixabay_api_key", ""), "Pixabay API-avain"
    )
    f_apikeys.addRow(_lbl("API-avain:"), pixabay_key_widget)
    f_apikeys.addRow("", _desc(
        "Kuvahaku soundboard-napeille. Ilmainen, 500 pyyntöä/tunti.\n"
        "Rekisteröidy: pixabay.com → API → Get API Key."
    ))

    f_apikeys.addRow(_header("Picovoice (valinnainen — ilmainen)"))

    access_key_edit = QLineEdit(settings.get("picovoice_access_key", ""))
    access_key_edit.setPlaceholderText("Liitä ilmainen avain osoitteesta console.picovoice.ai")
    f_apikeys.addRow(_lbl("AccessKey:"), access_key_edit)
    f_apikeys.addRow("", _desc(
        "Ilmainen henkilökohtainen avain — console.picovoice.ai (ei luottokorttia tarvita).\n"
        "Mahdollistaa Porcupine offline -aktivointisanatunnistuksen: välitön vaste, ei nettiä tarvita.\n"
        "Jätä tyhjäksi käyttääksesi Whisper-pohjaista tunnistusta. Wake-sana: Puhe & Kielet -välilehti."
    ))

    # ══════════════════════════════════════════════════════════════════
    # Puhe & Kielet
    # ══════════════════════════════════════════════════════════════════
    f_speech.addRow(_header("Aktivointisana (Wake Word)"))

    _BUILTIN_KEYWORDS = [
        "jarvis", "alexa", "computer", "hey google", "hey siri",
        "ok google", "terminator", "picovoice", "porcupine",
        "americano", "blueberry", "bumblebee", "grapefruit", "grasshopper",
    ]
    if PORCUPINE_AVAILABLE:
        _BUILTIN_KEYWORDS = sorted(set(_BUILTIN_KEYWORDS) | set(pvporcupine.KEYWORDS))

    keyword_combo = _QComboBox()
    keyword_combo.setEditable(True)
    keyword_combo.setInsertPolicy(_QComboBox.InsertPolicy.NoInsert)
    for kw in _BUILTIN_KEYWORDS:
        keyword_combo.addItem(kw)
    saved_kw = settings.get("wake_keyword", "jarvis")
    idx = keyword_combo.findText(saved_kw)
    if idx >= 0:
        keyword_combo.setCurrentIndex(idx)
    else:
        keyword_combo.setCurrentText(saved_kw)

    def _get_keyword():
        return keyword_combo.currentText().strip().lower() or "jarvis"

    f_speech.addRow(_lbl("Wake-sana:"), keyword_combo)
    f_speech.addRow("", _desc(
        "Sana, jonka sanominen käynnistää hands-free-äänityksen.\n"
        "Valitse listasta tai kirjoita oma — suomen kielen sanat toimivat myös (esim. 'hei tietokone').\n"
        "Ilman Picovoice-avainta käytetään Whisperia tunnistukseen (pieni viive, toimii offline).\n"
        "Picovoice-avaimella (Asetukset → API-avaimet) Porcupine tunnistaa sanan välittömästi ilman CPU-kuormaa."
    ))

    seconds_edit = QLineEdit(str(settings.get("wake_command_seconds", 6.0)))
    seconds_edit.setPlaceholderText("esim. 6.0")
    seconds_edit.setMaximumWidth(120)
    f_speech.addRow(_lbl("Tallennusaika (s):"), seconds_edit)
    f_speech.addRow("", _desc(
        "Kuinka monta sekuntia äänitetään wake-sanan jälkeen. "
        "Kasvata (esim. 10 s) pitkille lauseille tai hitaalle puheelle. "
        "Laske (esim. 3 s) nopeiden yksisanaisten komentojen käyttöön."
    ))

    ppn_row = _QHBoxLayout()
    ppn_row.setSpacing(6)
    custom_path_edit = QLineEdit(settings.get("wake_custom_ppn_path", ""))
    custom_path_edit.setPlaceholderText("Valinnainen — polku .ppn-tiedostoon")
    browse_btn = _QPushButton("Selaa…")
    browse_btn.setFixedWidth(80)
    def _browse():
        path, _ = QFileDialog.getOpenFileName(dlg, "Valitse .ppn-tiedosto", "", "Porcupine PPN (*.ppn)")
        if path:
            custom_path_edit.setText(path)
    browse_btn.clicked.connect(_browse)
    ppn_row.addWidget(custom_path_edit, 1)
    ppn_row.addWidget(browse_btn)
    custom_widget = QWidget()
    custom_widget.setLayout(ppn_row)
    f_speech.addRow(_lbl("Oma .ppn-tiedosto:"), custom_widget)
    f_speech.addRow("", _desc(
        "OMA AKTIVOINTISANA (.ppn):\n"
        "1. Luo ilmainen tili: console.picovoice.ai\n"
        "2. Porcupine → Train a custom model\n"
        "3. Kirjoita haluamasi aktivointifraasi (esim. 'hey router', 'aloita')\n"
        "4. Valitse alusta: Windows → Train → lataa .ppn-tiedosto\n"
        "5. Liitä Picovoice AccessKey Asetukset → API-avaimet -välilehdellä, selaa .ppn-tiedosto tähän\n"
        "6. Tallenna asetukset ja paina Start Listening"
    ))

    f_speech.addRow(_header("Tekstitys ja herkkyys"))

    overlay_font_spin = QDoubleSpinBox()
    overlay_font_spin.setRange(10, 48)
    overlay_font_spin.setSingleStep(2)
    overlay_font_spin.setDecimals(0)
    overlay_font_spin.setValue(float(settings.get("overlay_font_size", 16)))
    overlay_font_spin.setMaximumWidth(80)
    overlay_font_spin.setStyleSheet(
        "QDoubleSpinBox { background: #0a0f1e; color: #dce6ff; border: 1px solid #333;"
        " border-radius: 4px; padding: 2px 6px; }"
    )
    f_speech.addRow(_lbl("Tekstikoko (px):"), overlay_font_spin)
    f_speech.addRow("", _desc(
        "Kelluvan tekstityksen fonttikoko. CC-napista päälle/pois.\n"
        "Raahaa overlay haluamaasi kohtaan näyttöä."
    ))

    noise_gate_spin = QDoubleSpinBox()
    noise_gate_spin.setRange(0.0, 0.05)
    noise_gate_spin.setSingleStep(0.005)
    noise_gate_spin.setDecimals(3)
    noise_gate_spin.setValue(float(settings.get("noise_gate_threshold", 0.0)))
    noise_gate_spin.setMaximumWidth(120)
    noise_gate_spin.setStyleSheet(
        "QDoubleSpinBox { background: #0a0f1e; color: #dce6ff; border: 1px solid #333;"
        " border-radius: 4px; padding: 2px 6px; }"
    )
    f_speech.addRow(_lbl("Noise gate:"), noise_gate_spin)
    f_speech.addRow("", _desc(
        "Äänenvoimakkuuden alaraja — alle jäävät tallennukset ohitetaan eikä Whisperille lähetetä.\n"
        "0.000 = pois päältä. Kokeile 0.010–0.020 suodattamaan hiljaiset tallennukset."
    ))

    auto_stop_spin = QDoubleSpinBox()
    auto_stop_spin.setRange(0.0, 10.0)
    auto_stop_spin.setSingleStep(0.5)
    auto_stop_spin.setDecimals(1)
    auto_stop_spin.setValue(float(settings.get("auto_stop_silence", 2.0)))
    auto_stop_spin.setMaximumWidth(120)
    auto_stop_spin.setStyleSheet(
        "QDoubleSpinBox { background: #0a0f1e; color: #dce6ff; border: 1px solid #333;"
        " border-radius: 4px; padding: 2px 6px; }"
    )
    f_speech.addRow(_lbl("Auto-stop (s):"), auto_stop_spin)
    f_speech.addRow("", _desc(
        "Sekuntia hiljaisuutta ennen kuin tallennus pysähtyy automaattisesti.\n"
        "0.0 = pois päältä. Suositeltu: 2.0 s."
    ))


    f_speech.addRow(_header("Mukautetut kielet"))
    f_speech.addRow("", _desc(
        "Lisää kieliä, jotka eivät ole vakiolistassa. Nimi näkyy Kohde-valikossa. "
        "Koodi = 2-kirjaiminen maakoodi lipulle (esim. pt, br, ar). "
        "Edge TTS -ääni: tarkka ääni-ID osoitteesta learn.microsoft.com  "
        "(esim. pt-PT-RaquelNeural). Jätä tyhjäksi → käytetään englannin ääntä."
    ))

    custom_langs = [dict(e) for e in settings.get("custom_languages", [])]
    custom_list = _QListWidget()
    custom_list.setMinimumHeight(140)
    for entry in custom_langs:
        n, c, v = entry.get("name", ""), entry.get("country_code", ""), entry.get("edge_voice", "")
        custom_list.addItem(f"{n}  |  {c}  |  {v}" if v else f"{n}  |  {c}")
    f_speech.addRow("", custom_list)

    add_row = _QHBoxLayout()
    add_row.setSpacing(6)
    new_name_edit = QLineEdit()
    new_name_edit.setPlaceholderText("Nimi (esim. Portuguese)")
    new_code_edit = QLineEdit()
    new_code_edit.setPlaceholderText("Koodi (pt)")
    new_code_edit.setMaximumWidth(70)
    new_voice_edit = QLineEdit()
    new_voice_edit.setPlaceholderText("Edge TTS ääni (esim. pt-PT-RaquelNeural)")
    add_btn = _QPushButton("Lisää")
    remove_btn = _QPushButton("Poista")
    add_btn.setFixedWidth(70)
    remove_btn.setFixedWidth(70)

    def _add_custom_lang():
        name = new_name_edit.text().strip()
        code = new_code_edit.text().strip().lower()
        voice = new_voice_edit.text().strip()
        if not name:
            return
        entry = {"name": name, "country_code": code, "edge_voice": voice}
        custom_langs.append(entry)
        custom_list.addItem(f"{name}  |  {code}  |  {voice}" if voice else f"{name}  |  {code}")
        new_name_edit.clear()
        new_code_edit.clear()
        new_voice_edit.clear()

    def _remove_custom_lang():
        row = custom_list.currentRow()
        if row >= 0:
            custom_list.takeItem(row)
            custom_langs.pop(row)

    add_btn.clicked.connect(_add_custom_lang)
    remove_btn.clicked.connect(_remove_custom_lang)
    add_row.addWidget(new_name_edit, 3)
    add_row.addWidget(new_code_edit, 1)
    add_row.addWidget(new_voice_edit, 3)
    add_row.addWidget(add_btn)
    add_row.addWidget(remove_btn)
    add_widget = QWidget()
    add_widget.setLayout(add_row)
    f_speech.addRow("", add_widget)

    f_maint.addRow(_header("Varmuuskopio"))

    _DATA_FILES = ["app_settings.json", "speech_history.json", "credentials.env"]
    _DATA_DIRS  = ["soundboard", "favorites_audio"]

    _BACKUP_MODES = {
        "all": {
            "label": "Kaikki — asetukset, historia, soundboard-äänet/-kuvat, API-avaimet",
            "files": ["app_settings.json", "speech_history.json", "credentials.env"],
            "dirs":  ["soundboard", "favorites_audio"],
        },
        "settings": {
            "label": "Asetukset & historia — ei soundboard-ääni/kuvatiedostoja",
            "files": ["app_settings.json", "speech_history.json", "credentials.env"],
            "dirs":  [],
        },
        "soundboard": {
            "label": "Soundboard — äänet, kuvat ja slot-asetukset",
            "files": ["app_settings.json"],
            "dirs":  ["soundboard"],
        },
    }

    def _ask_mode(title: str, verb: str):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QDialogButtonBox, QLabel
        md = QDialog(dlg)
        md.setWindowTitle(title)
        md.setStyleSheet(
            "QDialog { background: #111; }"
            "QLabel { color: #b9c5e6; font-size: 12px; background: transparent; }"
            "QRadioButton { color: #dce6ff; font-size: 12px; background: transparent; }"
        )
        vlay = QVBoxLayout(md)
        vlay.setSpacing(10)
        vlay.setContentsMargins(20, 16, 20, 16)
        vlay.addWidget(QLabel(f"Mitä tietoja {verb}?"))
        radios = {}
        for key, cfg in _BACKUP_MODES.items():
            rb = QRadioButton(cfg["label"])
            vlay.addWidget(rb)
            radios[key] = rb
        radios["all"].setChecked(True)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(verb.capitalize())
        btns.accepted.connect(md.accept)
        btns.rejected.connect(md.reject)
        vlay.addWidget(btns)
        if md.exec() != QDialog.DialogCode.Accepted:
            return None
        return next(k for k, rb in radios.items() if rb.isChecked())

    def _export_data():
        mode = _ask_mode("Vie data", "viedä")
        if mode is None:
            return
        cfg = _BACKUP_MODES[mode]
        default_name = f"VoiceRoyale_backup_{mode}.zip"
        path, _ = QFileDialog.getSaveFileName(dlg, "Vie data", default_name, "ZIP-arkisto (*.zip)")
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname in cfg["files"]:
                    fp = os.path.join(BASE_PATH, fname)
                    if os.path.exists(fp):
                        zf.write(fp, fname)
                for dname in cfg["dirs"]:
                    dp = os.path.join(BASE_PATH, dname)
                    if os.path.isdir(dp):
                        for root_dir, _, files in os.walk(dp):
                            for f in files:
                                full = os.path.join(root_dir, f)
                                zf.write(full, os.path.relpath(full, BASE_PATH))
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(dlg, "Valmis", f"Data viety:\n{path}")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(dlg, "Virhe", str(e))

    def _import_data():
        path, _ = QFileDialog.getOpenFileName(dlg, "Tuo data", "", "ZIP-arkisto (*.zip)")
        if not path:
            return
        mode = _ask_mode("Tuo data", "tuoda")
        if mode is None:
            return
        from PyQt6.QtWidgets import QMessageBox
        warnings = {
            "all":       "Korvaa kaikki asetukset, historian, API-avaimet ja soundboard-tiedostot.",
            "settings":  "Korvaa asetukset, historian ja API-avaimet. Soundboard-tiedostoja ei kosketa.",
            "soundboard":"Korvaa soundboard-äänet/-kuvat ja päivittää slot-asetukset.\n"
                         "Muut asetukset säilyvät ennallaan.",
        }
        ans = QMessageBox.question(
            dlg, "Korvaa data?",
            f"{warnings[mode]}\n\nJatketaanko?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            with zipfile.ZipFile(path, "r") as zf:
                members = zf.namelist()
                if mode == "settings":
                    # Only extract non-soundboard files
                    members = [m for m in members if not m.startswith("soundboard") and not m.startswith("favorites_audio")]
                elif mode == "soundboard":
                    # Extract soundboard/ files, then merge soundboard_pages from archived settings
                    sb_members = [m for m in members if m.startswith("soundboard")]
                    for member in sb_members:
                        dest = os.path.join(BASE_PATH, member)
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                    if "app_settings.json" in members:
                        with zf.open("app_settings.json") as f:
                            arc_settings = json.load(f)
                        cur_settings = {}
                        if os.path.exists(SETTINGS_FILE):
                            with open(SETTINGS_FILE, encoding="utf-8") as f:
                                cur_settings = json.load(f)
                        cur_settings["soundboard_pages"] = arc_settings.get("soundboard_pages", [])
                        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                            json.dump(cur_settings, f, ensure_ascii=False, indent=2)
                    QMessageBox.information(dlg, "Tuotu", "Soundboard tuotu. Käynnistä sovellus uudelleen.")
                    return
                for member in members:
                    dest = os.path.join(BASE_PATH, member)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            QMessageBox.information(dlg, "Tuotu", "Data tuotu. Käynnistä sovellus uudelleen.")
        except Exception as e:
            QMessageBox.critical(dlg, "Virhe", str(e))

    _io_row = _QHBoxLayout()
    _io_row.setSpacing(10)
    export_btn = _QPushButton("Vie data…")
    export_btn.setToolTip("Vie valitsemasi data ZIP-arkistoon")
    export_btn.clicked.connect(_export_data)
    import_btn = _QPushButton("Tuo data…")
    import_btn.setToolTip("Tuo aiemmin viety ZIP-varmuuskopio")
    import_btn.clicked.connect(_import_data)
    _io_row.addWidget(export_btn)
    _io_row.addWidget(import_btn)
    _io_row.addStretch()
    _io_widget = QWidget()
    _io_widget.setLayout(_io_row)
    f_maint.addRow("", _io_widget)
    f_maint.addRow("", _desc(
        "Vie data — valitse: Kaikki / Asetukset & historia / Soundboard.\n"
        "Tuo data — valitse mitä tuodaan. Soundboard-tuonti ei korvaa muita asetuksia."
    ))

    # ══════════════════════════════════════════════════════════════════
    # TAB — Stream Deck (yhdistetään Home Assistantin kanssa myöhemmin)
    # ══════════════════════════════════════════════════════════════════
    # ── Stream Deck plugin info panel ──
    sd_port = StreamDeckHttpServer.PORT
    sd_server_ok = parent_app._stream_deck.is_running()

    sd_inner = QWidget()
    sd_inner_lay = QVBoxLayout(sd_inner)
    sd_inner_lay.setContentsMargins(20, 16, 20, 20)
    sd_inner_lay.setSpacing(12)

    # Status row
    sd_status_row = QWidget()
    sd_status_row_lay = QHBoxLayout(sd_status_row)
    sd_status_row_lay.setContentsMargins(0, 0, 0, 0)
    sd_status_row_lay.setSpacing(8)
    sd_status_dot = QLabel("●")
    sd_status_dot.setStyleSheet(f"color: {'#7fc97f' if sd_server_ok else '#ff8888'}; font-size: 18px; background: transparent;")
    sd_status_txt = QLabel(
        f"HTTP-palvelin käynnissä portissa {sd_port}" if sd_server_ok
        else f"HTTP-palvelin ei käynnissä (portti {sd_port} varattuna?)"
    )
    sd_status_txt.setStyleSheet("color: #C0C0E8; font-size: 13px; font-weight: 600; background: transparent;")
    sd_status_row_lay.addWidget(sd_status_dot)
    sd_status_row_lay.addWidget(sd_status_txt, 1)
    sd_inner_lay.addWidget(sd_status_row)

    # How-it-works description
    sd_desc = QLabel(
        "<b>Miten se toimii:</b><br>"
        "Voice Royale kuuntelee portissa <b>localhost:{port}</b>.<br>"
        "Elgato-plugin lähettää napin painallukset tänne HTTP-kutsuna ja hakee tilan päivitykset."
        .format(port=sd_port)
    )
    sd_desc.setWordWrap(True)
    sd_desc.setStyleSheet("color: #9090B8; font-size: 12px; background: transparent; line-height: 160%;")
    sd_inner_lay.addWidget(sd_desc)

    # Plugin install instructions
    sd_install_hdr = QLabel("Plugin-asennus")
    sd_install_hdr.setStyleSheet(
        "color: #C0C0E8; font-size: 13px; font-weight: 700; border-bottom: 1px solid #1c2c52;"
        " padding-bottom: 4px; background: transparent;"
    )
    sd_inner_lay.addWidget(sd_install_hdr)

    sd_install_desc = QLabel(
        "1. Varmista, että Elgato Stream Deck -ohjelmisto on asennettu.<br>"
        "2. Kaksoisnapsauta <b>com.voiceroyale.streamDeckPlugin</b> tiedostoa<br>"
        "   (löytyy <b>streamdeck-plugin/</b> kansiosta).<br>"
        "3. Stream Deck -ohjelmisto asentaa pluginin automaattisesti.<br>"
        "4. Vedä <b>Voice Royale</b> -toiminnot haluamillesi napeille.<br>"
        "5. Plugin hakee tilan 2 sekunnin välein — napit päivittyvät automaattisesti."
    )
    sd_install_desc.setWordWrap(True)
    sd_install_desc.setStyleSheet("color: #9090B8; font-size: 12px; background: transparent; line-height: 170%;")
    sd_inner_lay.addWidget(sd_install_desc)

    # Available actions list
    sd_actions_hdr = QLabel("Käytettävissä olevat toiminnot")
    sd_actions_hdr.setStyleSheet(
        "color: #C0C0E8; font-size: 13px; font-weight: 700; border-bottom: 1px solid #1c2c52;"
        " padding-bottom: 4px; background: transparent;"
    )
    sd_inner_lay.addWidget(sd_actions_hdr)

    _sd_action_labels = {
        "record_toggle": "Record (päälle/pois)",
        "wake_listen_toggle": "Listen / Wake word",
        "speak": "Puhu nyt",
        "stop_recording": "Pysäytä",
        "tts_toggle": "TTS-backend vaihto",
        "settings": "Avaa asetukset",
        "sb_page_goto_N": "Soundboard: siirry sivulle N (0-pohjainen indeksi)",
        "lang_*": "Kieli: English, Finnish, Swedish…",
        "soundboard_P_S": "Soundboard: sivu P, paikka S",
        "fx_*": "Voice FX: Normal, Robot, Deep, Helium…",
    }
    for act_key, act_label in _sd_action_labels.items():
        row_w = QWidget()
        row_lay = QHBoxLayout(row_w)
        row_lay.setContentsMargins(4, 0, 0, 0)
        row_lay.setSpacing(10)
        key_lbl = QLabel(f"<code>{act_key}</code>")
        key_lbl.setStyleSheet("color: #7BAFF0; font-size: 11px; background: transparent; min-width: 180px;")
        key_lbl.setFixedWidth(200)
        val_lbl = QLabel(act_label)
        val_lbl.setStyleSheet("color: #9090B8; font-size: 11px; background: transparent;")
        row_lay.addWidget(key_lbl)
        row_lay.addWidget(val_lbl, 1)
        sd_inner_lay.addWidget(row_w)

    sd_inner_lay.addStretch()

    sd_scroll = QScrollArea()
    sd_scroll.setWidget(sd_inner)
    sd_scroll.setWidgetResizable(True)
    sd_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

    # ── Tabs ──────────────────────────────────────────────────────────
    tabs = QTabWidget()
    # ══════════════════════════════════════════════════════════════════
    # TAB 6 — Asennukset
    # ══════════════════════════════════════════════════════════════════
    import importlib.util
    import importlib.metadata

    _PKG_LIST = [
        ("PyQt6",          "PyQt6",          True,  "UI-framework"),
        ("requests",       "requests",        True,  "HTTP"),
        ("dotenv",         "python-dotenv",   True,  "Ympäristömuuttujat"),
        ("sounddevice",    "sounddevice",     True,  "Äänilaitteet"),
        ("numpy",          "numpy",           True,  "Audion käsittely"),
        ("scipy",          "scipy",           True,  "Resampling"),
        ("keyboard",       "keyboard",        False, "Global hotkey (Windows/Linux)"),
        ("openai",         "openai",          True,  "Whisper + GPT"),
        ("pyttsx3",        "pyttsx3",         True,  "Paikallinen TTS"),
        ("edge_tts",       "edge-tts",        True,  "Edge TTS"),
        ("deep_translator","deep-translator", True,  "Google Translate"),
        ("pvporcupine",    "pvporcupine",     False, "Wake word offline (valinnainen)"),
        ("pyrubberband",   "pyrubberband",    False, "Voice FX laatu (valinnainen)"),
        ("pydub",          "pydub",           False, "MP3/OGG soundboard (valinnainen)"),
        ("faster_whisper", "faster-whisper",  False, "Paikallinen STT offline (valinnainen)"),
    ]

    def _pkg_status(import_name, pip_name):
        if getattr(sys, "frozen", False):
            # pvporcupine/pyrubberband are native optional libs that can crash on import error
            # in frozen mode — use sys.modules only for those.
            # All other bundled packages are safe to import normally.
            if import_name in ("pvporcupine", "pyrubberband"):
                in_modules = import_name in sys.modules
                return in_modules, ("bundled" if in_modules else "")
            try:
                importlib.import_module(import_name)
                return True, "bundled"
            except Exception:
                return False, ""
        try:
            importlib.import_module(import_name)
            try:
                ver = importlib.metadata.version(pip_name)
            except Exception:
                ver = "?"
            return True, ver
        except Exception:
            return False, ""

    # ---- Asennusvelho ----
    f_maint.addRow(_header("Asennusvelho"))

    wizard_btn = _QPushButton("Aja alkuasennus uudelleen (Setup Wizard)")

    def _run_wizard_again():
        global OPENAI_API_KEY, client
        dlg.reject()
        wiz = SetupWizard()
        wiz.exec()
        load_dotenv(os.path.join(BASE_PATH, "credentials.env"), override=True)
        new_key = os.getenv("OPENAI_API_KEY", "")
        if new_key and new_key != OPENAI_API_KEY:
            OPENAI_API_KEY = new_key
            client = OpenAI(api_key=new_key)
            parent_app.append_status("OpenAI API key updated via wizard.")
        # Reload device selections from history
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as _hf:
                parent_app.history_data = json.load(_hf)
        except Exception:
            pass
        parent_app._stop_mic_monitor()
        parent_app.populate_input_devices()
        parent_app.populate_output_devices()
        parent_app._start_mic_monitor()

    wizard_btn.clicked.connect(_run_wizard_again)
    f_maint.addRow(_lbl("Setup Wizard:"), wizard_btn)
    f_maint.addRow("", _desc(
        "Avaa alkuasennus uudelleen — voit vaihtaa API-avaimia, laiteasetuksia ja chat-reititystä."
    ))

    # ---- Python-paketit — vain kehitystilassa, exe:ssä kaikki on jo bundlattu ----
    if not getattr(sys, "frozen", False):
        f_maint.addRow(_header("Python-paketit (kehitystila)"))

        def _pip_install_pkg(pip_name: str, icon_lbl, name_lbl, install_btn):
            import queue as _q_pip
            _rq_pip = _q_pip.Queue()

            def _run():
                import subprocess as _sp
                ret = _sp.run(
                    [sys.executable, "-m", "pip", "install", pip_name],
                    capture_output=True, text=True
                )
                _rq_pip.put((ret.returncode == 0, ret.stderr[-300:] if ret.returncode != 0 else ""))

            def _poll_pip():
                try:
                    ok, stderr = _rq_pip.get_nowait()
                except Exception:
                    return
                _ptmr_pip.stop()
                if ok:
                    icon_lbl.setText("✅")
                    icon_lbl.setStyleSheet("font-size: 14px; background: transparent; color: #7fc97f;")
                    name_lbl.setStyleSheet("color: #dce6ff; background: transparent;")
                    install_btn.setText("Asennettu ✓")
                else:
                    install_btn.setText("Epäonnistui")
                    install_btn.setEnabled(True)
                    parent_app.append_status(f"pip install {pip_name} epäonnistui:\n{stderr}")

            install_btn.setText("Asennetaan…")
            install_btn.setEnabled(False)
            _ptmr_pip = QTimer(parent_app)
            _ptmr_pip.timeout.connect(_poll_pip)
            _ptmr_pip.start(200)
            threading.Thread(target=_run, daemon=True).start()

        for import_name, pip_name, required, desc in _PKG_LIST:
            ok, ver = _pkg_status(import_name, pip_name)
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(8)

            icon_lbl = QLabel("✅" if ok else ("❌" if required else "○"))
            icon_lbl.setFixedWidth(22)
            icon_lbl.setStyleSheet("font-size: 14px; background: transparent;")

            name_lbl = QLabel(f"<b>{pip_name}</b>")
            name_lbl.setStyleSheet(
                "color: #dce6ff; background: transparent;" if ok
                else ("color: #ff8888; background: transparent;" if required
                      else "color: #8a9bc4; background: transparent;")
            )
            name_lbl.setFixedWidth(160)

            desc_lbl = QLabel(f"{desc}   <span style='color:#8a9bc4'>v{ver}</span>" if ok
                              else f"<span style='color:#8a9bc4'>{desc}</span>")
            desc_lbl.setStyleSheet("background: transparent; font-size: 11px;")

            row_h.addWidget(icon_lbl)
            row_h.addWidget(name_lbl)
            row_h.addWidget(desc_lbl, 1)

            if not ok and not required:
                _install_btn = _QPushButton("Asenna")
                _install_btn.setFixedWidth(72)
                _install_btn.setStyleSheet(
                    "QPushButton { background: #14281e; border: 1px solid #1a5a30; border-radius: 5px;"
                    " color: #00cc6a; padding: 3px 6px; font-size: 11px; font-weight: 700; }"
                    "QPushButton:hover { border-color: #00ff88; color: #5AFFAA; }"
                    "QPushButton:disabled { background: #111; color: #444; border-color: #222; }"
                )
                _install_btn.clicked.connect(
                    lambda _checked, pn=pip_name, il=icon_lbl, nl=name_lbl, ib=_install_btn:
                        _pip_install_pkg(pn, il, nl, ib)
                )
                row_h.addWidget(_install_btn)

            label_txt = "Pakollinen" if required else "Valinnainen"
            f_maint.addRow(_lbl(label_txt + ":"), row_w)

    # ---- Virtuaaliäänilaitteet & chat-reititys — tila + linkki Setup Wizardiin.
    # Asennus/määritys/testaus tehdään wizardissa (samat _install_vbcable/
    # _install_voicemeeter/_voicemeeter_configure-funktiot), joten tässä ei
    # toisteta samaa UI:ta kahteen kertaan — vain tila ja yksi linkki. ----
    f_maint.addRow(_header("Virtuaaliäänilaitteet & chat-reititys"))

    _vbc_installed = _is_vbcable_installed()
    vbc_status_lbl = QLabel("VB-Cable: ✅ Asennettu" if _vbc_installed else "VB-Cable: ❌ Ei asennettu")
    vbc_status_lbl.setStyleSheet("color: #7fc97f; font-size: 13px;" if _vbc_installed else "color: #ff8888; font-size: 13px;")
    f_maint.addRow(_lbl("VB-Cable:"), vbc_status_lbl)

    if sys.platform == "win32":
        _vm_installed = _is_voicemeeter_installed()
        vm_status_lbl = QLabel(
            "Voicemeeter Banana: ✅ Asennettu" if _vm_installed else "Voicemeeter Banana: ❌ Ei asennettu"
        )
        vm_status_lbl.setStyleSheet(
            "color: #7fc97f; font-size: 13px;" if _vm_installed else "color: #ff8888; font-size: 13px;"
        )
        f_maint.addRow(_lbl("Voicemeeter:"), vm_status_lbl)

    f_maint.addRow("", _desc(
        "Asennus ja määritys (mikrofonivalinta, reititys, testaus) tehdään Setup Wizardissa — "
        "paina yllä 'Aja alkuasennus uudelleen', sama velho tunnistaa laitteesi ja hoitaa loput."
    ))

    f_maint.addRow(_header("Sovelluspäivitykset"))

    _cur_lbl = QLabel(f"v{APP_VERSION}")
    _cur_lbl.setStyleSheet("color: #dce6ff; font-size: 13px; font-weight: 700; background: transparent;")
    f_maint.addRow(_lbl("Nykyinen versio:"), _cur_lbl)

    _latest_lbl = QLabel("—")
    _latest_lbl.setStyleSheet("color: #8a9bc4; font-size: 12px; background: transparent;")
    f_maint.addRow(_lbl("Uusin versio:"), _latest_lbl)

    _upd_status = QLabel("")
    _upd_status.setStyleSheet("color: #8a9bc4; font-size: 11px; background: transparent;")
    _upd_status.setWordWrap(True)

    _dl_btn = _QPushButton("Lataa & Avaa asentaja")
    _dl_btn.setVisible(False)
    _dl_btn.setStyleSheet(
        "QPushButton { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #2e7fff,stop:1 #7b2fff);"
        " color: #fff; border: none; border-radius: 6px; padding: 8px 20px; font-weight: 700; }"
        "QPushButton:hover { background: #7b2fff; }"
        "QPushButton:disabled { background: #101a36; color: #8a9bc4; }"
    )

    _asset_url = [None]

    def _check_updates():
        import queue as _q
        _check_btn.setEnabled(False)
        _upd_status.setText("Tarkistetaan...")
        _upd_status.setStyleSheet("color: #8a9bc4; font-size: 11px; background: transparent;")
        _dl_btn.setVisible(False)

        _result_q: _q.Queue = _q.Queue()

        def _worker():
            try:
                resp = requests.get(
                    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                    headers={"User-Agent": "VoiceRoyale-Updater"},
                    timeout=10
                )
                resp.raise_for_status()
                data = resp.json()
                tag = data.get("tag_name", "").lstrip("v")
                assets = data.get("assets", [])
                url = next(
                    (a["browser_download_url"] for a in assets
                     if a["name"].endswith(".exe" if sys.platform == "win32" else ".dmg")),
                    None
                )
                _result_q.put(("ok", tag, url))
            except Exception as e:
                _result_q.put(("err", str(e)))

        def _poll():
            try:
                result = _result_q.get_nowait()
            except Exception:
                return
            _poll_timer.stop()
            _check_btn.setEnabled(True)
            if result[0] == "ok":
                _, tag, url = result
                _latest_lbl.setText(f"v{tag}")
                cur = [int(x) for x in APP_VERSION.split(".")]
                lat = [int(x) for x in tag.split(".")]
                if lat > cur:
                    _asset_url[0] = url
                    if url:
                        _upd_status.setText(f"Versio v{tag} saatavilla!")
                        _upd_status.setStyleSheet("color: #00ff88; font-size: 11px; background: transparent;")
                        _dl_btn.setVisible(True)
                    else:
                        _upd_status.setText(f"v{tag} saatavilla, mutta asentajaa ei löydy releasesta.")
                        _upd_status.setStyleSheet("color: #FF9A00; font-size: 11px; background: transparent;")
                else:
                    _upd_status.setText("Käytät uusinta versiota.")
                    _upd_status.setStyleSheet("color: #8a9bc4; font-size: 11px; background: transparent;")
            else:
                _upd_status.setText(f"Virhe: {result[1]}")
                _upd_status.setStyleSheet("color: #ff8888; font-size: 11px; background: transparent;")

        _poll_timer = QTimer(dlg)
        _poll_timer.timeout.connect(_poll)
        _poll_timer.start(200)
        threading.Thread(target=_worker, daemon=True).start()

    def _download_and_open():
        import queue as _q
        url = _asset_url[0]
        if not url:
            return
        _dl_btn.setEnabled(False)
        _dl_btn.setText("Ladataan...")

        _result_q: _q.Queue = _q.Queue()

        def _worker():
            try:
                resp = requests.get(url, stream=True, timeout=300)
                resp.raise_for_status()
                suffix = ".exe" if url.endswith(".exe") else ".dmg"
                fd, tmp_path = tempfile.mkstemp(suffix=suffix)
                with os.fdopen(fd, "wb") as f:
                    for chunk in resp.iter_content(65536):
                        f.write(chunk)
                _result_q.put(("ok", tmp_path))
            except Exception as e:
                _result_q.put(("err", str(e)))

        def _poll():
            try:
                result = _result_q.get_nowait()
            except Exception:
                return
            _dl_poll_timer.stop()
            _dl_btn.setEnabled(True)
            _dl_btn.setText("Lataa & Avaa asentaja")
            if result[0] == "ok":
                tmp_path = result[1]
                if sys.platform == "win32":
                    # ShellExecuteW with "runas" forces a fresh UAC prompt even
                    # if Voice Royale is already running elevated (e.g. from the
                    # previous Inno Setup install). subprocess.Popen would silently
                    # inherit admin rights and skip UAC.
                    import ctypes
                    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", tmp_path, None, None, 1)
                    if ret <= 32:
                        # User cancelled UAC or launch failed — fall back to normal open
                        os.startfile(tmp_path)
                else:
                    subprocess.Popen(["open", tmp_path])
            else:
                _upd_status.setText(f"Latausvirhe: {result[1]}")
                _upd_status.setStyleSheet("color: #ff8888; font-size: 11px; background: transparent;")

        _dl_poll_timer = QTimer(dlg)
        _dl_poll_timer.timeout.connect(_poll)
        _dl_poll_timer.start(500)
        threading.Thread(target=_worker, daemon=True).start()

    _check_btn = _QPushButton("Tarkista päivitykset")
    _check_btn.clicked.connect(_check_updates)
    _dl_btn.clicked.connect(_download_and_open)

    f_maint.addRow("", _check_btn)
    f_maint.addRow("", _upd_status)
    f_maint.addRow("", _dl_btn)
    f_maint.addRow("", _desc(
        "Windows: Inno Setup -asentaja käynnistyy — vanha versio suljetaan automaattisesti.\n"
        "macOS: DMG-tiedosto aukeaa — vedä Voice Royale.app Applications-kansioon."
    ))

    # ── Siivoa soundboard-tiedostot → Huolto ─────────────────────────────
    from PyQt6.QtWidgets import QListWidget as _LW, QListWidgetItem as _LWI, QAbstractItemView as _AIV

    f_maint.addRow(_header("Siivoa soundboard-tiedostot"))

    _clean_container = QWidget()
    lay_clean = QVBoxLayout(_clean_container)
    lay_clean.setContentsMargins(0, 0, 0, 4)
    lay_clean.setSpacing(8)

    lbl_clean_info = QLabel(
        "Tarkistaa soundboard-kansion tiedostot ja etsii orpoja (ei viittausta yhdessäkään slotissa).\n"
        "Valitse poistettavat ja paina Poista valitut."
    )
    lbl_clean_info.setWordWrap(True)
    lbl_clean_info.setStyleSheet("color: #888; font-size: 11px;")
    lay_clean.addWidget(lbl_clean_info)

    scan_btn = _QPushButton("Tarkista tiedostot")
    scan_btn.setStyleSheet(
        "QPushButton { background: #1E2A3A; color: #6AA0FF; border: 1px solid #2A4A7A;"
        " border-radius: 6px; padding: 7px 18px; font-weight: 700; }"
        "QPushButton:hover { background: #1A3060; border-color: #2e7fff; color: #AAC8FF; }"
    )
    lay_clean.addWidget(scan_btn)

    clean_status = QLabel("")
    clean_status.setStyleSheet("color: #888; font-size: 11px;")
    lay_clean.addWidget(clean_status)

    file_list = _LW()
    file_list.setSelectionMode(_AIV.SelectionMode.MultiSelection)
    file_list.setMinimumHeight(160)
    file_list.setStyleSheet(
        "QListWidget { background: #0E0E18; border: 1px solid #1c2c52; border-radius: 6px;"
        " color: #C0C0E0; font-size: 11px; }"
        "QListWidget::item { padding: 4px 8px; }"
        "QListWidget::item:selected { background: #1A2A50; color: #fff; }"
        "QListWidget::item:hover { background: #141428; }"
    )
    lay_clean.addWidget(file_list)

    sel_row = _QHBoxLayout()
    sel_all_btn = _QPushButton("Valitse kaikki")
    sel_none_btn = _QPushButton("Poista valinnat")
    del_btn = _QPushButton("Poista valitut")
    del_btn.setEnabled(False)
    del_btn.setStyleSheet(
        "QPushButton { background: #2A0808; color: #FF4444; border: 1px solid #6B0000;"
        " border-radius: 6px; padding: 7px 18px; font-weight: 700; }"
        "QPushButton:hover { background: #3A0808; border-color: #FF3333; }"
        "QPushButton:disabled { background: #0a0f1e; color: #444; border-color: #333; }"
    )
    for b in (sel_all_btn, sel_none_btn):
        b.setStyleSheet(
            "QPushButton { background: #1A1A2A; color: #888; border: 1px solid #333;"
            " border-radius: 6px; padding: 7px 14px; }"
            "QPushButton:hover { border-color: #666; color: #CCC; }"
        )
    sel_row.addWidget(sel_all_btn)
    sel_row.addWidget(sel_none_btn)
    sel_row.addStretch()
    sel_row.addWidget(del_btn)
    lay_clean.addLayout(sel_row)

    # paths found by scan
    _orphan_paths: list[str] = []

    def _collect_refs(slots: list, out: set):
        for s in slots:
            for key in ("file", "image"):
                p = s.get(key, "")
                if p:
                    out.add(os.path.normpath(p))
            if s.get("folder_slots"):
                _collect_refs(s["folder_slots"], out)

    def _do_scan():
        _orphan_paths.clear()
        file_list.clear()
        del_btn.setEnabled(False)

        sb_dir = os.path.join(BASE_PATH, "soundboard")
        audio_dir = os.path.join(sb_dir, "audio")
        img_dir = os.path.join(sb_dir, "images")

        # Collect all referenced paths from live soundboard state
        refs: set[str] = set()
        pages = parent_app.settings.get("soundboard_pages", [])
        for page in pages:
            _collect_refs(page.get("slots", []), refs)

        # Scan files on disk
        disk_files: list[str] = []
        for d in (audio_dir, img_dir):
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    disk_files.append(os.path.join(d, fn))

        orphans = [f for f in disk_files if os.path.normpath(f) not in refs]

        if not orphans:
            clean_status.setText(
                f"Kaikki {len(disk_files)} tiedostoa on kaytossa — ei siivottavaa."
            )
            return

        clean_status.setText(
            f"Loydetty {len(orphans)} orpo tiedostoa / {len(disk_files)} yhteensa."
        )
        for path in sorted(orphans):
            try:
                size_kb = os.path.getsize(path) // 1024
            except Exception:
                size_kb = 0
            item = _LWI(f"{os.path.basename(path)}  ({size_kb} KB)  —  {path}")
            item.setData(256, path)  # Qt.UserRole = 256
            file_list.addItem(item)
            _orphan_paths.append(path)
        del_btn.setEnabled(True)

    def _do_delete():
        selected = file_list.selectedItems()
        if not selected:
            clean_status.setText("Valitse ensin poistettavat tiedostot listalta.")
            return
        paths = [it.data(256) for it in selected]
        names = "\n".join(f"  {os.path.basename(p)}" for p in paths)
        from PyQt6.QtWidgets import QMessageBox as _MB
        ans = _MB.question(
            dlg, "Vahvista poisto",
            f"Poistetaanko {len(paths)} tiedostoa?\n\n{names}\n\nTätä ei voi peruuttaa.",
            _MB.StandardButton.Yes | _MB.StandardButton.No,
            _MB.StandardButton.No,
        )
        if ans != _MB.StandardButton.Yes:
            return
        removed = 0
        for path in paths:
            try:
                os.remove(path)
                removed += 1
            except Exception as e:
                clean_status.setText(f"Virhe: {e}")
        clean_status.setText(f"Poistettu {removed}/{len(paths)} tiedostoa.")
        _do_scan()  # refresh list

    scan_btn.clicked.connect(_do_scan)
    sel_all_btn.clicked.connect(file_list.selectAll)
    sel_none_btn.clicked.connect(file_list.clearSelection)
    del_btn.clicked.connect(_do_delete)
    file_list.itemSelectionChanged.connect(
        lambda: del_btn.setEnabled(bool(file_list.selectedItems()))
    )
    f_maint.addRow("", _clean_container)

    # ── Home Assistant tab ───────────────────────────────────────────────
    from PyQt6.QtWidgets import QScrollArea as _QSA2, QListWidget as _LW2, QListWidgetItem as _LWI2

    ha_widget = QWidget()
    ha_vbox = QVBoxLayout(ha_widget)
    ha_vbox.setContentsMargins(20, 14, 20, 14)
    ha_vbox.setSpacing(8)

    ha_vbox.addWidget(_header("Home Assistant — yhteys"))

    ha_url_row = QHBoxLayout()
    ha_url_row.addWidget(_lbl("HA URL:"))
    ha_url_edit = QLineEdit(settings.get("ha_url", ""))
    ha_url_edit.setPlaceholderText("http://homeassistant.local:8123  tai  https://ha.esimerkki.com")
    ha_url_row.addWidget(ha_url_edit, 1)
    ha_vbox.addLayout(ha_url_row)

    ha_token_row = QHBoxLayout()
    ha_token_row.addWidget(_lbl("Long-lived token:"))
    ha_token_edit = QLineEdit(settings.get("ha_token", ""))
    ha_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
    ha_token_edit.setPlaceholderText("eyJ0eXAiOiJKV1QiLCJhbGc…")
    ha_token_row.addWidget(ha_token_edit, 1)
    ha_vbox.addLayout(ha_token_row)

    ha_connect_btn = QPushButton("🔌  Testaa yhteys & hae soittimet")
    ha_status_lbl = QLabel("")
    ha_status_lbl.setStyleSheet("font-size: 12px; padding: 2px 0;")
    ha_vbox.addWidget(ha_connect_btn)
    ha_vbox.addWidget(ha_status_lbl)

    ha_vbox.addWidget(_header("Media Players"))
    ha_vbox.addWidget(_desc(
        "Rastita haluamasi laitteet ja anna niille lyhyt nimi. "
        "'▶ Testi' soittaa piipauksen kyseiselle laitteelle."
    ))

    ha_players_list = _LW2()
    ha_players_list.setMinimumHeight(200)
    ha_players_list.setStyleSheet(
        "QListWidget { background: #0d0d1a; border: 1px solid #1c2c52; border-radius: 6px; }"
        "QListWidget::item { padding: 2px 4px; }"
        "QListWidget::item:selected { background: transparent; }"
    )
    ha_vbox.addWidget(ha_players_list, 1)

    _ha_fetched_players: list = []   # [{entity_id, friendly_name}] from HA

    def _ha_make_player_row(entity_id: str, friendly: str, saved_name: str, checked: bool) -> QWidget:
        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        row_h = QHBoxLayout(row_w)
        row_h.setContentsMargins(4, 2, 4, 2)
        row_h.setSpacing(8)
        from PyQt6.QtWidgets import QCheckBox as _CB2
        cb = _CB2()
        cb.setChecked(checked)
        cb.setStyleSheet("QCheckBox { color: #b9c5e6; } QCheckBox::indicator { width: 15px; height: 15px; }")
        cb.setProperty("entity_id", entity_id)
        row_h.addWidget(cb)
        eid_lbl = QLabel(friendly or entity_id)
        eid_lbl.setStyleSheet("color: #8a9bc4; font-size: 11px; min-width: 160px;")
        eid_lbl.setToolTip(entity_id)
        row_h.addWidget(eid_lbl)
        name_edit = QLineEdit(saved_name)
        name_edit.setPlaceholderText("Nimi (esim. Olohuone)")
        name_edit.setFixedWidth(140)
        name_edit.setStyleSheet(
            "QLineEdit { background: #070b16; border: 1px solid #1c2c52; border-radius: 5px;"
            " color: #dce6ff; padding: 4px 8px; font-size: 12px; }"
        )
        name_edit.setProperty("entity_id", entity_id)
        row_h.addWidget(name_edit)
        test_btn = QPushButton("▶ Testi")
        test_btn.setFixedWidth(68)
        test_btn.setStyleSheet(
            "QPushButton { background: #14281e; border: 1px solid #1a5a30; border-radius: 5px;"
            " color: #00cc6a; padding: 4px 8px; font-size: 11px; font-weight: 700; }"
            "QPushButton:hover { border-color: #00ff88; color: #5AFFAA; }"
        )

        import queue as _q_ha_test
        _ha_test_q = _q_ha_test.Queue()
        _ha_test_timer = QTimer(parent_app)

        def _poll_ha_test():
            try:
                ok, msg, style = _ha_test_q.get_nowait()
            except Exception:
                return
            _ha_test_timer.stop()
            test_btn.setEnabled(True)
            test_btn.setText("▶ Testi")
            ha_status_lbl.setStyleSheet(style)
            ha_status_lbl.setText(msg)

        _ha_test_timer.timeout.connect(_poll_ha_test)

        def _do_test(eid=entity_id):
            test_btn.setEnabled(False)
            test_btn.setText("…")
            local_ip = _get_local_ip()
            test_url = f"http://{local_ip}:{StreamDeckHttpServer.PORT}/ha_test_audio"
            cur = {"ha_url": ha_url_edit.text().strip(), "ha_token": ha_token_edit.text().strip()}

            def _run():
                try:
                    _ha_api("POST", "/services/media_player/play_media", cur, {
                        "entity_id": eid,
                        "media_content_id": test_url,
                        "media_content_type": "music",
                    })
                    _ha_test_q.put((True,
                        f"✓ Testi lähetetty → {eid}",
                        "color: #00cc6a; font-size:12px;"))
                except Exception as exc:
                    _ha_test_q.put((False,
                        f"✗ {exc}",
                        "color: #ff4444; font-size:12px;"))

            _ha_test_timer.start(100)
            threading.Thread(target=_run, daemon=True).start()

        test_btn.clicked.connect(_do_test)
        row_h.addWidget(test_btn)
        row_h.addStretch()
        row_w._cb = cb
        row_w._name_edit = name_edit
        return row_w

    def _ha_populate_list(players: list, saved_players: list):
        ha_players_list.clear()
        saved_map = {p["entity_id"]: p.get("name", "") for p in saved_players}
        for pl in players:
            eid = pl["entity_id"]
            friendly = pl.get("friendly_name", "")
            saved_name = saved_map.get(eid, friendly or "")
            row_w = _ha_make_player_row(eid, friendly, saved_name, eid in saved_map)
            item = _LWI2()
            item.setSizeHint(row_w.sizeHint())
            ha_players_list.addItem(item)
            ha_players_list.setItemWidget(item, row_w)

    # Pre-populate from saved config on open
    saved_ha_players = settings.get("ha_players", [])
    if saved_ha_players:
        _ha_fetched_players = [{"entity_id": p["entity_id"],
                                "friendly_name": p.get("name", "")} for p in saved_ha_players]
        _ha_populate_list(_ha_fetched_players, saved_ha_players)
        ha_status_lbl.setStyleSheet("color: #8a9bc4; font-size:12px;")
        ha_status_lbl.setText(f"Tallennettu {len(saved_ha_players)} laitetta — paina 'Testaa' päivittääksesi listan")

    def _ha_connect():
        ha_connect_btn.setEnabled(False)
        ha_connect_btn.setText("Yhdistetään…")
        ha_status_lbl.setStyleSheet("color: #8a9bc4; font-size:12px;")
        ha_status_lbl.setText("Yhdistetään…")
        import queue as _qha
        _rq_ha = _qha.Queue()

        def _run():
            cur = {"ha_url": ha_url_edit.text().strip(), "ha_token": ha_token_edit.text().strip()}
            try:
                _ha_api("GET", "/", cur)
                states = _ha_api("GET", "/states", cur)
                media_players = [
                    {"entity_id": s["entity_id"],
                     "friendly_name": s.get("attributes", {}).get("friendly_name", "")}
                    for s in states if s.get("entity_id", "").startswith("media_player.")
                ]
                media_players.sort(key=lambda x: x["entity_id"])
                _rq_ha.put(("ok", media_players))
            except Exception as exc:
                _rq_ha.put(("err", str(exc)))

        def _poll_ha():
            try:
                kind, payload = _rq_ha.get_nowait()
            except Exception:
                return
            _ptmr_ha.stop()
            ha_connect_btn.setEnabled(True)
            ha_connect_btn.setText("🔌  Testaa yhteys & hae soittimet")
            if kind == "ok":
                nonlocal _ha_fetched_players
                _ha_fetched_players = payload
                _ha_populate_list(payload, settings.get("ha_players", []))
                ha_status_lbl.setStyleSheet("color: #00cc6a; font-size:12px;")
                ha_status_lbl.setText(f"✓ Yhdistetty — löydetty {len(payload)} media_player-laitetta")
            else:
                err = payload
                msg = err
                if "SSL" in err or "CERTIFICATE" in err.upper():
                    msg = f"SSL-virhe — kokeile http:// osoitteen alussa\n({err[:80]})"
                elif "timed out" in err.lower() or "timeout" in err.lower():
                    msg = f"Yhteys aikakatkaistiin — tarkista osoite ja portti\n({err[:80]})"
                elif "401" in err or "Unauthorized" in err:
                    msg = "Token virheellinen — tarkista Long-lived token"
                elif "refused" in err.lower():
                    msg = f"Yhteys evätty — onko HA käynnissä osoitteessa {ha_url_edit.text().strip()}?"
                ha_status_lbl.setStyleSheet("color: #ff4444; font-size:12px;")
                ha_status_lbl.setText(f"✗ {msg}")

        _ptmr_ha = QTimer(parent_app)
        _ptmr_ha.timeout.connect(_poll_ha)
        _ptmr_ha.start(200)
        threading.Thread(target=_run, daemon=True).start()

    ha_connect_btn.clicked.connect(_ha_connect)

    # Stream Deck + Home Assistant yhdistetty yhdeksi välilehdeksi (erotettu viivalla)
    _sd_ha_combined = QWidget()
    _sd_ha_lay = QVBoxLayout(_sd_ha_combined)
    _sd_ha_lay.setContentsMargins(0, 0, 0, 0)
    _sd_ha_lay.setSpacing(0)
    _sd_ha_lay.addWidget(sd_inner)
    _sd_ha_sep = QFrame()
    _sd_ha_sep.setFrameShape(QFrame.Shape.HLine)
    _sd_ha_sep.setStyleSheet("color: #1c2c52; margin: 10px 20px;")
    _sd_ha_lay.addWidget(_sd_ha_sep)
    _sd_ha_lay.addWidget(ha_widget)

    _sd_ha_scroll = QScrollArea()
    _sd_ha_scroll.setWidget(_sd_ha_combined)
    _sd_ha_scroll.setWidgetResizable(True)
    _sd_ha_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

    tabs.addTab(_scroll_tab(f_general), "Yleiset")
    tabs.addTab(_scroll_tab(f_apikeys), "API-avaimet")
    tabs.addTab(_scroll_tab(f_speech), "Puhe & Kielet")
    tabs.addTab(_sd_ha_scroll, "Stream Deck & HA")
    tabs.addTab(_scroll_tab(f_maint), "Huolto")

    # ── Buttons ───────────────────────────────────────────────────────
    btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    btns.button(QDialogButtonBox.StandardButton.Save).setText("Tallenna")
    btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Peruuta")
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)

    root = QVBoxLayout()
    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(8)
    root.addWidget(tabs, 1)
    root.addWidget(btns)
    dlg.setLayout(root)

    if dlg.exec() == QDialog.DialogCode.Accepted:
        new_settings = {
            "wake_keyword": _get_keyword(),
            "wake_custom_ppn_path": custom_path_edit.text().strip(),
            "picovoice_access_key": access_key_edit.text().strip(),
            "hotkey": hotkey_edit.text().strip() or "ctrl+alt+space",
            "default_target_lang": lang_combo.currentText(),
            "default_tts_backend": backend_combo.currentText(),
            "translation_backend": trans_backend_combo.currentText(),
            "stt_backend": stt_backend_combo.currentText(),
            "stt_source_language": stt_src_lang_combo.currentText(),
            "noise_gate_threshold": noise_gate_spin.value(),
            "auto_stop_silence": auto_stop_spin.value(),
            "overlay_font_size": int(overlay_font_spin.value()),
            "deepl_api_key": deepl_key_edit.text().strip(),
            "pixabay_api_key": pixabay_key_edit.text().strip(),
        }
        try:
            new_settings["wake_command_seconds"] = float(seconds_edit.text())
        except ValueError:
            new_settings["wake_command_seconds"] = 6.0
        new_settings["custom_languages"] = custom_langs

        # HA settings
        new_settings["ha_url"] = ha_url_edit.text().strip()
        new_settings["ha_token"] = ha_token_edit.text().strip()
        saved_ha: list = []
        for i in range(ha_players_list.count()):
            row_w = ha_players_list.itemWidget(ha_players_list.item(i))
            if row_w and hasattr(row_w, "_cb") and row_w._cb.isChecked():
                eid = row_w._cb.property("entity_id")
                name = row_w._name_edit.text().strip()
                if eid:
                    saved_ha.append({"entity_id": eid, "name": name})
        new_settings["ha_players"] = saved_ha

        # Save OpenAI API key to credentials.env and update globals
        new_key = api_key_edit.text().strip()
        if new_key and new_key != OPENAI_API_KEY:
            OPENAI_API_KEY = new_key
            client = OpenAI(api_key=new_key)
            env_file = os.path.join(BASE_PATH, "credentials.env")
            try:
                lines = []
                if os.path.exists(env_file):
                    with open(env_file, "r", encoding="utf-8") as f:
                        lines = [ln.rstrip() for ln in f if not ln.startswith("OPENAI_API_KEY")]
                lines.insert(0, f"OPENAI_API_KEY={new_key}")
                with open(env_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                parent_app.append_status("OpenAI API key updated.")
            except Exception as e:
                parent_app.append_status(f"Warning: could not save key to file: {e}")

        # Save ElevenLabs key + Voice ID to credentials.env and update globals
        new_eleven_key = eleven_key_edit.text().strip()
        new_voice_id = voice_id_edit.text().strip()
        if new_eleven_key != ELEVEN_API_KEY or new_voice_id != VOICE_ID:
            env_file = os.path.join(BASE_PATH, "credentials.env")
            try:
                lines = []
                if os.path.exists(env_file):
                    with open(env_file, "r", encoding="utf-8") as f:
                        lines = [ln.rstrip() for ln in f
                                 if not ln.startswith("ELEVEN_API_KEY") and not ln.startswith("VOICE_ID")]
                if new_voice_id:
                    lines.insert(0, f"VOICE_ID={new_voice_id}")
                if new_eleven_key:
                    lines.insert(0, f"ELEVEN_API_KEY={new_eleven_key}")
                with open(env_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                ELEVEN_API_KEY = new_eleven_key
                VOICE_ID = new_voice_id
                parent_app.append_status("ElevenLabs API key/Voice ID updated.")
            except Exception as e:
                parent_app.append_status(f"Warning: could not save ElevenLabs key: {e}")

        parent_app.settings.update(new_settings)
        save_settings(parent_app.settings)
        parent_app.apply_settings_changes()
        parent_app.append_status("Settings saved.")


# =========================
# SETUP WIZARD (combined)
# =========================
class SetupWizard(QDialog):
    """Asennusvelho: paketit → API-avain → VB-Cable → Voicemeeter → Äänilaitteet → Lopputesti."""

    _STYLE = T("""
        QDialog { background: @BG_DEEP; color: @TEXT; font-family: "Segoe UI", sans-serif; }
        QLabel  { color: @TEXT; }
        QPushButton {
            background: @GRAD_ACCENT; color: #ffffff; border: none;
            border-radius: 6px; padding: 8px 20px;
            font-size: 13px; font-weight: bold;
        }
        QPushButton:hover    { background: @BLUE; }
        QPushButton:disabled { background: @BG_RAISED; color: @TEXT_FAINT; }
        QLineEdit {
            background: @BG_INPUT; border: 1px solid @BORDER;
            border-radius: 6px; color: @TEXT;
            padding: 8px; font-size: 13px;
        }
        QLineEdit:focus { border: 1px solid @BORDER_GLOW; }
        QCheckBox { color: @TEXT_DIM; background: transparent; }
    """)
    _BAR_ACTIVE = T(
        "QProgressBar { background: @BG_RAISED; border-radius: 4px; border: 1px solid @GREEN; }"
        "QProgressBar::chunk { background: @GREEN; border-radius: 4px; }"
    )
    _BAR_IDLE = T(
        "QProgressBar { background: @BG_RAISED; border-radius: 4px; }"
        "QProgressBar::chunk { background: @BLUE; border-radius: 4px; }"
    )
    _BAR_DIM = T(
        "QProgressBar { background: @BG_RAISED; border-radius: 4px; }"
        "QProgressBar::chunk { background: @BORDER; border-radius: 4px; }"
    )
    _BTN_PRIMARY = T(
        "QPushButton { background: @GRAD_ACCENT; color: #ffffff; border: none;"
        " border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: bold; }"
        "QPushButton:hover { background: @BLUE; }"
        "QPushButton:disabled { background: @BG_RAISED; color: @TEXT_FAINT; }"
    )
    _BTN_SEC = T(
        "QPushButton { background: @BG_RAISED; color: @TEXT_DIM; border: 1px solid @BORDER;"
        " border-radius: 6px; padding: 6px 16px; font-size: 12px; font-weight: normal; }"
        "QPushButton:hover { background: @BLUE_DIM; }"
        "QPushButton:disabled { color: @TEXT_FAINT; }"
    )
    _BTN_SKIP = T(
        "QPushButton { background: @BG_RAISED; color: @TEXT_FAINT; border: 1px solid @BORDER;"
        " border-radius: 6px; padding: 5px 14px; font-size: 11px; font-weight: normal; }"
        "QPushButton:hover { background: @BLUE_DIM; color: @TEXT_DIM; }"
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Royale — Asennus")
        self.setFixedSize(780, 900)
        self.setStyleSheet(self._STYLE)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self._api_key = ""
        self._wiz_rec_buf = []
        self._wiz_rec_thread = None
        self._wiz_rec_stop = threading.Event()
        import queue as _q
        self._dev_level_queue = _q.Queue()
        self._dev_input_streams = []
        self._dev_level_bars = {}
        self._dev_level_peak = {}
        self._dev_sustained = {}
        self._dev_stream_opened = set()
        self._dev_row_widgets = {}
        self._dev_status_labels = {}
        self._dev_input_devices = []
        self._dev_output_devices = []
        self._dev_out_checkboxes = {}
        self._dev_selected_input = None
        self._dev_auto_selected = False
        self._dev_active_poll_timers = []
        self._dev_play_thread = None
        self._dev_closing = False
        self._dev_input_status_lbl = None
        self._dev_out_status_lbl = None
        self._dev_monitor_timer = QTimer(self)
        self._dev_monitor_timer.timeout.connect(self._update_dev_levels)
        self._dev_monitor_timer.setInterval(80)
        # Service selection state — updated by _page_services
        self._svc_stt = "openai"        # "openai" | "local"
        self._svc_trans = "google"      # "google" | "deepl" | "openai"
        self._svc_tts = "edge"          # "edge" | "elevenlabs"
        self._svc_routing = "simple"    # "simple" | "gaming"
        self._svc_mixer = False         # bool — fyysinen mikseri (RodeCaster ym.) → Voicemeeter
        # Dynaaminen "Vaihe X/Y" -mekanismi: _header() rekisteröi jokaisen sivun subtitle-labelin
        # tähän sanakirjaan rakennusjärjestyksessä (== stack-indeksi), ja _navigate() päivittää
        # tekstin joka kerta senhetkisen _get_page_sequence()-tuloksen mukaan. Näin numerointi on
        # AINA oikein riippumatta käyttäjän valitsemasta polusta — ei enää kovakoodattuja "Vaihe
        # X/6" -merkkijonoja jotka menevät sekaisin kun sivupolku muuttuu.
        self._step_labels = {}
        self._header_counter = 0
        self._build_ui()
        self._stack.setCurrentIndex(0)
        self._refresh_step_label(0)

    # ── helpers ──────────────────────────────────────────────────────────

    def _header(self, title, subtitle=""):
        w = QWidget()
        w.setStyleSheet("background: #0a0f1e; border-bottom: 1px solid #1c2c52;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 22, 32, 18)
        lbl = QLabel(title)
        lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #dce6ff; background: transparent;")
        lay.addWidget(lbl)
        sub = QLabel("")
        sub.setStyleSheet("font-size: 12px; color: #8a9bc4; background: transparent;")
        sub.setWordWrap(True)
        lay.addWidget(sub)
        self._step_labels[self._header_counter] = (sub, subtitle)
        self._header_counter += 1
        return w

    def _back_btn(self):
        btn = QPushButton("← Takaisin")
        btn.setFixedHeight(36)
        btn.setStyleSheet(self._BTN_SEC)
        btn.clicked.connect(self._nav_back)
        return btn

    # Sivuindeksit (ks. _build_ui) — lyhyt, suoraviivainen polku:
    # 0 welcome, 1 services, 2 packages (vain dev-tilassa), 3 api_key, 4 devices,
    # 5 chat_routing (vain jos mikseri tai pelit/Discord valittu), 6 finish.
    _PAGE_WELCOME = 0
    _PAGE_SERVICES = 1
    _PAGE_PACKAGES = 2
    _PAGE_API_KEY = 3
    _PAGE_DEVICES = 4
    _PAGE_CHAT_ROUTING = 5
    _PAGE_FINISH = 6

    def _navigate(self, page):
        coming_from = self._stack.currentIndex()
        if coming_from == self._PAGE_DEVICES and page != self._PAGE_DEVICES:
            self._stop_dev_monitoring()
        self._stack.setCurrentIndex(page)
        if page == self._PAGE_DEVICES and coming_from != self._PAGE_DEVICES:
            self._start_dev_monitoring()
        if page == self._PAGE_DEVICES:
            # Chat-reititys-osio elää laitteet-sivulla — sen selitys/näkyvyys riippuu
            # sivun 2 valinnoista, jotka ovat voineet muuttua ennen tänne paluuta.
            self._refresh_chat_routing_page()
            self._update_dev_next_gate()
        if page == self._PAGE_FINISH:
            self._refresh_finish_page()
        self._refresh_step_label(page)

    def _refresh_step_label(self, page):
        entry = self._step_labels.get(page)
        if not entry:
            return
        label, desc = entry
        seq = self._get_page_sequence()
        try:
            pos = seq.index(page) + 1
            total = len(seq)
            label.setText(f"Vaihe {pos}/{total}  —  {desc}" if desc else f"Vaihe {pos}/{total}")
        except ValueError:
            label.setText(desc)

    def _detected_mixer_name(self) -> str | None:
        """Return a clean display name for a physical mixer (e.g. RodeCaster) if plugged in.

        Windows' MME API truncates device names to ~31 chars, so raw names can come out as
        garbled fragments (e.g. "Microphone (RODECaster Pro II C"). Extract just the product
        name instead of echoing a possibly-truncated raw device string to the user.
        """
        import re as _re_mixer
        try:
            for d in sd.query_devices():
                if d["max_input_channels"] > 0:
                    n = d["name"]
                    m = _re_mixer.search(r"rode\s*caster\s*(pro\s*(?:ii|2)?)?", n, _re_mixer.IGNORECASE)
                    if m:
                        return "RØDECaster Pro II" if "ii" in (m.group(1) or "").lower() or "2" in (m.group(1) or "") else "RØDECaster Pro"
        except Exception:
            pass
        return None

    def _get_page_sequence(self) -> list:
        seq = [self._PAGE_WELCOME, self._PAGE_SERVICES]
        # Python-paketit asennetaan automaattisesti services-sivun "Seuraava"-napista
        # (dev-tila; exe:ssä kaikki on bundlattu) — erillistä pakettisivua ei näytetä.
        needs_api = (self._svc_stt == "openai" or
                     self._svc_trans == "openai" or
                     self._svc_tts == "elevenlabs")
        if needs_api:
            seq.append(self._PAGE_API_KEY)
        seq.append(self._PAGE_DEVICES)  # sisältää myös chat-reititys-osion
        seq.append(self._PAGE_FINISH)
        return seq

    def _nav_next(self):
        seq = self._get_page_sequence()
        cur = self._stack.currentIndex()
        try:
            nxt = seq[seq.index(cur) + 1]
            self._navigate(nxt)
        except (ValueError, IndexError):
            pass

    def _nav_back(self):
        seq = self._get_page_sequence()
        cur = self._stack.currentIndex()
        try:
            i = seq.index(cur)
            if i > 0:
                self._navigate(seq[i - 1])
        except (ValueError, IndexError):
            pass

    # ── pages ─────────────────────────────────────────────────────────────

    def _page_welcome(self):
        page = QWidget()
        page.setStyleSheet("background: #05070f;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Tervetuloa Voice Royale",
            "Asennusvelho — käy läpi kaikki vaiheet tai ohita jo valmiit kohdat."
        ))
        body = QWidget()
        body.setStyleSheet("background: #05070f;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 22, 32, 24)
        bl.setSpacing(16)
        info = QLabel(
            "Tämä sovellus:\n\n"
            "  •  Kuuntelee puhettasi mikrofonista\n"
            "  •  Tunnistaa puheen tekstiksi  (OpenAI Whisper)\n"
            "  •  Kääntää valitsemallesi kielelle  (Google Translate tai GPT-4.1-mini)\n"
            "  •  Toistaa käännöksen ääneen  (Edge TTS — täysin ilmainen)"
        )
        info.setStyleSheet("color: #b9c5e6; font-size: 17px; background: transparent; line-height: 1.6;")
        info.setWordWrap(True)
        bl.addWidget(info)
        bl.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        btn = QPushButton("Aloita  →")
        btn.setFixedHeight(42)
        btn.setMinimumWidth(140)
        btn.setStyleSheet(self._BTN_PRIMARY)
        btn.clicked.connect(lambda: self._navigate(1))
        row.addWidget(btn)
        bl.addLayout(row)
        lay.addWidget(body)
        return page

    def _page_services(self):
        from PyQt6.QtWidgets import QFrame, QCheckBox

        page = QWidget()
        page.setStyleSheet("background: #05070f;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Kerro tilanteestasi",
            "Mukautetaan asennus valintojesi mukaan — voit muuttaa kaikkia asetuksia myöhemmin."
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #05070f; }")

        body = QWidget()
        body.setStyleSheet("background: #05070f;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 16, 32, 16)
        bl.setSpacing(10)

        # ── SECTION 1: Devices ────────────────────────────────────────────
        s1_lbl = QLabel("Mitä laitteita sinulla on?")
        s1_lbl.setStyleSheet(
            "color: #dce6ff; font-size: 13px; font-weight: bold; background: transparent; padding-bottom: 2px;"
        )
        bl.addWidget(s1_lbl)

        def _device_row(icon, title, desc, always_on=False):
            w = QWidget()
            w.setFixedHeight(52)
            w.setStyleSheet(
                "QWidget { background: #0a0f1e; border: 1px solid #101a36; border-radius: 8px; }"
            )
            h = QHBoxLayout(w)
            h.setContentsMargins(14, 0, 14, 0)
            h.setSpacing(12)
            cb = QCheckBox()
            cb.setChecked(always_on)
            cb.setEnabled(not always_on)
            cb.setStyleSheet(
                "QCheckBox { background: transparent; border: none; }"
                "QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px;"
                " border: 2px solid #1c2c52; background: transparent; }"
                "QCheckBox::indicator:checked { background: #238636; border-color: #238636; }"
                "QCheckBox::indicator:hover { border-color: #6aa8ff; }"
                "QCheckBox::indicator:disabled { background: #238636; border-color: #238636; }"
            )
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size: 20px; background: transparent; border: none;")
            icon_lbl.setFixedWidth(28)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(
                "color: #dce6ff; font-size: 12px; font-weight: 600; background: transparent; border: none;"
            )
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(
                "color: #546a94; font-size: 11px; background: transparent; border: none;"
            )
            h.addWidget(cb)
            h.addWidget(icon_lbl)
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(title_lbl)
            col.addWidget(desc_lbl)
            h.addLayout(col, 1)
            return w, cb

        def _detect_mixer_reason() -> str:
            """Wizard voi avautua uudelleen (esim. versiopäivityksen jälkeen) ilman että
            käyttäjä muistaa rastia mikseri-ruudun uudelleen — tunnista se sen sijaan
            olemassa olevasta asennuksesta/laitteistosta niin ettei se koskaan nollaudu
            väärin ja tarjoa VB-Cablea Voicemeeterin sijaan. Palauttaa tunnistetun
            laitteen/ohjelman nimen tai tyhjän jos ei löytynyt."""
            try:
                names = [n for _, n in list_input_devices()] + [n for _, n in list_output_devices()]
                rode = next((n for n in names if "rode" in n.lower()), None)
                if rode:
                    return "RodeCaster"
            except Exception:
                pass
            try:
                if _is_voicemeeter_installed():
                    return "Voicemeeter"
            except Exception:
                pass
            return ""

        _mixer_found = _detect_mixer_reason()
        _mixer_desc = (f"✅ Tunnistettu automaattisesti tältä koneelta: {_mixer_found}"
                       if _mixer_found
                       else "Chat-mikin ääni pitää sekoittaa käännösääneen ennen peliä/Discordia.")
        _gw, gaming_cb = _device_row("🎮", "Haluan että käännetty ääneni kuuluu pelissä tai Discordissa",
            "Muut pelaajat kuulevat käännetyn puheesi, kun valitset pelin/Discordin mikrofoniksi virtuaalimikin.")
        _mw, mixer_cb = _device_row("🎚️", "Minulla on fyysinen mikseri (esim. RodeCaster Pro 2)",
            _mixer_desc)
        if _mixer_found:
            mixer_cb.setChecked(True)
        _sw, sd_cb = _device_row("🎛️", "Minulla on Elgato Stream Deck",
            "Voice Royalen napit Stream Deckiin — asetetaan viimeisellä sivulla.")
        _haw, ha_cb = _device_row("🏠", "Käytän Home Assistantia",
            "Kytke kotiautomaatio soundboard-nappeihin — asetetaan viimeisellä sivulla.")

        bl.addWidget(_gw)
        bl.addWidget(_mw)
        bl.addWidget(_sw)
        bl.addWidget(_haw)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #101a36;")
        bl.addWidget(sep1)

        # ── SECTION 2: Package cards ──────────────────────────────────────
        s2_lbl = QLabel("Valitse paketti")
        s2_lbl.setStyleSheet(
            "color: #dce6ff; font-size: 13px; font-weight: bold; background: transparent; padding-bottom: 2px;"
        )
        bl.addWidget(s2_lbl)

        _selected_pkg = [0]  # 0=Ilmainen, 1=OpenAI, 2=Premium

        _PKGS = [
            {
                "icon": "🆓", "title": "Ilmainen", "badge": "SUOSITELTU",
                "rows": [
                    ("Puheentunnistus", "Tietokone — offline"),
                    ("Käännös", "Google Translate"),
                    ("Ääni", "Microsoft Neural Voice"),
                ],
                "req": "✅  Ei tiliä eikä kuluja",
                "req_ok": True,
                "stt": "local",
                "trans": "google", "tts": "edge",
            },
            {
                "icon": "⭐", "title": "OpenAI", "badge": None,
                "rows": [
                    ("Puheentunnistus", "OpenAI — paras laatu"),
                    ("Käännös", "Google Translate (ilmainen)"),
                    ("Ääni", "Microsoft Neural Voice (ilmainen)"),
                ],
                "req": "⚠️  OpenAI API-avain (~1–2 €/kk)",
                "req_ok": False,
                "stt": "openai", "trans": "google", "tts": "edge",
            },
            {
                "icon": "💎", "title": "Premium", "badge": None,
                "rows": [
                    ("Puheentunnistus", "OpenAI — paras laatu"),
                    ("Käännös", "OpenAI AI-käännös"),
                    ("Ääni", "ElevenLabs — erittäin realistinen"),
                ],
                "req": "⚠️  OpenAI + ElevenLabs API-avaimet",
                "req_ok": False,
                "stt": "openai", "trans": "openai", "tts": "elevenlabs",
            },
        ]

        card_widgets = []
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)

        def _make_card(pkg):
            card = QFrame()
            card.setMinimumHeight(172)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(5)
            hdr = QHBoxLayout()
            hdr.setSpacing(6)
            icon_l = QLabel(pkg["icon"])
            icon_l.setStyleSheet("font-size: 22px; background: transparent; border: none;")
            title_l = QLabel(pkg["title"])
            title_l.setStyleSheet(
                "color: #dce6ff; font-size: 13px; font-weight: 700; background: transparent; border: none;"
            )
            hdr.addWidget(icon_l)
            hdr.addWidget(title_l)
            hdr.addStretch()
            if pkg["badge"]:
                bdg = QLabel(pkg["badge"])
                bdg.setStyleSheet(
                    "background: #2e7fff; color: #fff; font-size: 9px; font-weight: 700;"
                    " border-radius: 3px; padding: 1px 5px; border: none;"
                )
                hdr.addWidget(bdg)
            cl.addLayout(hdr)
            sph = QFrame()
            sph.setFrameShape(QFrame.Shape.HLine)
            sph.setStyleSheet("color: #101a36;")
            cl.addWidget(sph)
            for rt, rv in pkg["rows"]:
                rw = QHBoxLayout()
                rw.setSpacing(4)
                rt_l = QLabel(f"• {rt}:")
                rt_l.setStyleSheet(
                    "color: #8a9bc4; font-size: 10px; background: transparent; border: none;"
                )
                rt_l.setFixedWidth(92)
                rv_l = QLabel(rv)
                rv_l.setStyleSheet(
                    "color: #b9c5e6; font-size: 10px; background: transparent; border: none;"
                )
                rv_l.setWordWrap(True)
                rw.addWidget(rt_l)
                rw.addWidget(rv_l, 1)
                cl.addLayout(rw)
            cl.addStretch()
            req_l = QLabel(pkg["req"])
            req_l.setStyleSheet(
                f"color: {'#00ff88' if pkg['req_ok'] else '#ffb830'};"
                " font-size: 10px; background: transparent; border: none;"
            )
            req_l.setWordWrap(True)
            cl.addWidget(req_l)
            return card

        for idx, pkg in enumerate(_PKGS):
            c = _make_card(pkg)
            card_widgets.append(c)
            cards_row.addWidget(c, 1)
            c.mousePressEvent = lambda e, i=idx: _select_pkg(i)

        cards_container = QWidget()
        cards_container.setStyleSheet("background: transparent;")
        cards_container.setLayout(cards_row)
        bl.addWidget(cards_container)

        # ── Summary label ─────────────────────────────────────────────────
        summary_lbl = QLabel()
        summary_lbl.setWordWrap(True)
        bl.addWidget(summary_lbl)

        # ── Logic (defined after all widgets exist) ────────────────────────

        def _update_summary():
            p = _PKGS[_selected_pkg[0]]
            stt, trans, tts = p["stt"], p["trans"], p["tts"]
            routing = "gaming" if gaming_cb.isChecked() else "simple"
            mixer = mixer_cb.isChecked()
            self._svc_stt = stt
            self._svc_trans = trans
            self._svc_tts = tts
            self._svc_routing = routing
            self._svc_mixer = mixer
            self._svc_streamdeck = sd_cb.isChecked()
            self._svc_ha = ha_cb.isChecked()
            # Listaa vain se mitä OIKEASTI puuttuu tältä koneelta — jo asennettua
            # (ffmpeg/Voicemeeter/VB-Cable) ei pelotella "tarvitaan vielä" -rivillä.
            needs = []
            if stt == "openai" or trans == "openai" or tts == "elevenlabs":
                needs.append("OpenAI API-avain")
            if tts == "elevenlabs":
                needs.append("ElevenLabs API-avain")
            if stt == "local" and not shutil.which("ffmpeg"):
                needs.append("ffmpeg (ilmainen)")
            if mixer:
                try:
                    _vm_ok = _is_voicemeeter_installed()
                except Exception:
                    _vm_ok = False
                if not _vm_ok:
                    needs.append("Voicemeeter Banana (ilmainen)")
            elif routing == "gaming":
                try:
                    _vbc_ok = _is_vbcable_installed()
                except Exception:
                    _vbc_ok = False
                if not _vbc_ok:
                    needs.append("VB-Cable (ilmainen)")
            if needs:
                summary_lbl.setText("Tarvitaan vielä:  " + "  •  ".join(needs))
                summary_lbl.setStyleSheet(
                    "color: #ffb830; font-size: 11px; background: #2b1f0a;"
                    " border: 1px solid #9e6a03; border-radius: 6px; padding: 8px 12px;"
                )
            else:
                summary_lbl.setText("✅  Täysin ilmainen — ei tarvita tiliä eikä luottokorttia.")
                summary_lbl.setStyleSheet(
                    "color: #00ff88; font-size: 11px; background: #0d2b14;"
                    " border: 1px solid #238636; border-radius: 6px; padding: 8px 12px;"
                )

        def _select_pkg(idx):
            _selected_pkg[0] = idx
            for i, c in enumerate(card_widgets):
                if i == idx:
                    c.setStyleSheet(
                        "QFrame { background: #0d2b14; border: 2px solid #238636; border-radius: 10px; }"
                    )
                else:
                    c.setStyleSheet(
                        "QFrame { background: #0a0f1e; border: 1px solid #1c2c52; border-radius: 10px; }"
                    )
            _update_summary()

        gaming_cb.toggled.connect(lambda *_: _update_summary())
        mixer_cb.toggled.connect(lambda *_: _update_summary())
        sd_cb.toggled.connect(lambda *_: _update_summary())
        ha_cb.toggled.connect(lambda *_: _update_summary())
        _select_pkg(0)  # default: Ilmainen (suositeltu)

        # Asennuksen edistyminen — näkyviin vasta kun "Seuraava" asentaa jotain
        _inst_w = QWidget()
        _inst_w.setVisible(False)
        _inst_w.setStyleSheet("background: transparent;")
        _inst_bl = QVBoxLayout(_inst_w)
        _inst_bl.setContentsMargins(0, 4, 0, 0)
        _inst_bl.setSpacing(4)
        _inst_lbl = QLabel()
        _inst_lbl.setStyleSheet("color: #b9c5e6; font-size: 12px; background: transparent;")
        _inst_lbl.setWordWrap(True)
        _inst_bar = QProgressBar()
        _inst_bar.setFixedHeight(10)
        _inst_bar.setTextVisible(False)
        _inst_bar.setStyleSheet(self._BAR_IDLE)
        _inst_bl.addWidget(_inst_lbl)
        _inst_bl.addWidget(_inst_bar)
        bl.addWidget(_inst_w)

        bl.addStretch()
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

        nav = QHBoxLayout()
        nav.setContentsMargins(32, 8, 32, 16)
        nav.addWidget(self._back_btn())
        nav.addStretch()
        nxt = QPushButton("Seuraava  →")
        nxt.setFixedHeight(42)
        nxt.setMinimumWidth(140)
        nxt.setStyleSheet(self._BTN_PRIMARY)

        _REQ_IMPORTS = [
            ("PyQt6", "PyQt6"), ("requests", "requests"), ("dotenv", "python-dotenv"),
            ("sounddevice", "sounddevice"), ("numpy", "numpy"), ("scipy", "scipy"),
            ("openai", "openai"), ("pyttsx3", "pyttsx3"), ("edge_tts", "edge-tts"),
            ("deep_translator", "deep-translator"),
        ]

        _inst_reboot_btn = QPushButton("🔄  Käynnistä tietokone uudelleen")
        _inst_reboot_btn.setFixedHeight(34)
        _inst_reboot_btn.setStyleSheet(self._BTN_SEC)
        _inst_reboot_btn.setVisible(False)
        _inst_bl.addWidget(_inst_reboot_btn)

        def _inst_do_reboot():
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Käynnistä uudelleen",
                "Ajurin viimeistely vaatii uudelleenkäynnistyksen.\n\n"
                "Tietokone käynnistyy uudelleen 15 sekunnin kuluttua — tallenna avoimet "
                "tiedostot muissa ohjelmissa.\n\nVoice Royale avaa tämän saman sivun "
                "automaattisesti käynnistyksen jälkeen.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            try:
                _rs = load_settings()
                _rs["_resume_wizard_page"] = self._PAGE_SERVICES
                save_settings(_rs)
            except Exception:
                pass
            try:
                subprocess.Popen(
                    ["shutdown", "/r", "/t", "15"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as e:
                QMessageBox.warning(self, "Virhe", f"Uudelleenkäynnistystä ei voitu käynnistää: {e}")
                return
            _inst_reboot_btn.setEnabled(False)
            _inst_reboot_btn.setText("Käynnistyy uudelleen 15 s kuluttua…")

        _inst_reboot_btn.clicked.connect(_inst_do_reboot)

        def _install_then_next():
            """Asentaa KAIKEN mitä valittu paketti + laitevalinnat vaativat — pip-kirjastot
            (vain dev-tilassa; exe:ssä bundlattu) sekä Voicemeeter Banana / VB-Cable —
            edistymispalkilla, ja siirtyy sitten seuraavalle sivulle. Laitteet-sivulle jää
            vain reitityksen MÄÄRITYS (ei asennuksia normaalipolussa)."""
            import importlib as _il
            pip_missing = []
            if not getattr(sys, "frozen", False):
                for _imp, _pip in _REQ_IMPORTS:
                    try:
                        _il.import_module(_imp)
                    except Exception:
                        pip_missing.append(_pip)
                if self._svc_stt == "local":
                    try:
                        _il.import_module("faster_whisper")
                    except Exception:
                        pip_missing.append("faster-whisper")
            need_vm = (sys.platform == "win32" and self._svc_mixer
                       and not _is_voicemeeter_installed())
            need_vbc = (sys.platform == "win32" and not self._svc_mixer
                        and self._svc_routing == "gaming" and not _is_vbcable_installed())
            steps = [("pip", p) for p in pip_missing]
            if need_vm:
                steps.append(("voicemeeter", "Voicemeeter Banana"))
            if need_vbc:
                steps.append(("vbcable", "VB-Cable"))
            if not steps:
                self._nav_next()
                return
            nxt.setEnabled(False)
            _inst_reboot_btn.setVisible(False)
            _inst_w.setVisible(True)
            _inst_bar.setRange(0, len(steps))
            _inst_bar.setValue(0)
            _inst_bar.setStyleSheet(self._BAR_IDLE)
            _inst_lbl.setStyleSheet("color: #b9c5e6; font-size: 12px; background: transparent;")
            _inst_lbl.setText(f"Asennetaan 1/{len(steps)}: {steps[0][1]} …")
            import queue as _q
            _rq = _q.Queue()

            def _bg():
                import subprocess as _sp
                for i, (kind_s, label) in enumerate(steps):
                    _rq.put(("progress", i, label))
                    try:
                        if kind_s == "pip":
                            res = _sp.run(
                                [sys.executable, "-m", "pip", "install", label],
                                capture_output=True, text=True, timeout=300,
                            )
                            if res.returncode != 0:
                                _rq.put(("error", label, res.stderr[-200:]))
                                return
                        elif kind_s == "voicemeeter":
                            _install_voicemeeter(lambda m: _rq.put(("progress", i, f"{label}: {m}")))
                            if not _is_voicemeeter_installed():
                                _rq.put(("need_reboot", None, None))
                                return
                        elif kind_s == "vbcable":
                            _install_vbcable(lambda m: _rq.put(("progress", i, f"{label}: {m}")))
                            if not _is_vbcable_installed():
                                _rq.put(("error", label,
                                         "asennus ei valmistunut — kokeile uudelleen tai käynnistä kone uudelleen"))
                                return
                    except Exception as e:
                        _rq.put(("error", label, str(e)))
                        return
                _rq.put(("done", None, None))

            def _poll():
                try:
                    kind, a, b = _rq.get_nowait()
                except Exception:
                    return
                if kind == "progress":
                    _inst_bar.setValue(a)
                    _inst_lbl.setText(f"Asennetaan {a + 1}/{len(steps)}: {b}")
                elif kind == "done":
                    _ptmr.stop()
                    _inst_bar.setValue(len(steps))
                    _inst_bar.setStyleSheet(self._BAR_ACTIVE)
                    _inst_lbl.setText("✅ Kaikki asennettu.")
                    nxt.setEnabled(True)
                    self._nav_next()
                elif kind == "need_reboot":
                    _ptmr.stop()
                    _inst_lbl.setText(
                        "🔄 Voicemeeter Banana asennettu — ajurin viimeistely vaatii "
                        "uudelleenkäynnistyksen. Wizard jatkuu automaattisesti sen jälkeen."
                    )
                    _inst_lbl.setStyleSheet("color: #ffb830; font-size: 12px; background: transparent;")
                    _inst_reboot_btn.setVisible(True)
                    nxt.setEnabled(True)
                else:
                    _ptmr.stop()
                    _inst_lbl.setText(f"✗ Asennus epäonnistui ({a}): {b}")
                    _inst_lbl.setStyleSheet("color: #ff2e4d; font-size: 12px; background: transparent;")
                    nxt.setEnabled(True)

            _ptmr = QTimer(self)
            _ptmr.timeout.connect(_poll)
            _ptmr.start(150)
            threading.Thread(target=_bg, daemon=True).start()

        nxt.clicked.connect(_install_then_next)
        nav.addWidget(nxt)
        nav_w = QWidget()
        nav_w.setObjectName("wizNavW")
        nav_w.setStyleSheet("#wizNavW { background: #05070f; }")
        nav_w.setLayout(nav)
        lay.addWidget(nav_w)
        return page

    def _page_packages(self):
        import importlib, importlib.metadata as _ilm

        _PKG_LIST = [
            ("PyQt6",           "PyQt6",           True,  "UI-framework"),
            ("requests",        "requests",         True,  "HTTP"),
            ("dotenv",          "python-dotenv",    True,  "Ympäristömuuttujat"),
            ("sounddevice",     "sounddevice",      True,  "Äänilaitteet"),
            ("numpy",           "numpy",            True,  "Audion käsittely"),
            ("scipy",           "scipy",            True,  "Resampling"),
            ("keyboard",        "keyboard",         False, "Global hotkey (Windows/Linux)"),
            ("openai",          "openai",           True,  "Whisper + GPT"),
            ("pyttsx3",         "pyttsx3",          True,  "Paikallinen TTS"),
            ("edge_tts",        "edge-tts",         True,  "Edge TTS"),
            ("deep_translator", "deep-translator",  True,  "Google Translate"),
            ("pvporcupine",     "pvporcupine",      False, "Wake word (valinnainen)"),
            ("pyrubberband",    "pyrubberband",     False, "Voice FX laatu (valinnainen)"),
            ("pydub",           "pydub",            False, "MP3/OGG soundboard (valinnainen)"),
            ("faster_whisper",  "faster-whisper",   False, "Paikallinen STT offline (valinnainen)"),
        ]

        def _ck(imp, pip):
            try:
                importlib.import_module(imp)
                try:
                    ver = _ilm.version(pip)
                except Exception:
                    ver = "?"
                return True, ver
            except Exception:
                return False, ""

        statuses = {pip: _ck(imp, pip) for imp, pip, req, desc in _PKG_LIST}
        req_all_ok = all(statuses[pip][0] for imp, pip, req, _ in _PKG_LIST if req)

        page = QWidget()
        page.setStyleSheet("background: #05070f;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Python-paketit",
            "Tarkistetaan tarvittavat kirjastot."
        ))
        body = QWidget()
        body.setStyleSheet("background: #05070f;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 14, 32, 16)
        bl.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(250)
        scroll.setStyleSheet(
            "QScrollArea { background: #0a0f1e; border: 1px solid #1c2c52; border-radius: 6px; }"
        )
        cnt = QWidget()
        cnt.setStyleSheet("background: #0a0f1e;")
        cl = QVBoxLayout(cnt)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(3)
        for imp, pip, req, desc in _PKG_LIST:
            ok, ver = statuses[pip]
            r = QWidget()
            r.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(r)
            rl.setContentsMargins(2, 1, 2, 1)
            rl.setSpacing(8)
            nl = QLabel(pip)
            nl.setFixedWidth(200)
            nl.setStyleSheet(f"color: {'#b9c5e6' if req else '#546a94'}; font-size: 11px;")
            dl = QLabel(desc)
            dl.setStyleSheet("color: #546a94; font-size: 10px;")
            sl = QLabel("✅ " + ver if ok else ("✗ puuttuu" if req else "– ei asennettu"))
            sl.setStyleSheet(
                f"color: {'#00ff88' if ok else ('#ff2e4d' if req else '#546a94')};"
                " font-size: 11px; font-weight: bold;"
            )
            rl.addWidget(nl)
            rl.addWidget(dl, 1)
            rl.addWidget(sl)
            cl.addWidget(r)
        cl.addStretch()
        scroll.setWidget(cnt)
        bl.addWidget(scroll)

        summary_lbl = QLabel(
            "✅ Kaikki vaatimukset asennettu." if req_all_ok
            else "Joitakin paketteja puuttuu — paina Asenna."
        )
        summary_lbl.setStyleSheet(
            f"color: {'#00ff88' if req_all_ok else '#ffb830'};"
            " font-size: 12px; font-weight: bold; background: transparent;"
        )
        bl.addWidget(summary_lbl)

        install_btn = QPushButton("Asenna puuttuvat paketit")
        install_btn.setFixedHeight(36)
        install_btn.setEnabled(not req_all_ok)

        def _do_install():
            if getattr(sys, "frozen", False):
                summary_lbl.setText("EXE-tilassa paketteja ei voi asentaa automaattisesti.\nAvaa terminaali ja aja: pip install [paketti]")
                summary_lbl.setStyleSheet("color: #ffb830; font-size: 12px; background: transparent;")
                return
            missing = [pip for imp, pip, req, _ in _PKG_LIST if req and not _ck(imp, pip)[0]]
            # Also install faster-whisper if user selected local STT
            if getattr(self, "_svc_stt", "") == "local" and not _ck("faster_whisper", "faster-whisper")[0]:
                if "faster-whisper" not in missing:
                    missing.append("faster-whisper")
            if not missing:
                summary_lbl.setText("✅ Kaikki asennettu.")
                return
            install_btn.setEnabled(False)
            summary_lbl.setText("Asennetaan — odota...")
            summary_lbl.setStyleSheet("color: #8a9bc4; font-size: 12px; background: transparent;")
            import queue as _q
            _rq = _q.Queue()

            def _bg():
                import subprocess as _sp
                try:
                    res = _sp.run(
                        [sys.executable, "-m", "pip", "install"] + missing,
                        capture_output=True, text=True, timeout=180
                    )
                    ok2 = res.returncode == 0
                    msg = ("✅ Asennus valmis — käynnistä appi uudelleen."
                           if ok2 else f"✗ Virhe: {res.stderr[-200:]}")
                    _rq.put((ok2, msg))
                except Exception as e:
                    _rq.put((False, f"✗ Virhe: {e}"))

            def _poll():
                try:
                    ok2, msg = _rq.get_nowait()
                except Exception:
                    return
                _ptmr.stop()
                summary_lbl.setText(msg)
                summary_lbl.setStyleSheet(
                    f"color: {'#00ff88' if ok2 else '#ff2e4d'};"
                    " font-size: 12px; background: transparent;"
                )
                install_btn.setEnabled(not ok2)

            _ptmr = QTimer(self)
            _ptmr.timeout.connect(_poll)
            _ptmr.start(200)
            threading.Thread(target=_bg, daemon=True).start()

        install_btn.clicked.connect(_do_install)
        bl.addWidget(install_btn)

        if getattr(sys, "frozen", False):
            frozen_note = QLabel(
                "✅ Kaikki kirjastot — myös faster-whisper — on bundlattu asennuspakettiin."
            )
            frozen_note.setStyleSheet(
                "color: #00ff88; font-size: 11px; background: transparent;"
            )
            frozen_note.setWordWrap(True)
            bl.addWidget(frozen_note)
            install_btn.setVisible(False)

        # ffmpeg check
        import shutil as _shutil
        _has_ffmpeg = bool(_shutil.which("ffmpeg"))
        ffmpeg_row = QWidget()
        ffmpeg_row.setStyleSheet("background: transparent;")
        ffmpeg_rl = QHBoxLayout(ffmpeg_row)
        ffmpeg_rl.setContentsMargins(2, 1, 2, 1)
        ffmpeg_rl.setSpacing(8)
        ffmpeg_icon = QLabel("✅" if _has_ffmpeg else "⚠️")
        ffmpeg_icon.setFixedWidth(22)
        ffmpeg_icon.setStyleSheet("font-size: 14px; background: transparent;")
        ffmpeg_name = QLabel("<b>ffmpeg</b>")
        ffmpeg_name.setFixedWidth(160)
        ffmpeg_name.setStyleSheet(
            f"color: {'#dce6ff' if _has_ffmpeg else '#ffb830'}; background: transparent;"
        )
        ffmpeg_desc = QLabel(
            "Edge TTS (faster-whisper ei tarvitse ffmpegiä)" if _has_ffmpeg
            else "Edge TTS — ei löydy PATH:ista  (faster-whisper toimii ilman ffmpegiä)"
        )
        ffmpeg_desc.setStyleSheet("background: transparent; font-size: 11px; color: #8a9bc4;")
        ffmpeg_rl.addWidget(ffmpeg_icon)
        ffmpeg_rl.addWidget(ffmpeg_name)
        ffmpeg_rl.addWidget(ffmpeg_desc, 1)
        if not _has_ffmpeg:
            import queue as _ffq, shutil as _sh_ff
            _ff_result_q = _ffq.Queue()

            if sys.platform == "darwin":
                # Check if Homebrew is installed
                _brew_path = (
                    _sh_ff.which("brew")
                    or ("/opt/homebrew/bin/brew" if os.path.isfile("/opt/homebrew/bin/brew") else None)
                    or ("/usr/local/bin/brew" if os.path.isfile("/usr/local/bin/brew") else None)
                )
                _ff_btn_label = "brew install ffmpeg" if _brew_path else "Asenna Homebrew + ffmpeg"
            else:
                _brew_path = None
                _ff_btn_label = "winget install ffmpeg"

            ffmpeg_install_btn = QPushButton(_ff_btn_label)
            ffmpeg_install_btn.setFixedWidth(190)
            ffmpeg_install_btn.setStyleSheet(
                "QPushButton { background: #14281e; border: 1px solid #1a5a30; border-radius: 5px;"
                " color: #00cc6a; padding: 3px 6px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { border-color: #00ff88; color: #5AFFAA; }"
            )
            _ff_timer = QTimer(ffmpeg_install_btn)

            def _poll_ff():
                # macOS terminal install: check paths directly (no queue)
                if sys.platform == "darwin":
                    for _hb in ["/opt/homebrew/bin", "/usr/local/bin"]:
                        if os.path.isfile(os.path.join(_hb, "ffmpeg")):
                            os.environ["PATH"] = _hb + ":" + os.environ.get("PATH", "")
                            _ff_timer.stop()
                            ffmpeg_icon.setText("✅")
                            ffmpeg_name.setStyleSheet("color: #dce6ff; background: transparent;")
                            ffmpeg_desc.setText("Edge TTS — asennettu onnistuneesti")
                            ffmpeg_install_btn.setVisible(False)
                            return
                # Windows / macOS background thread: check queue
                try:
                    found = _ff_result_q.get_nowait()
                except Exception:
                    return
                _ff_timer.stop()
                if found:
                    ffmpeg_icon.setText("✅")
                    ffmpeg_name.setStyleSheet("color: #dce6ff; background: transparent;")
                    ffmpeg_desc.setText("Edge TTS — asennettu onnistuneesti")
                    ffmpeg_install_btn.setVisible(False)
                else:
                    ffmpeg_install_btn.setEnabled(True)
                    ffmpeg_install_btn.setText(_ff_btn_label)
                    ffmpeg_desc.setText("Ei löydy asennuksen jälkeen — käynnistä ohjelma uudelleen")

            _ff_timer.timeout.connect(_poll_ff)

            def _run_ffmpeg_install(brew=_brew_path):
                import subprocess as _sp2, shutil as _sh2
                ffmpeg_install_btn.setEnabled(False)

                if sys.platform == "darwin":
                    if not brew:
                        # Homebrew not installed — open Terminal, install brew + ffmpeg
                        ffmpeg_install_btn.setText("Terminal avattu — odota��")
                        ffmpeg_desc.setText("Syötä salasana terminaalissa — tarkistus automaattinen")
                        _cmd = (
                            '/bin/bash -c "$(curl -fsSL '
                            'https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" '
                            '&& (/opt/homebrew/bin/brew install ffmpeg '
                            '|| /usr/local/bin/brew install ffmpeg)'
                        )
                        _sp2.run(
                            ["osascript", "-e",
                             f'tell application "Terminal" to do script "{_cmd}"'],
                            capture_output=True,
                        )
                        _ff_timer.start(4000)  # poll every 4s until ffmpeg appears
                    else:
                        # Homebrew found — install ffmpeg in background thread
                        ffmpeg_install_btn.setText("Asentaa…")
                        _ff_timer.start(3000)

                        def _do_brew():
                            _sp2.run([brew, "install", "ffmpeg"],
                                     capture_output=True, timeout=600)
                            for _hb in ["/opt/homebrew/bin", "/usr/local/bin"]:
                                if os.path.isfile(os.path.join(_hb, "ffmpeg")):
                                    os.environ["PATH"] = _hb + ":" + os.environ.get("PATH", "")
                                    break

                        threading.Thread(target=_do_brew, daemon=True).start()
                else:
                    # Windows: winget
                    ffmpeg_install_btn.setText("Asentaa…")
                    _ff_timer.start(500)

                    def _do_win():
                        _sp2.run(
                            ["winget", "install", "--id", "Gyan.FFmpeg", "-e",
                             "--accept-source-agreements", "--accept-package-agreements"],
                            creationflags=getattr(_sp2, "CREATE_NEW_CONSOLE", 0),
                        )
                        try:
                            import winreg as _wreg
                            _k = _wreg.OpenKey(_wreg.HKEY_LOCAL_MACHINE,
                                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
                            _sp_val, _ = _wreg.QueryValueEx(_k, "Path"); _wreg.CloseKey(_k)
                        except Exception:
                            _sp_val = ""
                        try:
                            import winreg as _wreg2
                            _k2 = _wreg2.OpenKey(_wreg2.HKEY_CURRENT_USER, "Environment")
                            _up_val, _ = _wreg2.QueryValueEx(_k2, "Path"); _wreg2.CloseKey(_k2)
                        except Exception:
                            _up_val = ""
                        os.environ["PATH"] = _sp_val + ";" + _up_val + ";" + os.environ.get("PATH", "")
                        _ff_result_q.put(bool(_sh2.which("ffmpeg")))

                    threading.Thread(target=_do_win, daemon=True).start()

            ffmpeg_install_btn.clicked.connect(_run_ffmpeg_install)
            ffmpeg_rl.addWidget(ffmpeg_install_btn)
        bl.addWidget(ffmpeg_row)

        bl.addStretch()

        nav = QHBoxLayout()
        nav.addWidget(self._back_btn())
        nav.addStretch()
        nxt = QPushButton("Seuraava  →")
        nxt.setFixedHeight(42)
        nxt.setMinimumWidth(140)
        nxt.clicked.connect(self._nav_next)
        nav.addWidget(nxt)
        bl.addLayout(nav)
        lay.addWidget(body)
        return page

    def _page_api_key(self):
        existing = OPENAI_API_KEY or ""
        has_key = bool(existing)

        page = QWidget()
        page.setStyleSheet("background: #05070f;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "OpenAI API-avain",
            "Tarvitaan puheentunnistukseen. Ohitettavissa."
        ))
        body = QWidget()
        body.setStyleSheet("background: #05070f;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 20, 32, 20)
        bl.setSpacing(12)

        if has_key:
            masked = existing[:8] + "…" + existing[-4:] if len(existing) > 12 else "***"
            fl = QLabel(f"✅  Avain löytyy: {masked}")
            fl.setStyleSheet(
                "color: #00ff88; font-size: 15px; font-weight: bold; background: transparent;"
            )
            bl.addWidget(fl)
            hint = QLabel(
                "Tallennettu credentials.env-tiedostoon. "
                "Voit jatkaa suoraan tai syöttää uuden avaimen alle."
            )
            hint.setStyleSheet("color: #8a9bc4; font-size: 11px; background: transparent;")
            hint.setWordWrap(True)
            bl.addWidget(hint)
            sep_lbl = QLabel("— Vaihda avain (valinnainen) —")
            sep_lbl.setStyleSheet("color: #546a94; font-size: 11px; background: transparent;")
            bl.addWidget(sep_lbl)
        else:
            desc = QLabel(
                "OpenAI API-avain tarvitaan Whisper-puheentunnistukseen.\n"
                "Luo ilmainen tili → hanki avain → liitä alle.\n"
                "Jos haluat vain kääntää tekstiä, voit ohittaa tämän."
            )
            desc.setStyleSheet("color: #b9c5e6; font-size: 13px; background: transparent;")
            desc.setWordWrap(True)
            bl.addWidget(desc)

        link_btn = QPushButton("🌐   Avaa  platform.openai.com/api-keys")
        link_btn.setFixedHeight(36)
        link_btn.setStyleSheet(
            "QPushButton { background: #101a36; color: #6aa8ff; border: 1px solid #1c2c52;"
            " border-radius: 6px; padding: 6px 18px; font-size: 12px; font-weight: normal; }"
            "QPushButton:hover { background: #1c2c52; }"
        )
        link_btn.clicked.connect(lambda: webbrowser.open("https://platform.openai.com/api-keys"))
        bl.addWidget(link_btn)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx...")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setFixedHeight(40)
        self._key_input.textChanged.connect(self._on_key_changed)
        bl.addWidget(self._key_input)

        show_row = QHBoxLayout()
        show_cb = QCheckBox("Näytä avain")
        show_cb.toggled.connect(
            lambda on: self._key_input.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        show_row.addWidget(show_cb)
        show_row.addStretch()
        bl.addLayout(show_row)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Testaa yhteys")
        self._test_btn.setFixedHeight(34)
        self._test_btn.setEnabled(False)
        self._test_btn.setStyleSheet(self._BTN_SEC)
        self._test_btn.clicked.connect(self._test_key)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            "font-size: 12px; padding-left: 8px; background: transparent;"
        )
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._status_lbl)
        test_row.addStretch()
        bl.addLayout(test_row)

        self._save_btn = QPushButton("Tallenna avain")
        self._save_btn.setFixedHeight(34)
        self._save_btn.setEnabled(False)
        self._save_btn.setStyleSheet(
            "QPushButton { background: #238636; color: #fff; border: none;"
            " border-radius: 6px; padding: 5px 14px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover:enabled { background: #2ea043; }"
            "QPushButton:disabled { background: #101a36; color: #546a94; }"
        )
        self._save_btn.clicked.connect(self._save_key)
        bl.addWidget(self._save_btn)
        bl.addStretch()

        nav = QHBoxLayout()
        nav.addWidget(self._back_btn())
        skip = QPushButton("Ohita (ei puheentunnistusta)")
        skip.setFixedHeight(36)
        skip.setStyleSheet(self._BTN_SKIP)
        skip.clicked.connect(self._nav_next)
        nav.addWidget(skip)
        nav.addStretch()
        nxt = QPushButton("Seuraava  →")
        nxt.setFixedHeight(42)
        nxt.setMinimumWidth(140)
        nxt.clicked.connect(self._nav_next)
        nav.addWidget(nxt)
        bl.addLayout(nav)
        lay.addWidget(body)
        return page

    def _build_chat_routing_section(self) -> QWidget:
        """Chat-reititys — OSIO laitteet-sivulla (aiemmin oma sivu). "Määritä
        automaattisesti" tekee asennuksen+määrityksen+testauksen taustalla peräkkäin,
        ja laitetunnistus (mikserin Chat-kanava) on oma riippumaton avainsanahaku.
        Kutsutaan vain Windowsissa (kutsuja guardaa)."""
        sec = QWidget()
        sec.setStyleSheet("background: transparent;")
        bl = QVBoxLayout(sec)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(10)

        sec_hdr = QLabel("Chat-reititys — kuulu Discordissa ja peleissä")
        sec_hdr.setStyleSheet(
            "color: #dce6ff; font-size: 13px; font-weight: bold; background: transparent;"
        )
        bl.addWidget(sec_hdr)

        # Selitysteksti ja tilariippuvat osat täytetään/päivitetään _refresh_chat_routing_page():ssä
        # (kutsutaan sekä täältä alussa että joka kerta kun sivulle navigoidaan — _svc_mixer on
        # voinut muuttua käyttäjän palattua sivulle 1 sen jälkeen kun tämä sivu jo rakennettiin).
        self._chat_why_lbl = QLabel("")
        self._chat_why_lbl.setStyleSheet(
            "color: #8a9bc4; font-size: 12px; background: transparent; line-height: 145%;"
        )
        self._chat_why_lbl.setWordWrap(True)
        bl.addWidget(self._chat_why_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #101a36;")
        bl.addWidget(sep)

        # Yksi lyhyt, selkeä lopputulosrivi (✅/⚠️/❌) — EI raakaa tekniikkalokia. Tekniset
        # yksityiskohdat (mm. Voicemeeterin oma "Hardware Input 1 -kohtaan pitää näkyä..."
        # -varoitusteksti, joka tulee MUKANA myös onnistuneen konfiguroinnin viestissä ja
        # näytti aiemmin sekavalta kun se liimattiin suoraan pääviestin perään) ovat erikseen
        # "Näytä tekniset tiedot" -linkin takana.
        self._chat_verdict_lbl = QLabel("")
        self._chat_verdict_lbl.setWordWrap(True)
        self._chat_verdict_lbl.setStyleSheet(
            "color: #dce6ff; font-size: 14px; font-weight: bold; background: transparent;"
        )
        bl.addWidget(self._chat_verdict_lbl)

        self._chat_details_toggle_btn = QPushButton("▸  Näytä tekniset tiedot")
        self._chat_details_toggle_btn.setFlat(True)
        self._chat_details_toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #6aa8ff;"
            " font-size: 11px; text-align: left; padding: 2px 0; }"
            "QPushButton:hover { color: #6aa8ff; }"
        )
        self._chat_details_toggle_btn.setVisible(False)
        bl.addWidget(self._chat_details_toggle_btn)

        self._chat_details_w = QWidget()
        self._chat_details_w.setVisible(False)
        details_lay = QVBoxLayout(self._chat_details_w)
        details_lay.setContentsMargins(0, 4, 0, 0)
        self._chat_result_lbl = QLabel("")
        self._chat_result_lbl.setWordWrap(True)
        self._chat_result_lbl.setStyleSheet("color: #8a9bc4; font-size: 11px; background: transparent;")
        details_lay.addWidget(self._chat_result_lbl)
        bl.addWidget(self._chat_details_w)

        def _toggle_chat_details():
            vis = not self._chat_details_w.isVisible()
            self._chat_details_w.setVisible(vis)
            self._chat_details_toggle_btn.setText(
                "▾  Piilota tekniset tiedot" if vis else "▸  Näytä tekniset tiedot"
            )

        self._chat_details_toggle_btn.clicked.connect(_toggle_chat_details)

        self._chat_cfg_btn = QPushButton("🔧  Määritä automaattisesti")
        self._chat_cfg_btn.setFixedHeight(42)
        self._chat_cfg_btn.setStyleSheet(self._BTN_PRIMARY)
        bl.addWidget(self._chat_cfg_btn)

        self._chat_reboot_btn = QPushButton("🔄  Käynnistä tietokone uudelleen")
        self._chat_reboot_btn.setFixedHeight(34)
        self._chat_reboot_btn.setStyleSheet(self._BTN_SEC)
        self._chat_reboot_btn.setVisible(False)

        def _do_reboot():
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Käynnistä uudelleen",
                "Ajurin viimeistely vaatii uudelleenkäynnistyksen.\n\n"
                "Tietokone käynnistyy uudelleen 15 sekunnin kuluttua — tallenna avoimet "
                "tiedostot muissa ohjelmissa.\n\nVoice Royale avaa tämän saman sivun "
                "automaattisesti käynnistyksen jälkeen.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            try:
                _rs = load_settings()
                _rs["_resume_wizard_page"] = self._PAGE_DEVICES
                save_settings(_rs)
            except Exception:
                pass
            try:
                subprocess.Popen(
                    ["shutdown", "/r", "/t", "15"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as e:
                QMessageBox.warning(self, "Virhe", f"Uudelleenkäynnistystä ei voitu käynnistää: {e}")
                return
            self._chat_reboot_btn.setEnabled(False)
            self._chat_reboot_btn.setText("Käynnistyy uudelleen 15 s kuluttua…")

        self._chat_reboot_btn.clicked.connect(_do_reboot)
        bl.addWidget(self._chat_reboot_btn)

        # -- manuaalinen laitevalinta: näkyy VAIN jos automaattinen tunnistus epäonnistuu --
        self._chat_manual_row = QWidget()
        self._chat_manual_row.setVisible(False)
        manual_lay = QVBoxLayout(self._chat_manual_row)
        manual_lay.setContentsMargins(0, 4, 0, 0)
        manual_lay.setSpacing(6)
        manual_hint = QLabel("Emme tunnistaneet mikseriäsi automaattisesti — valitse laite:")
        manual_hint.setStyleSheet("color: #ffb830; font-size: 11px; background: transparent;")
        manual_hint.setWordWrap(True)
        self._chat_dev_combo = QComboBox()
        self._chat_dev_combo.setFixedHeight(32)
        self._chat_dev_combo.setStyleSheet(
            "QComboBox { background: #0a0f1e; border: 1px solid #1c2c52; border-radius: 6px;"
            " color: #dce6ff; padding: 4px 10px; font-size: 12px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #0a0f1e; color: #dce6ff; }"
        )
        manual_lay.addWidget(manual_hint)
        manual_lay.addWidget(self._chat_dev_combo)
        bl.addWidget(self._chat_manual_row)

        def _refresh_chat_dev_combo():
            self._chat_dev_combo.blockSignals(True)
            self._chat_dev_combo.clear()
            try:
                for d in sd.query_devices():
                    if d["max_input_channels"] > 0:
                        self._chat_dev_combo.addItem(d["name"])
            except Exception:
                pass
            self._chat_dev_combo.blockSignals(False)
            _fit_combo_dropdown(self._chat_dev_combo)

        # -- toissijaiset työkalut: rakennetaan aina, mutta näkyvyys (vain mikseri-polulla)
        # päätetään dynaamisesti _refresh_chat_routing_page():ssä, koska _svc_mixer voi vielä
        # muuttua käyttäjän palatessa sivulle 1 sen jälkeen kun tämä sivu on jo rakennettu kerran.
        self._chat_utility_w = QWidget()
        self._chat_utility_w.setStyleSheet("background: transparent;")
        utility_outer = QVBoxLayout(self._chat_utility_w)
        utility_outer.setContentsMargins(0, 0, 0, 0)
        utility_outer.setSpacing(6)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #101a36;")
        utility_outer.addWidget(sep2)

        # Piilotettu oletuksena "Lisäasetukset"-linkin taakse — nämä eivät ole osa normaalia
        # polkua (automaatio hoitaa 95% tapauksista), joten harmaana aina näkyvillä ne vain
        # sekoittivat käyttäjää siitä mitä pitäisi tehdä (käyttäjäpalaute).
        adv_toggle_btn = QPushButton("▸  Lisäasetukset")
        adv_toggle_btn.setFlat(True)
        adv_toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #6aa8ff;"
            " font-size: 11px; text-align: left; padding: 2px 0; }"
            "QPushButton:hover { color: #6aa8ff; }"
        )
        utility_outer.addWidget(adv_toggle_btn)

        adv_content_w = QWidget()
        adv_content_w.setVisible(False)
        utility_row = QHBoxLayout(adv_content_w)
        utility_row.setContentsMargins(0, 4, 0, 0)
        utility_row.setSpacing(8)
        cleanup_btn = QPushButton("Siivoa turhat virtuaalilaitteet")
        cleanup_btn.setFixedHeight(28)
        cleanup_btn.setStyleSheet(self._BTN_SKIP)
        manual_mic_btn = QPushButton("Aseta Windows-mikrofoni manuaalisesti")
        manual_mic_btn.setFixedHeight(28)
        manual_mic_btn.setStyleSheet(self._BTN_SKIP)
        utility_row.addWidget(cleanup_btn)
        utility_row.addWidget(manual_mic_btn)
        utility_row.addStretch()
        utility_outer.addWidget(adv_content_w)
        bl.addWidget(self._chat_utility_w)

        def _toggle_adv_content():
            vis = not adv_content_w.isVisible()
            adv_content_w.setVisible(vis)
            adv_toggle_btn.setText("▾  Piilota lisäasetukset" if vis else "▸  Lisäasetukset")

        adv_toggle_btn.clicked.connect(_toggle_adv_content)

        def _do_cleanup():
            cleanup_btn.setEnabled(False)
            cleanup_btn.setText("Siivotaan…")
            import queue as _qc
            rqc = _qc.Queue()

            def _cbc(msg):
                rqc.put(msg)

            def _pollc():
                try:
                    msg = rqc.get_nowait()
                except Exception:
                    return
                _ptmrc.stop()
                self._chat_result_lbl.setText(msg)
                self._chat_result_lbl.setStyleSheet(
                    f"color: {'#00ff88' if '✅' in msg else '#ff2e4d'};"
                    " font-size: 12px; background: transparent;"
                )
                cleanup_btn.setEnabled(True)
                cleanup_btn.setText("Siivoa turhat virtuaalilaitteet")

            _ptmrc = QTimer(self)
            _ptmrc.timeout.connect(_pollc)
            _ptmrc.start(200)
            threading.Thread(
                target=_disable_unused_voicemeeter_endpoints, args=(_cbc,), daemon=True
            ).start()

        cleanup_btn.clicked.connect(_do_cleanup)

        def _do_manual_mic():
            manual_mic_btn.setEnabled(False)
            manual_mic_btn.setText("Asetetaan…")
            import queue as _qm
            rqm = _qm.Queue()

            def _bgm():
                _, msg = _set_windows_default_recording("Voicemeeter Out B1")
                rqm.put(msg)

            def _pollm():
                try:
                    msg = rqm.get_nowait()
                except Exception:
                    return
                _ptmrm.stop()
                self._chat_result_lbl.setText(msg)
                manual_mic_btn.setEnabled(True)
                manual_mic_btn.setText("Aseta Windows-mikrofoni manuaalisesti")

            _ptmrm = QTimer(self)
            _ptmrm.timeout.connect(_pollm)
            _ptmrm.start(200)
            threading.Thread(target=_bgm, daemon=True).start()

        manual_mic_btn.clicked.connect(_do_manual_mic)

        # -- pääpainike: asenna (jos tarpeen) + konfiguroi + testaa, kaikki yhdessä --

        def _auto_detect_mixer_input_name():
            # list_input_devices() (_best_audio_devices) deduplikoi saman fyysisen
            # laitteen useista ajurirajapinnoista ja pitää PARHAAN (täyden, ei-
            # katkaistun) nimen — raaka sd.query_devices() voi palauttaa MME:n
            # katkaiseman ~31 merkin version ensin, jota Voicemeeter ei tunnista
            # omassa laitehaussaan (näkyy punaisena "no device" -tilana Hardware
            # Input 1 -stripissä vaikka mikki toimii muualla appissa).
            try:
                names = [n for _, n in list_input_devices()]
            except Exception:
                return None
            for keywords in (("chat",), ("mix minus", "mix-minus"), ("rodecaster", "rode caster")):
                for n in names:
                    if any(k in n.lower() for k in keywords):
                        return n
            return None

        def _do_configure_all():
            self._chat_run_started = True
            self._chat_cfg_btn.setEnabled(False)
            self._chat_cfg_btn.setText("Määritetään...")
            self._chat_manual_row.setVisible(False)
            self._chat_reboot_btn.setVisible(False)
            self._chat_details_w.setVisible(False)
            self._chat_details_toggle_btn.setVisible(False)
            self._chat_details_toggle_btn.setText("▸  Näytä tekniset tiedot")
            self._chat_verdict_lbl.setText("⏳  Määritetään...")
            self._chat_verdict_lbl.setStyleSheet(
                "color: #8a9bc4; font-size: 14px; font-weight: bold; background: transparent;"
            )
            self._chat_result_lbl.setText("")
            import queue as _q
            rq = _q.Queue()
            log_lines = []

            def _cb(msg):
                rq.put(("progress", msg))

            def _bg():
                try:
                    if self._svc_mixer:
                        if not _is_voicemeeter_installed():
                            _cb("Asennetaan Voicemeeter Banana...")
                            _install_voicemeeter(_cb)
                            if not _is_voicemeeter_installed():
                                rq.put(("need_reboot", None))
                                return
                        mic_name = (
                            self._chat_dev_combo.currentText()
                            if self._chat_manual_row.isVisible() and self._chat_dev_combo.count()
                            else _auto_detect_mixer_input_name()
                        )
                        if not mic_name:
                            rq.put(("need_manual", None))
                            return
                        _cb(f"Konfiguroidaan reititystä laitteelle: {mic_name}")
                        _ensure_voicemeeter_running()
                        cfg_lines = []
                        _voicemeeter_configure(mic_name, lambda m: cfg_lines.append(m))
                        cfg_msg = cfg_lines[-1] if cfg_lines else "Ei vastausta"
                        ok = "✅" in cfg_msg
                        _cb(cfg_msg)
                        if ok:
                            _, win_msg = _set_windows_default_recording("Voicemeeter Out B1")
                            if win_msg:
                                _cb(win_msg)
                            test_msg, test_ok = _check_voicemeeter_routing()
                            _cb(test_msg)
                            ok = ok and test_ok
                        rq.put(("done", ok))
                    else:
                        if not _is_vbcable_installed():
                            _cb("Asennetaan VB-Cable...")
                            _install_vbcable(_cb)
                        ok = _is_vbcable_installed()
                        if ok:
                            _cb(
                                "✅ VB-Cable asennettu. Voice Royalen ääni ohjataan kaapeliin "
                                "automaattisesti — valitse Discordissa/pelissä mikrofoniksi "
                                "'CABLE Output'."
                            )
                        rq.put(("done", ok))
                except Exception as exc:
                    _cb(f"Virhe: {exc}")
                    rq.put(("done", False))

            def _poll():
                final = None
                while True:
                    try:
                        kind, payload = rq.get_nowait()
                    except Exception:
                        break
                    if kind == "progress":
                        log_lines.append(payload)
                        self._chat_result_lbl.setText("\n".join(log_lines))
                    else:
                        final = (kind, payload)
                if final is None:
                    return
                _ptmr.stop()
                self._chat_cfg_btn.setEnabled(True)
                self._chat_result_lbl.setText("\n".join(log_lines))
                # Tekniset tiedot -linkki tulee näkyviin heti kun on jotain näytettävää,
                # mutta pysyy PIILOSSA ellei tulos vaadi käyttäjän huomiota (ks. alla) —
                # onnistuessa käyttäjän ei tarvitse lukea teknistä lokia ollenkaan.
                self._chat_details_toggle_btn.setVisible(bool(log_lines))
                # Ajo on nyt LOPPUNUT (onnistuipa se tai ei) — vapauta "Seuraava"-gate.
                self._chat_run_finished = True
                self._update_dev_next_gate()
                kind, payload = final
                if kind == "need_reboot":
                    self._chat_verdict_lbl.setText(
                        "🔄  Asennus vaatii uudelleenkäynnistyksen ennen jatkoa."
                    )
                    self._chat_verdict_lbl.setStyleSheet(
                        "color: #ffb830; font-size: 14px; font-weight: bold; background: transparent;"
                    )
                    self._chat_cfg_btn.setText("🔧  Yritä uudelleen")
                    self._chat_cfg_btn.setStyleSheet(self._BTN_PRIMARY)
                    self._chat_reboot_btn.setVisible(True)
                    self._chat_details_w.setVisible(True)
                    self._chat_details_toggle_btn.setText("▾  Piilota tekniset tiedot")
                elif kind == "need_manual":
                    self._chat_verdict_lbl.setText(
                        "⚠️  Emme tunnistaneet mikseriäsi automaattisesti — valitse laite alta."
                    )
                    self._chat_verdict_lbl.setStyleSheet(
                        "color: #ffb830; font-size: 14px; font-weight: bold; background: transparent;"
                    )
                    self._chat_cfg_btn.setText("🔧  Yritä uudelleen")
                    self._chat_cfg_btn.setStyleSheet(self._BTN_PRIMARY)
                    _refresh_chat_dev_combo()
                    self._chat_manual_row.setVisible(True)
                elif kind == "done":
                    ok = payload
                    if ok:
                        self._chat_verdict_lbl.setText("✅  Reititys toimii — kaikki valmista.")
                        self._chat_cfg_btn.setText("🔧  Määritä uudelleen")
                        self._chat_cfg_btn.setStyleSheet(self._BTN_SEC)
                    else:
                        self._chat_verdict_lbl.setText(
                            "❌  Jokin meni pieleen — katso tekniset tiedot alta tai yritä uudelleen."
                        )
                        self._chat_cfg_btn.setText("🔧  Yritä uudelleen")
                        self._chat_cfg_btn.setStyleSheet(self._BTN_PRIMARY)
                        self._chat_details_w.setVisible(True)
                        self._chat_details_toggle_btn.setText("▾  Piilota tekniset tiedot")
                    self._chat_verdict_lbl.setStyleSheet(
                        f"color: {'#00ff88' if ok else '#ff2e4d'};"
                        " font-size: 14px; font-weight: bold; background: transparent;"
                    )

            _ptmr = QTimer(self)
            _ptmr.timeout.connect(_poll)
            _ptmr.start(100)
            threading.Thread(target=_bg, daemon=True).start()

        self._chat_cfg_btn.clicked.connect(_do_configure_all)

        self._refresh_chat_routing_page()
        return sec

    def _update_dev_next_gate(self):
        """Laitteet-sivun "Seuraava" aukeaa vasta kun 1) mikki on valittu JA 2) chat-
        reititys on ajettu kertaalleen loppuun (jos osio on tarpeen tällä polulla) —
        muuten reitityksen voisi ohittaa koskematta eikä käyttäjä koskaan saisi
        tietää ettei se toimi."""
        if not hasattr(self, "_dev_next_btn"):
            return
        routing_needed = (
            sys.platform == "win32"
            and (self._svc_mixer or self._svc_routing == "gaming")
        )
        ok = bool(getattr(self, "_dev_mic_ok", False) or self._dev_selected_input is not None)
        if routing_needed and not getattr(self, "_chat_run_finished", False):
            ok = False
        self._dev_next_btn.setEnabled(ok)

    def _refresh_chat_routing_page(self):
        """Päivittää chat-reititys-sivun selitystekstin, tilaviestin ja työkalurivin näkyvyyden
        senhetkisen _svc_mixer/_svc_routing-valinnan mukaan. Sivu rakennetaan vain kerran
        _build_ui():ssä, mutta käyttäjä voi vaihtaa mikseri/pelit-valintaansa sivulla 1 sen
        JÄLKEEN — ilman tätä päivitystä sivu näyttäisi pysyvästi ensimmäisellä rakennuskerralla
        vallinneen (oletusarvoisen) tilan."""
        if not hasattr(self, "_chat_why_lbl") or sys.platform != "win32":
            return
        mixer_name = self._detected_mixer_name() if self._svc_mixer else None
        if self._svc_mixer:
            _dev_line = (f"Havaitsimme laitteesi: {mixer_name}.\n\n" if mixer_name else "")
            why_text = (
                _dev_line
                + "Mitä \"Määritä automaattisesti\" tekee tällä koneella (Voicemeeter Banana\n"
                "asennettiin jo edellisellä sivulla — tässä tehdään vain määritykset):\n"
                "  1.  Asettaa Voicemeeterin reitityksen: mikserisi Chat-mikki ja Voice Royalen\n"
                "       käännösääni yhdistetään samaan B1-virtuaalikanavaan.\n"
                "  2.  Vaihtaa Windowsin OLETUSMIKROFONIKSI \"Voicemeeter Out B1\"\n"
                "       (Ääniasetukset → Tallennus) — Discord ja pelit alkavat käyttää sitä\n"
                "       automaattisesti, ja muut kuulevat sekä oman äänesi että käännökset.\n"
                "  3.  Kaiuttimiin/oletustoistolaitteeseen EI kosketa.\n"
                "  4.  Testaa lopuksi että reititys oikeasti toimii."
            )
        else:
            why_text = (
                "Mitä \"Määritä automaattisesti\" tekee tällä koneella (VB-Cable asennettiin\n"
                "jo edellisellä sivulla — tässä tehdään vain määritykset):\n"
                "  1.  Varmistaa että VB-Cable-virtuaalikaapeli toimii.\n"
                "  2.  Voice Royalen käännösääni ohjataan kaapeliin automaattisesti — valitse\n"
                "       Discordissa/pelissä mikrofoniksi \"CABLE Output\", niin muut kuulevat\n"
                "       käännöksesi.\n"
                "  3.  Windowsin oletuslaitteisiin EI kosketa."
            )
        self._chat_why_lbl.setText(why_text)
        # Verdict/nappitila päivitetään vain ENNEN ensimmäistä "Määritä automaattisesti" -ajoa
        # tällä sivukäynnillä — muuten palaaminen sivulle esim. takaisin-napilla ylikirjoittaisi
        # juuri saadun tuloksen ("✅ Reititys toimii") takaisin geneeriseksi alkutilaksi.
        if not getattr(self, "_chat_run_started", False):
            already_ok = (
                _is_voicemeeter_installed() if self._svc_mixer else _is_vbcable_installed()
            )
            self._chat_verdict_lbl.setText(
                "✅  Jo asennettu — paina silti varmistaaksesi että reititys toimii."
                if already_ok else
                "Ei vielä asennettu — paina alta, hoidamme asennuksen, määrityksen ja testauksen."
            )
            self._chat_verdict_lbl.setStyleSheet(
                "color: #8a9bc4; font-size: 14px; font-weight: bold; background: transparent;"
            )
        if hasattr(self, "_chat_utility_w"):
            self._chat_utility_w.setVisible(self._svc_mixer)
        # Koko osio näkyy vain jos polku tarvitsee chat-reititystä (mikseri tai pelit/Discord)
        if hasattr(self, "_chat_section_w"):
            self._chat_section_w.setVisible(
                bool(self._svc_mixer or self._svc_routing == "gaming")
            )

    def _page_devices(self):
        """Mikrofoni + kaiuttimet, progressive disclosure -periaatteella: oletusnäkymä näyttää
        vain automaattisen tunnistuksen tuloksen ja yhden testinapin, koko laitelista/lisäasetukset
        avautuvat vain jos käyttäjä itse haluaa tarkistaa/vaihtaa laitteen."""
        page = QWidget()
        page.setStyleSheet("background: #05070f;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Mikrofoni ja kaiuttimet",
            "Puhu mikrofoniisi — tunnistamme sen automaattisesti."
        ))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #05070f; }")
        body = QWidget()
        body.setStyleSheet("background: #05070f;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 16, 28, 12)
        bl.setSpacing(10)

        # ── Mikrofoni: iso tilakortti + AINA näkyvä äänitasomittari + piilotettu tarkka lista ──
        # Aiempi versio piilotti KOKO laitelistan (ja sen ainoat äänitasopalkit) oletuksena, jolloin
        # käyttäjä ei nähnyt MITÄÄN todistetta siitä että sovellus ylipäätään kuulee mitään —
        # "ei toimi vaikka puhun mikkiin" -ilmoitus tästä. Yhdistetty mittari on AINA näkyvissä
        # heti kortin alla, joten puhuminen näkyy visuaalisesti vaikka tunnistus ei vielä osuisi.
        self._dev_input_status_lbl = QLabel("🎤  Puhu mikrofoniisi...")
        self._dev_input_status_lbl.setWordWrap(True)
        self._dev_input_status_lbl.setStyleSheet(
            "color: #dce6ff; font-size: 15px; font-weight: bold; background: #0a0f1e;"
            " border: 1px solid #1c2c52; border-radius: 8px; padding: 16px;"
        )
        bl.addWidget(self._dev_input_status_lbl)

        self._dev_combined_bar = QProgressBar()
        self._dev_combined_bar.setRange(0, 1000)
        self._dev_combined_bar.setValue(0)
        self._dev_combined_bar.setTextVisible(False)
        self._dev_combined_bar.setFixedHeight(10)
        self._dev_combined_bar.setStyleSheet(self._BAR_IDLE)
        bl.addWidget(self._dev_combined_bar)

        mic_toggle_btn = QPushButton("▸  Väärä laite? Näytä kaikki mikrofonit")
        mic_toggle_btn.setFlat(True)
        mic_toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #6aa8ff;"
            " font-size: 11px; text-align: left; padding: 2px 0; }"
            "QPushButton:hover { color: #6aa8ff; }"
        )
        bl.addWidget(mic_toggle_btn)

        mic_list_w = QWidget()
        mic_list_w.setVisible(False)
        mic_list_bl = QVBoxLayout(mic_list_w)
        mic_list_bl.setContentsMargins(0, 4, 0, 0)
        mic_list_bl.setSpacing(6)

        in_scroll = QScrollArea()
        in_scroll.setWidgetResizable(True)
        in_scroll.setFixedHeight(150)
        in_scroll.setStyleSheet(
            "QScrollArea { background: #0a0f1e; border: 1px solid #1c2c52; border-radius: 6px; }"
        )
        in_cnt = QWidget()
        in_cnt.setStyleSheet("background: #0a0f1e;")
        self._dev_bars_layout = QVBoxLayout(in_cnt)
        self._dev_bars_layout.setContentsMargins(10, 8, 10, 8)
        self._dev_bars_layout.setSpacing(6)

        # Suodatus: järjestelmähälyt + Windowsissa disabloidut laitteet + virtuaali-
        # kaapelit (Voicemeeter/VB-Cable ym.) pois — tällä sivulla valitaan OMA mikki,
        # virtuaalilaitteet eivät koskaan ole oikea valinta tähän ja vain sekoittavat.
        _disabled_names = _windows_disabled_audio_names()
        _VIRTUAL_KW = ("voicemeeter", "vb-audio", "cable", "voicemod", "virtual")
        self._dev_input_devices = [
            (idx, name) for idx, name in list_input_devices()
            if not name.startswith("{")
            and name.lower().strip() not in ("input ()", "output ()")
            and not any(
                k in name.lower()
                for k in ["microsoft sound mapper", "primary sound capture", "bthhfenum"]
            )
            and not any(k in name.lower() for k in _VIRTUAL_KW)
            and not _matches_disabled_name(name, _disabled_names)
        ]

        _def_in = -1
        try:
            _dn = sd.query_devices(kind="input")["name"].lower().strip()
            for _i, _n in self._dev_input_devices:
                if _n.lower().strip() == _dn:
                    _def_in = _i
                    break
            if _def_in == -1:
                for _i, _n in self._dev_input_devices:
                    _nl = _n.lower().strip()
                    cmp = min(len(_dn), len(_nl))
                    if cmp >= 16 and _dn[:cmp] == _nl[:cmp]:
                        _def_in = _i
                        break
        except Exception:
            pass

        # RodeCaster Pro II: a dedicated "...Chat..." channel is almost always
        # the correct mic for this app's purpose (pre-mixed chat feed) — prefer
        # it over whatever Windows happens to have as its system default device.
        for _i, _n in self._dev_input_devices:
            _nl = _n.lower()
            if "rode" in _nl and "chat" in _nl:
                _def_in = _i
                break

        self._dev_level_bars = {}
        self._dev_level_peak = {}
        self._dev_sustained = {}
        self._dev_row_widgets = {}
        self._dev_status_labels = {}

        for idx, name in self._dev_input_devices:
            row = QWidget()
            row.setStyleSheet("background: transparent; border-radius: 4px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(6, 3, 6, 3)
            rl.setSpacing(8)
            is_v = any(k in name.lower() for k in ["virtual", "vb-audio", "voicemeeter", "cable"])
            icon = "🔌" if is_v else "🎤"
            display = f"{icon} {name[:36]}{'…' if len(name) > 36 else ''}"
            nl = QLabel(display)
            nl.setFixedWidth(210)
            nl.setStyleSheet("color: #b9c5e6; font-size: 11px;")
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(12)
            bar.setStyleSheet(self._BAR_IDLE)
            is_def = (idx == _def_in)
            st_lbl = QLabel("★ Oletus" if is_def else "")
            st_lbl.setFixedWidth(68)
            st_lbl.setStyleSheet(
                "color: #ffb830; font-size: 10px;" if is_def
                else "color: #546a94; font-size: 10px;"
            )
            sel_btn = QPushButton("Valitse")
            sel_btn.setFixedWidth(60)
            sel_btn.setFixedHeight(24)
            sel_btn.setStyleSheet(
                "QPushButton { background: #101a36; color: #8a9bc4; border: 1px solid #1c2c52;"
                " border-radius: 4px; font-size: 10px; }"
                "QPushButton:hover { background: #1c2c52; color: #dce6ff; }"
            )
            sel_btn.clicked.connect(lambda _, i=idx: self._dev_select_input(i, auto=False))
            rl.addWidget(nl)
            rl.addWidget(bar, 1)
            rl.addWidget(st_lbl)
            rl.addWidget(sel_btn)
            self._dev_level_bars[idx] = bar
            self._dev_level_peak[idx] = 0.0
            self._dev_sustained[idx] = 0
            self._dev_row_widgets[idx] = row
            self._dev_status_labels[idx] = st_lbl
            self._dev_bars_layout.addWidget(row)

        if not self._dev_input_devices:
            self._dev_bars_layout.addWidget(QLabel("Ei äänitulolaitteita löytynyt"))
        self._dev_bars_layout.addStretch()
        in_scroll.setWidget(in_cnt)
        mic_list_bl.addWidget(in_scroll)
        bl.addWidget(mic_list_w)

        def _toggle_mic_list():
            vis = not mic_list_w.isVisible()
            mic_list_w.setVisible(vis)
            mic_toggle_btn.setText(
                "▾  Piilota mikrofonilista" if vis
                else "▸  Väärä laite? Näytä kaikki mikrofonit"
            )

        mic_toggle_btn.clicked.connect(_toggle_mic_list)
        # Referenssit talteen, jotta _update_dev_levels() voi avata listan automaattisesti
        # jos mikään laite ei ole reagoinut muutamassa sekunnissa (ks. alla _dev_no_speech_ticks).
        self._dev_mic_list_w = mic_list_w
        self._dev_mic_toggle_btn = mic_toggle_btn

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #101a36;")
        bl.addWidget(sep)

        # ── Chat-reititys — ennen ääntestiä (aiemmin oma sivu) ──
        if sys.platform == "win32":
            self._chat_section_w = self._build_chat_routing_section()
            bl.addWidget(self._chat_section_w)
            sep_cr = QFrame()
            sep_cr.setFrameShape(QFrame.Shape.HLine)
            sep_cr.setStyleSheet("color: #101a36;")
            bl.addWidget(sep_cr)

        # ── Kaiuttimet: oletuslaite + testi, muut laitteet piilotettuna ──
        # Sama suodatus kuin mikeille: disabloidut + virtuaalikaapelit pois —
        # kuuntelulaitteeksi valitaan oma kuuloke/kaiutin, ei koskaan virtuaalikaapelia.
        _raw_out = [
            (idx, name) for idx, name in list_output_devices()
            if not name.startswith("{")
            and name.lower().strip() not in ("input ()", "output ()")
            and not any(
                k in name.lower() for k in ["primary sound", "microsoft sound"]
            )
            and not any(k in name.lower() for k in _VIRTUAL_KW)
            and not _matches_disabled_name(name, _disabled_names)
        ]
        _def_out = -1
        try:
            _dn2 = sd.query_devices(kind="output")["name"].lower().strip()
            for _i, _n in _raw_out:
                if _n.lower().strip() == _dn2:
                    _def_out = _i
                    break
            if _def_out == -1:
                for _i, _n in _raw_out:
                    _nl = _n.lower().strip()
                    cmp = min(len(_dn2), len(_nl))
                    if cmp >= 16 and _dn2[:cmp] == _nl[:cmp]:
                        _def_out = _i
                        break
        except Exception:
            pass

        # RodeCaster Pro II: kuuntelun oletus on Main Stereo -ulostulo (kuulokkeet/
        # kaiuttimet) — EI Chat-kanava, joka on mikkisyöte peliin/Discordiin päin.
        for _i, _n in _raw_out:
            _nl = _n.lower()
            if "rode" in _nl and "main" in _nl:
                _def_out = _i
                break

        self._dev_output_devices = sorted(
            _raw_out, key=lambda x: 0 if x[0] == _def_out else 1
        )
        self._dev_default_out = _def_out

        out_hdr = QLabel("Kaiuttimet / kuulokkeet")
        out_hdr.setStyleSheet(
            "color: #dce6ff; font-size: 13px; font-weight: bold; background: transparent;"
        )
        bl.addWidget(out_hdr)

        _def_out_name = next((n for i, n in self._dev_output_devices if i == _def_out), "")
        out_row = QHBoxLayout()
        out_default_lbl = QLabel(f"🔊  {_def_out_name or 'Ei oletuslaitetta löytynyt'}")
        out_default_lbl.setStyleSheet("color: #b9c5e6; font-size: 12px; background: transparent;")
        out_default_lbl.setWordWrap(True)
        out_row.addWidget(out_default_lbl, 1)
        bl.addLayout(out_row)

        out_toggle_btn = QPushButton("▸  Vaihda laite")
        out_toggle_btn.setFlat(True)
        out_toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #6aa8ff;"
            " font-size: 11px; text-align: left; padding: 2px 0; }"
            "QPushButton:hover { color: #6aa8ff; }"
        )
        bl.addWidget(out_toggle_btn)

        out_list_w = QWidget()
        out_list_w.setVisible(False)
        out_list_bl = QVBoxLayout(out_list_w)
        out_list_bl.setContentsMargins(0, 4, 0, 0)

        out_scroll = QScrollArea()
        out_scroll.setWidgetResizable(True)
        out_scroll.setFixedHeight(130)
        out_scroll.setStyleSheet(
            "QScrollArea { background: #0a0f1e; border: 1px solid #1c2c52; border-radius: 6px; }"
        )
        out_cnt = QWidget()
        out_cnt.setStyleSheet("background: #0a0f1e;")
        out_lay = QVBoxLayout(out_cnt)
        out_lay.setContentsMargins(10, 8, 10, 8)
        out_lay.setSpacing(5)

        self._dev_out_checkboxes = {}
        for idx, name in self._dev_output_devices:
            r = QWidget()
            r.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(r)
            rl.setContentsMargins(4, 2, 4, 2)
            rl.setSpacing(8)
            is_cable_in = "cable input" in name.lower() or (
                "cable" in name.lower() and "output" not in name.lower()
                and "voicemeeter" not in name.lower()
            )
            is_v = any(k in name.lower() for k in ["virtual", "vb-audio", "voicemeeter", "cable"])
            icon = "🔌" if is_v else "🔊"
            is_def = (idx == _def_out)
            display_name = name[:38] + ("…" if len(name) > 38 else "")
            if is_cable_in:
                display_name += " [→ peliin]"
            cb = QCheckBox(f"{icon} {display_name}")
            cb.setChecked(is_def)
            cb.setStyleSheet(
                "QCheckBox { color: #b9c5e6; font-size: 11px; padding: 2px; background: transparent; }"
            )
            def_lbl = QLabel("★ Oletus" if is_def else "")
            def_lbl.setFixedWidth(60)
            def_lbl.setStyleSheet("color: #ffb830; font-size: 10px; background: transparent;")
            bp = QPushButton("▶ Beep")
            bp.setFixedWidth(68)
            bp.setFixedHeight(26)
            bp.setStyleSheet(
                "QPushButton { background: #101a36; color: #8a9bc4; border: 1px solid #1c2c52;"
                " border-radius: 4px; font-size: 11px; }"
                "QPushButton:hover { background: #1c2c52; color: #dce6ff; }"
                "QPushButton:disabled { color: #1c2c52; }"
            )
            bp.clicked.connect(lambda _, i=idx, b=bp: self._dev_test_output(i, b))
            rl.addWidget(cb, 1)
            rl.addWidget(def_lbl)
            rl.addWidget(bp)
            self._dev_out_checkboxes[idx] = cb
            out_lay.addWidget(r)

        if not self._dev_output_devices:
            out_lay.addWidget(QLabel("Ei äänilähtölaitteita löytynyt"))
        out_lay.addStretch()
        out_scroll.setWidget(out_cnt)
        out_list_bl.addWidget(out_scroll)
        bl.addWidget(out_list_w)

        def _toggle_out_list():
            vis = not out_list_w.isVisible()
            out_list_w.setVisible(vis)
            out_toggle_btn.setText(
                "▾  Piilota laitelista" if vis
                else "▸  Vaihda laite"
            )

        out_toggle_btn.clicked.connect(_toggle_out_list)

        self._dev_out_status_lbl = QLabel("")
        self._dev_out_status_lbl.setStyleSheet(
            "color: #8a9bc4; font-size: 11px; background: transparent;"
        )
        bl.addWidget(self._dev_out_status_lbl)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #101a36;")
        bl.addWidget(sep2)

        # ── Yhdistetty ääntesti (TTS + soundboard yhdellä napilla) ──────
        test_hdr = QLabel("Testaa ääni")
        test_hdr.setStyleSheet(
            "color: #dce6ff; font-size: 13px; font-weight: bold; background: transparent;"
        )
        bl.addWidget(test_hdr)
        test_hint = QLabel("Kuuletko käännösäänen ja soundboard-piippauksen kaiuttimistasi?")
        test_hint.setStyleSheet("color: #8a9bc4; font-size: 11px; background: transparent;")
        bl.addWidget(test_hint)
        sound_test_btn = QPushButton("🔊  Testaa ääni")
        sound_test_btn.setFixedHeight(36)
        sound_test_btn.setStyleSheet(self._BTN_SEC)
        sound_result = QLabel("")
        sound_result.setWordWrap(True)
        sound_result.setStyleSheet("color: #8a9bc4; font-size: 11px; background: transparent;")
        bl.addWidget(sound_test_btn)
        bl.addWidget(sound_result)

        def _do_sound_test():
            import shutil as _shutil2
            selected_out = [idx for idx, cb in self._dev_out_checkboxes.items() if cb.isChecked()]
            sound_test_btn.setEnabled(False)
            sound_test_btn.setText("Testataan...")
            sound_result.setText("")
            import queue as _q_snd
            rq = _q_snd.Queue()

            def _bg():
                results = []
                if not _shutil2.which("ffmpeg"):
                    results.append(
                        "⚠️ TTS: ffmpeg puuttuu (Asetukset → Asennukset → ffmpeg)"
                    )
                else:
                    try:
                        import asyncio
                        wav = asyncio.run(
                            request_edge_tts_wav("Voice Royale on valmis. Testi onnistui.", "Finnish")
                        )
                        play_wav_bytes(wav, device_indices=selected_out if selected_out else None)
                        results.append("✅ TTS toimii")
                    except Exception as exc:
                        results.append(f"⚠️ TTS-virhe: {exc}")
                try:
                    target = selected_out[0] if selected_out else None
                    info = (
                        sd.query_devices(target) if target is not None
                        else sd.query_devices(kind="output")
                    )
                    sr = int(info.get("default_samplerate", 48000))
                    ch = max(1, min(2, int(info.get("max_output_channels", 2))))
                    t = np.linspace(0, 0.7, int(sr * 0.7), endpoint=False)
                    mono = (np.sin(2 * np.pi * 660.0 * t) * 0.45).astype("float32")
                    tone = np.column_stack([mono] * ch) if ch > 1 else mono.reshape(-1, 1)
                    sd.play(tone, samplerate=sr, device=target, blocking=True)
                    results.append("✅ Soundboard toimii")
                except Exception as exc:
                    results.append(f"⚠️ Soundboard-virhe: {exc}")
                ok = all(r.startswith("✅") for r in results)
                rq.put((ok, " · ".join(results)))

            def _poll():
                try:
                    ok, msg = rq.get_nowait()
                except Exception:
                    return
                _ptmr.stop()
                try:
                    self._dev_active_poll_timers.remove(_ptmr)
                except ValueError:
                    pass
                sound_test_btn.setEnabled(True)
                sound_test_btn.setText("🔊  Testaa ääni")
                sound_result.setText(msg)
                sound_result.setStyleSheet(
                    f"color: {'#00ff88' if ok else '#ffb830'}; font-size: 11px; background: transparent;"
                )

            _ptmr = QTimer(self)
            _ptmr.timeout.connect(_poll)
            _ptmr.start(100)
            self._dev_active_poll_timers.append(_ptmr)
            threading.Thread(target=_bg, daemon=True).start()

        sound_test_btn.clicked.connect(_do_sound_test)

        bl.addStretch()

        nav = QHBoxLayout()
        nav.addWidget(self._back_btn())
        nav.addStretch()
        self._dev_next_btn = QPushButton("Seuraava  →")
        self._dev_next_btn.setFixedHeight(42)
        self._dev_next_btn.setMinimumWidth(140)
        self._dev_next_btn.setStyleSheet(self._BTN_PRIMARY)
        self._dev_next_btn.setEnabled(False)
        self._dev_next_btn.clicked.connect(self._nav_next)
        nav.addWidget(self._dev_next_btn)
        bl.addLayout(nav)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)
        return page

    def _page_final_test(self):
        """Viimeistelysivu. Mikrofoni-, TTS- ja soundboard-testit tehdään jo devices-sivulla
        (samalla sivulla missä laitteet valitaan) — ei toisteta niitä enää tässä."""
        page = QWidget()
        page.setStyleSheet("background: #05070f;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Valmis!",
            "Asennus on valmis."
        ))
        body = QWidget()
        body.setStyleSheet("background: #05070f;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 24, 32, 20)
        bl.setSpacing(14)

        summary = QLabel(
            "Perusasennus on valmis — mikrofoni, kaiuttimet ja chat-reititys on määritetty.\n"
            "Voit muuttaa mitä tahansa myöhemmin Asetukset-ikkunasta."
        )
        summary.setStyleSheet(
            "color: #b9c5e6; font-size: 14px; background: transparent; line-height: 1.6;"
        )
        summary.setWordWrap(True)
        bl.addWidget(summary)

        # ── Stream Deck -osio (näkyy vain jos valittu sivulla 2) ──
        self._fin_sd_w = QWidget()
        self._fin_sd_w.setVisible(False)
        self._fin_sd_w.setStyleSheet(
            "QWidget { background: #0a0f1e; border: 1px solid #1c2c52; border-radius: 8px; }"
        )
        _sd_bl = QVBoxLayout(self._fin_sd_w)
        _sd_bl.setContentsMargins(16, 12, 16, 14)
        _sd_bl.setSpacing(6)
        _sd_hdr = QLabel("🎛️  Stream Deck")
        _sd_hdr.setStyleSheet(
            "color: #dce6ff; font-size: 13px; font-weight: bold; background: transparent; border: none;"
        )
        _sd_bl.addWidget(_sd_hdr)
        self._fin_sd_status = QLabel()
        self._fin_sd_status.setStyleSheet(
            "color: #b9c5e6; font-size: 12px; background: transparent; border: none;"
        )
        _sd_bl.addWidget(self._fin_sd_status)
        _sd_steps = QLabel(
            "1.  Varmista että Elgato Stream Deck -ohjelmisto on asennettu.\n"
            "2.  Paina alla olevaa nappia — plugin asentuu itsestään.\n"
            "3.  Vedä Voice Royale -toiminnot haluamillesi napeille.\n"
            "Napit päivittyvät automaattisesti kun Voice Royale on käynnissä."
        )
        _sd_steps.setStyleSheet(
            "color: #8a9bc4; font-size: 11px; background: transparent; border: none; line-height: 150%;"
        )
        _sd_steps.setWordWrap(True)
        _sd_bl.addWidget(_sd_steps)

        _sd_open_btn = QPushButton("📂  Asenna Stream Deck -plugin")
        _sd_open_btn.setFixedHeight(32)
        _sd_open_btn.setStyleSheet(self._BTN_SEC)

        def _open_sd_plugin():
            cands = []
            if getattr(sys, "frozen", False):
                cands.append(os.path.join(
                    os.path.dirname(sys.executable), "StreamDeck",
                    "com.voiceroyale.streamDeckPlugin"))
            cands.append(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "streamdeck-plugin",
                "com.voiceroyale.streamDeckPlugin"))
            for _p in cands:
                if os.path.exists(_p):
                    try:
                        os.startfile(_p)
                        self._fin_sd_status.setText(
                            "✅ Plugin-tiedosto avattu — Stream Deck -ohjelmisto viimeistelee asennuksen."
                        )
                    except Exception as e:
                        self._fin_sd_status.setText(f"❌ Avaus epäonnistui: {e}")
                    return
            self._fin_sd_status.setText(
                "❌ Plugin-tiedostoa ei löytynyt — asenna se Asetukset → Stream Deck -välilehdeltä."
            )

        _sd_open_btn.clicked.connect(_open_sd_plugin)
        _sd_bl.addWidget(_sd_open_btn)
        bl.addWidget(self._fin_sd_w)

        # ── Home Assistant -osio (näkyy vain jos valittu sivulla 2) ──
        self._fin_ha_w = QWidget()
        self._fin_ha_w.setVisible(False)
        self._fin_ha_w.setStyleSheet(
            "QWidget { background: #0a0f1e; border: 1px solid #1c2c52; border-radius: 8px; }"
        )
        _ha_bl = QVBoxLayout(self._fin_ha_w)
        _ha_bl.setContentsMargins(16, 12, 16, 14)
        _ha_bl.setSpacing(6)
        _ha_hdr = QLabel("🏠  Home Assistant")
        _ha_hdr.setStyleSheet(
            "color: #dce6ff; font-size: 13px; font-weight: bold; background: transparent; border: none;"
        )
        _ha_bl.addWidget(_ha_hdr)
        _ha_url_row = QHBoxLayout()
        _ha_url_lbl = QLabel("HA-osoite:")
        _ha_url_lbl.setFixedWidth(110)
        _ha_url_lbl.setStyleSheet("color: #8a9bc4; font-size: 12px; background: transparent; border: none;")
        self._fin_ha_url_edit = QLineEdit(load_settings().get("ha_url", ""))
        self._fin_ha_url_edit.setPlaceholderText("http://homeassistant.local:8123")
        _ha_url_row.addWidget(_ha_url_lbl)
        _ha_url_row.addWidget(self._fin_ha_url_edit, 1)
        _ha_bl.addLayout(_ha_url_row)
        _ha_tok_row = QHBoxLayout()
        _ha_tok_lbl = QLabel("Token:")
        _ha_tok_lbl.setFixedWidth(110)
        _ha_tok_lbl.setStyleSheet("color: #8a9bc4; font-size: 12px; background: transparent; border: none;")
        self._fin_ha_token_edit = QLineEdit(load_settings().get("ha_token", ""))
        self._fin_ha_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._fin_ha_token_edit.setPlaceholderText("Long-lived access token (HA: Profiili → Turvallisuus)")
        _ha_tok_row.addWidget(_ha_tok_lbl)
        _ha_tok_row.addWidget(self._fin_ha_token_edit, 1)
        _ha_bl.addLayout(_ha_tok_row)
        _ha_test_row = QHBoxLayout()
        _ha_test_btn = QPushButton("🔌  Testaa yhteys")
        _ha_test_btn.setFixedHeight(30)
        _ha_test_btn.setFixedWidth(150)
        _ha_test_btn.setStyleSheet(self._BTN_SEC)
        self._fin_ha_test_lbl = QLabel("")
        self._fin_ha_test_lbl.setStyleSheet(
            "color: #8a9bc4; font-size: 12px; background: transparent; border: none;"
        )
        self._fin_ha_test_lbl.setWordWrap(True)
        _ha_test_row.addWidget(_ha_test_btn)
        _ha_test_row.addWidget(self._fin_ha_test_lbl, 1)
        _ha_bl.addLayout(_ha_test_row)

        def _test_ha_connection():
            url = self._fin_ha_url_edit.text().strip().rstrip("/")
            tok = self._fin_ha_token_edit.text().strip()
            if not url or not tok:
                self._fin_ha_test_lbl.setText("Täytä ensin osoite ja token.")
                self._fin_ha_test_lbl.setStyleSheet(
                    "color: #ffb830; font-size: 12px; background: transparent; border: none;")
                return
            _ha_test_btn.setEnabled(False)
            self._fin_ha_test_lbl.setText("Testataan…")
            self._fin_ha_test_lbl.setStyleSheet(
                "color: #8a9bc4; font-size: 12px; background: transparent; border: none;")
            import queue as _q
            _hq = _q.Queue()

            def _bg():
                try:
                    r = requests.get(
                        f"{url}/api/",
                        headers={"Authorization": f"Bearer {tok}"},
                        timeout=6,
                    )
                    if r.status_code == 200:
                        _hq.put((True, "✅ Yhteys toimii!"))
                    elif r.status_code == 401:
                        _hq.put((False, "❌ Token ei kelpaa (401) — tarkista long-lived token."))
                    else:
                        _hq.put((False, f"❌ HA vastasi koodilla {r.status_code}."))
                except Exception as e:
                    _hq.put((False, f"❌ Ei yhteyttä: {e}"))

            def _poll():
                try:
                    ok, msg = _hq.get_nowait()
                except Exception:
                    return
                _htmr.stop()
                _ha_test_btn.setEnabled(True)
                self._fin_ha_test_lbl.setText(msg)
                self._fin_ha_test_lbl.setStyleSheet(
                    f"color: {'#00ff88' if ok else '#ff2e4d'};"
                    " font-size: 12px; background: transparent; border: none;")

            _htmr = QTimer(self)
            _htmr.timeout.connect(_poll)
            _htmr.start(200)
            threading.Thread(target=_bg, daemon=True).start()

        _ha_test_btn.clicked.connect(_test_ha_connection)

        _ha_hint = QLabel(
            "Tallennetaan Valmis-napista. Laitteiden valinta soundboard-napeille tehdään "
            "Asetukset → Home Assistant -välilehdellä."
        )
        _ha_hint.setStyleSheet(
            "color: #8a9bc4; font-size: 11px; background: transparent; border: none;"
        )
        _ha_hint.setWordWrap(True)
        _ha_bl.addWidget(_ha_hint)
        bl.addWidget(self._fin_ha_w)

        bl.addStretch()

        nav = QHBoxLayout()
        nav.addWidget(self._back_btn())
        nav.addStretch()
        fin = QPushButton("Valmis  ✓")
        fin.setFixedHeight(42)
        fin.setMinimumWidth(140)
        fin.setStyleSheet(self._BTN_PRIMARY)
        fin.clicked.connect(self._finish_setup)
        nav.addWidget(fin)
        bl.addLayout(nav)
        lay.addWidget(body)
        return page

    def _refresh_finish_page(self):
        """Näyttää/piilottaa Valmis-sivun Stream Deck- ja Home Assistant -osiot sivun 2
        valintojen mukaan — valinnat voivat muuttua ennen tänne paluuta."""
        if not hasattr(self, "_fin_sd_w"):
            return
        sd_on = bool(getattr(self, "_svc_streamdeck", False))
        ha_on = bool(getattr(self, "_svc_ha", False))
        self._fin_sd_w.setVisible(sd_on)
        self._fin_ha_w.setVisible(ha_on)
        if sd_on:
            _port = StreamDeckHttpServer.PORT
            self._fin_sd_status.setText(
                f"Voice Royale kuuntelee Stream Deck -pluginia portissa localhost:{_port} "
                "aina kun appi on käynnissä."
            )

    # ── device monitoring ──────────────────────────────────────────────

    def _start_dev_monitoring(self):
        self._stop_dev_monitoring()
        self._dev_auto_selected = False
        self._dev_stream_opened = set()
        self._dev_no_speech_ticks = 0
        # RodeCaster Pro II "...Chat..." channel: select it immediately instead
        # of waiting ~6s for sustained audio level detection, and don't let any
        # other device's transient noise override it afterwards (_dev_select_input
        # sets _dev_auto_selected=True, which the level-based logic below respects).
        for _i, _n in self._dev_input_devices:
            _nl = _n.lower()
            if "rode" in _nl and "chat" in _nl:
                self._dev_select_input(_i, auto=True)
                break
        import queue as _q
        self._dev_level_queue = _q.Queue()
        _CONFIGS = [(1, 16000), (2, 48000), (1, 48000), (2, 44100), (1, 44100)]
        for idx, name in self._dev_input_devices:
            def _cb(data, frames, t, status, _i=idx):
                self._dev_level_queue.put((_i, float(np.max(np.abs(data)))))
            opened = False
            for ch, sr in _CONFIGS:
                try:
                    s = sd.InputStream(
                        device=idx, channels=ch, samplerate=sr,
                        blocksize=512, dtype="float32", callback=_cb
                    )
                    s.start()
                    self._dev_input_streams.append(s)
                    self._dev_stream_opened.add(idx)
                    opened = True
                    break
                except Exception:
                    pass
            if not opened:
                bar = self._dev_level_bars.get(idx)
                if bar:
                    bar.setStyleSheet(self._BAR_DIM)
                st = self._dev_status_labels.get(idx)
                if st and not st.text():
                    st.setText("Ei yhteyttä")
                    st.setStyleSheet("color: #546a94; font-size: 10px;")
        if self._dev_input_streams:
            self._dev_monitor_timer.start()

    def _stop_dev_monitoring(self):
        self._dev_monitor_timer.stop()
        for s in self._dev_input_streams:
            try:
                s.stop()
                s.close()
            except Exception:
                pass
        self._dev_input_streams.clear()

    def _update_dev_levels(self):
        import queue as _q
        peaks = {}
        try:
            while True:
                idx, lv = self._dev_level_queue.get_nowait()
                peaks[idx] = max(peaks.get(idx, 0.0), lv)
        except _q.Empty:
            pass

        THRESHOLD = 0.04
        SUSTAIN = 18
        for idx, bar in self._dev_level_bars.items():
            if idx not in self._dev_stream_opened:
                continue
            lv = peaks.get(idx, 0.0)
            self._dev_level_peak[idx] = max(lv, self._dev_level_peak.get(idx, 0.0) * 0.82)
            bar.setValue(int(min(self._dev_level_peak[idx] * 1000, 1000)))
            if lv > THRESHOLD:
                self._dev_sustained[idx] = self._dev_sustained.get(idx, 0) + 1
            else:
                self._dev_sustained[idx] = max(0, self._dev_sustained.get(idx, 0) - 1)

        # Yhdistetty mittari (aina näkyvissä, ks. _page_devices):
        # - kun mikki on jo valittu (auto tai käsin), näytä VAIN sen taso — muuten
        #   mittari heiluu jonkin toisen laitteen (esim. webcam-mikin) äänestä ja
        #   käyttäjä luulee valitun mikin kuuluvan vaikka se on mykistetty
        # - ennen valintaa näytä suurin taso kaikista, jotta näkyy tuleeko ääntä ollenkaan
        if hasattr(self, "_dev_combined_bar"):
            _sel = getattr(self, "_dev_selected_input", None)
            if _sel is not None and _sel in self._dev_stream_opened:
                combined_peak = self._dev_level_peak.get(_sel, 0.0)
            else:
                combined_peak = max(
                    (self._dev_level_peak.get(i, 0.0) for i in self._dev_stream_opened),
                    default=0.0,
                )
            self._dev_combined_bar.setValue(int(min(combined_peak * 1000, 1000)))
            self._dev_combined_bar.setStyleSheet(
                self._BAR_ACTIVE if combined_peak > THRESHOLD else self._BAR_IDLE
            )

        if not self._dev_auto_selected:
            cands = {
                k: v for k, v in self._dev_sustained.items()
                if k in self._dev_stream_opened
            }
            best, cnt = max(cands.items(), key=lambda x: x[1], default=(None, 0))
            if cnt >= SUSTAIN and best is not None:
                self._dev_select_input(best, auto=True)
            else:
                # Ei vielä osunut mihinkään laitteeseen. Jos ~6s on kulunut eikä mikään laite
                # ole reagoinut ollenkaan, avaa tarkka laitelista AUTOMAATTISESTI sen sijaan
                # että käyttäjä jää tuijottamaan muuttumatonta korttia ilman että tietää mitä
                # tehdä seuraavaksi (ks. käyttäjäpalaute: "ei näy mitä mikkiä yrittää").
                self._dev_no_speech_ticks = getattr(self, "_dev_no_speech_ticks", 0) + 1
                if (self._dev_no_speech_ticks == 75
                        and hasattr(self, "_dev_mic_list_w")
                        and not self._dev_mic_list_w.isVisible()):
                    self._dev_mic_list_w.setVisible(True)
                    self._dev_mic_toggle_btn.setText("▾  Piilota mikrofonilista")
                    if self._dev_input_status_lbl:
                        self._dev_input_status_lbl.setText(
                            "🎤  Emme vielä kuulleet sinua — puhu kovempaa, tarkista "
                            "mikrofonilupa tai valitse laite alta listalta."
                        )

    def _dev_select_input(self, idx, auto=False):
        self._dev_selected_input = idx
        self._dev_auto_selected = True
        for i, bar in self._dev_level_bars.items():
            if i == idx:
                bar.setStyleSheet(self._BAR_ACTIVE)
                self._dev_row_widgets[i].setStyleSheet(
                    "background: #0f2219; border-radius: 4px;"
                )
            else:
                bar.setStyleSheet(self._BAR_DIM)
                self._dev_row_widgets[i].setStyleSheet(
                    "background: transparent; border-radius: 4px;"
                )
        name = next((n for i, n in self._dev_input_devices if i == idx), str(idx))
        prefix = "Automaattisesti tunnistettu" if auto else "Valittu"
        if self._dev_input_status_lbl:
            self._dev_input_status_lbl.setText(f"✓  {prefix}: {name}")
            self._dev_input_status_lbl.setStyleSheet(
                "color: #00ff88; font-size: 15px; font-weight: bold; background: #0d2b14;"
                " border: 1px solid #238636; border-radius: 8px; padding: 16px;"
            )
        self._dev_mic_ok = True
        self._update_dev_next_gate()

    def _dev_test_output(self, device_idx, btn):
        import queue as _q
        btn.setEnabled(False)
        if self._dev_out_status_lbl:
            self._dev_out_status_lbl.setText("Soitetaan testiääni...")
            self._dev_out_status_lbl.setStyleSheet(
                "color: #8a9bc4; font-size: 11px; background: transparent;"
            )
        _result_q = _q.Queue()

        def _play():
            try:
                info = sd.query_devices(device_idx)
                sr = int(info.get("default_samplerate", 48000))
                ch = max(1, min(2, int(info.get("max_output_channels", 2))))
                t = np.linspace(0, 0.7, int(sr * 0.7), endpoint=False)
                mono = (np.sin(2 * np.pi * 660.0 * t) * 0.45).astype("float32")
                tone = np.column_stack([mono] * ch) if ch > 1 else mono.reshape(-1, 1)
                sd.play(tone, samplerate=sr, device=device_idx, blocking=True)
                name = next(
                    (n for i, n in self._dev_output_devices if i == device_idx),
                    str(device_idx)
                )
                _result_q.put((True, f"✓ Kuuluit: {name}"))
            except Exception as exc:
                _result_q.put((False, f"Virhe: {exc}"))

        def _poll():
            try:
                ok, msg = _result_q.get_nowait()
            except _q.Empty:
                return
            _ptmr.stop()
            try:
                self._dev_active_poll_timers.remove(_ptmr)
            except ValueError:
                pass
            if not self._dev_closing:
                if self._dev_out_status_lbl:
                    self._dev_out_status_lbl.setText(msg)
                    self._dev_out_status_lbl.setStyleSheet(
                        f"color: {'#00ff88' if ok else '#ff2e4d'};"
                        " font-size: 11px; background: transparent;"
                    )
                if ok:
                    name = next(
                        (n for i, n in self._dev_output_devices if i == device_idx), ""
                    )
                    is_v = any(k in name.lower() for k in [
                        "virtual", "vb-audio", "voicemeeter", "cable",
                        "nvidia", "amd hdmi", "intel hdmi", "hdmi",
                    ])
                    cb = self._dev_out_checkboxes.get(device_idx)
                    if cb and not is_v:
                        cb.setChecked(True)
                    btn.setStyleSheet(
                        "QPushButton { background: #1a4731; color: #00ff88;"
                        " border: 1px solid #00ff88; border-radius: 4px; font-size: 11px; }"
                    )
                    btn.setText("✓ OK")
                else:
                    btn.setEnabled(True)

        _ptmr = QTimer(self)
        _ptmr.timeout.connect(_poll)
        _ptmr.start(100)
        self._dev_active_poll_timers.append(_ptmr)
        self._dev_play_thread = threading.Thread(target=_play, daemon=True)
        self._dev_play_thread.start()

    # ── logic ─────────────────────────────────────────────────────────

    def _build_ui(self):
        self._stack = QStackedWidget(self)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(self._stack)
        self._stack.addWidget(self._page_welcome())        # 0
        self._stack.addWidget(self._page_services())       # 1
        self._stack.addWidget(self._page_packages())       # 2  (vain dev-tilassa sekvenssissä)
        self._stack.addWidget(self._page_api_key())        # 3
        self._stack.addWidget(self._page_devices())        # 4  mikrofoni + kaiuttimet + chat-reititys + ääntesti
        self._stack.addWidget(QWidget())                   # 5  (vanha chat-reititys-sivu — nyt osio sivulla 4; placeholder säilyttää indeksit)
        self._stack.addWidget(self._page_final_test())     # 6  Valmis

    def _on_key_changed(self, text):
        valid = text.strip().startswith("sk-") and len(text.strip()) > 20
        self._test_btn.setEnabled(valid)
        self._save_btn.setEnabled(valid)
        self._status_lbl.setText("")

    def _test_key(self):
        key = self._key_input.text().strip()
        self._test_btn.setEnabled(False)
        self._status_lbl.setText("Testataan...")
        self._status_lbl.setStyleSheet(
            "color: #8a9bc4; font-size: 12px; padding-left: 8px; background: transparent;"
        )
        QApplication.processEvents()
        try:
            OpenAI(api_key=key).models.list()
            self._status_lbl.setText("✓ Toimii!")
            self._status_lbl.setStyleSheet(
                "color: #00ff88; font-size: 12px; padding-left: 8px; background: transparent;"
            )
            self._save_btn.setEnabled(True)
        except Exception as e:
            msg = str(e)
            if "401" in msg or "invalid_api_key" in msg:
                txt = "✗ Väärä avain"
            elif "429" in msg:
                txt = "✗ Käyttöraja täynnä (tili ok)"
            else:
                txt = f"✗ {msg[:60]}"
            self._status_lbl.setText(txt)
            self._status_lbl.setStyleSheet(
                "color: #ff2e4d; font-size: 12px; padding-left: 8px; background: transparent;"
            )
        self._test_btn.setEnabled(True)

    def _save_key(self):
        key = self._key_input.text().strip()
        if not key:
            return
        self._api_key = key
        env_file = os.path.join(BASE_PATH, "credentials.env")
        try:
            lines = []
            if os.path.exists(env_file):
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = [ln.rstrip() for ln in f if not ln.startswith("OPENAI_API_KEY")]
            lines.insert(0, f"OPENAI_API_KEY={key}")
            with open(env_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            self._save_btn.setText("✅ Tallennettu")
            self._save_btn.setEnabled(False)
        except Exception:
            pass

    def _finish_setup(self):
        self._stop_dev_monitoring()
        self._dev_closing = True
        for t in self._dev_active_poll_timers:
            t.stop()
        self._dev_active_poll_timers.clear()
        if self._dev_play_thread and self._dev_play_thread.is_alive():
            try:
                sd.stop()
            except Exception:
                pass
            self._dev_play_thread.join(timeout=1.5)

        selected_out = [idx for idx, cb in self._dev_out_checkboxes.items() if cb.isChecked()]
        _virt_kw = ["virtual", "vb-audio", "voicemeeter", "cable"]
        try:
            hd = {}
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    hd = json.load(f)
            # Preserve virtual devices from previous Voicemeeter wizard config
            _prev = hd.get("selected_output_devices") or []
            for _pi in _prev:
                try:
                    _pn = sd.query_devices(_pi)["name"].lower()
                    if any(k in _pn for k in _virt_kw) and _pi not in selected_out:
                        selected_out.append(_pi)
                except Exception:
                    pass
            # Chat-reititys: lisää oikea virtuaalikaapeli output-laitteisiin AUTOMAATTISESTI —
            # wizardin laitelistat eivät enää näytä virtuaalilaitteita, joten käyttäjä ei voi
            # (eikä hänen tarvitse) valita niitä käsin. TTS/soundboard soittaa näihin.
            try:
                _routing_needed = self._svc_mixer or getattr(self, "_svc_routing", "") == "gaming"
                if _routing_needed:
                    _want = ("voicemeeter input (vb-audio voicemeeter vaio)"
                             if self._svc_mixer else "cable input")
                    for _oi, _on in list_output_devices():
                        _onl = _on.lower()
                        if (_onl == _want if self._svc_mixer else _want in _onl):
                            if _oi not in selected_out:
                                selected_out.append(_oi)
                            break
            except Exception:
                pass
            # Safety net: if no physical output selected, add system default
            _phys = []
            for _si in selected_out:
                try:
                    _sn = sd.query_devices(_si)["name"].lower()
                    if not any(k in _sn for k in _virt_kw):
                        _phys.append(_si)
                except Exception:
                    pass
            if not _phys:
                _def_idx = getattr(self, "_dev_default_out", -1)
                if _def_idx >= 0 and _def_idx not in selected_out:
                    selected_out.append(_def_idx)
            if self._dev_selected_input is not None:
                hd["selected_input_device"] = self._dev_selected_input
                _dev_name = next(
                    (n for i, n in self._dev_input_devices if i == self._dev_selected_input),
                    None,
                )
                if _dev_name:
                    hd["selected_input_device_name"] = f"🎤 {_dev_name}"
            if selected_out:
                hd["selected_output_devices"] = selected_out
                # Nimet mukaan indeksien lisäksi — sama syy kuin selected_input_device_name:
                # PortAudio-indeksit eivät pysy vakioina seuraavalle käynnistyskerralle.
                try:
                    _out_names_now = dict(list_output_devices())
                    hd["selected_output_device_names"] = [
                        _out_names_now[i] for i in selected_out if i in _out_names_now
                    ]
                except Exception:
                    pass
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(hd, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        settings = load_settings()
        # Save STT/TTS/translation backends chosen in wizard
        if getattr(self, "_svc_stt", "openai") == "local":
            settings["stt_backend"] = "Local Whisper (base)"
        else:
            settings.setdefault("stt_backend", "OpenAI Whisper API")
        if getattr(self, "_svc_tts", "edge") == "elevenlabs":
            settings.setdefault("default_tts_backend", "ElevenLabs")
        else:
            settings.setdefault("default_tts_backend", "Edge TTS (free)")
        if getattr(self, "_svc_trans", "google") == "openai":
            settings.setdefault("translation_backend", "OpenAI")
        elif getattr(self, "_svc_trans", "google") == "deepl":
            settings.setdefault("translation_backend", "DeepL")
        else:
            settings.setdefault("translation_backend", "Google (free)")
        # Home Assistant -asetukset Valmis-sivun kentistä (jos HA valittiin sivulla 2)
        if getattr(self, "_svc_ha", False) and getattr(self, "_fin_ha_url_edit", None) is not None:
            _ha_u = self._fin_ha_url_edit.text().strip()
            _ha_t = self._fin_ha_token_edit.text().strip()
            if _ha_u:
                settings["ha_url"] = _ha_u
            if _ha_t:
                settings["ha_token"] = _ha_t
        settings["_last_wizard_version"] = APP_VERSION
        save_settings(settings)
        self.accept()

    def closeEvent(self, event):
        self._dev_closing = True
        self._stop_dev_monitoring()
        for t in self._dev_active_poll_timers:
            t.stop()
        super().closeEvent(event)

    def get_api_key(self) -> str:
        return self._api_key


if __name__ == "__main__":
    # On Windows, OleInitialize must be called before QApplication so that
    # RegisterDragDrop works correctly in frozen EXE builds.
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.ole32.OleInitialize(None)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _app_icon_path = os.path.join(ASSETS_PATH, "iconimage.ico")
    if os.path.exists(_app_icon_path):
        app.setWindowIcon(QIcon(_app_icon_path))

    # First-run setup wizard — only on true first launch (no prior settings)
    _settings_path = os.path.join(BASE_PATH, "app_settings.json")
    if not OPENAI_API_KEY and not os.path.exists(_settings_path):
        wizard = SetupWizard()
        if wizard.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        OPENAI_API_KEY = wizard.get_api_key()
        if OPENAI_API_KEY:
            client = OpenAI(api_key=OPENAI_API_KEY)
        # _finish_setup() already stamps _last_wizard_version = APP_VERSION on Accept.
    elif os.path.exists(_settings_path):
        # Resume the wizard on the same page after a wizard-triggered reboot
        # (e.g. Voicemeeter Banana driver install) so it shows as installed.
        _resume_settings = load_settings()
        _resume_page = _resume_settings.pop("_resume_wizard_page", None)
        if _resume_page is not None:
            save_settings(_resume_settings)
            resume_wizard = SetupWizard()
            resume_wizard._svc_mixer = True
            resume_wizard._navigate(_resume_page)
            resume_wizard.exec()
        elif _resume_settings.get("_last_wizard_version") != APP_VERSION:
            # New version since the wizard was last seen — reopen the full wizard so the
            # user can review/re-check their setup after an update that touched it.
            update_wizard = SetupWizard()
            update_wizard.exec()
            try:
                _s2 = load_settings()
                _s2["_last_wizard_version"] = APP_VERSION
                save_settings(_s2)
            except Exception:
                pass

    # Match App.__init__ geometry exactly so splash and main window occupy the same spot
    _WIN_X, _WIN_Y, _WIN_W, _WIN_H = 100, 100, 1320, 637

    splash_path = os.path.join(ASSETS_PATH, "BluexDEV_logo.png")
    splash = None
    if os.path.exists(splash_path):
        logo = QPixmap(splash_path)
        logo = logo.scaled(
            _WIN_W - 120, _WIN_H - 120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QPixmap(_WIN_W, _WIN_H)
        canvas.fill(QColor("#05070f"))
        p = QPainter(canvas)
        p.drawPixmap((_WIN_W - logo.width()) // 2, (_WIN_H - logo.height()) // 2, logo)
        p.end()
        splash = QSplashScreen(canvas, Qt.WindowType.WindowStaysOnTopHint)
        splash.move(_WIN_X, _WIN_Y)
        splash.show()
        app.processEvents()

    _t0 = time.time()
    window = App()
    _elapsed_ms = int((time.time() - _t0) * 1000)

    _start_minimized = "--minimized" in sys.argv
    if splash:
        _remaining = max(0, 4000 - _elapsed_ms)
        if _start_minimized:
            QTimer.singleShot(_remaining, lambda: (splash.finish(window), window.hide()))
        else:
            QTimer.singleShot(_remaining, lambda: (splash.finish(window), window.show()))
    else:
        if _start_minimized:
            window.hide()
        else:
            window.show()

    sys.exit(app.exec())
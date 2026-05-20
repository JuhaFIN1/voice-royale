# Copyright (c) 2026 Juha Lempiäinen. All rights reserved.
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
    "keyboard": "keyboard",
    "openai": "openai",
    "pyttsx3": "pyttsx3",
    "edge_tts": "edge-tts",
    "deep_translator": "deep-translator",
}


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
import wave
import webbrowser

import edge_tts
import keyboard
import numpy as np
import pyttsx3
import requests
import sounddevice as sd
from dotenv import load_dotenv
from openai import OpenAI
from PyQt6.QtCore import QEvent, QObject, QRectF, QSize, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
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
    QSizePolicy,
    QSplashScreen,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

# =========================
# UI STYLE CONSTANTS
# =========================
METER_LABEL_STYLE = "color: #3A7BFF; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;"
METER_STYLE_MIC = (
    "QProgressBar { background: #0a0a0a; border: 1px solid #2a2a2a; border-radius: 4px; }"
    "QProgressBar::chunk { background: qlineargradient(x1:0, x2:1,"
    " stop:0 #00FF6A, stop:0.6 #FFD700, stop:1 #FF3A3A); border-radius: 3px; }"
)
METER_STYLE_OUT = (
    "QProgressBar { background: #0a0a0a; border: 1px solid #2a2a2a; border-radius: 4px; }"
    "QProgressBar::chunk { background: qlineargradient(x1:0, x2:1,"
    " stop:0 #00FF6A, stop:0.6 #FFD700, stop:1 #FF3A3A); border-radius: 3px; }"
)
LIST_STYLE = """
    QListWidget {
        background: #1A1A1A;
        border: 1px solid #2a2a2a;
        border-radius: 8px;
        font-family: "Inter", "Segoe UI", sans-serif;
        font-size: 12px;
    }
    QListWidget::item {
        background: #1E1E1E;
        border: 1px solid #2a2a2a;
        border-radius: 6px;
        margin: 2px 4px;
        padding: 4px 7px;
        color: #C8C8C8;
    }
    QListWidget::item:hover {
        background: #252525;
        border-color: #9A4DFF;
        color: #ffffff;
    }
    QListWidget::item:selected {
        background: qlineargradient(x1:0, x2:1, stop:0 #3A7BFF, stop:1 #9A4DFF);
        border-color: #3A7BFF;
        color: #ffffff;
    }
"""

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
    "deepl_api_key": "",
    "wake_command_seconds": 6.0,
    "custom_languages": [],
    "soundboard_pages": [
        {"name": "Peli aloitus", "slots": [{"name": f"Slot {i+1}", "file": "", "image": ""} for i in range(56)]}
    ],
    "stream_deck_enabled": True,
    "stream_deck_mapping": {},   # tyhjä = käytä DEFAULT_MAPPING
    "voice_fx_output_device": None,
    "voice_fx_monitor_device": None,
    "voice_fx_hear_myself": False,
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
# OPTIONAL: Picovoice Porcupine wake-word
# =========================
try:
    import pvporcupine  # type: ignore
    PORCUPINE_AVAILABLE = True
except Exception:
    pvporcupine = None
    PORCUPINE_AVAILABLE = False


# =========================
# VOICE EFFECT PROCESSOR
# =========================
class VoiceEffectProcessor:
    """Real-time mic → DSP effects → virtual output (e.g. VB-Cable).

    Uses a producer-consumer pattern: the InputStream callback just buffers audio,
    and a processing thread applies effects and writes to the OutputStream.
    This keeps the audio callback lightweight and avoids glitches.
    """

    PRESETS = {
        "Normal":    {"pitch": 0,   "robot": False},
        "Pitch +4":  {"pitch": 4,   "robot": False},
        "Pitch +8":  {"pitch": 8,   "robot": False},
        "Pitch -4":  {"pitch": -4,  "robot": False},
        "Pitch -8":  {"pitch": -8,  "robot": False},
        "Robot":     {"pitch": 0,   "robot": True},
        "Deep":      {"pitch": -6,  "robot": False},
        "Helium":    {"pitch": 10,  "robot": False},
    }

    _SAMPLE_RATE = 44100
    _BLOCKSIZE = 2048

    def __init__(self, status_cb):
        self._status = status_cb
        self._active = False
        self._pitch = 0
        self._robot = False
        self._robot_phase = 0
        self._current_preset = "Normal"
        self._lock = threading.Lock()
        import collections
        self._buf = collections.deque(maxlen=12)
        self._stream_in = None
        self._stream_out = None
        self._monitor_stream = None
        self._hear_myself = False
        self._monitor_device = None
        self._stop_evt = threading.Event()
        self._proc_thread = None

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def current_preset(self) -> str:
        return self._current_preset

    def set_preset(self, name: str):
        p = self.PRESETS.get(name, self.PRESETS["Normal"])
        with self._lock:
            self._pitch = p["pitch"]
            self._robot = p["robot"]
            self._current_preset = name

    def start(self, input_device, output_device):
        if self._active:
            self.stop()
        self._stop_evt.clear()
        try:
            self._stream_out = sd.OutputStream(
                device=output_device,
                samplerate=self._SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=self._BLOCKSIZE,
                latency="low",
            )
            self._stream_out.start()
            self._stream_in = sd.InputStream(
                device=input_device,
                samplerate=self._SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=self._BLOCKSIZE,
                callback=self._capture_cb,
                latency="low",
            )
            self._stream_in.start()
            self._active = True
            if self._hear_myself and self._monitor_device is not None:
                self._start_monitor_stream(self._monitor_device)
            self._proc_thread = threading.Thread(target=self._proc_loop, daemon=True)
            self._proc_thread.start()
            self._status(f"Voice FX: on [{self._current_preset}]")
        except Exception as e:
            self._active = False
            self._cleanup()
            self._status(f"Voice FX error: {e}")

    def stop(self):
        self._active = False
        self._stop_evt.set()
        self._cleanup()
        if self._proc_thread:
            self._proc_thread.join(timeout=2.0)
            self._proc_thread = None
        self._status("Voice FX: off")

    def _cleanup(self):
        for s in (self._stream_in, self._stream_out, self._monitor_stream):
            if s:
                try:
                    s.stop(); s.close()
                except Exception:
                    pass
        self._stream_in = None
        self._stream_out = None
        self._monitor_stream = None

    def _capture_cb(self, indata, frames, time_info, status):
        self._buf.append(indata[:, 0].copy())

    def _proc_loop(self):
        while not self._stop_evt.is_set():
            if not self._buf:
                time.sleep(0.005)
                continue
            try:
                chunk = self._buf.popleft()
            except IndexError:
                continue
            chunk = self._apply(chunk)
            if self._stream_out and self._active:
                try:
                    self._stream_out.write(chunk.reshape(-1, 1))
                except Exception:
                    pass
            if self._monitor_stream and self._hear_myself and self._active:
                try:
                    self._monitor_stream.write(chunk.reshape(-1, 1))
                except Exception:
                    pass

    def _apply(self, chunk: np.ndarray) -> np.ndarray:
        with self._lock:
            pitch = self._pitch
            robot = self._robot
        if robot:
            n = len(chunk)
            t = np.arange(self._robot_phase, self._robot_phase + n) / self._SAMPLE_RATE
            self._robot_phase = (self._robot_phase + n) % (self._SAMPLE_RATE * 100)
            chunk = chunk * np.sin(2 * np.pi * 40 * t).astype(np.float32)
        if pitch != 0:
            chunk = self._pitch_shift(chunk, pitch)
        return chunk

    def _pitch_shift(self, chunk: np.ndarray, semitones: int) -> np.ndarray:
        try:
            import pyrubberband as rb  # type: ignore
            return rb.pitch_shift(chunk, self._SAMPLE_RATE, semitones).astype(np.float32)
        except Exception:
            pass
        # Fallback: resampling trick (fast, acceptable quality for voice)
        from scipy.signal import resample
        factor = 2.0 ** (semitones / 12.0)
        n_new = max(1, int(len(chunk) / factor))
        pitched = resample(chunk, n_new)
        return resample(pitched, len(chunk)).astype(np.float32)

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
        "tts_toggle", "settings",
        "lang_Auto", "lang_English", "lang_Finnish", "lang_Swedish",
        "lang_German", "lang_Russian", "lang_Italian", "lang_Dutch",
        "lang_Norwegian", "lang_Danish", "lang_Romanian", "lang_Latvian",
        "lang_Lithuanian", "lang_Japanese", "lang_Chinese", "lang_Hungarian",
        "lang_French", "lang_Spanish", "lang_Portuguese",
        "sb_page_next", "sb_page_prev",
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
                            pi, si = int(parts[0]), int(parts[1])
                            st = app._get_sd_state()
                            pages_st = st.get("soundboard_pages", [])
                            if pi < len(pages_st):
                                sl = pages_st[pi].get("slots", [])
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
                ("127.0.0.1", self.PORT), _Handler
            )
            status_cb(f"Stream Deck: HTTP ready on port {self.PORT}")
            self._server.serve_forever()
        except OSError:
            status_cb(f"Stream Deck: port {self.PORT} busy — plugin won't connect")
        except Exception as e:
            status_cb(f"Stream Deck HTTP: {e}")


# =========================
# SOUNDBOARD IMPORT HELPERS
# =========================

def _sb_import_audio(src_path: str, page_index: int, slot_index: int) -> tuple[str, int, int]:
    """Convert and copy audio into soundboard data dir. Returns (dest_path, orig_bytes, new_bytes)."""
    out_dir = os.path.join(BASE_PATH, "soundboard", "audio")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"p{page_index}_slot_{slot_index}.wav")
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
    out_path = os.path.join(out_dir, f"p{page_index}_slot_{slot_index}.jpg")
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

    _edit_mode: bool = False

    @classmethod
    def set_edit_mode(cls, enabled: bool):
        cls._edit_mode = enabled

    _STYLE_IDLE = (
        "QToolButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #222228, stop:1 #14141A);"
        " border: 2px solid #333344; border-radius: 10px;"
        " color: #7A7A9A; font-size: 8px; font-weight: 700;"
        " padding-bottom: 2px; }"
        "QToolButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #2A2A38, stop:1 #1C1C26);"
        " border: 2px solid #9A4DFF; color: #E0E0FF; }"
        "QToolButton:pressed { background: #0e0e18; border: 2px solid #3A7BFF; }"
    )
    _STYLE_PLAY = (
        "QToolButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        " stop:0 #0a2818, stop:1 #06160C);"
        " border: 2px solid #00FF6A; border-radius: 10px;"
        " color: #00FF6A; font-size: 8px; font-weight: 700; padding-bottom: 2px; }"
    )
    _STYLE_DRAG = (
        "QToolButton { background: #080C1A; border: 2px dashed #3A7BFF; border-radius: 10px;"
        " color: #3A7BFF; font-size: 8px; font-weight: 700; padding-bottom: 2px; }"
    )

    def __init__(self, page_index: int, slot_index: int, parent=None):
        super().__init__(parent)
        self.page_index = page_index
        self.slot_index = slot_index
        self._data = {"name": f"Slot {slot_index + 1}", "file": "", "image": ""}
        self.setFixedSize(72, 68)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._btn = QToolButton()
        self._btn.setFixedSize(72, 68)
        self._btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._btn.setIconSize(QSize(46, 42))
        self._btn.setStyleSheet(self._STYLE_IDLE)
        self._btn.clicked.connect(lambda: self.clicked_play.emit(self.slot_index))
        self._btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._btn.customContextMenuRequested.connect(self._ctx_menu)
        self._btn.setAcceptDrops(True)
        self._btn.installEventFilter(self)
        lay.addWidget(self._btn)

        self._refresh()

    def set_data(self, d: dict):
        self._data = dict(d)
        self._refresh()

    def get_data(self) -> dict:
        return dict(self._data)

    def set_playing(self, playing: bool):
        self._btn.setStyleSheet(self._STYLE_PLAY if playing else self._STYLE_IDLE)

    # ---- drag-and-drop (only active in edit mode) ----

    _IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
    _AUDIO_EXTS = {'.wav', '.mp3', '.ogg', '.flac', '.aiff', '.aif'}

    def eventFilter(self, obj, event):
        if obj is self._btn:
            t = event.type()
            if t == QEvent.Type.DragEnter:
                self._on_drag_enter(event)
                return True
            if t == QEvent.Type.DragMove:
                if SoundboardButton._edit_mode and event.mimeData().hasUrls():
                    event.acceptProposedAction()
                else:
                    event.ignore()
                return True
            if t == QEvent.Type.DragLeave:
                self._btn.setStyleSheet(self._STYLE_IDLE)
                return True
            if t == QEvent.Type.Drop:
                self._on_drop(event)
                return True
        return super().eventFilter(obj, event)

    def _on_drag_enter(self, event):
        if not SoundboardButton._edit_mode:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = os.path.splitext(url.toLocalFile())[1].lower()
                if ext in self._IMAGE_EXTS or ext in self._AUDIO_EXTS:
                    event.acceptProposedAction()
                    self._btn.setStyleSheet(self._STYLE_DRAG)
                    return
        event.ignore()

    def _on_drop(self, event):
        self._btn.setStyleSheet(self._STYLE_IDLE)
        if not SoundboardButton._edit_mode or not event.mimeData().hasUrls():
            event.ignore()
            return
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if ext in self._IMAGE_EXTS:
                self._drop_image(path)
            elif ext in self._AUDIO_EXTS:
                self._drop_sound(path)
        event.acceptProposedAction()

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
        r = 8  # corner radius
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
            pen = QPen(QColor("#7040C8"))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.drawRoundedRect(inner, r, r)
        else:
            clip = QPainterPath()
            clip.addRoundedRect(inner, r, r)
            p.setClipPath(clip)
            p.fillRect(inner.toRect(), QColor("#14141E"))
            p.setClipping(False)
            p.setPen(QColor("#3A7BFF"))
            p.setFont(QFont("Segoe UI", size // 3))
            p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "♪")
            pen = QPen(QColor("#2A3060"))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.drawRoundedRect(inner, r, r)
        p.end()
        return px

    def _refresh(self):
        name = self._data.get("name") or f"Slot {self.slot_index + 1}"
        px = self._make_icon_pixmap(46)
        self._btn.setIcon(QIcon(px))
        display = name if len(name) <= 9 else name[:8] + "…"
        self._btn.setText(display)
        self._btn.setToolTip(name + ("\n" + self._data["file"] if self._data.get("file") else ""))

    def _ctx_menu(self, pos):
        if not SoundboardButton._edit_mode:
            return
        menu = QMenu(self)
        menu.addAction("Assign Sound…", self._assign_sound)
        menu.addAction("Assign Image…", self._assign_image)
        menu.addAction("Rename…", self._rename)
        if self._data.get("file"):
            menu.addSeparator()
            menu.addAction("Clear", self._clear)
        menu.exec(self.mapToGlobal(pos))

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
            ratio = (1 - new / orig) * 100 if orig > 0 else 0
            self._notify_status(
                f"Soundboard {self.slot_index+1}: ääni tuotu "
                f"({orig//1024} KB → {new//1024} KB, -{ratio:.0f}%)"
            )
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Tuontivirhe", str(e))
            self._data["file"] = path  # fallback: alkuperäinen polku
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

    def _notify_status(self, msg: str):
        p = self.parent()
        while p is not None:
            if isinstance(p, QWidget) and hasattr(p, "append_status"):
                p.append_status(msg)
                return
            p = p.parent() if hasattr(p, "parent") else None

    def _rename(self):
        text, ok = QInputDialog.getText(
            self, "Rename Slot", "Button name:",
            text=self._data.get("name", f"Slot {self.slot_index + 1}")
        )
        if ok and text.strip():
            self._data["name"] = text.strip()
            self._refresh()
            self.data_changed.emit(self.slot_index)

    def _clear(self):
        self._data = {"name": f"Slot {self.slot_index + 1}", "file": "", "image": ""}
        self._refresh()
        self.data_changed.emit(self.slot_index)


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

def list_output_devices():
    try:
        devices = sd.query_devices()
        return [
            (index, device["name"])
            for index, device in enumerate(devices)
            if device["max_output_channels"] > 0
        ]
    except Exception:
        return []


def list_input_devices():
    try:
        devices = sd.query_devices()
        return [
            (index, device["name"])
            for index, device in enumerate(devices)
            if device["max_input_channels"] > 0
        ]
    except Exception:
        return []


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


def transcribe_audio_wav(wav_bytes: bytes, language: str = None) -> str:
    try:
        if len(wav_bytes) < 100:
            return ""
        if not wav_bytes.startswith(b"RIFF"):
            return ""

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

def play_wav_bytes(wav_bytes: bytes, device_indices=None, level_callback=None):
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

        # Start level meter thread if callback provided
        if level_callback is not None:
            flat = audio_data.flatten().astype(np.float32) / 32768.0
            chunk_size = max(1, int(samplerate * 0.05))  # 50ms chunks

            def _level_thread():
                for i in range(0, len(flat), chunk_size):
                    chunk = flat[i:i + chunk_size]
                    if len(chunk) > 0:
                        level_callback(float(np.max(np.abs(chunk))))
                    time.sleep(chunk_size / samplerate)
                level_callback(0.0)

            threading.Thread(target=_level_thread, daemon=True).start()

        # Handle single device or multiple devices
        if device_indices is None:
            device_indices = []
        elif isinstance(device_indices, int):
            device_indices = [device_indices]
        elif not isinstance(device_indices, list):
            device_indices = []

        if not device_indices:
            sd.play(audio_data, samplerate=samplerate)
            sd.wait()
            return

        def play_to_device(device_index):
            try:
                device_info = sd.query_devices(device_index)
                if device_info['max_output_channels'] == 0:
                    return
                try:
                    sd.play(audio_data, samplerate=samplerate, device=device_index)
                    sd.wait()
                except Exception as first_err:
                    # Fallback: resample to the device's preferred rate
                    target_sr = int(device_info.get('default_samplerate') or 48000)
                    if target_sr == samplerate:
                        raise
                    import scipy.signal
                    float_audio = audio_data.astype(np.float32)
                    if float_audio.ndim == 1:
                        new_len = int(len(float_audio) * target_sr / samplerate)
                        resampled = scipy.signal.resample(float_audio, new_len)
                    else:
                        new_len = int(float_audio.shape[0] * target_sr / samplerate)
                        resampled = scipy.signal.resample(float_audio, new_len, axis=0)
                    resampled_int16 = np.clip(resampled, -32768, 32767).astype(np.int16)
                    print(f"[DEBUG] Resampled {samplerate}->{target_sr} Hz for device {device_index}")
                    sd.play(resampled_int16, samplerate=target_sr, device=device_index)
                    sd.wait()
            except Exception as e:
                print(f"Warning: Failed to play to device {device_index}: {e}")

        threads = []
        for device_index in device_indices:
            t = threading.Thread(target=play_to_device, args=(device_index,))
            t.daemon = True
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    except Exception as e:
        raise RuntimeError(f"Audio playback failed: {e}") from e


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

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, access_key: str, keyword: str, custom_ppn_path: str, device_index, level_callback=None):
        self._keyword = keyword.lower()
        self._device_index = device_index
        self._level_callback = level_callback

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
        sample_rate = self._porcupine.sample_rate
        frame_length = self._porcupine.frame_length
        try:
            with sd.InputStream(
                device=self._device_index,
                channels=1,
                samplerate=sample_rate,
                blocksize=frame_length,
                dtype="int16",
            ) as stream:
                self.on_status(f"👂 Porcupine listening (sr={sample_rate})")
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
        except Exception as e:
            self.on_status(f"Wake listener stopped: {e}")

    def _run_whisper(self):
        """Streams mic continuously in 2.5s chunks, transcribes, checks for wake keyword."""
        sample_rate = 16000
        chunk_duration = 2.5
        silence_threshold = 0.008

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
                    device=self._device_index,
                    channels=1,
                    samplerate=sample_rate,
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
                rms = float(np.sqrt(np.mean(audio ** 2)))
                if rms < silence_threshold:
                    continue

                audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
                wav_buf = io.BytesIO()
                with wave.open(wav_buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_int16.tobytes())

                try:
                    transcript = transcribe_audio_wav(wav_buf.getvalue())
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
                    self.on_status(f"Wake listener error: {e}")
                    time.sleep(1.0)


# =========================
class _TextboxRecordBtnFilter(QObject):
    """Repositions the overlay record button whenever the textbox is resized."""
    def __init__(self, btn: QPushButton):
        super().__init__()
        self._btn = btn

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self._btn.move(obj.width() - self._btn.width() - 6, obj.height() - self._btn.height() - 6)
        return False


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

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Royale")
        self.setGeometry(100, 100, 1320, 820)
        icon_path = os.path.join(ASSETS_PATH, "iconimage.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setStyleSheet("""
            QWidget {
                background: #121212;
                color: #E0E0E0;
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #121212,stop:1 #1A1A1A);
                border: 1px solid #2a2a2a;
                border-radius: 8px;
            }
            QLabel { background: transparent; border: none; color: #E0E0E0; }

            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1E1E1E,stop:1 #181818);
                border: 1px solid #333333;
                border-radius: 8px;
                color: #E0E0E0;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
                min-height: 30px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #252525,stop:1 #1E1E1E);
                border-color: #9A4DFF;
                color: #ffffff;
            }
            QPushButton:pressed { background: #0e0e0e; border-color: #3A7BFF; }
            QPushButton:checked {
                background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);
                border-color: #3A7BFF;
                color: #ffffff;
            }
            QPushButton:disabled { background: #1A1A1A; color: #444444; border-color: #222222; }

            QToolButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1E1E1E,stop:1 #161616);
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                color: #B0B0B0;
                font-size: 11px;
                font-weight: 700;
            }
            QToolButton:hover { background: #252525; border-color: #3A7BFF; color: #ffffff; }
            QToolButton:pressed { background: #0e0e0e; border-color: #9A4DFF; }

            QComboBox {
                background: #1E1E1E;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                color: #E0E0E0;
                padding: 5px 10px;
                min-height: 30px;
            }
            QComboBox:hover { border-color: #3A7BFF; }
            QComboBox::drop-down { border: none; width: 22px; }
            QComboBox QAbstractItemView {
                background: #1A1A1A;
                border: 1px solid #2a2a2a;
                selection-background-color: #3A7BFF;
                color: #E0E0E0;
            }

            QTextEdit {
                background: #181818;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                color: #E0E0E0;
                padding: 6px;
                selection-background-color: #3A7BFF;
            }
            QTextEdit:focus { border-color: #3A7BFF; }
            QLineEdit {
                background: #1E1E1E;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                color: #E0E0E0;
                padding: 5px 10px;
                min-height: 30px;
            }
            QLineEdit:focus { border-color: #3A7BFF; }

            QCheckBox { color: #E0E0E0; background: transparent; spacing: 8px; }
            QCheckBox::indicator {
                width: 17px; height: 17px; border-radius: 5px;
                border: 1px solid #333333; background: #1E1E1E;
            }
            QCheckBox::indicator:hover { border-color: #3A7BFF; }
            QCheckBox::indicator:checked {
                background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);
                border-color: #3A7BFF;
            }

            QScrollBar:vertical { background: #121212; width: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);
                border-radius: 4px; min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: #9A4DFF; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal { background: #121212; height: 8px; border-radius: 4px; margin: 0; }
            QScrollBar::handle:horizontal {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);
                border-radius: 4px; min-width: 24px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

            QTabWidget::pane {
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                background: #1A1A1A;
            }
            QTabBar::tab {
                background: #1E1E1E;
                color: #888888;
                padding: 9px 20px;
                font-weight: 700;
                font-size: 12px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                border: 1px solid #2a2a2a;
                border-bottom: none;
                border-radius: 8px 8px 0 0;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);
                color: #ffffff;
                border-color: #3A7BFF;
            }
            QTabBar::tab:hover:!selected { background: #252525; color: #E0E0E0; border-color: #9A4DFF; }

            QListWidget { background: #1A1A1A; border: 1px solid #2a2a2a; border-radius: 8px; }
            QListWidget::item {
                background: #1E1E1E; border: 1px solid #2a2a2a;
                border-radius: 6px; margin: 2px 4px; padding: 5px 8px; color: #E0E0E0;
            }
            QListWidget::item:hover { background: #252525; border-color: #9A4DFF; }
            QListWidget::item:selected {
                background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);
                border-color: #3A7BFF; color: #fff;
            }

            QScrollArea { background: #1A1A1A; border: 1px solid #2a2a2a; border-radius: 8px; }
            QProgressBar { background: #0a0a0a; border: 1px solid #2a2a2a; border-radius: 4px; }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);
                border-radius: 3px;
            }

            QMenu {
                background: #1A1A1A;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                color: #E0E0E0;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected {
                background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);
                color: #ffffff;
            }
        """)

        # Load app settings first so custom languages are available for icon building
        self.settings = load_settings()
        _apply_custom_languages_to_globals(self.settings.get("custom_languages", []))

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

        # Voice FX + soundboard state
        self._voice_fx = VoiceEffectProcessor(self.append_status)
        self._current_fx_preset = "Normal"
        self._soundboard_buttons: list[list[SoundboardButton]] = []
        self._fx_preset_buttons: dict[str, QPushButton] = {}
        self._mb_bars: dict[int, tuple] = {}  # device_index -> (bar, db_lbl)
        self._sb_play_id: int = 0
        self._sb_playing_btn: "SoundboardButton | None" = None

        # Stream Deck HTTP server (for official Elgato plugin)
        self._stream_deck = StreamDeckHttpServer(self.append_status)

        # ============ Menu bar ============
        menu_bar = QMenuBar()
        menu_bar.setStyleSheet(
            "QMenuBar { background: #0e0e0e; color: #C0C0C0; border-bottom: 1px solid #2a2a2a;"
            " font-size: 12px; padding: 2px 4px; }"
            "QMenuBar::item { padding: 4px 12px; border-radius: 4px; }"
            "QMenuBar::item:selected { background: #1E1E1E; color: #E0E0E0; }"
            "QMenuBar::item:pressed { background: #3A7BFF; color: #fff; }"
            "QMenu { background: #1A1A1A; border: 1px solid #2a2a2a; color: #E0E0E0; }"
            "QMenu::item { padding: 7px 20px; }"
            "QMenu::item:selected { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF); color: #fff; }"
            "QMenu::separator { height: 1px; background: #2a2a2a; margin: 4px 0; }"
        )
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("⚙  Settings", lambda: open_settings_dialog(self))
        file_menu.addSeparator()
        file_menu.addAction("ℹ  About Voice Royale", self._show_app_info)
        file_menu.addSeparator()
        file_menu.addAction("✕  Exit", QApplication.instance().quit)

        # ============ Top row: Speech card (left) + History card (right) ============
        top_row = QHBoxLayout()
        top_row.addWidget(self._build_speech_card(), 2)
        top_row.addWidget(self._build_history_card(), 1)

        # ============ Bottom tab widget: Outputs / Soundboard / Voice FX ============
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.addTab(self._build_soundboard_card(), "  Soundboard  ")
        self._bottom_tabs.addTab(self._build_voice_fx_card(), "  Voice FX  ")
        self._bottom_tabs.addTab(self._build_outputs_card(), "  Output Devices  ")

        # ============ Root layout ============
        root = QVBoxLayout()
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(6)
        root.setMenuBar(menu_bar)
        root.addLayout(top_row, 1)
        root.addWidget(self._bottom_tabs, 1)
        root.addWidget(self._build_meters_bar())
        self.setLayout(root)

        # Wire signals — safe cross-thread UI updates
        self.sig_mic_level.connect(self._update_mic_meter)
        self.sig_out_level.connect(self._update_output_meters)
        self.sig_status.connect(self._on_status)
        self.sig_set_textbox.connect(self.textbox.setPlainText)

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
        self._stream_deck.start(self)

    # ============ Card builders ============

    def _make_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #141414,stop:1 #1A1A1A);"
            " border: 1px solid #2a2a2a; border-radius: 8px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        if title:
            title_lbl = QLabel(title.upper())
            title_lbl.setStyleSheet(
                "font-weight: 700; font-size: 12px; color: #3A7BFF; border: none;"
                " letter-spacing: 0.5px; padding-bottom: 2px;"
            )
            layout.addWidget(title_lbl)
        return frame, layout

    def _build_speech_card(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #141414,stop:1 #1A1A1A);"
            " border: 1px solid #2a2a2a; border-radius: 8px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)

        # Card title
        title_lbl = QLabel("SPEECH")
        title_lbl.setStyleSheet(
            "font-weight: 700; font-size: 12px; color: #3A7BFF; border: none; letter-spacing: 0.5px;"
        )
        layout.addWidget(title_lbl)

        # Status log — 5 rows
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setPlainText("Ready. Type or record. Hotkey: Ctrl+Alt+Space")
        self.status_text.setMinimumHeight(90)
        self.status_text.setMaximumHeight(115)
        self.status_text.setStyleSheet(
            "QTextEdit { background: #0e0e0e; border: 1px solid #2a2a2a; border-radius: 8px;"
            " color: #888888; font-size: 11px; padding: 5px; }"
        )
        layout.addWidget(self.status_text)

        # Translated text label
        self.translated_label = QLabel("Translated text will appear here.")
        self.translated_label.setWordWrap(True)
        self.translated_label.setMinimumHeight(32)
        self.translated_label.setStyleSheet(
            "color: #3A7BFF; padding: 5px 10px; background: #0e0e0e;"
            "border: 1px solid #3A7BFF; border-radius: 8px; font-size: 12px;"
        )
        layout.addWidget(self.translated_label)

        # Target selector (left narrow column) + textbox (right)
        text_row = QHBoxLayout()
        text_row.setSpacing(6)
        text_row.setContentsMargins(0, 0, 0, 0)

        lang_col = QVBoxLayout()
        lang_col.setSpacing(2)
        lang_col.setContentsMargins(0, 0, 0, 0)
        lbl_target = QLabel("TARGET")
        lbl_target.setStyleSheet(
            "color: #555555; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;"
        )
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
        self.textbox.setPlaceholderText("Type the phrase to speak…\nOr press 🎤 to record.")
        self.textbox.setMinimumHeight(90)
        text_row.addWidget(self.textbox, 1)
        layout.addLayout(text_row, 1)

        # Record button — floating overlay inside textbox
        self.record_button = QPushButton("🎤", self.textbox)
        self.record_button.setFixedSize(38, 38)
        self.record_button.setToolTip("Record")
        self.record_button.clicked.connect(self.on_record_toggle)
        self.record_button.setStyleSheet(
            "QPushButton { background: rgba(18,18,18,210); border: 1px solid #333333;"
            " border-radius: 10px; font-size: 18px; padding: 0; }"
            "QPushButton:hover { background: rgba(58,123,255,180); border-color: #3A7BFF; }"
            "QPushButton:disabled { opacity: 0.3; }"
        )
        self.record_button.move(self.textbox.width() - 44, self.textbox.height() - 44)
        self._rec_filter = _TextboxRecordBtnFilter(self.record_button)
        self.textbox.installEventFilter(self._rec_filter)
        self.record_button.raise_()

        # Hidden widgets — needed by app logic but not shown in this card
        self.backend_combo = QComboBox()
        for backend in ("ElevenLabs", "Edge TTS (free)"):
            self.backend_combo.addItem(backend)
        self.backend_combo.setCurrentText(self.settings.get("default_tts_backend", DEFAULT_TTS_BACKEND))

        self.test_audio_button = QPushButton("🧪  Test")
        self.test_audio_button.clicked.connect(self.on_test_audio)

        # Button row: Speak | Favorite | Listen
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self.speak_button = QPushButton("🔊  Speak")
        self.speak_button.clicked.connect(self.on_speak)
        self.speak_button.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,"
            " stop:0 #3A7BFF, stop:1 #9A4DFF);"
            " border: 1px solid #3A7BFF; border-radius: 8px; color: #fff;"
            " font-size: 13px; font-weight: 700; padding: 8px 18px; letter-spacing: 0.5px; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,"
            " stop:0 #5590FF, stop:1 #B060FF); border-color: #9A4DFF; }"
            "QPushButton:pressed { background: #1a1a1a; border-color: #3A7BFF; }"
            "QPushButton:disabled { background: #1A1A1A; color: #444444; border-color: #222222; }"
        )
        button_row.addWidget(self.speak_button, 2)

        self.favorite_button = QPushButton("⭐  Favorite")
        self.favorite_button.clicked.connect(self.toggle_favorite)
        self.favorite_button.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            " stop:0 #2a2000, stop:1 #1c1600);"
            " border: 1px solid #5a4200; border-radius: 8px; color: #FFD700; font-weight: 600; }"
            "QPushButton:hover { border-color: #FFD700; color: #FFE84D; background: #2e2200; }"
        )
        button_row.addWidget(self.favorite_button, 1)

        self.listen_button = QPushButton("👂  Listen")
        self.listen_button.setCheckable(True)
        self.listen_button.clicked.connect(self.toggle_wake_listener)
        self.listen_button.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            " stop:0 #141a14, stop:1 #0e130e);"
            " border: 1px solid #1f3d1f; border-radius: 8px; color: #00FF6A; font-weight: 600; }"
            "QPushButton:hover { border-color: #00FF6A; color: #5AFFAA; background: #192319; }"
            "QPushButton:checked { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            " stop:0 #0a2e14, stop:1 #071e0d);"
            " border: 2px solid #00FF6A; color: #00FF6A; }"
        )
        button_row.addWidget(self.listen_button, 1)
        layout.addLayout(button_row)

        # Status + hotkey compact row
        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        self.wake_status_label = QLabel("Wake-word: off")
        self.wake_status_label.setStyleSheet("color: #444444; font-size: 10px; border: none;")
        info_row.addWidget(self.wake_status_label, 1)
        self.hotkey_label = QLabel(f"Hotkey: {self.settings.get('hotkey', 'ctrl+alt+space')}")
        self.hotkey_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.hotkey_label.setStyleSheet("color: #444444; font-size: 10px; border: none;")
        info_row.addWidget(self.hotkey_label)
        layout.addLayout(info_row)

        # Wake-word usage instructions — shown only when listening is active
        self.wake_instructions_label = QLabel()
        self.wake_instructions_label.setWordWrap(True)
        self.wake_instructions_label.setStyleSheet(
            "QLabel { background: #0d1f12; border: 1px solid #1f6b35; border-radius: 6px;"
            " color: #7ee89a; font-size: 11px; padding: 8px 10px; }"
        )
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
        fav_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #9A4DFF; border: none; margin-top: 6px; letter-spacing: 0.5px;")
        layout.addWidget(fav_title)

        self.favorites_list = QListWidget()
        self.favorites_list.itemClicked.connect(self.on_history_item_selected)
        self.favorites_list.setMinimumHeight(100)
        self.favorites_list.setStyleSheet(LIST_STYLE)
        layout.addWidget(self.favorites_list, 1)

        return frame

    def _build_soundboard_card(self) -> QWidget:
        frame = QWidget()
        frame.setObjectName("card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        self._sb_tabs = QTabWidget()
        self._sb_tabs.setTabsClosable(False)
        self._sb_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #2a2a2a; border-radius: 8px; background: #121212; }"
            "QTabBar { margin-right: 84px; }"
            "QTabBar::tab { background: #1E1E1E; color: #666666; padding: 7px 14px;"
            " font-size: 11px; font-weight: 700; letter-spacing: 0.5px;"
            " border: 1px solid #2a2a2a; border-bottom: none; border-radius: 4px 4px 0 0; margin-right: 2px; }"
            "QTabBar::tab:selected { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);"
            " color: #fff; border-color: #3A7BFF; }"
            "QTabBar::tab:hover:!selected { background: #252525; color: #E0E0E0; border-color: #9A4DFF; }"
        )

        # Right-click context menu on tab bar
        self._sb_tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._sb_tabs.tabBar().customContextMenuRequested.connect(self._sb_tab_ctx_menu)

        # Corner buttons — height locked to tab bar height so they don't overflow
        _corner_wrap = QWidget()
        _corner_wrap.setFixedHeight(28)
        _corner_lay = QHBoxLayout(_corner_wrap)
        _corner_lay.setContentsMargins(0, 2, 4, 2)
        _corner_lay.setSpacing(4)

        self._sb_edit_btn = QPushButton("Edit")
        self._sb_edit_btn.setCheckable(True)
        self._sb_edit_btn.setFixedWidth(46)
        self._sb_edit_btn.setToolTip("Muokkaustila: vedä kuva/ääni napin päälle tai oikeaklikkaa")
        self._sb_edit_btn.setStyleSheet(
            "QPushButton { background: #1E1E2A; color: #666688; border: 1px solid #333344;"
            " border-radius: 4px; font-size: 10px; font-weight: 700; }"
            "QPushButton:hover:!checked { background: #252535; border-color: #9A4DFF; color: #AAAACC; }"
            "QPushButton:checked { background: #1A0E00; color: #FF9A00; border: 2px solid #FF9A00; }"
        )
        self._sb_edit_btn.toggled.connect(self._sb_toggle_edit_mode)
        _corner_lay.addWidget(self._sb_edit_btn)

        add_page_btn = QPushButton("+")
        add_page_btn.setFixedWidth(26)
        add_page_btn.setToolTip("Lisää sivu (max 10)")
        add_page_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF);"
            " color: #fff; border: none; border-radius: 4px; font-size: 15px; font-weight: bold; padding: 0; }"
            "QPushButton:hover { background: #9A4DFF; }"
            "QPushButton:pressed { background: #1a1a1a; border: 1px solid #3A7BFF; }"
        )
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
        while len(slots) < 56:
            slots.append({"name": f"Slot {len(slots)+1}", "file": "", "image": ""})

        page_btns: list[SoundboardButton] = []
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(6)
        grid.setContentsMargins(6, 6, 6, 6)

        for i in range(56):
            btn = SoundboardButton(pi, i)
            if slots[i]:
                btn.set_data(slots[i])
            btn.clicked_play.connect(self._sb_play_handler)
            btn.data_changed.connect(self._sb_data_handler)
            page_btns.append(btn)
            row, col = divmod(i, 14)
            grid.addWidget(btn, row, col)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._soundboard_buttons.append(page_btns)
        self._sb_tabs.addTab(scroll, name)

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
        elif act == delete_act:
            self._sb_remove_page(index)

    def _sb_play_handler(self, slot_index: int):
        sender_btn = self.sender()
        for pi, page_btns in enumerate(self._soundboard_buttons):
            if sender_btn in page_btns:
                self._play_soundboard_slot(pi, slot_index)
                return

    def _sb_data_handler(self, slot_index: int):
        sender_btn = self.sender()
        for pi, page_btns in enumerate(self._soundboard_buttons):
            if sender_btn in page_btns:
                self._save_soundboard()
                return

    def _sb_toggle_edit_mode(self, enabled: bool):
        SoundboardButton.set_edit_mode(enabled)
        if enabled:
            self.append_status("Soundboard muokkaustila ON — vedä kuva/ääni napin päälle tai oikeaklikkaa")
        else:
            self.append_status("Soundboard muokkaustila OFF")

    def _build_voice_fx_card(self) -> QWidget:
        frame, layout = self._make_card("Voice FX — real-time voice morphing via virtual output")

        # Enable toggle
        self._fx_toggle = QPushButton("Enable Voice FX")
        self._fx_toggle.setCheckable(True)
        self._fx_toggle.setStyleSheet(
            "QPushButton { background: #1E1E1E; border: 1px solid #2a2a2a; color: #888888; }"
            "QPushButton:hover { border-color: #3A7BFF; color: #E0E0E0; }"
            "QPushButton:checked { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #003A1A,stop:1 #00270F);"
            " border: 1px solid #00FF6A; color: #00FF6A; }"
        )
        self._fx_toggle.clicked.connect(self._toggle_voice_fx)
        layout.addWidget(self._fx_toggle)

        # FX output device selector
        out_row = QHBoxLayout()
        out_lbl = QLabel("FX OUTPUT:")
        out_lbl.setStyleSheet("border: none; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; color: #666666;")
        out_row.addWidget(out_lbl)
        self._fx_output_combo = QComboBox()
        self._populate_fx_output_combo()
        out_row.addWidget(self._fx_output_combo, 1)
        layout.addLayout(out_row)

        # Hear myself toggle + monitor device selector
        hear_row = QHBoxLayout()
        self._hear_myself_btn = QPushButton("Hear Myself: OFF")
        self._hear_myself_btn.setCheckable(True)
        self._hear_myself_btn.setChecked(self.settings.get("voice_fx_hear_myself", False))
        self._hear_myself_btn.setStyleSheet(
            "QPushButton { background: #1E1E1E; border: 1px solid #2a2a2a; color: #888888;"
            " font-size: 11px; font-weight: 700; padding: 5px 10px; }"
            "QPushButton:hover { border-color: #FF9500; color: #E0E0E0; }"
            "QPushButton:checked { background: #2A1A00; border: 1px solid #FF9500; color: #FF9500; }"
        )
        self._hear_myself_btn.clicked.connect(self._toggle_hear_myself)
        hear_row.addWidget(self._hear_myself_btn)
        self._fx_monitor_combo = QComboBox()
        self._populate_fx_monitor_combo()
        hear_row.addWidget(self._fx_monitor_combo, 1)
        layout.addLayout(hear_row)
        if self.settings.get("voice_fx_hear_myself", False):
            self._hear_myself_btn.setText("Hear Myself: ON")

        # Preset buttons
        presets_lbl = QLabel("PRESET:")
        presets_lbl.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.5px; color: #3A7BFF; border: none; margin-top: 6px;")
        layout.addWidget(presets_lbl)

        preset_grid = QGridLayout()
        preset_grid.setSpacing(6)
        preset_items = list(VoiceEffectProcessor.PRESETS.keys())
        for i, preset in enumerate(preset_items):
            btn = QPushButton(preset)
            btn.setCheckable(True)
            btn.setChecked(preset == "Normal")
            btn.setStyleSheet(
                "QPushButton { background: #1E1E1E; border: 1px solid #2a2a2a;"
                " border-radius: 8px; color: #888888; font-weight: 600; padding: 7px 10px; }"
                "QPushButton:hover { background: #252525; border-color: #9A4DFF; color: #E0E0E0; }"
                "QPushButton:checked { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,"
                " stop:0 #3A7BFF, stop:1 #9A4DFF); border: 2px solid #3A7BFF; color: #fff; }"
            )
            btn.clicked.connect(lambda checked, p=preset: self._select_fx_preset(p))
            preset_grid.addWidget(btn, i // 2, i % 2)
            self._fx_preset_buttons[preset] = btn
        layout.addLayout(preset_grid)

        layout.addStretch()

        hint = QLabel("Tip: select VB-Cable or Voicemod as FX Output\nso the morphed audio reaches your games/apps.")
        hint.setStyleSheet("color: #444444; font-size: 11px; border: none; margin-top: 4px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return frame

    def _populate_fx_output_combo(self):
        self._fx_output_combo.clear()
        saved = self.settings.get("voice_fx_output_device")
        virtual_kw = ("cable", "voicemeeter", "voicemod", "virtual")
        virtual, other = [], []
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_output_channels"] > 0:
                    n = dev["name"]
                    if any(k in n.lower() for k in virtual_kw):
                        virtual.append((i, n))
                    elif not n.startswith("{"):
                        other.append((i, n))
        except Exception:
            pass
        for i, n in virtual:
            self._fx_output_combo.addItem(f"🔌 {n}", i)
        for i, n in other[:8]:
            self._fx_output_combo.addItem(f"🔊 {n}", i)
        if saved is not None:
            for idx in range(self._fx_output_combo.count()):
                if self._fx_output_combo.itemData(idx) == saved:
                    self._fx_output_combo.setCurrentIndex(idx)
                    break

    def _populate_fx_monitor_combo(self):
        self._fx_monitor_combo.clear()
        saved = self.settings.get("voice_fx_monitor_device")
        virtual_kw = ("cable", "voicemeeter", "voicemod", "virtual")
        real_outputs = []
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev["max_output_channels"] > 0:
                    n = dev["name"]
                    if not n.startswith("{") and not any(k in n.lower() for k in virtual_kw):
                        real_outputs.append((i, n))
        except Exception:
            pass
        for i, n in real_outputs[:10]:
            self._fx_monitor_combo.addItem(f"🎧 {n}", i)
        if saved is not None:
            for idx in range(self._fx_monitor_combo.count()):
                if self._fx_monitor_combo.itemData(idx) == saved:
                    self._fx_monitor_combo.setCurrentIndex(idx)
                    break

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
        title_lbl.setStyleSheet("font-weight: 700; font-size: 12px; color: #3A7BFF; letter-spacing: 0.5px; border: none;")
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
            "QScrollArea { border: 1px solid #2a2a2a; border-radius: 8px; background: #111111; }"
        )
        container = QWidget()
        container.setStyleSheet("background: #111111;")
        self._device_rows_layout = QVBoxLayout(container)
        self._device_rows_layout.setSpacing(2)
        self._device_rows_layout.setContentsMargins(4, 4, 4, 4)
        self._device_rows_layout.addStretch()  # push items up
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Input device row at the bottom
        input_row = QHBoxLayout()
        input_lbl = QLabel("INPUT MIC:")
        input_lbl.setStyleSheet("border: none; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; color: #666666;")
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
        frame.setStyleSheet(
            "QFrame { background: #0e0e0e; border: 1px solid #2a2a2a; border-radius: 8px; }"
        )
        outer = QHBoxLayout(frame)
        outer.setContentsMargins(10, 4, 10, 4)
        outer.setSpacing(0)

        # MIC section (always visible)
        mic_lbl = QLabel("MIC")
        mic_lbl.setStyleSheet("color: #00FF6A; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; border: none; min-width: 26px;")
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
        self.mic_db_label.setStyleSheet(
            "color: #444444; font-size: 9px; font-family: Consolas; border: none;"
        )
        self.mic_db_label.setFixedWidth(34)
        self.mic_db_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        outer.addWidget(self.mic_db_label)

        sep0 = QFrame()
        sep0.setFrameShape(QFrame.Shape.VLine)
        sep0.setFixedWidth(1)
        sep0.setStyleSheet("background: #2a2a2a; border: none;")
        outer.addSpacing(6)
        outer.addWidget(sep0)
        outer.addSpacing(6)

        lbl = QLabel("OUT")
        lbl.setStyleSheet("color: #3A7BFF; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; border: none; min-width: 26px;")
        outer.addWidget(lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #2a2a2a; border: none;")
        outer.addWidget(sep)
        outer.addSpacing(8)

        # Inner container rebuilt by _refresh_bottom_meters
        self._mb_inner = QWidget()
        self._mb_inner.setStyleSheet("background: transparent;")
        self._mb_inner_lay = QHBoxLayout(self._mb_inner)
        self._mb_inner_lay.setContentsMargins(0, 0, 0, 0)
        self._mb_inner_lay.setSpacing(14)
        self._mb_placeholder = QLabel("No output devices selected")
        self._mb_placeholder.setStyleSheet("color: #333333; font-size: 11px; border: none;")
        self._mb_inner_lay.addWidget(self._mb_placeholder)
        self._mb_inner_lay.addStretch()
        outer.addWidget(self._mb_inner, 1)

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
            name_lbl.setStyleSheet("color: #555555; font-size: 9px; border: none;")

            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setMinimumWidth(70)
            bar.setStyleSheet(METER_STYLE_OUT)

            db_lbl = QLabel("-∞")
            db_lbl.setStyleSheet(
                "color: #444444; font-size: 9px; font-family: Consolas; border: none;"
            )
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
            "QWidget { background: #1A1A1A; border: 1px solid #2a2a2a; border-radius: 8px; }"
        )
        row = QHBoxLayout(container)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(8)

        cb = QCheckBox()
        cb.setChecked(was_selected)
        cb.stateChanged.connect(self.on_output_device_changed)

        name_lbl = QLabel(display_name)
        name_lbl.setStyleSheet("color: #C0C0C0; font-size: 12px; border: none;")
        name_lbl.setMinimumWidth(180)
        name_lbl.setMaximumWidth(280)
        name_lbl.setToolTip(full_name)

        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(12)
        bar.setStyleSheet(METER_STYLE_OUT)

        db_lbl = QLabel("-∞ dB")
        db_lbl.setStyleSheet("color: #555555; font-family: 'Consolas', monospace; font-size: 11px; border: none;")
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

    def update_translated(self, text: str):
        self.sig_status.emit(f"→ {text}")
        QTimer.singleShot(0, lambda: self.translated_label.setText(f"Translated: {text}"))

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

        # Prioritize routing-capable devices (VoiceMeeter, virtual, Rodecaster, etc.)
        routing_devices = [
            (index, name) for index, name in devices
            if any(keyword in name.lower() for keyword in ["voicemeeter", "virtual", "vb-audio", "voice", "rodecaster", "rode caster"])
        ]
        other_devices = [
            (index, name) for index, name in devices
            if not any(keyword in name.lower() for keyword in ["voicemeeter", "virtual", "vb-audio", "voice", "rodecaster", "rode caster"])
        ]

        for index, name in routing_devices:
            self._add_device_row(index, f"🎛️ {name}", name, was_selected=(index in saved_devices))
        for index, name in other_devices[:8]:
            self._add_device_row(index, f"🔊 {name}", name, was_selected=(index in saved_devices))

        device_count = len(routing_devices) + min(len(other_devices), 8)
        self.append_status(f"Found {device_count} output devices ({len(routing_devices)} routing-capable)")
        self._refresh_bottom_meters()

    def refresh_all_devices(self):
        self.populate_output_devices()
        self.populate_input_devices()

    def populate_input_devices(self):
        self.input_device_combo.clear()
        devices = list_input_devices()
        if not devices:
            self.input_device_combo.addItem("No audio input devices detected", -1)
            self.append_status("No audio input devices detected")
            return

        _virtual_kw = ["voicemeeter", "vb-audio", "voicemod"]
        _exclude_kw = ["bthhfenum", "microsoft sound mapper", "primary sound capture"]

        # Deduplicate by friendly name, prefer highest sample rate
        best: dict[str, tuple] = {}  # friendly_name -> (index, name, samplerate)
        for index, name in devices:
            n = name.lower()
            # Skip GUID-style names and system entries
            if name.startswith("{") or any(k in n for k in _exclude_kw):
                continue
            try:
                sr = sd.query_devices(index)["default_samplerate"]
            except Exception:
                sr = 0
            # Use full name as key for dedup
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

        # Sort physical: Rode first, then others alphabetically
        physical.sort(key=lambda x: (0 if "rode" in x[1].lower() else 1, x[1]))

        for index, name in physical:
            self.input_device_combo.addItem(f"🎤 {name}", index)
        for index, name in virtual:
            self.input_device_combo.addItem(f"🔌 {name}", index)

        self.append_status(f"Found {self.input_device_combo.count()} input devices ({len(physical)} physical, {len(virtual)} virtual)")

        # Restore previously selected input device
        saved_input_device = self.history_data.get("selected_input_device")
        if saved_input_device is not None:
            # Find the index in the combo box that matches the saved device index
            for i in range(self.input_device_combo.count()):
                if self.input_device_combo.itemData(i) == saved_input_device:
                    self.input_device_combo.setCurrentIndex(i)
                    break

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
        """Called when a device checkbox is toggled — persist selection."""
        selected_devices = self.get_selected_devices()
        self.history_data["selected_output_devices"] = selected_devices or []
        save_history_data(self.history_data)
        for w in self._device_widgets.values():
            if not w["checkbox"].isChecked():
                w["meter"].setValue(0)
                w["db_label"].setText("-∞ dB")
        self._refresh_bottom_meters()

    def on_input_device_changed(self):
        selected_device = self.get_selected_input_device()
        if selected_device is not None:
            self.history_data["selected_input_device"] = selected_device
            save_history_data(self.history_data)
        self._stop_mic_monitor()
        self._start_mic_monitor()

    def register_hotkey(self):
        # Unregister previous hotkey first (if any)
        if self._registered_hotkey:
            try:
                keyboard.remove_hotkey(self._registered_hotkey)
            except Exception:
                pass
            self._registered_hotkey = None

        hk = self.settings.get("hotkey", "ctrl+alt+space")
        try:
            self._registered_hotkey = keyboard.add_hotkey(hk, self.on_hotkey_triggered)
        except Exception as exc:
            self.append_status(f"Hotkey registration failed: {exc}")

    def apply_settings_changes(self):
        """Re-apply settings after the dialog saves them."""
        _apply_custom_languages_to_globals(self.settings.get("custom_languages", []))
        self.rebuild_langbox()
        new_lang = self.settings.get("default_target_lang", "Auto")
        if self.langbox.findText(new_lang) >= 0:
            self.langbox.setCurrentText(new_lang)
        new_backend = self.settings.get("default_tts_backend", DEFAULT_TTS_BACKEND)
        if self.backend_combo.findText(new_backend) >= 0:
            self.backend_combo.setCurrentText(new_backend)

        self.hotkey_label.setText(f"Global hotkey: {self.settings.get('hotkey', 'ctrl+alt+space')}")
        self.register_hotkey()

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
            ok = self._start_wake_listener()
            if ok:
                self.listen_button.setText("⏹  Stop")
                self.listen_button.setChecked(True)
                kw = self.settings.get("wake_keyword", "jarvis")
                custom = self.settings.get("wake_custom_ppn_path", "")
                kw_display = os.path.basename(custom) if custom else kw
                self.wake_status_label.setText(f"Listening: {kw_display}")
                self._mic_peak_ref[0] = 0.0
                self._stop_mic_monitor()
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
            transcript = transcribe_audio_wav(wav_bytes)
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

        self.record_button.setText("🔴")
        self.record_button.setStyleSheet(
            "QPushButton { background: rgba(160,40,40,220); border: 1px solid #cc4444;"
            " border-radius: 8px; font-size: 18px; padding: 0; }"
        )
        self.append_status(f"🎤 Recording from: {input_device_name}")

    def _stop_recording(self):
        self.is_recording = False
        self.record_button.setEnabled(False)
        self.record_button.setText("⏳")
        self.record_button.setStyleSheet(
            "QPushButton { background: rgba(60,60,60,200); border: 1px solid #555;"
            " border-radius: 8px; font-size: 18px; padding: 0; }"
        )

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

            def _audio_cb(indata, frame_count, time_info, status):
                # No Qt calls here — PortAudio thread must stay clean
                peak = float(np.max(np.abs(indata)))
                if peak > max_peak_ref[0]:
                    max_peak_ref[0] = peak
                if peak > self._mic_peak_ref[0]:
                    self._mic_peak_ref[0] = peak
                frames.append(indata.copy())

            with sd.InputStream(device=input_device_index, channels=channels,
                                samplerate=sample_rate, blocksize=blocksize,
                                dtype="float32", callback=_audio_cb):
                while self.is_recording:
                    time.sleep(0.05)

            if not frames:
                self.append_status("No audio data recorded")
                return

            total_seconds = (len(frames) * blocksize) / sample_rate

            # Concatenate and flatten to 1D float32
            audio_data = np.concatenate(frames, axis=0).flatten()

            # Normalize to [-1, 1]
            max_val = np.max(np.abs(audio_data))
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

            self.append_status(f"Sending {total_seconds:.1f}s audio to Whisper...")
            try:
                transcribed = transcribe_audio_wav(wav_bytes)
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
        if not self.wake_listener.is_running():
            self._start_mic_monitor()
        self.record_button.setEnabled(True)
        self.record_button.setText("🎤")
        self.record_button.setStyleSheet(
            "QPushButton { background: rgba(40,52,80,200); border: 1px solid #4f5f7f;"
            " border-radius: 8px; font-size: 18px; padding: 0; }"
            "QPushButton:hover { background: rgba(80,100,150,220); }"
            "QPushButton:disabled { opacity: 0.4; }"
        )

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
        dev = self.get_selected_input_device()
        if dev is None:
            return
        try:
            def _cb(indata, frames, time_info, status):
                peak = float(np.max(np.abs(indata)))
                if peak > self._mic_peak_ref[0]:
                    self._mic_peak_ref[0] = peak
            self._mic_monitor_stream = sd.InputStream(
                device=dev, channels=1, samplerate=16000,
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
        menu.setStyleSheet(
            "QMenu { background: #1A1A1A; border: 1px solid #2a2a2a; border-radius: 8px; color: #E0E0E0; }"
            "QMenu::item { padding: 7px 20px; }"
            "QMenu::item:selected { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #3A7BFF,stop:1 #9A4DFF); color: #fff; }"
            "QMenu::separator { height: 1px; background: #2a2a2a; margin: 4px 0; }"
        )
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
            "© 2026 Juha Lempiäinen. All rights reserved.\n\n"
            "Speech-to-text: OpenAI Whisper\n"
            "Translation: GPT-4.1-mini\n"
            "TTS: Edge TTS (free) / ElevenLabs\n"
            "Voice FX: pyrubberband / scipy\n"
            "Stream Deck: Elgato StreamDeck SDK"
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
        path = data.get("file", "")
        if not path or not os.path.exists(path):
            self.append_status(f"Soundboard p{page_index+1} slot {slot_index+1}: ei ääntä (oikeaklikkaa)")
            return

        # Stop any currently playing soundboard sound
        self._sb_play_id += 1
        my_play_id = self._sb_play_id
        sd.stop()
        if self._sb_playing_btn and self._sb_playing_btn is not btn:
            old_btn = self._sb_playing_btn
            QTimer.singleShot(0, lambda: old_btn.set_playing(False))
        self._sb_playing_btn = btn

        def _play():
            try:
                QTimer.singleShot(0, lambda: btn.set_playing(True))
                wav = self._load_audio_as_wav(path)
                if self._sb_play_id == my_play_id:
                    play_wav_bytes(wav, device_indices=self.get_selected_devices(),
                                   level_callback=self.update_output_level)
                self.update_output_level(0.0)
            except Exception as e:
                if self._sb_play_id == my_play_id:
                    self.append_status(f"Soundboard error: {e}")
            finally:
                if self._sb_play_id == my_play_id:
                    QTimer.singleShot(0, lambda: btn.set_playing(False))

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
        for pi, page_btns in enumerate(self._soundboard_buttons):
            name = self._sb_tabs.tabText(pi)
            pages.append({"name": name, "slots": [b.get_data() for b in page_btns]})
        self.settings["soundboard_pages"] = pages
        save_settings(self.settings)

    # ============ Voice FX ============

    def _toggle_voice_fx(self):
        if self._fx_toggle.isChecked():
            in_dev = self.get_selected_input_device()
            out_dev = self._fx_output_combo.currentData()
            if in_dev is None:
                self.append_status("Voice FX: select a microphone first")
                self._fx_toggle.setChecked(False)
                return
            if out_dev is None:
                self.append_status("Voice FX: select an output device first")
                self._fx_toggle.setChecked(False)
                return
            self.settings["voice_fx_output_device"] = out_dev
            save_settings(self.settings)
            self._voice_fx.set_preset(self._current_fx_preset)
            mon_dev = self._fx_monitor_combo.currentData()
            hear_on = self._hear_myself_btn.isChecked()
            self._voice_fx.set_monitor(mon_dev, hear_on)
            self._voice_fx.start(in_dev, out_dev)
            self._fx_toggle.setText("Voice FX: ON")
        else:
            self._voice_fx.stop()
            self._fx_toggle.setText("Enable Voice FX")

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
        elif action.startswith("lang_"):
            lang = action[5:]
            idx = self.langbox.findText(lang)
            if idx >= 0:
                self.langbox.setCurrentIndex(idx)
        elif action == "sb_page_next":
            n = self._sb_tabs.count()
            self._sb_tabs.setCurrentIndex((self._sb_tabs.currentIndex() + 1) % n)
        elif action == "sb_page_prev":
            n = self._sb_tabs.count()
            self._sb_tabs.setCurrentIndex((self._sb_tabs.currentIndex() - 1) % n)
        elif action.startswith("soundboard_"):
            parts = action[11:].split("_")
            if len(parts) == 2:
                # uusi muoto: soundboard_{page}_{slot}
                self._play_soundboard_slot(int(parts[0]), int(parts[1]))
            else:
                # vanha muoto: soundboard_{slot} -> käyttää nykyistä sivua
                self._play_soundboard_slot(self._sb_tabs.currentIndex(), int(parts[0]))
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
                    slots.append({
                        "name": slot.get("name", f"Slot {si+1}"),
                        "has_file": bool(slot.get("file")),
                        "has_image": bool(img and os.path.exists(img)),
                        "image_path": img if img and os.path.exists(img) else "",
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
        if action == "sb_page_next":
            n = self._sb_tabs.count()
            cur = self._sb_tabs.currentIndex()
            nxt = (cur + 1) % n
            name = self._sb_tabs.tabText(nxt).strip()
            return (f"-> {name[:8]}", False)
        if action == "sb_page_prev":
            n = self._sb_tabs.count()
            cur = self._sb_tabs.currentIndex()
            prv = (cur - 1) % n
            name = self._sb_tabs.tabText(prv).strip()
            return (f"<- {name[:8]}", False)
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

    # ============ App close ============

    def closeEvent(self, event):
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
    global OPENAI_API_KEY, client
    from PyQt6.QtWidgets import (
        QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QFileDialog, QScrollArea,
        QComboBox as _QComboBox, QPushButton as _QPushButton, QHBoxLayout as _QHBoxLayout,
        QListWidget as _QListWidget,
    )

    dlg = QDialog(parent_app)
    dlg.setWindowTitle("Voice Royale — Asetukset")
    dlg.resize(860, 660)
    dlg.setMinimumSize(700, 520)
    dlg.setStyleSheet(parent_app.styleSheet() + """
        QTabWidget::pane { border: 1px solid #2a2a3a; border-radius: 0 8px 8px 8px;
            background: #111118; padding: 4px; }
        QTabBar::tab { background: #1A1A26; color: #666680; padding: 9px 22px;
            font-size: 12px; font-weight: 700; letter-spacing: 0.4px;
            border: 1px solid #2a2a3a; border-bottom: none;
            border-radius: 6px 6px 0 0; margin-right: 3px; }
        QTabBar::tab:selected { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,
            stop:0 #3A7BFF, stop:1 #9A4DFF); color: #fff; border-color: #3A7BFF; }
        QTabBar::tab:hover:!selected { background: #222232; color: #C0C0E0;
            border-color: #9A4DFF; }
        QScrollArea { border: none; background: transparent; }
        QLineEdit { background: #18182A; border: 1px solid #2E2E48;
            border-radius: 7px; color: #E0E0F0; padding: 7px 12px;
            font-size: 13px; min-height: 18px; }
        QLineEdit:focus { border-color: #7A4DFF; background: #1C1C32; }
        QLineEdit:disabled { color: #444455; background: #141420; }
        QComboBox { background: #18182A; border: 1px solid #2E2E48; border-radius: 7px;
            color: #E0E0F0; padding: 7px 12px; font-size: 13px; min-height: 18px; }
        QComboBox:focus { border-color: #7A4DFF; }
        QComboBox::drop-down { border: none; width: 22px; }
        QComboBox QAbstractItemView { background: #1A1A2A; border: 1px solid #2E2E48;
            color: #E0E0F0; selection-background-color: #3A7BFF; padding: 4px; }
        QPushButton { background: #1E1E30; border: 1px solid #2E2E48; border-radius: 7px;
            color: #A0A0C0; padding: 7px 16px; font-size: 12px; font-weight: 600; }
        QPushButton:hover { background: #272740; border-color: #9A4DFF; color: #E0E0FF; }
        QPushButton:pressed { background: #0e0e1e; border-color: #3A7BFF; }
        QListWidget { background: #18182A; border: 1px solid #2E2E48; border-radius: 7px;
            color: #E0E0F0; font-size: 12px; padding: 4px; }
        QListWidget::item:selected { background: #3A7BFF; color: #fff; border-radius: 4px; }
        QDialogButtonBox QPushButton { min-width: 90px; padding: 8px 20px; font-size: 13px; }
    """)

    settings = dict(parent_app.settings)

    # ── shared helpers ────────────────────────────────────────────────
    LABEL_STYLE = "color: #9090B8; font-size: 12px; font-weight: 600;"
    DESC_STYLE  = "color: #5A6A8A; font-size: 11px; padding: 2px 0 10px 0; line-height: 150%;"

    def _desc(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(DESC_STYLE)
        lbl.setWordWrap(True)
        return lbl

    def _header(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #C0C0E8; font-size: 13px; font-weight: 700; letter-spacing: 0.4px;"
            " padding: 14px 0 6px 0; border-bottom: 1px solid #2A2A42; margin-bottom: 2px;"
        )
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
    # TAB 1 — Käännös & Ääni
    # ══════════════════════════════════════════════════════════════════
    f1 = _make_form()
    f1.addRow(_header("Käännösmoottori"))

    trans_backend_combo = _QComboBox()
    for b in ("Google (free)", "DeepL", "OpenAI"):
        trans_backend_combo.addItem(b)
    trans_backend_combo.setCurrentText(settings.get("translation_backend", "Google (free)"))
    f1.addRow(_lbl("Käännösmoottori:"), trans_backend_combo)
    f1.addRow("", _desc(
        "Google (free) — ei tarvitse API-avainta, toimii heti.\n"
        "DeepL — laadukas käännös, vaatii ilmaisen avaimen (deepl.com).\n"
        "OpenAI — GPT-4.1-mini, vaatii maksullisen OpenAI-avaimen."
    ))

    api_key_widget, api_key_edit = _secret_row(OPENAI_API_KEY, "sk-...")
    f1.addRow(_lbl("OpenAI API-avain:"), api_key_widget)
    f1.addRow("", _desc(
        "Tarvitaan puheentunnistukseen (Whisper) ja käännökseen kun moottori = OpenAI.\n"
        "Hae avain: platform.openai.com/api-keys  •  Tallennetaan credentials.env-tiedostoon."
    ))

    deepl_key_widget, deepl_key_edit = _secret_row(
        settings.get("deepl_api_key", ""), "DeepL API-avain — päättyy :fx (ilmainen)"
    )
    f1.addRow(_lbl("DeepL API-avain:"), deepl_key_widget)
    f1.addRow("", _desc(
        "Ilmainen avain: rekisteröidy osoitteessa deepl.com/pro#developer → Authentication Key.\n"
        "Ilmainen tili: 500 000 merkkiä/kk. Avain päättyy :fx."
    ))

    def _update_deepl_visibility():
        is_deepl = trans_backend_combo.currentText() == "DeepL"
        deepl_key_widget.setVisible(is_deepl)
    trans_backend_combo.currentTextChanged.connect(lambda _: _update_deepl_visibility())
    _update_deepl_visibility()

    f1.addRow(_header("Puhesynteesi (TTS)"))

    backend_combo = _QComboBox()
    for b in ("Edge TTS (free)", "ElevenLabs"):
        backend_combo.addItem(b)
    backend_combo.setCurrentText(settings.get("default_tts_backend", DEFAULT_TTS_BACKEND))
    f1.addRow(_lbl("TTS-moottori:"), backend_combo)
    f1.addRow("", _desc(
        "Edge TTS (free) — Microsoftin neuraaliäänet, ei tiliä tarvita, hyvä laatu.\n"
        "ElevenLabs — erittäin realistinen AI-ääni, vaatii maksullisen tilin ja API-avaimen."
    ))

    lang_combo = _QComboBox()
    for lang in LANGS.keys():
        lang_combo.addItem(lang)
    lang_combo.setCurrentText(settings.get("default_target_lang", "Auto"))
    f1.addRow(_lbl("Oletuskohde­kieli:"), lang_combo)
    f1.addRow("", _desc(
        "Kieli, jolle teksti tai puhe käännetään oletuksena. "
        "'Auto' tunnistaa puhutun kielen ja kääntää englanniksi. "
        "Voit vaihtaa kielen myös pääikkunassa lennossa."
    ))

    # ══════════════════════════════════════════════════════════════════
    # TAB 2 — Wake Word
    # ══════════════════════════════════════════════════════════════════
    f2 = _make_form()
    f2.addRow(_header("Aktivointisana"))

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

    f2.addRow(_lbl("Wake-sana:"), keyword_combo)
    f2.addRow("", _desc(
        "Sana, jonka sanominen käynnistää hands-free-äänityksen.\n"
        "Valitse listasta tai kirjoita oma — suomen kielen sanat toimivat myös (esim. 'hei tietokone').\n"
        "Ilman Picovoice-avainta käytetään Whisperia tunnistukseen (pieni viive, toimii offline).\n"
        "Picovoice-avaimella (ilmainen) Porcupine tunnistaa sanan välittömästi ilman CPU-kuormaa."
    ))

    seconds_edit = QLineEdit(str(settings.get("wake_command_seconds", 6.0)))
    seconds_edit.setPlaceholderText("esim. 6.0")
    seconds_edit.setMaximumWidth(120)
    f2.addRow(_lbl("Tallennusaika (s):"), seconds_edit)
    f2.addRow("", _desc(
        "Kuinka monta sekuntia äänitetään wake-sanan jälkeen. "
        "Kasvata (esim. 10 s) pitkille lauseille tai hitaalle puheelle. "
        "Laske (esim. 3 s) nopeiden yksisanaisten komentojen käyttöön."
    ))

    f2.addRow(_header("Picovoice (valinnainen — ilmainen)"))

    access_key_edit = QLineEdit(settings.get("picovoice_access_key", ""))
    access_key_edit.setPlaceholderText("Liitä ilmainen avain osoitteesta console.picovoice.ai")
    f2.addRow(_lbl("Picovoice AccessKey:"), access_key_edit)
    f2.addRow("", _desc(
        "Ilmainen henkilökohtainen avain — console.picovoice.ai (ei luottokorttia tarvita).\n"
        "Mahdollistaa Porcupine offline -aktivointisanatunnistuksen: välitön vaste, ei nettiä tarvita.\n"
        "Jätä tyhjäksi käyttääksesi Whisper-pohjaista tunnistusta."
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
    f2.addRow(_lbl("Oma .ppn-tiedosto:"), custom_widget)
    f2.addRow("", _desc(
        "OMA AKTIVOINTISANA (.ppn):\n"
        "1. Luo ilmainen tili: console.picovoice.ai\n"
        "2. Porcupine → Train a custom model\n"
        "3. Kirjoita haluamasi aktivointifraasi (esim. 'hey router', 'aloita')\n"
        "4. Valitse alusta: Windows → Train → lataa .ppn-tiedosto\n"
        "5. Liitä Picovoice AccessKey yllä, selaa .ppn-tiedosto tähän\n"
        "6. Tallenna asetukset ja paina Start Listening"
    ))

    # ══════════════════════════════════════════════════════════════════
    # TAB 3 — Kielet
    # ══════════════════════════════════════════════════════════════════
    f3 = _make_form()
    f3.addRow(_header("Mukautetut kielet"))
    f3.addRow("", _desc(
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
    f3.addRow("", custom_list)

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
    f3.addRow("", add_widget)

    # ══════════════════════════════════════════════════════════════════
    # TAB 4 — Pikavalinnat & Data
    # ══════════════════════════════════════════════════════════════════
    f4 = _make_form()
    f4.addRow(_header("Pikanäppäin"))

    hotkey_edit = QLineEdit(settings.get("hotkey", "ctrl+alt+space"))
    hotkey_edit.setPlaceholderText("esim. ctrl+alt+space")
    hotkey_edit.setMaximumWidth(220)
    f4.addRow(_lbl("Global hotkey:"), hotkey_edit)
    f4.addRow("", _desc(
        "Pikanäppäin, joka toistaa tekstiruudun sisällön vaikka ikkuna on taustalla. "
        "Käytä nimiä: ctrl, alt, shift, space, f1–f12. Yhdistä +-merkillä (esim. ctrl+alt+space). "
        "Vältä OS:n tai pelin omia pikanäppäimiä."
    ))

    f4.addRow(_header("Varmuuskopio"))

    _DATA_FILES = ["app_settings.json", "speech_history.json", "credentials.env"]
    _DATA_DIRS  = ["soundboard", "favorites_audio"]

    def _export_data():
        path, _ = QFileDialog.getSaveFileName(
            dlg, "Vie data", "ai_voice_router_backup.zip", "ZIP-arkisto (*.zip)"
        )
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname in _DATA_FILES:
                    fp = os.path.join(BASE_PATH, fname)
                    if os.path.exists(fp):
                        zf.write(fp, fname)
                for dname in _DATA_DIRS:
                    dp = os.path.join(BASE_PATH, dname)
                    if os.path.isdir(dp):
                        for root_dir, _, files in os.walk(dp):
                            for f in files:
                                full = os.path.join(root_dir, f)
                                arcname = os.path.relpath(full, BASE_PATH)
                                zf.write(full, arcname)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(dlg, "Valmis", f"Data viety:\n{path}")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(dlg, "Virhe", str(e))

    def _import_data():
        path, _ = QFileDialog.getOpenFileName(
            dlg, "Tuo data", "", "ZIP-arkisto (*.zip)"
        )
        if not path:
            return
        from PyQt6.QtWidgets import QMessageBox
        ans = QMessageBox.question(
            dlg, "Korvaa data?",
            "Tämä korvaa nykyiset asetukset, historian ja soundboard-tiedostot.\nJatketaanko?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            with zipfile.ZipFile(path, "r") as zf:
                for member in zf.namelist():
                    dest = os.path.join(BASE_PATH, member)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            QMessageBox.information(
                dlg, "Tuotu",
                "Data tuotu. Käynnistä sovellus uudelleen jotta muutokset astuvat voimaan."
            )
        except Exception as e:
            QMessageBox.critical(dlg, "Virhe", str(e))

    _io_row = _QHBoxLayout()
    _io_row.setSpacing(10)
    export_btn = _QPushButton("Vie data…")
    export_btn.setToolTip("Pakkaa kaikki asetukset, historia ja soundboard-tiedostot ZIP-arkistoon")
    export_btn.clicked.connect(_export_data)
    import_btn = _QPushButton("Tuo data…")
    import_btn.setToolTip("Palauttaa aiemmin viedyn ZIP-varmuuskopion")
    import_btn.clicked.connect(_import_data)
    _io_row.addWidget(export_btn)
    _io_row.addWidget(import_btn)
    _io_row.addStretch()
    _io_widget = QWidget()
    _io_widget.setLayout(_io_row)
    f4.addRow("", _io_widget)
    f4.addRow("", _desc(
        "Vie data — pakkaa asetukset, historia, soundboard-äänet/-kuvat ja API-avaimet ZIP-tiedostoon.\n"
        "Tuo data — palauttaa ZIP-varmuuskopiosta. Vaatii sovelluksen uudelleenkäynnistyksen."
    ))

    # ══════════════════════════════════════════════════════════════════
    # TAB 5 — Stream Deck
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
        "color: #C0C0E8; font-size: 13px; font-weight: 700; border-bottom: 1px solid #2A2A42;"
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
        "color: #C0C0E8; font-size: 13px; font-weight: 700; border-bottom: 1px solid #2A2A42;"
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
        "sb_page_next": "Soundboard: seuraava sivu",
        "sb_page_prev": "Soundboard: edellinen sivu",
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
        ("keyboard",       "keyboard",        True,  "Global hotkey"),
        ("openai",         "openai",          True,  "Whisper + GPT"),
        ("pyttsx3",        "pyttsx3",         True,  "Paikallinen TTS"),
        ("edge_tts",       "edge-tts",        True,  "Edge TTS"),
        ("deep_translator","deep-translator", True,  "Google Translate"),
        ("pvporcupine",    "pvporcupine",     False, "Wake word offline (valinnainen)"),
        ("pyrubberband",   "pyrubberband",    False, "Voice FX laatu (valinnainen)"),
        ("pydub",          "pydub",           False, "MP3/OGG soundboard (valinnainen)"),
    ]

    def _pkg_status(import_name, pip_name):
        if getattr(sys, "frozen", False):
            # In frozen exe importlib.import_module can crash for native optional libs
            # Check sys.modules instead (already imported at startup) and skip re-import
            in_modules = import_name in sys.modules
            return in_modules, ("bundled" if in_modules else "")
        try:
            importlib.import_module(import_name)
            try:
                ver = importlib.metadata.version(pip_name)
            except Exception:
                ver = "?"
            return True, ver
        except Exception:
            return False, ""

    f6 = _make_form()
    f6.addRow(_header("Python-paketit"))

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
            "color: #e6edf3; background: transparent;" if ok
            else ("color: #ff8888; background: transparent;" if required
                  else "color: #8b949e; background: transparent;")
        )
        name_lbl.setFixedWidth(160)

        desc_lbl = QLabel(f"{desc}   <span style='color:#8b949e'>v{ver}</span>" if ok
                          else f"<span style='color:#8b949e'>{desc}</span>")
        desc_lbl.setStyleSheet("background: transparent; font-size: 11px;")

        row_h.addWidget(icon_lbl)
        row_h.addWidget(name_lbl)
        row_h.addWidget(desc_lbl, 1)

        label_txt = "Pakollinen" if required else "Valinnainen"
        f6.addRow(_lbl(label_txt + ":"), row_w)

    # ---- VB-Cable (siirretty tänne) ----
    f6.addRow(_header("Virtuaalimikrofoni"))

    _vbc_installed = _is_vbcable_installed()
    vbc_status_lbl = QLabel("VB-Cable: ✅ Asennettu" if _vbc_installed else "VB-Cable: ❌ Ei asennettu")
    vbc_status_lbl.setStyleSheet("color: #7fc97f; font-size: 13px;" if _vbc_installed else "color: #ff8888; font-size: 13px;")
    f6.addRow(_lbl("Tila:"), vbc_status_lbl)
    f6.addRow("", _desc(
        "VB-Audio Virtual Cable — ilmainen virtuaaliäänilaite, jolla tämän sovelluksen "
        "käännetty puhe näkyy mikrofonina peleissä ja Discord/TeamSpeak-sovelluksissa.\n"
        "Asennuksen jälkeen: aseta lähtölaite → 'CABLE Input' tässä appissa, "
        "ja mikrofoni → 'CABLE Output' pelissä tai Discordissa."
    ))

    vbc_install_btn = _QPushButton(
        "VB-Cable on jo asennettu" if _vbc_installed else "Asenna VB-Cable (Virtuaalimikrofoni)"
    )
    vbc_install_btn.setEnabled(not _vbc_installed)

    def _do_vbc_install():
        vbc_install_btn.setEnabled(False)
        vbc_install_btn.setText("Asennetaan...")

        def _vbc_status(msg):
            def _apply():
                vbc_status_lbl.setText(msg)
                vbc_status_lbl.setStyleSheet("color: #7fc97f; font-size: 13px;" if "✅" in msg else "color: #ff8888; font-size: 13px;")
                if "✅" in msg:
                    vbc_install_btn.setText("VB-Cable on jo asennettu")
                    QTimer.singleShot(800, parent_app.populate_output_devices)
                else:
                    vbc_install_btn.setEnabled(True)
                    vbc_install_btn.setText("Yritä uudelleen")
            QTimer.singleShot(0, _apply)

        threading.Thread(target=_install_vbcable, args=(_vbc_status,), daemon=True).start()

    vbc_install_btn.clicked.connect(_do_vbc_install)
    f6.addRow("", vbc_install_btn)

    tabs.addTab(_scroll_tab(f1), "  Käännös & Ääni  ")
    tabs.addTab(_scroll_tab(f2), "  Wake Word  ")
    tabs.addTab(_scroll_tab(f3), "  Kielet  ")
    tabs.addTab(_scroll_tab(f4), "  Pikavalinnat & Data  ")
    tabs.addTab(sd_scroll, "  Stream Deck  ")
    tabs.addTab(_scroll_tab(f6), "  Asennukset  ")

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
            "deepl_api_key": deepl_key_edit.text().strip(),
        }
        try:
            new_settings["wake_command_seconds"] = float(seconds_edit.text())
        except ValueError:
            new_settings["wake_command_seconds"] = 6.0
        new_settings["custom_languages"] = custom_langs

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

        parent_app.settings.update(new_settings)
        save_settings(parent_app.settings)
        parent_app.apply_settings_changes()
        parent_app.append_status("Settings saved.")


# =========================
# FIRST-RUN SETUP WIZARD
# =========================
class SetupWizard(QDialog):
    """Shown on first launch when no OPENAI_API_KEY is configured."""

    _STYLE = """
        QDialog { background: #0d1117; color: #e6edf3; font-family: "Segoe UI", sans-serif; }
        QLabel  { color: #e6edf3; }
        QPushButton {
            background: #1f6feb; color: #ffffff; border: none;
            border-radius: 6px; padding: 8px 20px;
            font-size: 13px; font-weight: bold;
        }
        QPushButton:hover    { background: #388bfd; }
        QPushButton:disabled { background: #21262d; color: #8b949e; }
        QLineEdit {
            background: #161b22; border: 1px solid #30363d;
            border-radius: 6px; color: #e6edf3;
            padding: 8px; font-size: 13px;
        }
        QLineEdit:focus { border: 1px solid #1f6feb; }
        QCheckBox { color: #8b949e; background: transparent; }
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Royale — Alkuasennus")
        self.setFixedSize(620, 540)
        self.setStyleSheet(self._STYLE)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self._api_key = ""
        # Init mic preview state before _build_ui so closeEvent is always safe
        self._wiz_peak_ref = [0.0]
        self._wiz_stop_flag = threading.Event()
        self._wiz_mic_thread = None
        self._wiz_timer = QTimer(self)
        self._wiz_rec_buf = []
        self._wiz_rec_thread = None
        self._wiz_rec_stop = threading.Event()
        self._wiz_timer.setInterval(40)
        self._build_ui()
        self._wiz_timer.timeout.connect(self._tick_wiz_mic)
        self._stack.setCurrentIndex(0)

    # ---- helpers ----

    def _header(self, title: str, subtitle: str = "") -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #161b22; border-bottom: 1px solid #30363d;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 22, 32, 18)
        lbl = QLabel(title)
        lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #e6edf3; background: transparent;")
        lay.addWidget(lbl)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet("font-size: 12px; color: #8b949e; background: transparent;")
            sub.setWordWrap(True)
            lay.addWidget(sub)
        return w

    def _back_btn(self, target: int) -> QPushButton:
        btn = QPushButton("← Takaisin")
        btn.setFixedHeight(36)
        btn.setStyleSheet(
            "QPushButton { background: #21262d; color: #c9d1d9; border: 1px solid #30363d;"
            " border-radius: 6px; padding: 6px 16px; font-size: 13px; font-weight: normal; }"
            "QPushButton:hover { background: #30363d; }"
        )
        btn.clicked.connect(lambda: self._stack.setCurrentIndex(target))
        return btn

    # ---- pages ----

    def _page_welcome(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: #0d1117;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Tervetuloa Voice Royale",
            "Alkuasennus — kestää noin 2 minuuttia."
        ))

        body = QWidget()
        body.setStyleSheet("background: #0d1117;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 22, 32, 24)
        bl.setSpacing(16)

        info = QLabel(
            "Tämä sovellus:\n\n"
            "  •  Kuuntelee puhettasi mikrofonista\n"
            "  •  Tunnistaa puheen tekstiksi  (OpenAI Whisper)\n"
            "  •  Kääntää valitsemallesi kielelle  (Google Translate ilmaiseksi tai GPT-4.1-mini)\n"
            "  •  Toistaa käännöksen ääneen  (Edge TTS — täysin ilmainen)\n\n"
            "OpenAI API-avain tarvitaan puheentunnistukseen (Whisper).\n"
            "Jos haluat vain kirjoittaa tekstiä ja kääntää, voit ohittaa avaimen."
        )
        info.setStyleSheet("color: #c9d1d9; font-size: 13px; background: transparent; line-height: 1.7;")
        info.setWordWrap(True)
        bl.addWidget(info)

        cost = QWidget()
        cost.setStyleSheet("background: #161b22; border: 1px solid #30363d; border-radius: 8px;")
        cl = QVBoxLayout(cost)
        cl.setContentsMargins(16, 12, 16, 12)
        lbl = QLabel(
            "💡  Hinta-arvio per puheenvuoro:\n"
            "     • Whisper (puheentunnistus):  ~0,006 $ / minuutti ääntä\n"
            "     • GPT-4.1-mini (käännös):     ~0,001 $ per kutsu\n"
            "     → Yhteensä n. 0,007–0,01 $ / puheenvuoro  —  1 000 puheenvuoroa ≈ 7–10 $\n\n"
            "     Uudet OpenAI-tilit saavat ilmaisia krediittejä aloitukseen."
        )
        lbl.setStyleSheet("color: #8b949e; font-size: 12px; background: transparent;")
        lbl.setWordWrap(True)
        cl.addWidget(lbl)
        bl.addWidget(cost)
        bl.addStretch()

        row = QHBoxLayout()
        row.addStretch()
        btn = QPushButton("Aloita  →")
        btn.setFixedHeight(42)
        btn.setMinimumWidth(140)
        btn.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        row.addWidget(btn)
        bl.addLayout(row)

        lay.addWidget(body)
        return page

    def _page_get_key(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: #0d1117;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Hanki OpenAI API-avain",
            "Vaihe 1/4  —  Luo avain OpenAI:n sivuilla. Ilmainen tili riittää aloitukseen."
        ))

        body = QWidget()
        body.setStyleSheet("background: #0d1117;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 20, 32, 24)
        bl.setSpacing(16)

        steps = QLabel(
            "Noudata näitä ohjeita:\n\n"
            "  1.  Klikkaa alla olevaa painiketta  →  sivu avautuu selaimeen\n"
            "  2.  Kirjaudu sisään tai luo ilmainen tili  (Sign up)\n"
            "  3.  Klikkaa  \"Create new secret key\"\n"
            "  4.  Anna avaimelle nimi, esim.  Voice Royale\n"
            "  5.  Kopioi avain  —  se näytetään vain kerran!\n\n"
            "Jos sinulla on jo OpenAI-tili, kirjaudu vain sisään ja luo uusi avain."
        )
        steps.setStyleSheet("color: #c9d1d9; font-size: 13px; background: transparent; line-height: 1.7;")
        steps.setWordWrap(True)
        bl.addWidget(steps)

        open_btn = QPushButton("🌐   Avaa  platform.openai.com/api-keys")
        open_btn.setFixedHeight(40)
        open_btn.setStyleSheet(
            "QPushButton { background: #21262d; color: #58a6ff; border: 1px solid #30363d;"
            " border-radius: 6px; padding: 6px 18px; font-size: 13px; font-weight: normal; }"
            "QPushButton:hover { background: #30363d; }"
        )
        open_btn.clicked.connect(lambda: webbrowser.open("https://platform.openai.com/api-keys"))
        bl.addWidget(open_btn)
        bl.addStretch()

        row = QHBoxLayout()
        row.addWidget(self._back_btn(0))
        row.addStretch()
        nxt = QPushButton("Minulla on avain  →")
        nxt.setFixedHeight(42)
        nxt.setMinimumWidth(180)
        nxt.clicked.connect(lambda: self._stack.setCurrentIndex(2))
        row.addWidget(nxt)
        bl.addLayout(row)

        lay.addWidget(body)
        return page

    def _page_enter_key(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: #0d1117;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Syötä API-avain",
            "Vaihe 2/4  —  Liitä kopioimasi avain alle ja testaa yhteys."
        ))

        body = QWidget()
        body.setStyleSheet("background: #0d1117;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 24, 32, 24)
        bl.setSpacing(12)

        hint = QLabel("API-avain alkaa  sk-  ja on noin 50+ merkkiä pitkä.")
        hint.setStyleSheet("color: #8b949e; font-size: 12px; background: transparent;")
        bl.addWidget(hint)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx...")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setFixedHeight(42)
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

        bl.addSpacing(8)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Testaa yhteys")
        self._test_btn.setFixedHeight(36)
        self._test_btn.setEnabled(False)
        self._test_btn.setStyleSheet(
            "QPushButton { background: #21262d; color: #c9d1d9; border: 1px solid #30363d;"
            " border-radius: 6px; padding: 6px 16px; font-size: 13px; font-weight: normal; }"
            "QPushButton:hover:enabled { background: #30363d; }"
            "QPushButton:disabled { color: #484f58; }"
        )
        self._test_btn.clicked.connect(self._test_key)
        test_row.addWidget(self._test_btn)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size: 12px; padding-left: 10px; background: transparent;")
        test_row.addWidget(self._status_lbl)
        test_row.addStretch()
        bl.addLayout(test_row)

        bl.addStretch()

        row = QHBoxLayout()
        row.addWidget(self._back_btn(1))
        skip_btn = QPushButton("Ohita (ei puheentunnistusta)")
        skip_btn.setFixedHeight(42)
        skip_btn.setStyleSheet(
            "QPushButton { background: #21262d; color: #8b949e; border: 1px solid #30363d;"
            " border-radius: 6px; padding: 6px 16px; font-size: 12px; font-weight: normal; }"
            "QPushButton:hover { background: #30363d; color: #c9d1d9; }"
        )
        skip_btn.clicked.connect(self._skip_key)
        row.addWidget(skip_btn)
        row.addStretch()
        self._save_btn = QPushButton("Tallenna ja aloita  ✓")
        self._save_btn.setFixedHeight(42)
        self._save_btn.setMinimumWidth(200)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_and_accept)
        row.addWidget(self._save_btn)
        bl.addLayout(row)

        lay.addWidget(body)
        return page

    def _page_vbcable(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: #0d1117;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Virtuaalimikrofoni (VB-Cable)",
            "Vaihe 3/4  —  Tarvitaan jos haluat äänen näkyvän mikrofonina peleissä tai Discordissa."
        ))

        body = QWidget()
        body.setStyleSheet("background: #0d1117;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 22, 32, 24)
        bl.setSpacing(14)

        vbc_installed = _is_vbcable_installed()

        status_txt = (
            "Virtuaalimikrofoni löytyi (VB-Cable tai Voicemod). Ei toimia tarvita."
            if vbc_installed else
            "Virtuaalimikrofonia ei löydy."
        )
        self._vbc_status_lbl = QLabel(status_txt)
        self._vbc_status_lbl.setStyleSheet(
            ("color: #3fb950; font-size: 13px; font-weight: bold; background: transparent;"
             if vbc_installed else
             "color: #e3b341; font-size: 13px; font-weight: bold; background: transparent;")
        )
        self._vbc_status_lbl.setWordWrap(True)
        bl.addWidget(self._vbc_status_lbl)

        desc = QLabel(
            "VB-Audio Virtual Cable on ilmainen virtuaaliäänilaite. Se tekee Voice Royalen käännetystä "
            "puheesta mikrofonilähdön, jota pelit, Discord ja muut sovellukset voivat käyttää.\n\n"
            "Asennuksen jälkeen:\n"
            "  • Aseta Voice Royalessa FX Output → CABLE Input\n"
            "  • Pelissä / Discordissa: mikrofoni → CABLE Output\n\n"
            "Jos sinulla on jo Voicemod asennettuna, se toimii samalla periaatteella."
        )
        desc.setStyleSheet("color: #8b949e; font-size: 12px; background: transparent; line-height: 160%;")
        desc.setWordWrap(True)
        bl.addWidget(desc)

        self._vbc_install_btn = QPushButton(
            "VB-Cable on jo asennettu" if vbc_installed else "Asenna VB-Cable nyt (ilmainen)"
        )
        self._vbc_install_btn.setFixedHeight(38)
        self._vbc_install_btn.setEnabled(not vbc_installed)
        if not vbc_installed:
            self._vbc_install_btn.setStyleSheet(
                "QPushButton { background: #1f6feb; color: #fff; border: none; border-radius: 6px;"
                " padding: 6px 18px; font-size: 13px; font-weight: bold; }"
                "QPushButton:hover { background: #388bfd; }"
                "QPushButton:disabled { background: #21262d; color: #8b949e; }"
            )

        def _do_vbc_install():
            self._vbc_install_btn.setEnabled(False)
            self._vbc_install_btn.setText("Asennetaan — hyväksy UAC-pyyntö...")
            self._vbc_status_lbl.setStyleSheet("color: #8b949e; font-size: 13px; background: transparent;")

            def _cb(msg):
                def _apply():
                    self._vbc_status_lbl.setText(msg)
                    ok = "✅" in msg or "installed" in msg.lower()
                    self._vbc_status_lbl.setStyleSheet(
                        "color: #3fb950; font-size: 13px; font-weight: bold; background: transparent;"
                        if ok else
                        "color: #f85149; font-size: 13px; font-weight: bold; background: transparent;"
                    )
                    if ok:
                        self._vbc_install_btn.setText("VB-Cable asennettu")
                    else:
                        self._vbc_install_btn.setEnabled(True)
                        self._vbc_install_btn.setText("Yritä uudelleen")
                QTimer.singleShot(0, _apply)

            threading.Thread(target=_install_vbcable, args=(_cb,), daemon=True).start()

        self._vbc_install_btn.clicked.connect(_do_vbc_install)
        bl.addWidget(self._vbc_install_btn)

        skip_note = QLabel(
            "Ei pakollinen — ohita jos et tarvitse ääntä peleissä tai Discordissa."
        )
        skip_note.setStyleSheet("color: #484f58; font-size: 11px; background: transparent;")
        skip_note.setWordWrap(True)
        bl.addWidget(skip_note)

        bl.addStretch()

        row = QHBoxLayout()
        row.addWidget(self._back_btn(2))
        row.addStretch()
        nxt = QPushButton("Seuraava  →")
        nxt.setFixedHeight(42)
        nxt.setMinimumWidth(140)
        nxt.clicked.connect(lambda: (self._stack.setCurrentIndex(4), self._start_wiz_mic_preview()))
        row.addWidget(nxt)
        bl.addLayout(row)

        lay.addWidget(body)
        return page

    def _page_devices(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: #0d1117;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._header(
            "Äänilaitteet",
            "Vaihe 4/4  —  Valitse mikrofoni ja kaiuttimet. Testaa ääni ennen jatkamista."
        ))

        body = QWidget()
        body.setStyleSheet("background: #0d1117;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(32, 20, 32, 24)
        bl.setSpacing(14)

        # --- Mic section ---
        mic_title = QLabel("Mikrofoni (äänitulon lähde)")
        mic_title.setStyleSheet("color: #e6edf3; font-size: 13px; font-weight: bold; background: transparent;")
        bl.addWidget(mic_title)

        self._wiz_mic_combo = QComboBox()
        self._wiz_mic_combo.setFixedHeight(36)
        self._wiz_mic_combo.setStyleSheet(
            "QComboBox { background: #161b22; border: 1px solid #30363d; border-radius: 6px;"
            " color: #e6edf3; padding: 4px 10px; font-size: 13px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #161b22; color: #e6edf3; }"
        )
        input_devices = list_input_devices()
        self._wiz_input_indices = []
        for idx, name in input_devices:
            n = name.lower()
            if name.startswith("{") or any(k in n for k in ["microsoft sound mapper", "primary sound capture", "bthhfenum"]):
                continue
            prefix = "🎤" if not any(k in n for k in ["virtual", "vb-audio", "voicemeeter"]) else "🔌"
            self._wiz_mic_combo.addItem(f"{prefix} {name}", idx)
            self._wiz_input_indices.append(idx)
        bl.addWidget(self._wiz_mic_combo)

        # Live mic meter
        mic_meter_row = QHBoxLayout()
        mic_m_lbl = QLabel("MIC")
        mic_m_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: bold; background: transparent; min-width: 32px;")
        self._wiz_mic_bar = QProgressBar()
        self._wiz_mic_bar.setRange(0, 1000)
        self._wiz_mic_bar.setValue(0)
        self._wiz_mic_bar.setTextVisible(False)
        self._wiz_mic_bar.setFixedHeight(10)
        self._wiz_mic_bar.setStyleSheet(METER_STYLE_MIC)
        mic_meter_row.addWidget(mic_m_lbl)
        mic_meter_row.addWidget(self._wiz_mic_bar, 1)
        bl.addLayout(mic_meter_row)

        mic_hint = QLabel("Puhu mikrofoniin — palkki liikkuu kun ääni kuuluu")
        mic_hint.setStyleSheet("color: #484f58; font-size: 11px; background: transparent;")
        bl.addWidget(mic_hint)

        bl.addSpacing(4)

        # --- Output section ---
        out_title = QLabel("Kaiuttimet / lähtölaitteet (valitse kaikki joihin haluat äänen)")
        out_title.setStyleSheet("color: #e6edf3; font-size: 13px; font-weight: bold; background: transparent;")
        bl.addWidget(out_title)

        out_scroll = QScrollArea()
        out_scroll.setWidgetResizable(True)
        out_scroll.setFixedHeight(140)
        out_scroll.setStyleSheet(
            "QScrollArea { background: #161b22; border: 1px solid #30363d; border-radius: 6px; }"
        )
        out_container = QWidget()
        out_container.setStyleSheet("background: #161b22;")
        self._wiz_out_layout = QVBoxLayout(out_container)
        self._wiz_out_layout.setContentsMargins(8, 6, 8, 6)
        self._wiz_out_layout.setSpacing(4)

        self._wiz_out_checkboxes = {}  # device_index -> QCheckBox
        output_devices = list_output_devices()
        for idx, name in output_devices:
            n = name.lower()
            if name.startswith("{") or "primary sound" in n or "microsoft sound" in n:
                continue
            cb = QCheckBox(name)
            cb.setStyleSheet("QCheckBox { color: #c9d1d9; font-size: 12px; background: transparent; padding: 2px; }")
            self._wiz_out_checkboxes[idx] = cb
            self._wiz_out_layout.addWidget(cb)

        if not self._wiz_out_checkboxes:
            no_dev = QLabel("Ei löytynyt äänilähtölaitteita")
            no_dev.setStyleSheet("color: #484f58; font-size: 12px; background: transparent;")
            self._wiz_out_layout.addWidget(no_dev)

        self._wiz_out_layout.addStretch()
        out_scroll.setWidget(out_container)
        bl.addWidget(out_scroll)

        bl.addStretch()

        # Recording test
        rec_row = QHBoxLayout()
        self._wiz_rec_btn = QPushButton("⏺  Ääntiä 3s ja kuuntele")
        self._wiz_rec_btn.setFixedHeight(34)
        self._wiz_rec_btn.setStyleSheet(
            "QPushButton { background: #21262d; color: #c9d1d9; border: 1px solid #30363d;"
            " border-radius: 6px; padding: 5px 14px; font-size: 12px; }"
            "QPushButton:hover { background: #30363d; }"
            "QPushButton:disabled { color: #484f58; }"
        )
        self._wiz_rec_btn.clicked.connect(self._wiz_record_and_playback)
        self._wiz_rec_status = QLabel("Nauhoita — soitetaan takaisin, jotta tiedät mikki toimii")
        self._wiz_rec_status.setStyleSheet("color: #484f58; font-size: 11px; background: transparent;")
        self._wiz_rec_status.setWordWrap(True)
        rec_row.addWidget(self._wiz_rec_btn)
        rec_row.addWidget(self._wiz_rec_status, 1)
        bl.addLayout(rec_row)

        # Buttons
        row = QHBoxLayout()
        back_btn = self._back_btn(3)
        row.addWidget(back_btn)
        row.addStretch()
        test_btn = QPushButton("▶  Toistotesti (beep)")
        test_btn.setFixedHeight(36)
        test_btn.setStyleSheet(
            "QPushButton { background: #21262d; color: #c9d1d9; border: 1px solid #30363d;"
            " border-radius: 6px; padding: 6px 16px; font-size: 13px; font-weight: normal; }"
            "QPushButton:hover { background: #30363d; }"
        )
        test_btn.clicked.connect(self._test_audio)
        row.addWidget(test_btn)
        row.addSpacing(8)
        finish_btn = QPushButton("Valmis  ✓")
        finish_btn.setFixedHeight(42)
        finish_btn.setMinimumWidth(140)
        finish_btn.clicked.connect(self._finish_setup)
        row.addWidget(finish_btn)
        bl.addLayout(row)

        lay.addWidget(body)

        self._wiz_mic_combo.currentIndexChanged.connect(self._on_wiz_mic_changed)

        return page

    def _start_wiz_mic_preview(self):
        self._stop_wiz_mic_preview()
        idx = self._wiz_mic_combo.currentData()
        if idx is None:
            return
        self._wiz_stop_flag.clear()
        self._wiz_peak_ref[0] = 0.0

        def _listen():
            try:
                with sd.InputStream(
                    device=idx,
                    channels=1,
                    samplerate=16000,
                    blocksize=512,
                    dtype="float32",
                    callback=lambda d, *_: self._wiz_peak_ref.__setitem__(
                        0, max(self._wiz_peak_ref[0], float(np.max(np.abs(d))))
                    ),
                ):
                    while not self._wiz_stop_flag.is_set():
                        time.sleep(0.05)
            except Exception:
                pass

        self._wiz_mic_thread = threading.Thread(target=_listen, daemon=True)
        self._wiz_mic_thread.start()
        self._wiz_timer.start()

    def _stop_wiz_mic_preview(self):
        self._wiz_stop_flag.set()
        self._wiz_timer.stop()
        if self._wiz_mic_thread is not None:
            self._wiz_mic_thread.join(timeout=1.5)
            self._wiz_mic_thread = None
        self._wiz_mic_bar.setValue(0)

    def _tick_wiz_mic(self):
        val = int(min(self._wiz_peak_ref[0] * 1000, 1000))
        self._wiz_mic_bar.setValue(val)
        self._wiz_peak_ref[0] *= 0.75

    def _on_wiz_mic_changed(self, _idx):
        self._start_wiz_mic_preview()

    def _wiz_record_and_playback(self):
        mic_idx = self._wiz_mic_combo.currentData()
        if mic_idx is None:
            self._wiz_rec_status.setText("Valitse mikrofoni ensin.")
            return
        self._wiz_rec_btn.setEnabled(False)
        self._wiz_rec_status.setText("Nauhoitetaan 3 sekuntia...")
        self._wiz_rec_status.setStyleSheet("color: #FF9500; font-size: 11px; background: transparent;")
        self._wiz_rec_buf.clear()
        self._wiz_rec_stop.clear()

        btn = self._wiz_rec_btn
        status = self._wiz_rec_status

        def _set_error(msg):
            status.setText(msg)
            status.setStyleSheet("color: #f85149; font-size: 11px; background: transparent;")
            btn.setEnabled(True)

        def _record():
            sr = 44100
            try:
                with sd.InputStream(device=mic_idx, channels=1, samplerate=sr,
                                    blocksize=1024, dtype="float32",
                                    callback=lambda d, *_: self._wiz_rec_buf.append(d[:, 0].copy())):
                    deadline = time.monotonic() + 3.0
                    while time.monotonic() < deadline and not self._wiz_rec_stop.is_set():
                        time.sleep(0.05)
            except Exception as e:
                QTimer.singleShot(0, lambda msg=str(e): _set_error(f"Nauhoitusvirhe: {msg}"))
                return

            if not self._wiz_rec_buf:
                QTimer.singleShot(0, lambda: _set_error("Mikrofoni ei tuottanut ääntä — tarkista laite."))
                return

            audio = np.concatenate(self._wiz_rec_buf)
            peak = float(np.max(np.abs(audio)))

            if peak < 0.005:
                QTimer.singleShot(0, lambda: _set_error("Signaali liian hiljainen — onko mikki auki?"))
                return

            QTimer.singleShot(0, lambda: status.setText("Toistetaan takaisin..."))

            buf = io.BytesIO()
            pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(pcm.tobytes())
            wav_bytes = buf.getvalue()
            selected_out = [idx for idx, cb in self._wiz_out_checkboxes.items() if cb.isChecked()]
            play_wav_bytes(wav_bytes, device_indices=selected_out if selected_out else None)

            def _done():
                status.setText("Mikrofoni OK — kuulit oman äänesi?")
                status.setStyleSheet("color: #3fb950; font-size: 11px; background: transparent;")
                btn.setEnabled(True)
            QTimer.singleShot(0, _done)

        self._wiz_rec_thread = threading.Thread(target=_record, daemon=True)
        self._wiz_rec_thread.start()

    def _test_audio(self):
        selected_out = [idx for idx, cb in self._wiz_out_checkboxes.items() if cb.isChecked()]
        wav = self._make_beep_wav()
        threading.Thread(target=play_wav_bytes, kwargs={
            "wav_bytes": wav,
            "device_indices": selected_out if selected_out else None,
        }, daemon=True).start()

    @staticmethod
    def _make_beep_wav(freq: int = 880, duration: float = 0.4, sr: int = 44100) -> bytes:
        import math, struct
        n = int(sr * duration)
        fade = int(sr * 0.04)
        samples = []
        for i in range(n):
            s = math.sin(2 * math.pi * freq * i / sr)
            if i < fade:
                s *= i / fade
            elif i > n - fade:
                s *= (n - i) / fade
            samples.append(int(s * 28000))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(struct.pack(f"{n}h", *samples))
        return buf.getvalue()

    def _build_ui(self):
        self._stack = QStackedWidget(self)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(self._stack)
        self._stack.addWidget(self._page_welcome())      # 0
        self._stack.addWidget(self._page_get_key())      # 1
        self._stack.addWidget(self._page_enter_key())    # 2
        self._stack.addWidget(self._page_vbcable())      # 3
        self._stack.addWidget(self._page_devices())      # 4

    # ---- logic ----

    def _on_key_changed(self, text: str):
        valid = text.strip().startswith("sk-") and len(text.strip()) > 20
        self._test_btn.setEnabled(valid)
        self._save_btn.setEnabled(valid)
        self._status_lbl.setText("")

    def _test_key(self):
        key = self._key_input.text().strip()
        self._test_btn.setEnabled(False)
        self._status_lbl.setText("Testataan yhteyttä...")
        self._status_lbl.setStyleSheet("color: #8b949e; font-size: 12px; padding-left: 10px; background: transparent;")
        QApplication.processEvents()
        try:
            OpenAI(api_key=key).models.list()
            self._status_lbl.setText("✓  Avain toimii!")
            self._status_lbl.setStyleSheet("color: #3fb950; font-size: 12px; padding-left: 10px; background: transparent;")
        except Exception as e:
            msg = str(e)
            if "401" in msg or "Incorrect API key" in msg or "invalid_api_key" in msg:
                txt = "✗  Väärä avain — tarkista kirjoitusvirheet"
            elif "429" in msg:
                txt = "✗  Käyttöraja täynnä, mutta tili ok"
            else:
                txt = f"✗  Virhe: {msg[:70]}"
            self._status_lbl.setText(txt)
            self._status_lbl.setStyleSheet("color: #f85149; font-size: 12px; padding-left: 10px; background: transparent;")
        self._test_btn.setEnabled(True)

    def _save_and_accept(self):
        self._api_key = self._key_input.text().strip()
        env_file = os.path.join(BASE_PATH, "credentials.env")
        try:
            lines = []
            if os.path.exists(env_file):
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = [ln.rstrip() for ln in f if not ln.startswith("OPENAI_API_KEY")]
            lines.insert(0, f"OPENAI_API_KEY={self._api_key}")
            with open(env_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass
        self._stack.setCurrentIndex(3)  # VB-Cable page

    def _skip_key(self):
        """Proceed without OpenAI key — translation only, no voice transcription."""
        self._api_key = ""
        self._stack.setCurrentIndex(3)  # VB-Cable page

    def _finish_setup(self):
        self._stop_wiz_mic_preview()
        # Save device selections to speech_history.json
        selected_in = self._wiz_mic_combo.currentData()
        selected_out = [idx for idx, cb in self._wiz_out_checkboxes.items() if cb.isChecked()]
        try:
            history_data = {}
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
            if selected_in is not None:
                history_data["selected_input_device"] = selected_in
            if selected_out:
                history_data["selected_output_devices"] = selected_out
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        self.accept()

    def closeEvent(self, event):
        self._wiz_rec_stop.set()
        self._stop_wiz_mic_preview()
        super().closeEvent(event)

    def get_api_key(self) -> str:
        return self._api_key


if __name__ == "__main__":
    app = QApplication(sys.argv)
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

    # Match App.__init__ geometry exactly so splash and main window occupy the same spot
    _WIN_X, _WIN_Y, _WIN_W, _WIN_H = 100, 100, 1320, 637

    splash_path = os.path.join(ASSETS_PATH, "juhalempiainensoftware.png")
    splash = None
    if os.path.exists(splash_path):
        logo = QPixmap(splash_path)
        logo = logo.scaled(
            _WIN_W - 120, _WIN_H - 120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QPixmap(_WIN_W, _WIN_H)
        canvas.fill(QColor("#0d1117"))
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

    if splash:
        _remaining = max(0, 4000 - _elapsed_ms)
        QTimer.singleShot(_remaining, lambda: (splash.finish(window), window.show()))
    else:
        window.show()

    sys.exit(app.exec())
# Copyright (c) 2026 Juha Lempiäinen. All rights reserved.
# Use permitted. Modification and redistribution of source code prohibited.
# See LICENSE for full terms.

# =========================
# SELF INSTALL DEPENDENCIES
# =========================
import importlib
import os
import subprocess
import sys
import tempfile

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
    "edge_tts": "edge-tts"
}


def install_deps():
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

import edge_tts
import keyboard
import numpy as np
import pyttsx3
import requests
import sounddevice as sd
from dotenv import load_dotenv
from openai import OpenAI
from PyQt6.QtCore import QEvent, QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplashScreen,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

# =========================
# UI STYLE CONSTANTS
# =========================
METER_LABEL_STYLE = "color: #aab; font-size: 11px; font-weight: bold;"
METER_STYLE_MIC = (
    "QProgressBar { background: #111620; border: 1px solid #3b4a6b; border-radius: 3px; }"
    "QProgressBar::chunk { background: qlineargradient(x1:0, x2:1,"
    " stop:0 #22cc44, stop:0.55 #cccc22, stop:1 #cc2222); border-radius: 2px; }"
)
METER_STYLE_OUT = (
    "QProgressBar { background: #111620; border: 1px solid #3b4a6b; border-radius: 3px; }"
    "QProgressBar::chunk { background: qlineargradient(x1:0, x2:1,"
    " stop:0 #2266ff, stop:0.55 #aa44cc, stop:1 #cc2222); border-radius: 2px; }"
)
LIST_STYLE = """
    QListWidget {
        background: #171c2d;
        border: 1px solid #3b4a6b;
        border-radius: 6px;
        font-family: "Segoe UI", sans-serif;
        font-weight: bold;
    }
    QListWidget::item {
        background: #2a3441;
        border: 1px solid #3b4a6b;
        border-radius: 4px;
        margin: 2px;
        padding: 4px;
        color: #ffffff;
    }
    QListWidget::item:hover {
        background: #3b4a6b;
        border: 1px solid #4f5f7f;
    }
    QListWidget::item:selected {
        background: #50648f;
        border: 1px solid #6b7fa0;
    }
"""

# =========================
# CONFIG
# =========================
def get_base_path():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
ENV_PATH = os.path.join(BASE_PATH, ".env")
if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(BASE_PATH, "credentials.env")

load_dotenv(ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY", "")
VOICE_ID = os.getenv("VOICE_ID", "")
HISTORY_FILE = os.path.join(BASE_PATH, "speech_history.json")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY in .env / credentials.env")

DEFAULT_TTS_BACKEND = "Edge TTS (free)"

client = OpenAI(api_key=OPENAI_API_KEY)

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
    "wake_command_seconds": 6.0,
    "custom_languages": [],
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
        return any("cable" in d["name"].lower() for d in sd.query_devices())
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
# OPENAI TRANSLATION
# =========================

def translate_text(text: str, lang: str) -> str:
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

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, access_key: str, keyword: str, custom_ppn_path: str, device_index):
        self._keyword = keyword.lower()
        self._device_index = device_index

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
                    result = self._porcupine.process(pcm.tolist())
                    if result >= 0:
                        self.on_status("✨ Wake-word detected!")
                        self.on_wake()
                        time.sleep(0.3)
        except Exception as e:
            self.on_status(f"Wake listener stopped: {e}")

    def _run_whisper(self):
        """Records 2.5s chunks, transcribes with Whisper, checks for wake keyword."""
        sample_rate = 16000
        chunk_duration = 2.5
        silence_threshold = 0.008  # RMS below this = silence, skip

        self.on_status(f"👂 Whisper mode listening for: '{self._keyword}'")

        while not self._stop_flag.is_set():
            try:
                frames = int(chunk_duration * sample_rate)
                recording = sd.rec(
                    frames, samplerate=sample_rate, channels=1,
                    dtype="float32", device=self._device_index
                )
                sd.wait()

                if self._stop_flag.is_set():
                    break

                audio = recording.flatten()
                rms = float(np.sqrt(np.mean(audio ** 2)))
                if rms < silence_threshold:
                    continue  # Silent chunk — skip transcription to save API cost

                audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
                wav_buf = io.BytesIO()
                with wave.open(wav_buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_int16.tobytes())
                wav_bytes = wav_buf.getvalue()

                try:
                    transcript = transcribe_audio_wav(wav_bytes)
                    if transcript and self._keyword in transcript.lower():
                        self.on_status(f"✨ Wake-word '{self._keyword}' detected!")
                        self.on_wake()
                        time.sleep(1.0)
                except Exception:
                    pass

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
        self.setWindowTitle("AI Voice Router")
        self.setGeometry(200, 200, 1100, 720)
        self.setStyleSheet(
            "QWidget { background: #1a1f2b; color: #f5f5f5; }"
            "QLabel { font-size: 13px; }"
            "QPushButton { background: #3b4a6b; border: 1px solid #4f5f7f; padding: 8px 12px; border-radius: 6px; }"
            "QPushButton:hover { background: #50648f; }"
            "QPushButton:disabled { background: #2d3346; color: #777777; }"
            "QComboBox, QTextEdit { background: #252c40; border: 1px solid #3b4a6b; color: #f5f5f5; padding: 4px; border-radius: 4px; }"
            "QListWidget { background: #171c2d; border: 1px solid #3b4a6b; }"
            "QCheckBox { color: #ddd; }"
            "QCheckBox::indicator { width: 16px; height: 16px; }"
            "QCheckBox::indicator:unchecked { background: #252c40; border: 1px solid #3b4a6b; border-radius: 3px; }"
            "QCheckBox::indicator:checked { background: #50a050; border: 1px solid #6bbf6b; border-radius: 3px; }"
        )

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

        # ============ Top row: Speech card (left) + History card (right) ============
        top_row = QHBoxLayout()
        top_row.addWidget(self._build_speech_card(), 2)
        top_row.addWidget(self._build_history_card(), 1)

        # ============ Bottom: Outputs & Levels card ============
        outputs_card = self._build_outputs_card()

        # ============ Root layout ============
        root = QVBoxLayout()
        root.setContentsMargins(8, 8, 8, 8)
        root.addLayout(top_row, 1)
        root.addWidget(outputs_card)
        self.setLayout(root)

        # Wire signals — safe cross-thread UI updates
        self.sig_mic_level.connect(self._update_mic_meter)
        self.sig_out_level.connect(self._update_output_meters)
        self.sig_status.connect(self._on_status)
        self.sig_set_textbox.connect(self.textbox.setPlainText)

        # Load data + populate devices
        self.history_data = load_history_data()
        self.history = self.history_data.get("history", [])
        self.favorites = self.history_data.get("favorites", [])
        self.refresh_history_views()

        self.populate_output_devices()
        self.populate_input_devices()
        self.register_hotkey()

        # Recording state
        self.is_recording = False
        self.recording_thread = None

        # Mic level meter — updated by QTimer on main thread (never from PortAudio callback)
        self._mic_peak_ref = [0.0]
        self._mic_timer = QTimer(self)
        self._mic_timer.setInterval(40)
        self._mic_timer.timeout.connect(self._tick_mic_meter)

    # ============ Card builders ============

    def _make_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { background: #1a1f2b; border: 1px solid #2f3c5a; border-radius: 8px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        if title:
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #cce; border: none;")
            layout.addWidget(title_lbl)
        return frame, layout

    def _build_speech_card(self) -> QWidget:
        frame, layout = self._make_card("Speech")

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setPlainText("Ready. Type or record. Hotkey: Ctrl+Alt+Space")
        self.status_text.setMinimumHeight(60)
        self.status_text.setMaximumHeight(90)
        self.status_text.setStyleSheet(
            "font-weight: bold; color: #dcdcdc; background: #151a28;"
            "border: 1px solid #2f3c5a; border-radius: 4px; padding: 4px;"
        )
        layout.addWidget(self.status_text)

        # Target lang + TTS backend
        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("Target:"))
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
        options_row.addWidget(self.langbox, 1)
        options_row.addSpacing(12)
        options_row.addWidget(QLabel("TTS:"))
        self.backend_combo = QComboBox()
        for backend in ("ElevenLabs", "Edge TTS (free)"):
            self.backend_combo.addItem(backend)
        self.backend_combo.setCurrentText(self.settings.get("default_tts_backend", DEFAULT_TTS_BACKEND))
        options_row.addWidget(self.backend_combo, 1)
        layout.addLayout(options_row)

        self.translated_label = QLabel("Translated text will appear here.")
        self.translated_label.setWordWrap(True)
        self.translated_label.setMinimumHeight(40)
        self.translated_label.setStyleSheet(
            "color: #9ec0ff; padding: 8px; background: #151a28;"
            "border: 1px solid #2f3c5a; border-radius: 4px;"
        )
        layout.addWidget(self.translated_label)

        self.textbox = QTextEdit()
        self.textbox.setPlaceholderText("Type the phrase to speak...\nOr press Record to use voice input.")
        self.textbox.setMinimumHeight(140)
        layout.addWidget(self.textbox, 1)

        self.record_button = QPushButton("🎤", self.textbox)
        self.record_button.setFixedSize(36, 36)
        self.record_button.setToolTip("Record")
        self.record_button.clicked.connect(self.on_record_toggle)
        self.record_button.setStyleSheet(
            "QPushButton { background: rgba(40,52,80,200); border: 1px solid #4f5f7f;"
            " border-radius: 8px; font-size: 18px; padding: 0; }"
            "QPushButton:hover { background: rgba(80,100,150,220); }"
            "QPushButton:disabled { opacity: 0.4; }"
        )
        self.record_button.move(self.textbox.width() - 42, self.textbox.height() - 42)
        self._rec_filter = _TextboxRecordBtnFilter(self.record_button)
        self.textbox.installEventFilter(self._rec_filter)
        self.record_button.raise_()

        # Buttons
        button_row = QHBoxLayout()
        self.speak_button = QPushButton("🔊 Speak")
        self.speak_button.clicked.connect(self.on_speak)
        button_row.addWidget(self.speak_button)

        self.test_audio_button = QPushButton("🧪 Test")
        self.test_audio_button.clicked.connect(self.on_test_audio)
        button_row.addWidget(self.test_audio_button)

        self.favorite_button = QPushButton("⭐ Favorite")
        self.favorite_button.clicked.connect(self.toggle_favorite)
        button_row.addWidget(self.favorite_button)
        layout.addLayout(button_row)

        # Wake-word + settings row
        ws_row = QHBoxLayout()
        self.listen_button = QPushButton("👂 Start Listening")
        self.listen_button.setCheckable(True)
        self.listen_button.clicked.connect(self.toggle_wake_listener)
        ws_row.addWidget(self.listen_button)

        self.wake_status_label = QLabel("Wake-word listener: off")
        self.wake_status_label.setStyleSheet("color: #99a6c8; font-size: 11px; border: none;")
        ws_row.addWidget(self.wake_status_label, 1)

        self.settings_button = QPushButton("⚙️ Settings")
        self.settings_button.clicked.connect(lambda: open_settings_dialog(self))
        ws_row.addWidget(self.settings_button)
        layout.addLayout(ws_row)

        # MIC meter row (inside speech card, as in chosen preview)
        mic_row = QHBoxLayout()
        mic_lbl = QLabel("MIC")
        mic_lbl.setStyleSheet(METER_LABEL_STYLE)
        mic_lbl.setMinimumWidth(60)
        self.mic_level_bar = QProgressBar()
        self.mic_level_bar.setRange(0, 1000)
        self.mic_level_bar.setValue(0)
        self.mic_level_bar.setTextVisible(False)
        self.mic_level_bar.setFixedHeight(12)
        self.mic_level_bar.setStyleSheet(METER_STYLE_MIC)
        self.mic_db_label = QLabel("-∞ dB")
        self.mic_db_label.setStyleSheet("color: #99a; font-family: 'Consolas', monospace; font-size: 11px;")
        self.mic_db_label.setMinimumWidth(64)
        self.mic_db_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        mic_row.addWidget(mic_lbl)
        mic_row.addWidget(self.mic_level_bar, 1)
        mic_row.addWidget(self.mic_db_label)
        layout.addLayout(mic_row)

        self.hotkey_label = QLabel(f"Global hotkey: {self.settings.get('hotkey', 'ctrl+alt+space')}")
        self.hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hotkey_label.setStyleSheet("color: #99a6c8; font-size: 11px; margin-top: 4px;")
        layout.addWidget(self.hotkey_label)

        return frame

    def _build_history_card(self) -> QWidget:
        frame, layout = self._make_card("History (last 10)")

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_history_item_selected)
        self.history_list.setMinimumHeight(180)
        self.history_list.setStyleSheet(LIST_STYLE)
        layout.addWidget(self.history_list, 1)

        fav_title = QLabel("Favorites")
        fav_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #cce; border: none; margin-top: 6px;")
        layout.addWidget(fav_title)

        self.favorites_list = QListWidget()
        self.favorites_list.itemClicked.connect(self.on_history_item_selected)
        self.favorites_list.setMinimumHeight(180)
        self.favorites_list.setStyleSheet(LIST_STYLE)
        layout.addWidget(self.favorites_list, 1)

        return frame

    def _build_outputs_card(self) -> QWidget:
        frame, layout = self._make_card("")

        # Header row: title + action buttons
        header = QHBoxLayout()
        title_lbl = QLabel("Output Devices & Levels")
        title_lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #cce; border: none;")
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
        scroll.setMinimumHeight(140)
        scroll.setMaximumHeight(220)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #2f3c5a; border-radius: 4px; background: #151a28; }"
        )
        container = QWidget()
        container.setStyleSheet("background: #151a28;")
        self._device_rows_layout = QVBoxLayout(container)
        self._device_rows_layout.setSpacing(2)
        self._device_rows_layout.setContentsMargins(4, 4, 4, 4)
        self._device_rows_layout.addStretch()  # push items up
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Input device row at the bottom
        input_row = QHBoxLayout()
        input_lbl = QLabel("Input mic:")
        input_lbl.setStyleSheet("border: none;")
        input_row.addWidget(input_lbl)
        self.input_device_combo = QComboBox()
        self.input_device_combo.currentIndexChanged.connect(self.on_input_device_changed)
        input_row.addWidget(self.input_device_combo, 1)
        layout.addLayout(input_row)

        return frame

    # ============ Per-device row helpers ============

    def _add_device_row(self, device_index: int, display_name: str, full_name: str, was_selected: bool):
        container = QWidget()
        container.setStyleSheet(
            "QWidget { background: #2a3441; border: 1px solid #3b4a6b; border-radius: 4px; }"
        )
        row = QHBoxLayout(container)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(8)

        cb = QCheckBox()
        cb.setChecked(was_selected)
        cb.stateChanged.connect(self.on_output_device_changed)

        name_lbl = QLabel(display_name)
        name_lbl.setStyleSheet("color: #ddd; font-size: 12px; border: none;")
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
        db_lbl.setStyleSheet("color: #99a; font-family: 'Consolas', monospace; font-size: 11px; border: none;")
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
        for w in self._device_widgets.values():
            if w["checkbox"].isChecked():
                w["meter"].setValue(value)
                w["db_label"].setText(db_text)
            else:
                w["meter"].setValue(0)
                w["db_label"].setText("-∞ dB")

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
            translated = translate_text(text, lang_code)
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
        # Reset meters for unchecked devices immediately
        for w in self._device_widgets.values():
            if not w["checkbox"].isChecked():
                w["meter"].setValue(0)
                w["db_label"].setText("-∞ dB")

    def on_input_device_changed(self):
        selected_device = self.get_selected_input_device()
        if selected_device is not None:
            self.history_data["selected_input_device"] = selected_device
            save_history_data(self.history_data)

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
            self.listen_button.setText("👂 Start Listening")
            self.listen_button.setChecked(False)
            self.wake_status_label.setText("Wake-word listener: off")
        else:
            ok = self._start_wake_listener()
            if ok:
                self.listen_button.setText("⏹️ Stop Listening")
                self.listen_button.setChecked(True)
                kw = self.settings.get("wake_keyword", "jarvis")
                custom = self.settings.get("wake_custom_ppn_path", "")
                kw_display = os.path.basename(custom) if custom else kw
                self.wake_status_label.setText(f"Listening for: {kw_display}")
            else:
                self.listen_button.setChecked(False)

    def _start_wake_listener(self) -> bool:
        return self.wake_listener.start(
            access_key=self.settings.get("picovoice_access_key", ""),
            keyword=self.settings.get("wake_keyword", "jarvis"),
            custom_ppn_path=self.settings.get("wake_custom_ppn_path", ""),
            device_index=self.get_selected_input_device(),
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
            self._mic_timer.start()
            with sd.InputStream(
                device=device_index, channels=channels, samplerate=sample_rate,
                blocksize=1024, dtype="float32", callback=_cb,
            ):
                end_time = time.time() + seconds
                while time.time() < end_time:
                    time.sleep(0.05)
            QTimer.singleShot(0, lambda: (self._mic_timer.stop(), self.mic_level_bar.setValue(0)))

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
        self._mic_timer.start()
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

            self.append_status(f"Opening stream: device={input_device_index}, ch={channels}, sr={sample_rate}")
            with sd.InputStream(device=input_device_index, channels=channels,
                                samplerate=sample_rate, blocksize=blocksize,
                                dtype="float32", callback=_audio_cb):
                self.append_status("Stream opened OK — recording...")
                while self.is_recording:
                    time.sleep(0.05)

            max_peak = max_peak_ref[0]

            if not frames:
                self.append_status("No audio data recorded")
                return

            total_seconds = (len(frames) * blocksize) / sample_rate
            self.append_status(f"Recording stopped: {total_seconds:.1f}s, peak: {max_peak:.4f}")

            # Concatenate and flatten to 1D float32
            audio_data = np.concatenate(frames, axis=0).flatten()

            # Normalize to [-1, 1]
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val
            else:
                self.append_status("Warning: recorded audio is silent")

            # Resample on float32 BEFORE int16 conversion
            target_sample_rate = 16000
            if sample_rate != target_sample_rate:
                import scipy.signal
                new_length = int(len(audio_data) * target_sample_rate / sample_rate)
                audio_data = scipy.signal.resample(audio_data, new_length).astype(np.float32)
                self.append_status(f"Resampled {sample_rate}→{target_sample_rate} Hz")
                sample_rate = target_sample_rate

            audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)

            wav_bytes = io.BytesIO()
            with wave.open(wav_bytes, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())
            wav_bytes = wav_bytes.getvalue()

            # Save debug WAV so we can verify audio content
            debug_wav = os.path.join(BASE_PATH, "debug_last_recording.wav")
            with open(debug_wav, "wb") as f:
                f.write(wav_bytes)
            print(f"[DEBUG] WAV saved: {debug_wav} ({len(wav_bytes)} bytes, {total_seconds:.1f}s)")

            self.append_status(f"Sending {total_seconds:.1f}s audio to Whisper...")
            try:
                transcribed = transcribe_audio_wav(wav_bytes)
                print(f"[DEBUG] Whisper result: '{transcribed}'")
            except Exception as e:
                print(f"[DEBUG] Transcription exception: {e}")
                traceback.print_exc()
                self.append_status(f"Transcription failed: {e}")
                QTimer.singleShot(0, lambda err=str(e): __import__('PyQt6.QtWidgets', fromlist=['QMessageBox']).QMessageBox.critical(self, "Transcription Error", err))
                return

            if not transcribed:
                self.append_status("Whisper returned empty — try speaking louder or check the audio file: debug_last_recording.wav")
                return

            self.sig_set_textbox.emit(transcribed)
            self.append_status(f"Transcribed: {transcribed}")

            # Auto-translate+play if target language is set (no confirmation dialog)
            target_lang = self.langbox.currentText()
            print(f"[DEBUG] Recording target_lang: '{target_lang}'")
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
        self._mic_timer.stop()
        self.mic_level_bar.setValue(0)
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
        self._mic_peak_ref[0] *= 0.75  # decay between ticks

    def update_mic_level(self, peak: float):
        # Safe to call from any thread — just writes a float to a list slot
        if peak > self._mic_peak_ref[0]:
            self._mic_peak_ref[0] = peak

    def update_output_level(self, peak: float):
        self.sig_out_level.emit(int(min(peak * 1000, 1000)))

    def closeEvent(self, event):
        try:
            if self.wake_listener.is_running():
                self.wake_listener.stop()
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
            translated = translate_text(text, lang)
            if not translated or not translated.strip():
                raise RuntimeError("Translation returned empty output. Check your OpenAI API key and input text.")

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
    from PyQt6.QtWidgets import (
        QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QFileDialog, QScrollArea,
        QComboBox as _QComboBox, QPushButton as _QPushButton, QHBoxLayout as _QHBoxLayout,
        QListWidget as _QListWidget,
    )

    dlg = QDialog(parent_app)
    dlg.setWindowTitle("Settings")
    dlg.setMinimumWidth(600)
    dlg.setMinimumHeight(500)
    dlg.setStyleSheet(parent_app.styleSheet())

    settings = dict(parent_app.settings)
    form = QFormLayout()
    form.setVerticalSpacing(2)
    form.setContentsMargins(8, 8, 8, 8)

    DESC = "color: #7a8fbb; font-size: 11px; padding-bottom: 6px;"

    def _desc(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(DESC)
        lbl.setWordWrap(True)
        return lbl

    # ── Wake keyword ──────────────────────────────────────────────────
    builtin_keywords = sorted(pvporcupine.KEYWORDS) if PORCUPINE_AVAILABLE else []
    if PORCUPINE_AVAILABLE:
        keyword_combo = _QComboBox()
        for kw in builtin_keywords:
            keyword_combo.addItem(kw)
        if settings.get("wake_keyword") in builtin_keywords:
            keyword_combo.setCurrentText(settings["wake_keyword"])
        keyword_widget = keyword_combo
        def _get_keyword():
            return keyword_combo.currentText()
        form.addRow("Wake keyword (built-in):", keyword_widget)
    else:
        keyword_edit = QLineEdit(settings.get("wake_keyword", "jarvis"))
        keyword_edit.setPlaceholderText("e.g. jarvis")
        keyword_widget = keyword_edit
        def _get_keyword():
            return keyword_edit.text().strip().lower() or "jarvis"
        form.addRow("Wake keyword (Whisper):", keyword_widget)
    form.addRow("", _desc(
        "The word you say to activate hands-free recording. "
        "After the app hears this word it starts recording your command automatically. "
        "Porcupine mode: choose from the list. Whisper mode: type any word — even Finnish words work."
    ))

    # ── Custom .ppn wake-word file ────────────────────────────────────
    custom_row = _QHBoxLayout()
    custom_path_edit = QLineEdit(settings.get("wake_custom_ppn_path", ""))
    custom_path_edit.setPlaceholderText("Optional path to a .ppn file")
    browse_btn = _QPushButton("Browse...")
    def _browse():
        path, _ = QFileDialog.getOpenFileName(dlg, "Select .ppn wake-word file", "", "Porcupine PPN (*.ppn)")
        if path:
            custom_path_edit.setText(path)
    browse_btn.clicked.connect(_browse)
    custom_row.addWidget(custom_path_edit, 1)
    custom_row.addWidget(browse_btn)
    custom_widget = QWidget()
    custom_widget.setLayout(custom_row)
    form.addRow("Custom wake .ppn:", custom_widget)
    form.addRow("", _desc(
        "Use a custom wake-word model (.ppn file) you trained at console.picovoice.ai. "
        "This overrides the built-in keyword above. Leave empty if you use a built-in keyword or Whisper mode."
    ))

    # ── Picovoice access key ──────────────────────────────────────────
    access_key_edit = QLineEdit(settings.get("picovoice_access_key", ""))
    access_key_edit.setPlaceholderText("Paste your free key from console.picovoice.ai")
    form.addRow("Picovoice AccessKey:", access_key_edit)
    form.addRow("", _desc(
        "Required only for Porcupine wake-word detection (faster, offline). "
        "Get a free key at console.picovoice.ai — no payment needed. "
        "Leave empty to use Whisper-based detection instead (works without a key, slightly slower)."
    ))

    # ── Global hotkey ─────────────────────────────────────────────────
    hotkey_edit = QLineEdit(settings.get("hotkey", "ctrl+alt+space"))
    hotkey_edit.setPlaceholderText("e.g. ctrl+alt+space")
    form.addRow("Global hotkey:", hotkey_edit)
    form.addRow("", _desc(
        "Keyboard shortcut to speak the text currently in the text box — works even when the app is in the background. "
        "Use key names like ctrl, alt, shift, space, f1–f12. Combine with + (e.g. ctrl+alt+space). "
        "Avoid shortcuts already used by your OS or game."
    ))

    # ── Default target language ───────────────────────────────────────
    lang_combo = _QComboBox()
    for lang in LANGS.keys():
        lang_combo.addItem(lang)
    lang_combo.setCurrentText(settings.get("default_target_lang", "Auto"))
    form.addRow("Default target language:", lang_combo)
    form.addRow("", _desc(
        "The language your text or speech is translated into when you press Speak or record. "
        "'Auto' detects the spoken language and translates to English. "
        "You can override this per-session from the main window's Target dropdown."
    ))

    # ── Default TTS backend ───────────────────────────────────────────
    backend_combo = _QComboBox()
    for b in ("ElevenLabs", "Edge TTS (free)"):
        backend_combo.addItem(b)
    backend_combo.setCurrentText(settings.get("default_tts_backend", DEFAULT_TTS_BACKEND))
    form.addRow("Default TTS backend:", backend_combo)
    form.addRow("", _desc(
        "Edge TTS (free): Microsoft neural voices, no account needed, good quality. "
        "ElevenLabs: very realistic AI voices, requires a paid account and API key in credentials.env. "
        "You can switch between them per-session in the main window."
    ))

    # ── Wake command capture seconds ──────────────────────────────────
    seconds_edit = QLineEdit(str(settings.get("wake_command_seconds", 6.0)))
    seconds_edit.setPlaceholderText("e.g. 6.0")
    form.addRow("Command capture (s):", seconds_edit)
    form.addRow("", _desc(
        "How many seconds the app records after it hears the wake word. "
        "Increase (e.g. 10) if your sentences are long or you speak slowly. "
        "Decrease (e.g. 3) for faster single-word commands. Default: 6 seconds."
    ))

    # ── Custom languages ──────────────────────────────────────────────
    custom_langs = [dict(e) for e in settings.get("custom_languages", [])]
    custom_list = _QListWidget()
    custom_list.setMaximumHeight(100)
    for entry in custom_langs:
        n, c, v = entry.get("name", ""), entry.get("country_code", ""), entry.get("edge_voice", "")
        custom_list.addItem(f"{n}  |  {c}  |  {v}" if v else f"{n}  |  {c}")
    form.addRow("Custom languages:", custom_list)
    form.addRow("", _desc(
        "Add languages not in the built-in list. Select an entry and click Remove to delete it. "
        "Name: display name shown in the Target dropdown (e.g. Portuguese). "
        "Code: 2-letter country code for the flag (e.g. pt, br, ar). "
        "Edge TTS voice: exact voice ID from learn.microsoft.com/azure/ai-services/speech-service/language-support "
        "(e.g. pt-PT-RaquelNeural). Leave voice empty to fall back to English voice."
    ))

    add_row = _QHBoxLayout()
    new_name_edit = QLineEdit()
    new_name_edit.setPlaceholderText("Name (e.g. Portuguese)")
    new_code_edit = QLineEdit()
    new_code_edit.setPlaceholderText("Code (pt)")
    new_code_edit.setMaximumWidth(60)
    new_voice_edit = QLineEdit()
    new_voice_edit.setPlaceholderText("Edge TTS voice (e.g. pt-PT-RaquelNeural)")
    add_btn = _QPushButton("Add")
    remove_btn = _QPushButton("Remove")

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
    form.addRow("", add_widget)

    # ── VB-Cable virtual audio device ─────────────────────────────────
    _vbc_installed = _is_vbcable_installed()
    vbc_status_lbl = QLabel("VB-Cable: ✅ Installed" if _vbc_installed else "VB-Cable: ❌ Not installed")
    vbc_status_lbl.setStyleSheet("color: #7fc97f;" if _vbc_installed else "color: #ff8888;")
    form.addRow("Virtual mic:", vbc_status_lbl)
    form.addRow("", _desc(
        "Installs VB-Audio Virtual Cable — a free virtual audio device that lets this app's translated speech "
        "appear as a microphone in games and voice chat (Discord, TeamSpeak, in-game VOIP). "
        "After install: set output device to 'CABLE Input' in this app, "
        "and set microphone to 'CABLE Output' in your game or Discord."
    ))

    vbc_install_btn = _QPushButton("Install VB-Cable (Virtual Mic)" if not _vbc_installed else "VB-Cable already installed")
    vbc_install_btn.setEnabled(not _vbc_installed)

    def _do_vbc_install():
        vbc_install_btn.setEnabled(False)
        vbc_install_btn.setText("Working...")

        def _status(msg):
            def _apply():
                vbc_status_lbl.setText(msg)
                vbc_status_lbl.setStyleSheet("color: #7fc97f;" if "✅" in msg else "color: #ff8888;")
                if "✅" in msg:
                    vbc_install_btn.setText("VB-Cable already installed")
                    QTimer.singleShot(800, parent_app.populate_output_devices)
                else:
                    vbc_install_btn.setEnabled(True)
                    vbc_install_btn.setText("Retry Install")
            QTimer.singleShot(0, _apply)

        threading.Thread(target=_install_vbcable, args=(_status,), daemon=True).start()

    vbc_install_btn.clicked.connect(_do_vbc_install)
    form.addRow("", vbc_install_btn)

    # ── Buttons ───────────────────────────────────────────────────────
    btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)

    # Wrap form in a scroll area so the dialog stays manageable
    scroll_content = QWidget()
    scroll_content.setLayout(form)
    scroll = QScrollArea()
    scroll.setWidget(scroll_content)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)

    root = QVBoxLayout()
    root.addWidget(scroll, 1)
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
        }
        try:
            new_settings["wake_command_seconds"] = float(seconds_edit.text())
        except ValueError:
            new_settings["wake_command_seconds"] = 6.0
        new_settings["custom_languages"] = custom_langs

        parent_app.settings.update(new_settings)
        save_settings(parent_app.settings)
        parent_app.apply_settings_changes()
        parent_app.append_status("Settings saved.")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Match App.__init__ geometry exactly so splash and main window occupy the same spot
    _WIN_X, _WIN_Y, _WIN_W, _WIN_H = 200, 200, 1100, 720

    splash_path = os.path.join(BASE_PATH, "juhalempiainensoftware.png")
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
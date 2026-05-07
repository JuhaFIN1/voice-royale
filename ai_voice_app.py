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
import io
import json
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
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

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
}

LANG_FLAG_CODES = {
    "English": "us",
    "German": "de",
    "Swedish": "se",
    "Finnish": "fi",
    "Russian": "ru",
    "Italian": "it",
}

# Edge TTS voices mapping
EDGE_VOICES = {
    "English": "en-US-AriaNeural",
    "German": "de-DE-KatjaNeural",
    "Swedish": "sv-SE-SofieNeural",
    "Finnish": "fi-FI-NooraNeural",
    "Russian": "ru-RU-SvetlanaNeural",
    "Italian": "it-IT-ElsaNeural",
}

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
                sd.play(audio_data, samplerate=samplerate, device=device_index)
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
# APPLICATION
# =========================
class App(QWidget):
    sig_mic_level = pyqtSignal(int)
    sig_out_level = pyqtSignal(int)
    sig_status = pyqtSignal(str)

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
        else:
            painter.fillRect(0, 0, 20, 14, Qt.GlobalColor.lightGray)

        painter.end()
        return QIcon(pixmap)

    def build_language_icons(self):
        icons = {}
        for lang, country_code in LANG_FLAG_CODES.items():
            icons[lang] = self.create_flag_icon(country_code)
        return icons

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Voice Router")
        self.setGeometry(200, 200, 900, 560)
        self.setStyleSheet(
            "QWidget { background: #1a1f2b; color: #f5f5f5; }"
            "QLabel { font-size: 13px; }"
            "QPushButton { background: #3b4a6b; border: 1px solid #4f5f7f; padding: 10px; border-radius: 6px; }"
            "QPushButton:hover { background: #50648f; }"
            "QPushButton:disabled { background: #2d3346; color: #777777; }"
            "QComboBox, QTextEdit { background: #252c40; border: 1px solid #3b4a6b; color: #f5f5f5; }"
            "QListWidget { background: #171c2d; border: 1px solid #3b4a6b; }"
        )

        main_layout = QHBoxLayout()
        left_panel = QVBoxLayout()
        right_panel = QVBoxLayout()

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setPlainText("Ready. Enter text, select language, then press Speak or use Ctrl+Alt+Space.\nUse Test Audio to verify your output device.")
        self.status_text.setMinimumHeight(80)
        self.status_text.setMaximumHeight(120)
        self.status_text.setStyleSheet("font-weight: bold; color: #dcdcdc; background: #1a1f2b; border: 1px solid #3b4a6b;")
        left_panel.addWidget(self.status_text)

        self.translated_label = QLabel("Translated text will appear here.")
        self.translated_label.setWordWrap(True)
        self.translated_label.setMinimumHeight(40)
        self.translated_label.setStyleSheet("color: #b0b0b0;")
        left_panel.addWidget(self.translated_label)

        self.textbox = QTextEdit()
        self.textbox.setPlaceholderText("Type the phrase to speak...\nOr press Record & Speak to use voice input.")
        self.textbox.setMinimumHeight(180)
        left_panel.addWidget(self.textbox)

        self.lang_icons = self.build_language_icons()
        self.langbox = QComboBox()
        for lang in LANGS.keys():
            icon = self.lang_icons.get(lang)
            if icon:
                self.langbox.addItem(icon, lang)
            else:
                self.langbox.addItem(lang)
        left_panel.addWidget(QLabel("Target language:"))
        left_panel.addWidget(self.langbox)

        self.backend_combo = QComboBox()
        backend_items = ["ElevenLabs", "Edge TTS (free)"]
        for backend in backend_items:
            self.backend_combo.addItem(backend)
        self.backend_combo.setCurrentText(DEFAULT_TTS_BACKEND)
        left_panel.addWidget(QLabel("TTS backend:"))
        left_panel.addWidget(self.backend_combo)

        self.device_list = QListWidget()
        self.device_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.device_list.setMaximumHeight(200)
        self.device_list.setStyleSheet("""
            QListWidget {
                background: #252c40;
                border: 1px solid #3b4a6b;
                border-radius: 4px;
            }
            QListWidget::item {
                background: #2a3441;
                border: 1px solid #3b4a6b;
                border-radius: 2px;
                margin: 1px;
                padding: 2px;
            }
            QListWidget::item:selected {
                background: #50648f;
                border: 1px solid #6b7fa0;
            }
        """)
        left_panel.addWidget(QLabel("Audio output devices (select multiple):"))
        left_panel.addWidget(self.device_list)
        self.device_list.itemSelectionChanged.connect(self.on_output_device_changed)

        device_button_layout = QHBoxLayout()
        self.refresh_devices_button = QPushButton("🔄 Refresh Devices")
        self.refresh_devices_button.clicked.connect(self.refresh_all_devices)
        device_button_layout.addWidget(self.refresh_devices_button)
        device_button_layout.addStretch()
        left_panel.addLayout(device_button_layout)

        self.input_device_combo = QComboBox()
        left_panel.addWidget(QLabel("Audio input device (microphone):"))
        left_panel.addWidget(self.input_device_combo)
        self.input_device_combo.currentIndexChanged.connect(self.on_input_device_changed)

        button_layout = QHBoxLayout()
        self.speak_button = QPushButton("Speak")
        self.speak_button.clicked.connect(self.on_speak)
        button_layout.addWidget(self.speak_button)

        self.record_button = QPushButton("🎤 Record")
        self.record_button.clicked.connect(self.on_record_toggle)
        button_layout.addWidget(self.record_button)

        self.test_audio_button = QPushButton("🔊 Test Audio")
        self.test_audio_button.clicked.connect(self.on_test_audio)
        button_layout.addWidget(self.test_audio_button)

        self.device_info_button = QPushButton("ℹ️ Device Info")
        self.device_info_button.clicked.connect(self.on_device_info)
        button_layout.addWidget(self.device_info_button)
        left_panel.addLayout(button_layout)

        self.favorite_button = QPushButton("⭐ Add Favorite")
        self.favorite_button.clicked.connect(self.toggle_favorite)
        left_panel.addWidget(self.favorite_button)

        self.hotkey_label = QLabel("Global hotkey: Ctrl+Alt+Space")
        self.hotkey_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hotkey_label.setStyleSheet("color: #99a6c8; margin-top: 12px;")
        left_panel.addWidget(self.hotkey_label)

        _meter_style_mic = (
            "QProgressBar { background: #111620; border: 1px solid #3b4a6b; border-radius: 3px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, x2:1,"
            " stop:0 #22cc44, stop:0.55 #cccc22, stop:1 #cc2222); border-radius: 2px; }"
        )
        _meter_style_out = (
            "QProgressBar { background: #111620; border: 1px solid #3b4a6b; border-radius: 3px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, x2:1,"
            " stop:0 #2266ff, stop:0.55 #aa44cc, stop:1 #cc2222); border-radius: 2px; }"
        )
        _label_style = "color: #778; font-size: 10px; min-width: 32px;"

        mic_row = QHBoxLayout()
        mic_lbl = QLabel("MIC")
        mic_lbl.setStyleSheet(_label_style)
        self.mic_level_bar = QProgressBar()
        self.mic_level_bar.setRange(0, 1000)
        self.mic_level_bar.setValue(0)
        self.mic_level_bar.setTextVisible(False)
        self.mic_level_bar.setFixedHeight(12)
        self.mic_level_bar.setStyleSheet(_meter_style_mic)
        mic_row.addWidget(mic_lbl)
        mic_row.addWidget(self.mic_level_bar)
        left_panel.addLayout(mic_row)

        out_row = QHBoxLayout()
        out_lbl = QLabel("OUT")
        out_lbl.setStyleSheet(_label_style)
        self.output_level_bar = QProgressBar()
        self.output_level_bar.setRange(0, 1000)
        self.output_level_bar.setValue(0)
        self.output_level_bar.setTextVisible(False)
        self.output_level_bar.setFixedHeight(12)
        self.output_level_bar.setStyleSheet(_meter_style_out)
        out_row.addWidget(out_lbl)
        out_row.addWidget(self.output_level_bar)
        left_panel.addLayout(out_row)

        # Wire signals — safe cross-thread UI updates
        self.sig_mic_level.connect(self.mic_level_bar.setValue)
        self.sig_out_level.connect(self.output_level_bar.setValue)
        self.sig_status.connect(self._on_status)

        main_layout.addLayout(left_panel, 2)

        history_frame = QFrame()
        history_frame.setFrameShape(QFrame.Shape.StyledPanel)
        history_frame.setStyleSheet("background: #151a28; border: 1px solid #2f3c5a; border-radius: 8px;")
        right_layout = QVBoxLayout(history_frame)
        right_layout.addWidget(QLabel("History (last 10)"))
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_history_item_selected)
        self.history_list.setMinimumHeight(200)
        self.history_list.setStyleSheet("""
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
                font-family: "Segoe UI", sans-serif;
                font-weight: bold;
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
        """)
        right_layout.addWidget(self.history_list)

        right_layout.addWidget(QLabel("Favorites"))
        self.favorites_list = QListWidget()
        self.favorites_list.itemClicked.connect(self.on_history_item_selected)
        self.favorites_list.setMinimumHeight(200)
        self.favorites_list.setStyleSheet("""
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
                font-family: "Segoe UI", sans-serif;
                font-weight: bold;
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
        """)
        right_layout.addWidget(self.favorites_list)

        main_layout.addWidget(history_frame, 1)

        self.setLayout(main_layout)

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

        # Get current language
        current_lang = self.langbox.currentText()
        lang_code = LANGS.get(current_lang, "auto")

        # Create favorite entry with text and language
        favorite_entry = {
            "text": text,
            "language": lang_code,
            "display_lang": current_lang
        }

        # Check if already favorited (by text)
        existing_fav = next((f for f in self.favorites if isinstance(f, dict) and f.get("text") == text), None)
        if existing_fav:
            self.favorites.remove(existing_fav)
            self.append_status("Removed from favorites.")
        else:
            self.favorites.insert(0, favorite_entry)
            self.append_status("Added to favorites.")

        self.history_data["favorites"] = self.favorites
        save_history_data(self.history_data)
        self.refresh_history_views()

    def on_history_item_selected(self, item):
        item_data = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(item_data, dict):
            # New format with language info
            text = item_data.get("text", "")
            display_lang = item_data.get("display_lang", "Auto")

            self.textbox.setPlainText(text)
            # Set the language dropdown to match
            lang_index = self.langbox.findText(display_lang)
            if lang_index >= 0:
                self.langbox.setCurrentIndex(lang_index)
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
        self.device_list.clear()
        devices = list_output_devices()
        if not devices:
            item = QListWidgetItem("No audio output devices detected")
            item.setData(Qt.ItemDataRole.UserRole, -1)
            self.device_list.addItem(item)
            self.append_status("No audio output devices detected")
            return

        # Prioritize routing-capable devices (VoiceMeeter, virtual, Rodecaster, etc.)
        routing_devices = [
            (index, name) for index, name in devices
            if any(keyword in name.lower() for keyword in ["voicemeeter", "virtual", "vb-audio", "voice", "rodecaster", "rode caster"])
        ]
        other_devices = [
            (index, name) for index, name in devices
            if not any(keyword in name.lower() for keyword in ["voicemeeter", "virtual", "vb-audio", "voice", "rodecaster", "rode caster"])
        ]

        # Add routing devices first (recommended for audio routing)
        for index, name in routing_devices:
            item = QListWidgetItem(f"🎛️ {name}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.device_list.addItem(item)

        # Then other devices
        for index, name in other_devices[:8]:  # Allow more devices since user can select multiple
            item = QListWidgetItem(f"🔊 {name}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.device_list.addItem(item)

        device_count = len(routing_devices) + min(len(other_devices), 8)
        self.append_status(f"Found {device_count} output devices ({len(routing_devices)} routing-capable)")

        # Restore previously selected devices
        self.restore_selected_output_devices()

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
        """Get list of selected output device indices"""
        selected_devices = []
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.isSelected():
                device_index = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(device_index, int) and device_index >= 0:
                    selected_devices.append(device_index)
        return selected_devices if selected_devices else None

    def get_selected_input_device(self):
        index = self.input_device_combo.currentData()
        return index if isinstance(index, int) and index >= 0 else None

    def restore_selected_output_devices(self):
        """Restore previously selected output devices from history"""
        saved_devices = self.history_data.get("selected_output_devices", [])
        if saved_devices:
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                device_index = item.data(Qt.ItemDataRole.UserRole)
                if device_index in saved_devices:
                    item.setSelected(True)

    def on_output_device_changed(self):
        """Called when device selection changes - save to history"""
        selected_devices = self.get_selected_devices()
        if selected_devices:
            self.history_data["selected_output_devices"] = selected_devices
            save_history_data(self.history_data)

    def on_input_device_changed(self):
        selected_device = self.get_selected_input_device()
        if selected_device is not None:
            self.history_data["selected_input_device"] = selected_device
            save_history_data(self.history_data)

    def register_hotkey(self):
        try:
            keyboard.add_hotkey("ctrl+alt+space", self.on_hotkey_triggered)
        except Exception as exc:
            self.append_status(f"Hotkey registration failed: {exc}")

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

        self.record_button.setText("⏹️ Stop Recording")
        self.record_button.setStyleSheet("QPushButton { background: #cc3333; color: white; }")
        self.append_status(f"🎤 Recording from: {input_device_name}")

    def _stop_recording(self):
        self.is_recording = False
        self.record_button.setEnabled(False)
        self.record_button.setText("⏳ Processing...")
        self.record_button.setStyleSheet("QPushButton { background: #555; color: #aaa; }")

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

            # Add to textbox
            current_text = self.textbox.toPlainText().strip()
            new_text = (current_text + " " + transcribed).strip() if current_text else transcribed
            QTimer.singleShot(0, lambda t=new_text: self.textbox.setPlainText(t))
            self.append_status(f"Transcribed: {transcribed}")

            # Ask to translate+play if target language is set
            target_lang = self.langbox.currentText()
            if target_lang != "Auto":
                QTimer.singleShot(0, lambda t=transcribed: self.ask_play_transcribed(t))

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
        self.record_button.setStyleSheet("")
        self.record_button.setText("🎤 Record")

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
            device_names = []
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if item.isSelected():
                    device_names.append(item.text())
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

        device_names = []
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.isSelected():
                device_names.append(item.text())
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
                device_names = []
                for i in range(self.device_list.count()):
                    item = self.device_list.item(i)
                    if item.isSelected():
                        device_names.append(item.text())
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())
# AI Voice Router

Copyright (c) 2026 Juha Lempiäinen. All rights reserved.
Use permitted. Modification and redistribution of source code prohibited — see [LICENSE](LICENSE).

Windows desktop app (PyQt6) that listens for a wake-word, transcribes your speech, translates it with GPT-4.1-mini, and speaks the result via TTS — all routed to any audio output device you choose.

## Features

- **Wake-word detection** — "Jarvis, translate to German: hello team" triggers automatically
  - Picovoice Porcupine (offline, accurate) if you have an AccessKey
  - Whisper VAD fallback (works without any key)
- **Speech-to-text** — OpenAI Whisper API
- **AI translation** — GPT-4.1-mini parses target language and translates
- **TTS output** — Edge TTS (free), ElevenLabs, or local pyttsx3 fallback
- **Multi-device output** — play to multiple audio devices simultaneously
- **15 languages** — Auto, English, German, Swedish, Finnish, Russian, Italian, Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian, Japanese, Chinese, Hungarian
- **Global hotkey** — push-to-talk from any app (default: `Ctrl+Alt+Space`)
- **History & favorites** — saved to `speech_history.json`
- **Dark-themed UI** with mic/output level meters

## Requirements

- Windows 10/11
- Python 3.10+
- OpenAI API key (Whisper + GPT-4.1-mini)
- Optional: ElevenLabs API key, Picovoice AccessKey

```
pip install -r requirements.txt
```

## Setup

1. Copy your API keys to `credentials.env`:
   ```
   OPENAI_API_KEY=sk-...
   ELEVEN_API_KEY=...        # optional
   VOICE_ID=...              # optional ElevenLabs voice
   ```

2. Run:
   ```
   python ai_voice_app.py
   ```

3. For wake-word with Porcupine (recommended):
   - Register free at [console.picovoice.ai](https://console.picovoice.ai)
   - Paste your AccessKey in ⚙️ Settings → Picovoice AccessKey
   - Choose a wake-word (jarvis, computer, alexa, terminator…)
   - Press **👂 Start Listening**

## Usage

### Wake-word mode
Say your wake-word → wait for the beep → speak your command:

> *"Jarvis"* → *"in German, hello team, how is everyone doing?"*

The app translates and speaks the result in the selected language.

### Push-to-talk
Press `Ctrl+Alt+Space` → speak → release → translation plays.

### Settings (⚙️)
| Setting | Description |
|---|---|
| Wake keyword | Built-in Porcupine words or custom .ppn file |
| Picovoice AccessKey | Free key from console.picovoice.ai |
| Global hotkey | Default: `ctrl+alt+space` |
| Default target language | Pre-selected language |
| Default TTS backend | Edge TTS (free) or ElevenLabs |
| Command capture (s) | How long to record after wake-word (default: 6s) |

## Building EXE

```
build_app.bat
```

Requires PyInstaller. Output in `dist/`.

## File Structure

| File | Description |
|---|---|
| `ai_voice_app.py` | Entire app (~2100 lines) |
| `credentials.env` | API keys (not committed) |
| `app_settings.json` | User settings |
| `speech_history.json` | Translation history |
| `requirements.txt` | Python dependencies |
| `build_app.bat` | PyInstaller build script |

# AI Voice Router

Copyright (c) 2026 Juha Lempiäinen. All rights reserved.
Use permitted. Modification and redistribution of source code prohibited — see [LICENSE](LICENSE).

Windows desktop app (PyQt6) that listens for a wake-word, transcribes your speech, translates it with GPT-4.1-mini, and speaks the result via TTS — all routed to any audio output device you choose, including virtual audio cables for game voice chat.

## Features

- **Wake-word detection** — say "Jarvis, in German: hello team" to trigger automatically
  - Picovoice Porcupine (offline, accurate) if you have an AccessKey
  - Whisper VAD fallback (works without any key)
- **Speech-to-text** — OpenAI Whisper API, transcribed text shown in the type box
- **AI translation** — GPT-4.1-mini parses target language and translates
- **TTS output** — Edge TTS (free), ElevenLabs, or local pyttsx3 fallback
- **Multi-device output** — play to multiple audio devices simultaneously
- **22 built-in languages + custom** — Auto, English, German, Swedish, Finnish, Russian, Italian, Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian, Japanese, Chinese, Hungarian, Polish, Czech, Catalan, Belarusian, Spanish, French — plus any language you add in Settings
- **Global hotkey** — push-to-talk from any app (default: `Ctrl+Alt+Space`)
- **History & favorites** — favorites auto-cache translated audio so replaying needs no API call
- **Virtual mic (VB-Cable)** — one-click install from Settings so TTS audio goes into game voice chat
- **Dark-themed UI** — mic/output level meters, record button embedded in the type box
- **Splash screen** — branded startup screen (replace `juhalempiainensoftware.png`)

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
   VOICE_ID=...              # optional ElevenLabs voice ID
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
Say your wake-word → the app records → speaks the translation:

> *"Jarvis"* → *"in German, hello team, how is everyone doing?"*

### Push-to-talk
Press `Ctrl+Alt+Space` → speak → translation plays automatically.

### Type & speak
Type in the text box → press 🔊 Speak — or use the 🎤 button inside the text box to record.

### Favorites
Star (⭐) any phrase — the app caches the translated audio immediately.
Next time you click that favorite, it plays instantly with no API call.

### Game voice chat (virtual mic)
1. Open ⚙️ Settings → click **Install VB-Cable (Virtual Mic)**
2. Approve the Windows admin prompt
3. Select **CABLE Input** as the output device in this app
4. Select **CABLE Output** as the microphone in your game / Discord

## Settings (⚙️)

| Setting | Description |
|---|---|
| Wake keyword | Built-in Porcupine list or type any word (Whisper mode) |
| Custom wake .ppn | Custom wake-word model from console.picovoice.ai |
| Picovoice AccessKey | Free key — leave empty for Whisper-based detection |
| Global hotkey | Default: `ctrl+alt+space` |
| Default target language | Pre-selected translation language |
| Default TTS backend | Edge TTS (free) or ElevenLabs |
| Command capture (s) | Recording duration after wake-word (default: 6 s) |
| Custom languages | Add any language with name, country code, Edge TTS voice |
| Virtual mic | Install VB-Cable for game voice chat routing |

## Building EXE

```
build_app.bat
```

Requires PyInstaller. Output in `dist/`.

## File Structure

| File / Folder | Description |
|---|---|
| `ai_voice_app.py` | Entire app (~2600 lines) |
| `credentials.env` | API keys (not committed) |
| `app_settings.json` | User settings |
| `speech_history.json` | Translation history + favorites |
| `favorites_audio/` | Cached TTS WAV files for favorites |
| `juhalempiainensoftware.png` | Splash screen image |
| `requirements.txt` | Python dependencies |
| `build_app.bat` | PyInstaller build script |

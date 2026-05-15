# AI Voice Router

Copyright (c) 2026 Juha Lempiäinen. All rights reserved.
Use permitted. Modification and redistribution of source code prohibited — see [LICENSE](LICENSE).

Windows desktop app (PyQt6) that listens for a wake-word, transcribes your speech, translates it with GPT-4.1-mini, and speaks the result via TTS — all routed to any audio output device you choose, including virtual audio cables for game voice chat.

## Download

**[→ Download installer (Windows)](https://github.com/JuhaFIN1/ai-voice-router/releases/latest)**

Run `AI_Voice_Router_Setup_1.0.1.exe` — no Python needed. The first-run wizard guides you through setup.

> **Windows SmartScreen warning?** Click **"More info"** → **"Run anyway"**.
> This appears because the installer is not commercially code-signed. The app is safe.

## Features

- **First-run wizard** — guided setup: OpenAI API key + mic and speaker selection with live audio test
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
- **Live audio meters** — mic level shown during recording AND while Start Listening is active
- **Dark-themed UI** — record button embedded in the type box, splash screen on startup

## Installation (EXE — recommended)

1. Download `AI_Voice_Router_Setup_1.0.0.exe` from [Releases](https://github.com/JuhaFIN1/ai-voice-router/releases/latest)
2. Run the installer — it creates Start Menu shortcuts and an optional desktop icon
3. On first launch the **Setup Wizard** opens automatically:
   - **Step 1** — get an OpenAI API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (free tier available)
   - **Step 2** — paste and test the key
   - **Step 3** — select your microphone and speakers, play a test beep
4. Done — the app opens and is ready to use

Upgrading: just run the new installer over the old one. Your API key, settings, and history are preserved.

## API Keys

| Key | Required | Where to get |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) — free credits for new accounts |
| `ELEVEN_API_KEY` + `VOICE_ID` | No | [elevenlabs.io](https://elevenlabs.io) — realistic TTS voices |
| `PICOVOICE_ACCESS_KEY` | No | [console.picovoice.ai](https://console.picovoice.ai) — offline wake-word, free personal use |

Cost estimate: ~$0.001 per voice interaction — 1 000 interactions ≈ $1.

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

## Running from source

```
pip install -r requirements.txt
python ai_voice_app.py
```

## Building EXE + installer

```
build_app.bat
```

Requires Python + PyInstaller. Inno Setup is downloaded automatically if not installed.
Output: `installer_output\AI_Voice_Router_Setup_1.0.0.exe`

## File Structure

| File / Folder | Description |
|---|---|
| `ai_voice_app.py` | Entire app (~2900 lines) |
| `credentials.env` | API keys (not committed) |
| `app_settings.json` | User settings |
| `speech_history.json` | Translation history + favorites |
| `favorites_audio/` | Cached TTS WAV files for favorites |
| `juhalempiainensoftware.png` | Splash screen image |
| `requirements.txt` | Python dependencies |
| `build_app.bat` | PyInstaller + installer build script |
| `installer.iss` | Inno Setup installer script |

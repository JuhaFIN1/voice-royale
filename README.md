# AI Voice Router

Copyright (c) 2026 Juha Lempiäinen. All rights reserved.
Use permitted. Modification and redistribution of source code prohibited — see [LICENSE](LICENSE).

Windows desktop app (PyQt6) that listens for a wake-word, transcribes your speech, translates it with GPT-4.1-mini, and speaks the result via TTS — routed to any audio output device, including virtual audio cables for game voice chat. Now with live voice morphing, soundboard, and Stream Deck XL support.

## Download

**[→ Download installer (Windows)](https://github.com/JuhaFIN1/ai-voice-router/releases/latest)**

Run `AI_Voice_Router_Setup_1.1.0.exe` — no Python needed. The first-run wizard guides you through setup.

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
- **Multi-device output** — play to multiple audio devices simultaneously, always-visible level meters
- **22 built-in languages + custom** — Auto, English, German, Swedish, Finnish, Russian, Italian, Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian, Japanese, Chinese, Hungarian, Polish, Czech, Catalan, Belarusian, Spanish, French — plus any language you add in Settings
- **Global hotkey** — push-to-talk from any app (default: `Ctrl+Alt+Space`)
- **History & favorites** — favorites auto-cache translated audio so replaying needs no API call
- **Live voice morphing (Voice FX)** — real-time pitch shift and effects routed to a virtual output (VB-Cable / Voicemod). Presets: Normal, Pitch +4/+8, Pitch -4/-8, Robot, Deep, Helium
- **Soundboard** — up to 10 pages × 56 buttons. Assign your own audio files and images per button, right-click to configure. Pages support rename and delete
- **Stream Deck XL** — full 32-button layout: record, wake, speak, stop, language shortcuts, soundboard slots, Voice FX presets, TTS toggle, settings
- **Virtual mic (VB-Cable)** — one-click install from Settings so TTS audio goes into game voice chat
- **Data backup** — export all your data (settings, history, soundboard files, API keys) to a ZIP; restore with one click
- **Dark-themed UI** — GitHub-style dark theme, record button embedded in the type box, splash screen on startup

## Installation (EXE — recommended)

1. Download `AI_Voice_Router_Setup_1.1.0.exe` from [Releases](https://github.com/JuhaFIN1/ai-voice-router/releases/latest)
2. Run the installer — it creates Start Menu shortcuts and an optional desktop icon
3. On first launch the **Setup Wizard** opens automatically:
   - **Step 1** — get an OpenAI API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (free tier available)
   - **Step 2** — paste and test the key
   - **Step 3** — select your microphone and speakers, play a test beep
4. Done — the app opens and is ready to use

Upgrading: just run the new installer over the old one. Your API key, settings, and history are preserved.

## Optional packages

Install these for extra features (all optional):

| Package | Feature |
|---|---|
| `pip install streamdeck` | Stream Deck XL control (requires Pillow) |
| `pip install pyrubberband` | Higher-quality pitch shift in Voice FX (+ rubberband CLI) |
| `pip install pydub` | MP3/OGG support in Soundboard (+ ffmpeg on PATH) |

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

### Soundboard
Right-click any button → **Assign Sound** (WAV/MP3/OGG) or **Assign Image**.
Audio is automatically converted to mono 22 kHz WAV on import to save space.
Add pages with the **+** button next to the tabs (up to 10). Right-click a tab to rename or delete.

### Voice FX (live voice morphing)
Enable in the **Voice FX** tab — select a virtual output (VB-Cable/Voicemod) and pick a preset.
Your mic audio is pitch-shifted in real time and sent to the chosen output device.

### Stream Deck XL
Connect before launching — the app assigns buttons automatically:
- 0 = Record, 1 = Wake Listen, 2 = Speak, 3 = Stop
- 4–11 = Language shortcuts
- 12–23 = Soundboard slots (page 1)
- 24–29 = Voice FX presets
- 30 = TTS backend toggle, 31 = Settings

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
| Data backup | Export/import all personal data as a ZIP archive |

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
Output: `installer_output\AI_Voice_Router_Setup_1.1.0.exe`

## File Structure

| File / Folder | Description |
|---|---|
| `ai_voice_app.py` | Entire app (~4000 lines) |
| `credentials.env` | API keys (not committed) |
| `app_settings.json` | User settings |
| `speech_history.json` | Translation history + favorites |
| `favorites_audio/` | Cached TTS WAV files for favorites |
| `soundboard/` | Imported soundboard audio and images |
| `juhalempiainensoftware.png` | Splash screen image |
| `requirements.txt` | Python dependencies |
| `build_app.bat` | PyInstaller + installer build script |
| `installer.iss` | Inno Setup installer script |

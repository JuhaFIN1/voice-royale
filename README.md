# Voice Royale

Copyright (c) 2026 Juha Lempiäinen. All rights reserved.
Use permitted. Modification and redistribution of source code prohibited — see [LICENSE](LICENSE).

Windows desktop app (PyQt6) that listens for a wake-word, transcribes your speech, translates it with GPT-4.1-mini, and speaks the result via TTS — routed to any audio output device, including virtual audio cables for game voice chat. Now with live voice morphing, soundboard, and Stream Deck XL support.

## Download

| Platform | Link |
|---|---|
| **Windows** | [Voice_Royale_Setup_1.2.7.exe](https://github.com/JuhaFIN1/voice-royale/releases/latest) — no Python needed |
| **macOS** | [Voice_Royale_1.2.7.dmg](https://github.com/JuhaFIN1/voice-royale/releases/latest) |

> **Windows SmartScreen warning?** Click **"More info"** → **"Run anyway"**.
> This appears because the installer uses a self-signed certificate. The app is safe.

## Features

- **First-run wizard** — guided 4-step setup: OpenAI API key → VB-Cable virtual mic check/install → mic and speaker selection with live recording test (records 3 s and plays back)
- **Wake-word detection** — say "Jarvis, in German: hello team" to trigger automatically
  - Picovoice Porcupine (offline, accurate) if you have an AccessKey
  - Whisper VAD fallback (works without any key)
- **Speech-to-text** — OpenAI Whisper API, transcribed text shown in the type box
- **AI translation** — GPT-4.1-mini parses target language and translates
- **Translation engine** — choose Google Translate (free, default), DeepL, or OpenAI
- **TTS output** — Edge TTS (free), ElevenLabs, or local pyttsx3 fallback
- **Multi-device output** — play to multiple audio devices simultaneously, always-visible level meters
- **28 built-in languages + custom** — Auto, English, German, Swedish, Finnish, Russian, Italian, Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian, Japanese, Chinese, Hungarian, Polish, Czech, Catalan, Belarusian, Spanish, French, Turkish, Hindi, Hebrew, Greek, Croatian, Arabic — plus any language you add in Settings
- **Global hotkey** — push-to-talk from any app (default: `Ctrl+Alt+Space`)
- **History & favorites** — favorites auto-cache translated audio so replaying needs no API call
- **Live voice morphing (Voice FX)** — real-time pitch shift and effects routed to a virtual output (VB-Cable / Voicemod). Presets: Normal, Pitch +4/+8, Pitch -4/-8, Robot, Deep, Helium. **Hear Myself** toggle lets you monitor your own processed voice through headphones in real time
- **Wake-word instructions** — usage guide appears automatically when Listen mode is active
- **Soundboard** — up to 10 pages × 56 buttons. Edit Mode: drag-and-drop audio/image onto any button. Right-click to configure. Pages support rename and delete
- **Stream Deck XL** — full 32-button layout: record, wake, speak, stop, language shortcuts, soundboard slots, Voice FX presets, TTS toggle, settings
- **Virtual mic (VB-Cable)** — one-click install from Settings so TTS audio goes into game voice chat
- **Data backup** — export all your data (settings, history, soundboard files, API keys) to a ZIP; restore with one click
- **Dark-themed UI** — GitHub-style dark theme, record button embedded in the type box, splash screen on startup

## Installation (Windows)

1. Download `Voice_Royale_Setup_1.2.7.exe` from [Releases](https://github.com/JuhaFIN1/voice-royale/releases/latest)
2. Run the installer — it creates Start Menu shortcuts and an optional desktop icon
3. On first launch the **Setup Wizard** opens automatically:
   - **Step 1/4** — get an OpenAI API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (free tier available)
   - **Step 2/4** — paste and test the key
   - **Step 3/4** — VB-Cable virtual mic check — install with one click if not already present (needed for game voice chat)
   - **Step 4/4** — select your microphone and speakers, record 3 seconds to verify the mic works, play a test beep
4. Done — the app opens and is ready to use

Upgrading: just run the new installer over the old one. Your API key, settings, and history are preserved.

## Installation (macOS)

1. Download `Voice_Royale_1.2.7.dmg` from [Releases](https://github.com/JuhaFIN1/voice-royale/releases/latest)
2. Open the DMG and drag **Voice Royale** to Applications
3. First launch: right-click → **Open** to bypass Gatekeeper (app is ad-hoc signed, not notarized)
4. Grant microphone and accessibility permissions when prompted

## Optional packages

Install these for extra features (all optional):

| Package | Feature |
|---|---|
| `pip install pyrubberband` | Higher-quality pitch shift in Voice FX (+ rubberband CLI) |
| `pip install pydub` | MP3/OGG support in Soundboard (+ ffmpeg on PATH) |

## API Keys

| Key | Required | Where to get |
|---|---|---|
| `OPENAI_API_KEY` | **Yes** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) — free credits for new accounts |
| `ELEVEN_API_KEY` + `VOICE_ID` | No | [elevenlabs.io](https://elevenlabs.io) — realistic TTS voices |
| `PICOVOICE_ACCESS_KEY` | No | [console.picovoice.ai](https://console.picovoice.ai) — offline wake-word, free personal use |
| `DEEPL_API_KEY` | No | [deepl.com/pro-api](https://www.deepl.com/pro-api) — free tier available |

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
Click **Edit** in the soundboard corner to enter Edit Mode.
Drag an audio file (WAV/MP3/OGG) or image onto any button to assign it.
Right-click a button for options. Add pages with **+** (up to 10). Right-click a tab to rename or delete.

### Voice FX (live voice morphing)
Enable in the **Voice FX** tab — select a virtual output (VB-Cable/Voicemod) as FX Output and pick a preset.
Your mic audio is pitch-shifted in real time and sent to the chosen output device.

**Hear Myself** — toggle the **Hear Myself** button and select a monitor output (e.g. your headphones).
You will hear your own voice with the active preset applied so you know what others hear.

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
| Translation engine | Google Translate (free), DeepL, or OpenAI |
| DeepL API key | Optional — required if DeepL engine is selected |
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

Requires Python + PyInstaller. Inno Setup is installed automatically via Chocolatey if not present.
The installer is signed automatically if `SIGN_CERT_PATH` and `SIGN_CERT_PASSWORD` are set in `.env`.
Output: `installer_output\Voice_Royale_Setup_1.2.7.exe`

## File Structure

| File / Folder | Description |
|---|---|
| `ai_voice_app.py` | Entire app (~5600 lines) |
| `credentials.env` | API keys (not committed) |
| `app_settings.json` | User settings |
| `speech_history.json` | Translation history + favorites |
| `favorites_audio/` | Cached TTS WAV files for favorites |
| `soundboard/` | Imported soundboard audio and images |
| `juhalempiainensoftware.png` | Splash screen image |
| `requirements.txt` | Python dependencies |
| `build_app.bat` | PyInstaller + installer build + signing |
| `installer.iss` | Inno Setup installer script |

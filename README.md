# Voice Royale

Copyright (c) 2026 Juha Lempiäinen. All rights reserved.
Use permitted. Modification and redistribution of source code prohibited — see [LICENSE](LICENSE).

Windows + macOS desktop app (PyQt6) that listens for a wake-word, transcribes your speech, translates it with GPT-4.1-mini, and speaks the result via TTS — routed to any audio output device, including virtual audio cables for game voice chat. Now with live voice morphing, soundboard, Stream Deck XL support, and full Voicemeeter Banana integration for zero-config game chat routing.

## Download

| Platform | Link |
|---|---|
| **Windows** | [Voice_Royale_Setup_1.3.27.exe](https://github.com/JuhaFIN1/voice-royale/releases/latest) — no Python needed |
| **macOS Apple Silicon** (M1/M2/M3) | [Voice_Royale_1.3.27_macOS_arm64.dmg](https://github.com/JuhaFIN1/voice-royale/releases/latest) |
| **macOS Intel** (x86_64) | [Voice_Royale_1.3.27_macOS_x86_64.dmg](https://github.com/JuhaFIN1/voice-royale/releases/latest) |

> **Windows SmartScreen warning?** Click **"More info"** → **"Run anyway"**.
> This appears because the installer uses a self-signed certificate. The app is safe.

> **Not sure which macOS build?** M1/M2/M3 Macs (2020 and later) → arm64. Older Intel Macs → x86_64.

## Features

- **Setup Wizard** — guided 6-step setup: packages → OpenAI API key → VB-Cable → Voicemeeter Banana → mic/speaker selection → end-to-end audio test (mic level, TTS playback, soundboard beep)
- **Voicemeeter Banana auto-start** — app launches Voicemeeter Banana automatically on startup; no manual action needed
- **Zero-config game chat** — wizard installs and configures Voicemeeter Banana, sets Windows default microphone to Voicemeeter Out B1 automatically; Discord, Fortnite, and all other apps pick it up with no in-game changes
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
- **Soundboard** — up to 10 pages × 55 buttons per page:
  - **Edit Mode**: drag audio/image onto any button; drag a button over a tab label (700 ms) to move it cross-page; drag tab labels to reorder pages
  - **Bulk import**: drop a folder or multiple files onto a button to fill consecutive slots; or right-click → Bulk Import
  - **Subfolders**: right-click a button in Edit Mode → "Kansioksi…" to create a nested folder of 55 more slots
  - **Image search**: right-click → "Etsi kuva netistä…" — search DuckDuckGo Images by button name, browse thumbnails, download with one click
  - **■ STOP button**: fixed red button in the bottom-right corner — stops all active playback instantly (soundboard, speak, favorites, wake TTS)
  - Right-click to rename, assign sound/image, link to another page, or clear
  - Add pages with **+** (up to 10); right-click a tab to rename or delete
- **Stream Deck XL** — full 32-button layout via official Elgato plugin + local HTTP API (port 17842)
- **Virtual mic (VB-Cable)** — one-click install from wizard so TTS audio goes into game voice chat
- **Windows autostart** — start with Windows, optionally minimized to tray
- **Auto-update** — Settings → Päivitys checks GitHub releases; downloads and launches the installer
- **Data backup** — export all settings, history, soundboard audio/images, and API keys to a ZIP; restore with one click
- **Dark-themed UI** — GitHub-style dark theme, record button embedded in the type box, splash screen on startup

## Installation (Windows)

1. Download `Voice_Royale_Setup_1.3.27.exe` from [Releases](https://github.com/JuhaFIN1/voice-royale/releases/latest)
2. Run the installer — it creates Start Menu shortcuts and an optional desktop icon
3. On first launch the **Setup Wizard** opens automatically:
   - **Step 1/6** — install required Python packages automatically
   - **Step 2/6** — enter your OpenAI API key ([platform.openai.com/api-keys](https://platform.openai.com/api-keys), free credits for new accounts)
   - **Step 3/6** — VB-Cable virtual mic: one-click install if not present
   - **Step 4/6** — Voicemeeter Banana: one-click install + automatic routing configuration
     - After clicking **Konfiguroi reititys**, open Voicemeeter Banana and confirm Hardware Input 1 shows your mic/Chat device with **B1** lit. If it's blank, click Hardware Input 1 and select the device manually.
   - **Step 5/6** — speak into your mic to auto-detect it; beep-test your speakers
   - **Step 6/6** — end-to-end test: mic level check, TTS playback, soundboard beep
4. Done — the app opens and is ready to use. Voicemeeter Banana starts automatically with the app.

Upgrading: just run the new installer over the old one. Your API key, settings, and history are preserved.

## How game chat routing works

```
RodeCaster Chat mic → Voicemeeter Hardware Input 1 → B1 bus ─┐
                                                               ├→ Voicemeeter Out B1 → Windows default mic → Fortnite / Discord
Voice Royale TTS/Soundboard → Voicemeeter Input → B1 bus ────┘
```

The wizard sets **Windows default microphone = Voicemeeter Out B1** automatically. Any game or app that uses the Windows default mic will hear both your physical mic and TTS/soundboard audio without any in-game configuration.

## Installation (macOS)

1. Download the correct DMG from [Releases](https://github.com/JuhaFIN1/voice-royale/releases/latest):
   - **arm64** — Mac with M1, M2, or M3 chip (2020 and later)
   - **x86_64** — older Intel Mac
2. Open the DMG and drag **Voice Royale** to Applications
3. First launch: right-click → **Open** to bypass Gatekeeper (app is ad-hoc signed, not notarized)
4. Grant microphone and accessibility permissions when prompted
5. Global hotkeys require **Accessibility** permission: System Settings → Privacy & Security → Accessibility → enable Voice Royale

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

- **Assign sound/image**: drag a file onto a button, or right-click → Assign Sound / Assign Image
- **Search image online**: right-click → "Etsi kuva netistä…" — type a search term, pick from results
- **Bulk import**: drag a folder or multiple audio files onto any button to fill that slot and the ones after it; or right-click → Bulk Import
- **Subfolders**: right-click in Edit Mode → "Kansioksi…" — creates a nested page of 55 slots inside that button. Navigate back with the blue ← button in the bottom-left corner
- **Move cross-page**: drag a button over a tab label and hold 700 ms — the page switches, then drop onto the target slot
- **Reorder pages**: in Edit Mode, drag a tab label to a new position
- **■ STOP**: the red ■ STOP button in the bottom-right corner stops all active playback instantly — soundboard, speak, favorites, and wake TTS
- Add pages with **+** (up to 10). Right-click a tab to rename or delete.

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
| Windows autostart | Start with Windows, optionally minimized |
| Auto-update | Check for new version and download installer |
| Virtual mic | Install VB-Cable for game voice chat routing |
| Voicemeeter Banana | Re-run wizard configuration for game chat routing |
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

## File Structure

| File / Folder | Description |
|---|---|
| `ai_voice_app.py` | Entire app (~8400 lines) |
| `credentials.env` | API keys (not committed) |
| `app_settings.json` | User settings |
| `speech_history.json` | Translation history + favorites + selected audio devices |
| `favorites_audio/` | Cached TTS WAV files for favorites |
| `soundboard/` | Imported soundboard audio and images |
| `juhalempiainensoftware.png` | Splash screen image |
| `requirements.txt` | Python dependencies |
| `build_app.bat` | PyInstaller + installer build + signing |
| `installer.iss` | Inno Setup installer script |

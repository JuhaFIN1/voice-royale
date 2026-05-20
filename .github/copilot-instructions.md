# Voice Royale — Copilot Instructions

## Project overview

Windows + macOS desktop app (PyQt6): microphone → Whisper transcription → translation (Google/DeepL/OpenAI) → TTS playback.
All logic in one file: `ai_voice_app.py` (~5600 lines).

Working directory: `E:\CLOUDS\AI-SYSTEMS\ai-voice-router\`

```bat
python ai_voice_app.py
```

GitHub: https://github.com/JuhaFIN1/voice-royale

---

## Architecture

| Component | What |
|---|---|
| `install_deps()` | Auto pip install on startup |
| `LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`, `_GOOGLE_LANG_MAP`, `_DEEPL_LANG_MAP` | Language dicts (28 built-in) |
| `create_flag_icon(country_code)` | Flag icons — fillRect ONLY |
| `transcribe_audio_wav(wav_bytes)` | Whisper API transcription |
| `translate_text(text, lang, backend, deepl_key)` | Translation — Google/DeepL/OpenAI |
| `parse_voice_command(transcript, default_lang)` | GPT-4.1-mini: extract lang + translate wake command |
| `WakeListener` | Wake-word detector (Porcupine or Whisper VAD fallback) |
| `SoundboardButton` | Soundboard button with Edit Mode |
| `VoiceEffectProcessor` | Real-time DSP: pitch/robot + VB-Cable output. `set_monitor(device, enabled)` = Hear Myself |
| `class App(QWidget)` | Entire UI and logic |
| `SetupWizard` | First-run dialog (4 steps: API key → VB-Cable → Devices with recording test) |
| `open_settings_dialog()` | 6-tab settings window (Käännös, Wake Word, Kielet, Pikavalinnat, Stream Deck, Asennukset) |

---

## Critical rules

### Flag icons
`create_flag_icon()` uses **only** `fillRect` — never `setBrush`, `drawEllipse`, `drawRect`.
PyQt6 strict mode crashes on ellipses.

### Adding a built-in language
Update all **five** places: `LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`, `_GOOGLE_LANG_MAP`, `_DEEPL_LANG_MAP`, and `create_flag_icon()` elif-chain.
- Hebrew = `"iw"` in `_GOOGLE_LANG_MAP` (not `"he"`)
- Hindi / Hebrew / Croatian = `None` in `_DEEPL_LANG_MAP` (not supported by DeepL)

### Thread-safe UI
Always use Qt signals from background threads:
- `self.sig_status.emit(msg)` → status log
- `self.sig_set_textbox.emit(text)` → type box
- `self.sig_mic_level.emit(val)` / `self.sig_out_level.emit(val)` → meters

### Soundboard
- `SoundboardButton._edit_mode` — class-level flag, toggled with `set_edit_mode(bool)` classmethod
- `_sb_play_id` (int) counter prevents concurrent-play crashes
- `_soundboard_buttons` is `list[list[SoundboardButton]]` (not flat)
- Button size: `setFixedSize(72, 68)`, icon: `setIconSize(46, 42)`

### Wake listener
Two modes selected automatically:
- **Porcupine** — if `pvporcupine` installed AND Picovoice key set
- **Whisper VAD fallback** — records 2.5s chunks, transcribes, checks for keyword
  - Errors must be shown via `on_status`, never swallowed silently

### Wake word flow
1. Wake word detected → records `wake_command_seconds` (default 6s)
2. `parse_voice_command(transcript, default_lang)` → GPT-4.1-mini extracts target language + translates
3. TTS playback — always uses GPT-4.1-mini regardless of translation_backend setting
4. `wake_instructions_label` visible when Listen active, hidden on Stop

### Setup wizard
- Shown only when `app_settings.json` does not exist (true first run)
- 4 pages: Welcome → API key (browser) → Enter key → VB-Cable check → Devices
- VB-Cable page: `_is_vbcable_installed()` detects "cable" OR "voicemod" in device names; offers one-click install if absent
- Devices page: mic level meter + recording test (3 s record → playback to verify signal) + playback beep test
- OpenAI key is optional — "Ohita" button skips to VB-Cable page
- Env loading: `credentials.env` first (API keys), `.env` second without override (signing vars)

### Voice FX — Hear Myself
- `VoiceEffectProcessor.set_monitor(device, enabled)` starts/stops `_monitor_stream` (second OutputStream to headphones)
- In frozen exe: `_pkg_status()` in Settings Asennukset tab uses `sys.modules` check — NEVER call `importlib.import_module` for optional native libs (pyrubberband, pvporcupine) in frozen mode → crash
- `_is_vbcable_installed()` checks both "cable" and "voicemod" in device names

### Code signing
- Local: `build_app.bat` reads `SIGN_CERT_PATH` + `SIGN_CERT_PASSWORD` from `.env`
- CI: GitHub secrets `SIGN_CERT_BASE64` + `SIGN_CERT_PASSWORD`
- Never commit: `.env`, `certs/`, `*.pfx`

---

## Key files

| File | Purpose |
|---|---|
| `ai_voice_app.py` | Entire app (~5600 lines) |
| `credentials.env` | `OPENAI_API_KEY`, `ELEVEN_API_KEY`, `VOICE_ID` — never commit |
| `.env` | `SIGN_CERT_PATH`, `SIGN_CERT_PASSWORD` — never commit |
| `app_settings.json` | User settings |
| `speech_history.json` | History + favorites |
| `build_app.bat` | PyInstaller + Inno Setup + signtool |
| `installer.iss` | Inno Setup script |
| `.github/workflows/release.yml` | Auto-build on v* tag push |

---

## Supported languages (28 built-in)

Auto, English, German, Swedish, Finnish, Russian, Italian,
Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian,
Japanese, Chinese, Hungarian, Polish, Czech, Catalan,
Belarusian, Spanish, French, Turkish, Hindi, Hebrew, Greek, Croatian, Arabic

Plus custom languages added via Settings (stored in `app_settings.json → custom_languages`).

---

## Settings (app_settings.json)

| Key | Default | Description |
|---|---|---|
| `hotkey` | `ctrl+alt+space` | Global push-to-talk |
| `wake_keyword` | `jarvis` | Wake-word |
| `wake_custom_ppn_path` | `""` | Custom Porcupine .ppn |
| `picovoice_access_key` | `""` | Porcupine key |
| `default_target_lang` | `Auto` | Pre-selected language |
| `default_tts_backend` | `Edge TTS (free)` | TTS engine |
| `wake_command_seconds` | `6.0` | Recording after wake-word |
| `translation_backend` | `Google (free)` | Google / DeepL / OpenAI |
| `deepl_api_key` | `""` | DeepL key (optional) |
| `custom_languages` | `[]` | User-added languages |
| `voice_fx_output_device` | `null` | FX virtual output (VB-Cable device index) |
| `voice_fx_monitor_device` | `null` | Hear Myself monitor output (headphones device index) |
| `voice_fx_hear_myself` | `false` | Hear Myself enabled |

---

## Future idea: fully free mode

Replace paid OpenAI calls with free alternatives:
- Whisper API → `faster-whisper` (local model, ~150 MB, CPU)
- GPT-4.1-mini → rule-based language keyword parser + Google Translate
- No API key needed at all
- Trade-off: model downloads on first run, slightly slower, less flexible parsing

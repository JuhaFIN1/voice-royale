# Voice Royale — Copilot Instructions

## Project overview

Windows + macOS desktop app (PyQt6): microphone → Whisper transcription → translation (Google/DeepL/OpenAI) → TTS playback.
All logic in one file: `ai_voice_app.py` (~6000 lines).

Working directory: `E:\CLOUDS\AI-SYSTEMS\ai-voice-router\`
GitHub: https://github.com/JuhaFIN1/voice-royale
Current version: `APP_VERSION = "1.3.2"` (constant near top of file; CI auto-patches from git tag)

---

## Architecture

| Component | What |
|---|---|
| `install_deps()` | Auto pip install on startup (skipped in frozen exe) |
| `APP_VERSION`, `GITHUB_REPO` | Version string and repo slug for auto-update |
| `LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`, `_GOOGLE_LANG_MAP`, `_DEEPL_LANG_MAP` | Language dicts (28 built-in) |
| `create_flag_icon(country_code)` | Flag icons — fillRect ONLY |
| `_get_autostart_state()` / `_apply_autostart(enabled, minimized)` | Windows registry autostart (HKCU Run key) |
| `transcribe_audio_wav(wav_bytes)` | Whisper API transcription |
| `translate_text(text, lang, backend, deepl_key)` | Translation — Google/DeepL/OpenAI |
| `parse_voice_command(transcript, default_lang)` | GPT-4.1-mini: extract lang + translate wake command |
| `WakeListener` | Wake-word detector (Porcupine or Whisper VAD fallback) |
| `SoundboardButton` | Soundboard slot with drag-to-swap, page-link, edit mode |
| `VoiceEffectProcessor` | Real-time DSP: pitch/robot + VB-Cable output. `set_monitor(device, enabled)` = Hear Myself |
| `class App(QWidget)` | Entire UI and logic |
| `SetupWizard` | First-run dialog (4 steps: API key → VB-Cable → Devices with recording test) |
| `open_settings_dialog()` | 7-tab settings window (see tabs below) |

---

## Settings tabs (open_settings_dialog)

Tab font: 10px, padding: 5px 9px — all 7 tabs visible without scrolling at 900px dialog width.

| Tab | Name | Content |
|---|---|---|
| 1 | Käännös & TTS | Translation backend, API keys, TTS backend |
| 2 | Wake Word | Keyword, Porcupine key, wake command duration |
| 3 | Kielet | Custom languages |
| 4 | Pika & Data | Hotkey, history, data files |
| 5 | Stream Deck | HTTP API settings (port 17842) |
| 6 | Asennus | Run Setup Wizard again, Windows autostart, Python packages, VB-Cable |
| 7 | Päivitys | Version check via GitHub releases API, download & open installer |

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
Always use Qt signals from background threads — never call widget methods directly.
Stream Deck actions: use `_sd_action_queue` (Queue) + `_sd_action_timer` (50ms QTimer drains queue on main thread). `QTimer.singleShot(0, cb)` from bg thread is NOT reliable in PyQt6.

### Soundboard
- `SoundboardButton._edit_mode` — class-level flag, `set_edit_mode(bool)` classmethod
- `swap_requested = pyqtSignal(int, int, int, int)` — drag-to-swap between slots
- Edit mode: left-click drag over another button swaps their data (within or across pages)
- Right-click in edit mode → "Link to Page…" — button navigates to another page when pressed
- Link buttons use `_STYLE_LINK` (blue), store `link_page_name` in data dict
- `_sb_swap_handler(src_page, src_slot, dst_page, dst_slot)` on App does the swap + save
- `_play_soundboard_slot` checks `link_page_name` first — if set and not in edit mode, switches tab
- Edit mode OFF automatically calls `_save_soundboard()`
- `_sb_play_id` (int) counter prevents concurrent-play crashes
- `_soundboard_buttons` is `list[list[SoundboardButton]]` (pages × slots)

### Wake listener
Two modes selected automatically:
- **Porcupine** — if `pvporcupine` installed AND Picovoice key set
- **Whisper VAD fallback** — records 2.5s chunks, transcribes, checks for keyword

Both `_run_porcupine` and `_run_whisper` use a local `device` variable (initialized from `self._device_index`).
On PortAudio "out of range" error (MME -9999): automatically retries with `device=None` (default device).

### Windows autostart
- `_apply_autostart(enabled, minimized)` writes/removes `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` key
- Only works in frozen exe (`getattr(sys, "frozen", False)`)
- `--minimized` in `sys.argv` → `window.showMinimized()` instead of `window.show()`
- Changes take effect immediately (no Save needed)

### Auto-update (Päivitys tab)
- Calls `https://api.github.com/repos/GITHUB_REPO/releases/latest` via `requests`
- Compares `APP_VERSION` (semver) with latest tag
- Downloads `.exe` (Windows) or `.dmg` (macOS) to `tempfile.mkstemp()`, then opens it
- CI patches `APP_VERSION` in `ai_voice_app.py` from the git tag at build time

### Frozen exe / Settings
In frozen exe, `_pkg_status()` uses `sys.modules` check — NEVER call `importlib.import_module` for optional native libs (pyrubberband, pvporcupine) in frozen mode → crash with non-ImportError exception.

### Voice FX — Hear Myself
`VoiceEffectProcessor.set_monitor(device, enabled)` starts/stops `_monitor_stream` (second OutputStream to headphones).
`_is_vbcable_installed()` checks both "cable" and "voicemod" in device names.

### Code signing
- Local: `build_app.bat` reads `SIGN_CERT_PATH` + `SIGN_CERT_PASSWORD` from `.env`
- CI: GitHub secrets `SIGN_CERT_BASE64` + `SIGN_CERT_PASSWORD`
- Never commit: `.env`, `certs/`, `*.pfx`

### macOS build specifics
PyInstaller flags needed: `--hidden-import pyttsx3.drivers.nsss`, `--hidden-import PyQt6.sip`, `--collect-all pyttsx3`, `--osx-bundle-identifier com.voiceroyale.app`
Post-build: PlistBuddy injects `NSMicrophoneUsageDescription` + `NSInputMonitoringUsageDescription` into Info.plist.
DMG layout: `Voice Royale.app` + `/Applications` symlink (Finder shows arrow) + `Stream Deck Plugin/` folder.

---

## Key files

| File | Purpose |
|---|---|
| `ai_voice_app.py` | Entire app (~6000 lines) |
| `credentials.env` | `OPENAI_API_KEY`, `ELEVEN_API_KEY`, `VOICE_ID` — never commit |
| `.env` | `SIGN_CERT_PATH`, `SIGN_CERT_PASSWORD` — never commit |
| `app_settings.json` | User settings |
| `speech_history.json` | History + favorites |
| `build_app.bat` | PyInstaller + Inno Setup + signtool (local Windows build) |
| `installer.iss` | Inno Setup script |
| `.github/workflows/release.yml` | CI: auto-build + patch APP_VERSION on v* tag push |
| `streamdeck-plugin/com.voiceroyale.sdPlugin/` | Elgato Stream Deck plugin |

---

## Stream Deck HTTP API (port 17842)

`StreamDeckHttpServer` always starts with the app.

| Endpoint | Description |
|---|---|
| `GET /health` | `{"ok": true}` |
| `GET /state` | recording, listening, language, fx_preset, soundboard page/slots |
| `GET /actions` | All available action names |
| `POST /action/{name}` | Execute action (no body, no Content-Type) |
| `GET /soundboard/image/{page}/{slot}` | `{"image": "data:image/png;base64,..."}` |

Action names: `record_toggle`, `wake_listen_toggle`, `speak`, `stop_recording`, `settings`, `tts_toggle`, `sb_page_next`, `sb_page_prev`, `lang_{language}`, `fx_{preset}`, `soundboard_{page}_{slot}`

---

## Supported languages (28 built-in)

Auto, English, German, Swedish, Finnish, Russian, Italian,
Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian,
Japanese, Chinese, Hungarian, Polish, Czech, Catalan,
Belarusian, Spanish, French, Turkish, Hindi, Hebrew, Greek, Croatian, Arabic

Plus custom languages added via Settings → Kielet (stored in `app_settings.json → custom_languages`).

---

## Settings keys (app_settings.json)

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
| `voice_fx_output_device` | `null` | FX virtual output device index |
| `voice_fx_monitor_device` | `null` | Hear Myself monitor output device index |
| `voice_fx_hear_myself` | `false` | Hear Myself enabled |
| `start_with_windows` | `false` | Windows autostart (registry) |
| `start_minimized` | `false` | Start minimized when autolaunching |
| `soundboard_pages` | `[...]` | Pages with slots `{name,file,image,link_page_name}` |

---

## Future idea: fully free mode

Replace paid OpenAI calls with free alternatives:
- Whisper API → `faster-whisper` (local model, ~150 MB, CPU)
- GPT-4.1-mini → rule-based language keyword parser + Google Translate
- No API key needed at all

# Voice Royale — Copilot Instructions

## Project overview

Windows + macOS desktop app (PyQt6): microphone → Whisper transcription → translation (Google/DeepL/OpenAI) → TTS playback.
All logic in one file: `ai_voice_app.py` (~6300 lines).

Working directory: `E:\CLOUDS\AI-SYSTEMS\ai-voice-router\`
GitHub: https://github.com/JuhaFIN1/voice-royale
Current version: `APP_VERSION = "1.3.6"` (constant near top of file; CI auto-patches from git tag)

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
| `SoundboardButton` | Soundboard slot — see Soundboard section |
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
| 4 | Pika & Data | Hotkey, history, data export/import ZIP |
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
**`QTimer.singleShot(0, cb)` from a background thread does NOT work in PyQt6.**
Always use `queue.Queue` + a `QTimer` polling on the main thread (200ms interval).
Stream Deck actions: `_sd_action_queue` (Queue) + `_sd_action_timer` (50ms QTimer drains on main thread).

### Frozen exe / pkg_status
`_pkg_status()` in frozen exe: use `importlib.import_module()` for all packages **except** `pvporcupine` and `pyrubberband`. Those two native optional libs can crash with non-ImportError exceptions — use `sys.modules` check only for them.

### Soundboard
- **55 slots per page** (not 56) + fixed red **■ STOP** button at grid position (row 3, col 13)
- `_sb_stop_playback()`: increments `_sb_play_id`, calls `sd.stop()`, `update_output_level(0.0)`, resets playing btn
- Sound meter: `_level_cb` wrapper in `_play_soundboard_slot` checks `_sb_play_id` — emits 0.0 if superseded
- `SoundboardButton._edit_mode` — class-level flag, `set_edit_mode(bool)` classmethod
- Signals: `swap_requested(src_page, src_slot, dst_page, dst_slot)`, `bulk_import_requested(start_slot, [paths])`
- **Cross-page drag**: App.eventFilter intercepts DragMove on tab bar → 700ms timer switches tab
  - `_sb_hover_tab`, `_sb_tab_hover_timer` (singleShot QTimer) state on App
- **Tab reorder**: `setMovable(True)` in edit mode; `tabMoved` → `_sb_tab_moved(from, to)` reorders `_soundboard_buttons`
- **Bulk import**: drop folder/multi-files on button or right-click → "Bulk Import — tiedostot/kansio…"
- **Image search**: right-click → "Etsi kuva netistä…" — Bing Images via `requests.Session()`; parse with `html.unescape()` then regex `"murl"` (full URL) and `"turl"` (thumbnail); thumbnail grid (5 col, 130×100); queue+QTimer for all network ops
- `_sb_swap_handler(src_page, src_slot, dst_page, dst_slot)` on App does the swap + save
- Edit mode OFF automatically calls `_save_soundboard()`
- `_sb_play_id` (int) counter prevents concurrent-play crashes
- `_soundboard_buttons` is `list[list[SoundboardButton]]` (pages × slots, 55 per page)

### Wake listener
Two modes selected automatically:
- **Porcupine** — if `pvporcupine` installed AND Picovoice key set
- **Whisper VAD fallback** — records 2.5s chunks, transcribes, checks for keyword

On PortAudio "out of range" error (MME -9999): automatically retries with `device=None` (default device).

### Windows autostart
- `_apply_autostart(enabled, minimized)` writes/removes `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` key
- Only works in frozen exe (`getattr(sys, "frozen", False)`)
- `--minimized` in `sys.argv` → `window.showMinimized()` instead of `window.show()`

### Auto-update (Päivitys tab)
- Calls GitHub releases API via `requests` in a daemon thread; result via `queue.Queue` + 200ms QTimer poll
- Downloads `.exe` (Windows) or `.dmg` (macOS) to `tempfile.mkstemp()`, then opens it
- CI patches `APP_VERSION` in `ai_voice_app.py` from the git tag at build time

### Export / Import data
Three backup modes selectable via radio dialog (`_ask_mode()`):
- **all** — `app_settings.json`, `speech_history.json`, `credentials.env`, `soundboard/`, `favorites_audio/`
- **settings** — `app_settings.json`, `speech_history.json`, `credentials.env` (no soundboard audio/images)
- **soundboard** — `soundboard/` audio+images + `soundboard_pages` key from `app_settings.json` only

`_BACKUP_MODES` dict drives both export and import. Soundboard import merges only `soundboard_pages` into current settings (does not overwrite other settings). `soundboard/` includes `audio/` and `images/` subfolders via `os.walk`.

### Voice FX — Hear Myself
`VoiceEffectProcessor.set_monitor(device, enabled)` starts/stops `_monitor_stream` (second OutputStream to headphones).

### Code signing
- Local: `build_app.bat` reads `SIGN_CERT_PATH` + `SIGN_CERT_PASSWORD` from `.env`
- CI: GitHub secrets `SIGN_CERT_BASE64` + `SIGN_CERT_PASSWORD`
- Never commit: `.env`, `certs/`, `*.pfx`

### macOS build specifics
PyInstaller flags needed: `--hidden-import pyttsx3.drivers.nsss`, `--hidden-import PyQt6.sip`, `--collect-all pyttsx3`, `--osx-bundle-identifier com.voiceroyale.app`, `--icon iconimage.ico`
Post-build: PlistBuddy injects `NSMicrophoneUsageDescription` + `NSInputMonitoringUsageDescription` into Info.plist.
DMG layout: `Voice Royale.app` + `/Applications` symlink (Finder shows arrow) + `Stream Deck Plugin/` folder.

---

## Key files

| File | Purpose |
|---|---|
| `ai_voice_app.py` | Entire app (~6300 lines) |
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

# Voice Royale — Copilot Instructions

## Project overview

Windows + macOS desktop app (PyQt6): microphone → Whisper transcription → translation (Google/DeepL/OpenAI) → TTS playback.
All logic in one file: `ai_voice_app.py` (~6800 lines).

Working directory: `E:\CLOUDS\AI-SYSTEMS\ai-voice-router\`
GitHub: https://github.com/JuhaFIN1/voice-royale
Current version: `APP_VERSION = "1.3.12"` (constant near top of file; CI auto-patches from git tag)

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
| `play_wav_bytes(wav_bytes, device_indices, level_callback, volume, stop_event)` | Chunk-based per-device OutputStream playback with cancellation |
| `WakeListener` | Wake-word detector (Porcupine or Whisper VAD fallback) |
| `SoundboardButton` | Soundboard slot — see Soundboard section |
| `VoiceEffectProcessor` | Real-time DSP: pitch/robot + VB-Cable output. Always-on stream, toggle = preset only |
| `class App(QWidget)` | Entire UI and logic |
| `SetupWizard` | First-run dialog (4 steps: API key → VB-Cable → Devices with recording test) |
| `open_settings_dialog()` | 8-tab settings window (see tabs below) |

---

## Settings tabs (open_settings_dialog)

Tab font: 10px, padding: 5px 9px.

| Tab | Name | Content |
|---|---|---|
| 1 | Käännös & TTS | Translation backend, API keys, TTS backend |
| 2 | Wake Word | Keyword, Porcupine key, wake command duration |
| 3 | Kielet | Custom languages |
| 4 | Pika & Data | Hotkey, history, data export/import ZIP |
| 5 | Stream Deck | HTTP API settings (port 17842) |
| 6 | Asennus | Run Setup Wizard again, Windows autostart, Python packages, VB-Cable |
| 7 | Siivoa | Scan soundboard audio/images dirs for orphaned files; multi-select + confirm before delete |
| 8 | Päivitys | Version check via GitHub releases API, download & open installer |

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

### Soundboard — playback
- **Only one slot plays at a time.** Starting a new slot immediately stops the previous one.
- `play_wav_bytes` writes in 4096-frame chunks and checks `stop_event: threading.Event` between chunks.
- `App._sb_stop_event: threading.Event` — set it to stop current playback, then replace with a new Event.
- STOP button sets the event. `sd.stop()` has **no effect** on OutputStream-based playback — do not use it.
- `_sb_play_id` (int) — secondary guard against race conditions.
- `_sb_playing_btn` — reference to the currently playing SoundboardButton widget.

### Soundboard — structure
- **55 slots per page** (not 56) + fixed red **■ STOP** button at grid position (row 3, col 13).
- `SoundboardButton._edit_mode` — class-level flag, `set_edit_mode(bool)` classmethod.
- Signals: `clicked_play(slot_index)`, `data_changed(slot_index)`, `swap_requested(src_page, src_slot, dst_page, dst_slot)`, `bulk_import_requested(start_slot, [paths])`.
- `_soundboard_buttons: list[list[SoundboardButton]]` (pages × 55 slots).
- Edit mode OFF automatically calls `_save_soundboard()`.
- **Cross-page drag**: App.eventFilter intercepts DragMove on tab bar → 700ms timer (`_sb_hover_tab`, `_sb_tab_hover_timer`) switches tab.
- **Tab reorder**: `setMovable(True)` in edit mode; `tabMoved` → `_sb_tab_moved(from, to)` reorders `_soundboard_buttons` AND remaps `_sb_nav_stack` indices.
- **Bulk import**: drop folder/multi-files → `bulk_import_requested` signal → `_sb_bulk_import_handler`. Files beyond slot 54 are silently skipped.
- **Clear button**: deletes the file from disk if it lives under `BASE_PATH/soundboard/`. Never touches the original source.

### Soundboard — subfolder navigation
- Right-click in edit mode → "Kansioksi…" → converts slot to a folder (`_data["subfolder"] = True`, `_data["folder_slots"] = [{...} × 55]`). Gold/amber style `_STYLE_FOLDER`.
- Clicking a folder in play mode calls `_sb_enter_folder(page_index, slot_index)`:
  - Snapshots current slots + tab name onto `_sb_nav_stack[page_index]` as `(parent_slots, folder_slot_idx, prev_tab_name)`.
  - Loads `folder_slots` into buttons; sets slot 42 (row 3, col 0 = bottom-left) to back button (`_data["_back"] = True`). Dark-blue style `_STYLE_BACK`.
  - Sets tab name to `"📁 FolderName"`.
- Back button calls `_sb_go_back(page_index)`:
  - Snapshots current subfolder contents (replacing back slot placeholder), pops stack, saves into parent's `folder_slots`, restores parent buttons + original tab name, calls `_save_soundboard()`.
- `_get_page_root_slots(page_index)` unwinds the full nav stack to reconstruct root-level data for `_save_soundboard()`.
- Back button: `NoContextMenu`, `setAcceptDrops(False)`. `_sb_swap_handler` refuses swaps involving back slots.
- Subfolders support nesting (folder inside folder).

### Soundboard — image search (DuckDuckGo)
Two-step process:
1. GET `https://duckduckgo.com/?q=...&iax=images&ia=images` → extract `vqd` token with regex `vqd=([\d-]+)`.
2. GET `https://duckduckgo.com/i.js?q=...&vqd=...&o=json&f=,,,,,` with these **required** headers:
   - `X-Requested-With: XMLHttpRequest` ← without this, DDG returns 403
   - `Accept: application/json, text/javascript, */*; q=0.01`
   - `Referer: https://duckduckgo.com/?q=...&iax=images&ia=images`

Use `queue.Queue` + `QTimer` for all network ops (never block the main thread).

### Wake listener
Two modes selected automatically:
- **Porcupine** — if `pvporcupine` installed AND Picovoice key set.
- **Whisper VAD fallback** — records 2.5s chunks, transcribes, checks for keyword.

On PortAudio "out of range" error (MME -9999): automatically retries with `device=None`.

### Voice FX
`VoiceEffectProcessor`: single `sd.Stream` at 48kHz / 512 blocksize always running when devices configured.
Toggle = preset only ("Normal" = passthrough, others = effect). Stream never stops on toggle.
`set_monitor(device, enabled)` starts/stops second `_monitor_stream` OutputStream to headphones ("Hear Myself").
Autostart 600ms after app launch via `QTimer.singleShot(600, self._autostart_voice_fx)`.

### Windows autostart
- `_apply_autostart(enabled, minimized)` writes/removes `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` key.
- Only works in frozen exe (`getattr(sys, "frozen", False)`).
- `--minimized` in `sys.argv` → `window.showMinimized()`.

### Auto-update (Päivitys tab)
- GitHub releases API in daemon thread; result via `queue.Queue` + 200ms QTimer poll.
- Downloads `.exe` (Windows) or `.dmg` (macOS) to `tempfile.mkstemp()`, then opens it.
- CI patches `APP_VERSION` in `ai_voice_app.py` and version fields in `installer.iss` from git tag at build time.

### Export / Import data
Three backup modes selectable via radio dialog (`_ask_mode()`):
- **all** — `app_settings.json`, `speech_history.json`, `credentials.env`, `soundboard/`, `favorites_audio/`
- **settings** — `app_settings.json`, `speech_history.json`, `credentials.env` (no soundboard audio/images)
- **soundboard** — `soundboard/` audio+images + `soundboard_pages` key from `app_settings.json` only

`_BACKUP_MODES` dict drives both export and import. Soundboard import merges only `soundboard_pages` into current settings.

### Code signing
- Local: `build_app.bat` reads `SIGN_CERT_PATH` + `SIGN_CERT_PASSWORD` from `.env`.
- CI: GitHub secrets `SIGN_CERT_BASE64` + `SIGN_CERT_PASSWORD`.
- Never commit: `.env`, `certs/`, `*.pfx`.

### macOS build specifics
CI installs Pillow and converts `iconimage.ico` → `iconimage.icns` before PyInstaller.
PyInstaller flags: `--hidden-import pyttsx3.drivers.nsss`, `--hidden-import PyQt6.sip`, `--collect-all pyttsx3`, `--osx-bundle-identifier com.voiceroyale.app`, `--icon iconimage.icns`.
Post-build: PlistBuddy injects `NSMicrophoneUsageDescription` + `NSInputMonitoringUsageDescription`.
DMG layout: `Voice Royale.app` + `/Applications` symlink + `Stream Deck Plugin/` folder.

---

## Key files

| File | Purpose |
|---|---|
| `ai_voice_app.py` | Entire app (~6800 lines) |
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
| `soundboard_volume` | `1.0` | Global soundboard volume multiplier |
| `soundboard_pages` | `[...]` | Pages with slots `{name,file,image,link_page_name,volume,subfolder?,folder_slots?}` |

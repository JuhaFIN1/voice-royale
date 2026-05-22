# Voice Royale — Copilot Instructions

## Project overview

Windows + macOS desktop app (PyQt6): microphone → Whisper transcription → translation (Google/DeepL/OpenAI) → TTS playback.
All logic in one file: `ai_voice_app.py` (~6800 lines).

Working directory: `E:\CLOUDS\AI-SYSTEMS\ai-voice-router\`
GitHub: https://github.com/JuhaFIN1/voice-royale
Current version: `APP_VERSION = "1.3.25"` (constant near top of file; CI auto-patches from git tag)

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
| `play_wav_bytes(wav_bytes, device_indices, level_callback, volume, stop_event)` | Chunk-based per-device OutputStream playback with cancellation. Level callback runs **inside** the write loop (synced to actual output, not a free-running timer). |
| `WakeListener` | Wake-word detector (Porcupine or Whisper VAD fallback) |
| `SoundboardButton` | Soundboard slot — see Soundboard section |
| `VoiceEffectProcessor` | Real-time DSP: pitch/robot + VB-Cable output. Always-on stream, toggle = preset only |
| `class App(QWidget)` | Entire UI and logic |
| `SetupWizard` | First-run dialog (5 steps: API key → VB-Cable → Voicemeeter Banana → Devices with recording test) |
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
| 6 | Asennus | Run Setup Wizard again, Windows autostart, Python packages, VB-Cable, Voicemeeter Banana |
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

### Soundboard — playback and STOP

- **Only one slot plays at a time.** Starting a new slot immediately stops the previous one.
- `play_wav_bytes` writes in 4096-frame chunks and checks `stop_event: threading.Event` between chunks.
- **Level callback is computed inside the write loop** (primary device only), not a separate timer thread. This keeps the meter in sync with actual audio output.
- Two stop events on `App`:
  - `_sb_stop_event: threading.Event` — soundboard playback only. Set + replace on new play or STOP.
  - `_play_stop_event: threading.Event` — all other playback (speak/`run_pipeline`, wake-command TTS, `_play_favorite_audio`). Passed as `stop_event=` to every non-soundboard `play_wav_bytes` call.
- `_sb_stop_playback()` sets **both** events — the soundboard ■ STOP button stops all active audio.
- `sd.stop()` has **no effect** on OutputStream-based playback — do not use it.
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

### Voicemeeter Banana (chat routing) — v1.3.25+

Windows-only. Implemented in Settings → Asennus tab and SetupWizard page 4.

#### Routing architecture

```
Voice Royale TTS/soundboard → Voicemeeter Input (Strip[2]) → B1 bus → Voicemeeter Out B1
RodeCaster Chat / Mix Minus mic → Strip[0] → B1 bus → Voicemeeter Out B1
Windows default recording = Voicemeeter Out B1 → all games/apps automatically
```

**CABLE Input is NOT used** — Voicemeeter holds it in exclusive mode → PaErrorCode -9996.
Always use `Voicemeeter Input (VB-Audio Voicemeeter VAIO)` as Voice Royale output device.

#### Functions (module level, near VB-Cable block)

- `_is_voicemeeter_installed()` — registry scan + sounddevice name check
- `_get_voicemeeter_dll_path()` — finds `VoicemeeterRemote64.dll` in Program Files
- `_get_voicemeeter_download_url()` — scrapes banana.htm for download link
- `_install_voicemeeter(status_cb)` — requests stream download + progress %, PowerShell /S silent install
- `_check_voicemeeter_routing()` — verifies "Voicemeeter Output" (recording) + "Voicemeeter Input" (playback) exist
- `_voicemeeter_configure(mic_device_name, status_cb)` — ctypes → `VoicemeeterRemote64.dll`:
  - `VBVMR_Login()` / `VBVMR_Logout()`
  - `Strip[0].device.wdm` = user's mic (RodeCaster Chat / Mix Minus)
  - `Strip[0].B1 = 1` and `Strip[2].B1 = 1` → both to B1 virtual bus
  - `Bus[3].On = 1` → Voicemeeter Output recording device on
- `_set_windows_default_recording(name_contains)` — inline C# + IPolicyConfig COM via PowerShell:
  - Sets Windows default recording device (all 3 roles: eConsole/eCommunications/eAll)
  - Returns `(bool, message)`
- `_open_windows_sound_recording()` — opens Windows Sound → Recording tab (manual fallback)
- `_get_voicemeeter_output_device_indices()` — returns `[voicemeeter_input_idx, headphones_idx]` from `list_output_devices()`

#### Wizard plug-and-play (v1.3.25)

`_do_vm_wiz_configure` in SetupWizard page 4 does all three steps in one background thread:
1. Voicemeeter routing via `_voicemeeter_configure`
2. Auto-selects `Voicemeeter Input` + headphones as Voice Royale output devices (saves to `_sd`)
3. Sets Windows default recording to `Voicemeeter Out B1` via `_set_windows_default_recording`
4. Calls `populate_output_devices()` on success to refresh UI

No manual game settings needed — Windows default mic is set automatically.

#### PortAudio error codes

- **-9993**: Input/output devices use different host API → `_populate_fx_output_combo` must use `list_output_devices()` (not raw `sd.query_devices()`)
- **-9996**: Invalid device = exclusive mode lock (CABLE Input) → use Voicemeeter Input instead
- **-9999**: WDM-KS blocking API not supported → `_best_audio_devices` skips WDM-KS if non-WDM alternative exists

#### Audio device helpers (v1.3.22+)

- `_best_audio_devices(channel_key)` — replaces `_dedup_audio_devices`:
  - Skips WDM-KS when a non-WDM alternative exists for same device name
  - Deduplicates by name, preferring WASAPI > DirectSound > MME
  - Removes MME-truncated duplicate entries (MME names are ≤31 chars, prefix of longer names)
- `_fit_combo_dropdown(combo)` — sets `combo.view().setMinimumWidth()` based on longest item
- `_add_device_row()` — `setMaximumWidth(500)` (was 280)

UI in Settings → Asennus:
- Status label (installed / not installed)
- Install button (hidden on non-Windows)
- Device dropdown (recording devices, pre-selects RodeCaster/Chat if found)
- "Konfiguroi reititys" button + status label

### Code signing
- Local: `build_app.bat` reads `SIGN_CERT_PATH` + `SIGN_CERT_PASSWORD` from `.env`.
- CI: GitHub secrets `SIGN_CERT_BASE64` + `SIGN_CERT_PASSWORD`.
- Never commit: `.env`, `certs/`, `*.pfx`.

### macOS build (release.yml) — two separate jobs

**macos-13 is retired. Use macos-14 (ARM64) only.**

#### build-macos-arm64
- Runner: `macos-14` (Apple Silicon M1/M2/M3)
- Python: `actions/setup-python@v5` (ARM64)
- No brew portaudio — sounddevice 0.4.x bundles its own. Use `--collect-all sounddevice --collect-all _sounddevice_data`.
- Icon: `iconutil -c icns iconimage.iconset -o iconimage.icns` (proper ICNS, not `PIL.save`)
- `sleep 2` before `hdiutil create` — codesign holds file locks briefly; the sleep prevents "Resource busy"
- Output: `Voice_Royale_{version}_macOS_arm64.dmg`

#### build-macos-intel
- Runner: `macos-14` (M1), cross-build x86_64 via Rosetta 2
- `NONINTERACTIVE=1 arch -x86_64 /bin/bash -c "$(curl ... install.sh)"` installs x86_64 Homebrew to `/usr/local`
- `HOMEBREW_NO_ENV_HINTS=1 arch -x86_64 /usr/local/bin/brew install python@3.11 || true` — `|| true` required: brew link fails if `/usr/local/bin/python3.11` already exists on runner
- Python path: `/usr/local/opt/python@3.11/bin/python3.11`
- All pip + PyInstaller commands prefixed with `arch -x86_64`
- Output: `Voice_Royale_{version}_macOS_x86_64.dmg`

Shared PyInstaller flags (both jobs):
`--hidden-import pyttsx3.drivers.nsss`, `--hidden-import PyQt6.sip`, `--collect-all edge_tts`, `--collect-all sounddevice`, `--collect-all _sounddevice_data`, `--collect-all pyttsx3`, `--collect-all certifi`, `--osx-bundle-identifier com.voiceroyale.app`

Post-build: PlistBuddy injects `NSMicrophoneUsageDescription` + `NSInputMonitoringUsageDescription`.

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

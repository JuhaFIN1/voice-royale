# Voice Royale — Copilot Instructions

## Project overview

Windows + macOS desktop app (PyQt6): microphone → Whisper transcription → translation (Google/DeepL/OpenAI) → TTS playback.
All logic in one file: `ai_voice_app.py` (~8500 lines).

Working directory: `E:\CLOUDS\AI-SYSTEMS\ai-voice-router\`
GitHub: https://github.com/JuhaFIN1/voice-royale
Current version: `APP_VERSION = "1.3.29"` (constant near top of file; CI auto-patches from git tag)

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
| `play_wav_bytes(wav_bytes, device_indices, level_callback, volume, stop_event)` | Chunk-based per-device OutputStream. **Fault-tolerant**: continues to remaining devices if one fails; only raises if ALL fail. `device_ok: list[bool]` + `results_lock` track per-device success. |
| `WakeListener` | Wake-word detector (Porcupine or Whisper VAD fallback) |
| `SoundboardButton` | Soundboard slot — classmethod `set_edit_mode(bool)`, `_edit_mode` class flag |
| `VoiceEffectProcessor` | Real-time DSP: pitch/robot + VB-Cable output. Always-on stream. |
| `class App(QWidget)` | Entire UI and logic |
| `SetupWizard` | First-run dialog — 7 stack pages (0–6), shown as "Vaihe 1/6"–"Vaihe 6/6" |
| `open_settings_dialog()` | 8-tab settings window |

---

## SetupWizard pages

| Stack index | UI label | Content |
|---|---|---|
| 0 | Welcome | Intro |
| 1 | Vaihe 1/6 | Python packages (pip auto-install) |
| 2 | Vaihe 2/6 | OpenAI API key |
| 3 | Vaihe 3/6 | VB-Cable install |
| 4 | Vaihe 4/6 | Voicemeeter Banana install + routing configure + Windows default mic |
| 5 | Vaihe 5/6 | Mic auto-detect (live bars) + output device checkboxes |
| 6 | Vaihe 6/6 | End-to-end test: mic level, TTS playback, soundboard beep |

### Wizard device page (index 5) — v1.3.28+
- System default output device is **pre-checked** on page load
- CABLE Input devices get `[→ peliin]` suffix to clarify they route to game audio
- `self._dev_default_out` stored for use in `_finish_setup`
- `_finish_setup` safety net: if only virtual devices checked, adds `_dev_default_out` automatically

---

## EXE vs Python device index mismatch

**Critical:** EXE bundles its own PortAudio via `--collect-all sounddevice`. Device indices in the EXE
can differ from the Python dev environment. `speech_history.json → selected_output_devices` stores
raw integer indices — an index that works in Python may resolve to a WDM-KS device in the EXE
(PaErrorCode -9999, blocking API not supported).

Mitigation: `play_wav_bytes` is fault-tolerant (v1.3.29) — one device failing does not block the others.
Do NOT store CABLE Input (VB-Audio Virtual Cable) as output — it goes to game audio, not monitoring headphones.

---

## Voicemeeter Banana routing

```
RodeCaster Chat mic → Voicemeeter Hardware Input 1 (Strip[0]) → B1 bus ─┐
                                                                          ├→ Voicemeeter Out B1 → Windows default mic → all apps
Voice Royale TTS/Soundboard → Voicemeeter Input (Strip[2]) → B1 bus ────┘
```

- `_ensure_voicemeeter_running()` — starts `voicemeeterb.exe` if not running; App.__init__ (1.2s delay, bg thread)
- `_is_voicemeeter_installed()` — registry + sounddevice check
- `_get_voicemeeter_dll_path()` — finds VoicemeeterRemote64.dll
- `_install_voicemeeter(status_cb)` — downloads + installs silently
- `_voicemeeter_configure(mic_device_name, status_cb)` — ctypes DLL: Strip[0].device.wdm+mme = mic, Strip[0]+Strip[2] → B1, Bus[3].On
- `_set_windows_default_recording(name_contains)` — PowerShell inline C# + IPolicyConfig COM
- `_get_voicemeeter_output_device_indices()` — returns [Voicemeeter Input idx, headphones idx]; saves to HISTORY_FILE

**Critical:** Voice Royale outputs TTS to `"Voicemeeter Input (VB-Audio Voicemeeter VAIO)"` (Strip[2] exact name).
**Never use CABLE Input** — Voicemeeter holds it in exclusive mode → PaErrorCode -9996.

---

## Settings tabs (open_settings_dialog)

| Tab | Name | Content |
|---|---|---|
| 1 | Käännös & TTS | Translation backend, API keys, TTS backend |
| 2 | Wake Word | Keyword, Porcupine key, wake command duration |
| 3 | Kielet | Custom languages |
| 4 | Pika & Data | Hotkey, history, data export/import ZIP |
| 5 | Stream Deck | HTTP API settings (port 17842) |
| 6 | Asennus | Run Setup Wizard again, Windows autostart, Python packages, VB-Cable, Voicemeeter Banana |
| 7 | Siivoa | Scan soundboard dirs for orphaned files |
| 8 | Päivitys | Version check via GitHub releases API, download & open installer |

---

## Stream Deck HTTP API (port 17842)

| Endpoint | Description |
|---|---|
| `GET /health` | `{"ok": true}` |
| `GET /state` | recording, listening, language, fx_preset, tts_backend, soundboard state |
| `GET /actions` | List all actions |
| `POST /action/{name}` | Execute action (no body, no Content-Type) |
| `GET /soundboard/image/{page}/{slot}` | Base64 PNG or null |

**Action names:** `record_toggle`, `wake_listen_toggle`, `speak`, `stop_recording`, `settings`, `tts_toggle`, `sb_page_next`, `sb_page_prev`, `lang_{language}`, `fx_{preset}`, `soundboard_{page}_{slot}`

**Thread-safety:** Use `queue.Queue` + QTimer poll from bg threads. `QTimer.singleShot(0, cb)` from bg thread does NOT work in PyQt6.

---

## Critical rules

### Flag icons
`create_flag_icon()` uses **only** `fillRect` — never `setBrush`, `drawEllipse`, `drawRect`. PyQt6 strict mode crashes on ellipses.

### Thread safety
Never call widget methods from background threads. Always use signals or queue.Queue + QTimer poll pattern.

### Adding a built-in language
Update all **five** places: `LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`, `_GOOGLE_LANG_MAP`, `_DEEPL_LANG_MAP`, and `create_flag_icon()` elif-chain.
- Hebrew = `"iw"` in `_GOOGLE_LANG_MAP` (not `"he"`)
- Hindi/Hebrew/Croatian = `None` in `_DEEPL_LANG_MAP`

### Soundboard
- 55 buttons per page + fixed ■ STOP (grid row 3, col 13)
- `_sb_play_id` (int) counter prevents concurrent play crashes
- `SoundboardButton._edit_mode` is a class-level flag

### Stop events
- `_sb_stop_event` — soundboard playback
- `_play_stop_event` — TTS/speak/favorites/wake TTS
- `_sb_stop_playback()` sets both

### PortAudio errors to watch
- **-9993**: I/O devices on different host APIs
- **-9996**: CABLE Input exclusive mode — never use as output
- **-9999**: WDM-KS blocking API — `_best_audio_devices` skips WDM-KS if alternatives exist, but EXE indices can still resolve to WDM-KS; handled by fault-tolerant `play_wav_bytes`

### exe/frozen mode
- `BASE_PATH = %APPDATA%\Voice Royale\` when frozen (separate from dev `speech_history.json`)
- `_pkg_status()`: use `sys.modules` for pvporcupine/pyrubberband (not importlib — can crash frozen)
- Auto-updater uses `ShellExecuteW("runas", ...)` to force UAC prompt

---

## Build & release

```bat
python ai_voice_app.py          # dev
build_app.bat                   # PyInstaller + Inno Setup + signing → installer_output\
```

CI (`release.yml`) triggers on `v*` tag → Windows EXE + 2 macOS DMGs + .streamDeckPlugin.
Secrets: `SIGN_CERT_BASE64`, `SIGN_CERT_PASSWORD`.
Never commit: `.env`, `certs/`, `*.pfx`, `credentials.env`.

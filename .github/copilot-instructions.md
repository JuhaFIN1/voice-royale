# Voice Royale — Copilot Instructions

## Project overview

Windows + macOS desktop app (PyQt6): microphone → Whisper transcription → translation (Google/DeepL/OpenAI) → TTS playback.
All logic in one file: `ai_voice_app.py` (~8400 lines).

Working directory: `E:\CLOUDS\AI-SYSTEMS\ai-voice-router\`
GitHub: https://github.com/JuhaFIN1/voice-royale
Current version: `APP_VERSION = "1.3.42"` (constant near top of file; CI auto-patches from git tag)

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
| `play_wav_bytes(wav_bytes, device_indices, level_callback, volume, stop_event)` | Chunk-based per-device OutputStream playback with cancellation. Level callback runs **inside** the write loop. |
| `WakeListener` | Wake-word detector (Porcupine or Whisper VAD fallback) |
| `SoundboardButton` | Soundboard slot — classmethod `set_edit_mode(bool)`, `_edit_mode` class flag |
| `VoiceEffectProcessor` | Real-time DSP: pitch/robot + VB-Cable output. Always-on stream. |
| `class App(QWidget)` | Entire UI and logic |
| `SetupWizard` | First-run dialog — 6 pages (0–5 stack index, 1–6 in UI labels) |
| `open_settings_dialog()` | 8-tab settings window |

---

## SetupWizard pages

| Index | Label | Content |
|---|---|---|
| 0 | Welcome | Intro |
| 1 | Vaihe 1/6 | Python packages (pip auto-install) |
| 2 | Vaihe 2/6 | OpenAI API key |
| 3 | Vaihe 3/6 | VB-Cable install |
| 4 | Vaihe 4/6 | Voicemeeter Banana install + routing configure + Windows default mic |
| 5 | Vaihe 5/6 | Mic auto-detect (live bars) + output beep test |
| 6 | Vaihe 6/6 | End-to-end test: mic level, TTS playback, soundboard beep |

---

## Voicemeeter Banana routing

```
RodeCaster Chat mic → Voicemeeter Hardware Input 1 (Strip[0]) → B1 bus ─┐
                                                                          ├→ Voicemeeter Out B1 → Windows default mic → all apps
Voice Royale TTS/Soundboard → Voicemeeter Input (Strip[2]) → B1 bus ────┘
```

- `_ensure_voicemeeter_running()` — starts Voicemeeter Banana if not running (SW_SHOWMINIMIZED); tries exe names `["voicemeeterb.exe", "voicemeeterpro_x64.exe", "voicemeeterpro.exe"]` (new VB-Audio installer = `voicemeeterpro_x64.exe`); searches standard paths + WOW6432Node registry `UninstallString`/`DisplayIcon`; called from App.__init__ (1.2s delay, bg thread, unconditional) and before wizard configure. All subprocess calls use `CREATE_NO_WINDOW`.
- `_is_voicemeeter_installed()` — registry + sounddevice check (no longer gates App.__init__ autostart)
- `_check_voicemeeter_running()` — polls tasklist every 60s (bg thread, CREATE_NO_WINDOW); shows/hides red `_vm_warning_label` QLabel above status_text when Banana is not running
- `_get_voicemeeter_dll_path()` — finds VoicemeeterRemote64.dll
- `_install_voicemeeter(status_cb)` — downloads + installs silently
- `_voicemeeter_configure(mic_device_name, status_cb)` — ctypes DLL: Strip[0].device.wdm+mme = mic, Strip[0]+Strip[2] → B1, Bus[3].On
- `_set_windows_default_recording(name_contains)` — PowerShell: reads registry `{a45c254e...},2` for device name, uses `PolicyConfigHelperVR` C# class to call IPolicyConfig.SetDefaultEndpoint
- `_get_voicemeeter_output_device_indices()` — finds "Voicemeeter Input (VB-Audio Voicemeeter VAIO)" (Strip[2] playback device) + headphones; saves to HISTORY_FILE

**Critical:** Voice Royale must output TTS to `"Voicemeeter Input (VB-Audio Voicemeeter VAIO)"` (exact name, Strip[2]). NOT "Voicemeeter In 2" or other strips. Selected output devices saved to `speech_history.json → selected_output_devices`.

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

**Action names:** `record_toggle`, `wake_listen_toggle`, `speak`, `stop_recording`, `settings`, `tts_toggle`, `sb_page_goto_{N}`, `lang_{language}`, `fx_{preset}`, `soundboard_{page}_{slot}`

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
- 55 buttons per page + `_OctagonStopButton` (red octagon stop-sign, grid row 3, col 13)
- `_sb_play_id` (int) counter prevents concurrent play crashes
- `SoundboardButton._edit_mode` is a class-level flag
- Edit button: `setFixedSize(46, 24)` to fit inside 28px corner widget

### Stop events
- `_sb_stop_event` — soundboard playback
- `_play_stop_event` — TTS/speak/favorites/wake TTS
- `_sb_stop_playback()` sets both

### System tray

`QSystemTrayIcon` lives in `App.__init__`. Minimize/close → hides to tray. To actually quit, user right-clicks tray → "Sulje ohjelma" which sets `self._force_quit = True` then calls `self.close()`.
- `changeEvent`: catches `WindowStateChange` + `isMinimized()` → `QTimer.singleShot(0, self.hide)`
- `closeEvent`: if not `_force_quit` → `event.ignore(); self.hide(); return`
- `app.setQuitOnLastWindowClosed(False)` is set in `__main__`

### PortAudio errors to watch
- **-9993**: I/O devices on different host APIs
- **-9996**: Device in exclusive mode (don't use CABLE Input directly)
- **-9999**: WDM-KS blocking — `_best_audio_devices` skips WDM-KS if alternatives exist

### exe/frozen mode
- `BASE_PATH = %APPDATA%\Voice Royale\` when frozen
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

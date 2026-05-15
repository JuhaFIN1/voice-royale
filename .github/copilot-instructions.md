# AI Voice Router — Copilot Instructions

## Project overview

Windows desktop app (PyQt6) — microphone → Whisper transcription → GPT-4.1-mini translation → TTS playback.
All logic lives in one file: `ai_voice_app.py` (~2600 lines).

Working directory: `E:\CLOUDS\AI-SYSTEMS\ai-voice-router\`

```bat
python ai_voice_app.py
```

---

## Architecture

| Lines (approx.) | What |
|---|---|
| 10–36 | `install_deps()` — auto pip install on startup |
| 60–75 | PyQt6 imports |
| 80–140 | UI style constants |
| 145–215 | `LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES` dicts |
| 220–230 | `DEFAULT_SETTINGS` |
| 255–340 | `_apply_custom_languages_to_globals()`, VB-Cable helpers |
| 570–600 | `transcribe_audio_wav()` — Whisper API |
| 620–840 | `WakeListener` — wake-word (Porcupine or Whisper VAD) |
| 845–860 | `_TextboxRecordBtnFilter` — overlay button resize handler |
| 860+ | `class App(QWidget)` — entire UI and logic |
| ~2260+ | `open_settings_dialog()` — settings window |

---

## Critical rules

### Flag icons
`create_flag_icon(country_code)` uses **only** `fillRect` — never `setBrush`, `drawEllipse`, or `drawRect`.
PyQt6 strict mode crashes `build_language_icons()` if ellipses are used.

### Adding a built-in language
Add to all three dicts AND the `create_flag_icon()` elif-chain:
```python
LANGS["Portuguese"] = "Portuguese"
LANG_FLAG_CODES["Portuguese"] = "pt"
EDGE_VOICES["Portuguese"] = "pt-PT-RaquelNeural"
# + elif country_code == "pt": ... fillRect only
```

### Custom languages (runtime)
Users add languages via Settings → Custom languages.
`_apply_custom_languages_to_globals(list)` merges them into the global dicts.
`App.rebuild_langbox()` refreshes the dropdown. Both are called in `apply_settings_changes()`.

### Thread-safe UI updates
Always use Qt signals for UI changes from worker threads:
- `self.sig_status.emit(msg)` → status log
- `self.sig_set_textbox.emit(text)` → type box
- `self.sig_mic_level.emit(val)` / `self.sig_out_level.emit(val)` → meters
Never call Qt widget methods directly from background threads.

### Record button
Lives as an **overlay QPushButton** inside `self.textbox` (not in the button row).
`_TextboxRecordBtnFilter` (event filter) repositions it on resize.
States: `🎤` idle → `🔴` recording → `⏳` processing.

### Favorites audio cache
`toggle_favorite()` triggers `_generate_favorite_audio()` in a background thread.
WAV files saved to `favorites_audio/<md5hash>.wav`.
Clicking a cached favorite plays it directly via `_play_favorite_audio()` — no re-translation.

---

## Key files

| File | Purpose |
|---|---|
| `ai_voice_app.py` | Entire app |
| `credentials.env` | `OPENAI_API_KEY`, `ELEVEN_API_KEY`, `VOICE_ID` — never commit |
| `app_settings.json` | User settings (hotkey, TTS backend, custom languages…) |
| `speech_history.json` | History + favorites (includes audio_file paths) |
| `favorites_audio/` | Cached TTS WAV files for favorites |
| `juhalempiainensoftware.png` | Splash screen image (4 s on startup) |
| `requirements.txt` | Python dependencies |
| `build_app.bat` | PyInstaller EXE build |

---

## Supported languages (built-in, 2026-05-15)

Auto, English, German, Swedish, Finnish, Russian, Italian,
Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian,
Japanese, Chinese, Hungarian, Polish, Czech, Catalan,
Belarusian, Spanish, French — **plus any custom languages added via Settings**

---

## Settings stored in app_settings.json

| Key | Default | Description |
|---|---|---|
| `hotkey` | `ctrl+alt+space` | Global push-to-talk shortcut |
| `wake_keyword` | `jarvis` | Wake-word for hands-free mode |
| `wake_custom_ppn_path` | `""` | Path to custom Porcupine .ppn model |
| `picovoice_access_key` | `""` | Porcupine API key |
| `default_target_lang` | `Auto` | Pre-selected output language |
| `default_tts_backend` | `Edge TTS (free)` | TTS engine |
| `wake_command_seconds` | `6.0` | Recording duration after wake-word |
| `custom_languages` | `[]` | User-added languages (name/code/voice) |

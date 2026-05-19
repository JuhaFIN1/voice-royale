# Copilot Instructions for Voice Royale

Windows desktop Python app for AI-powered voice translation, built with PyQt6.

## Architecture

Single file: `ai_voice_app.py` (~2100 lines)

Key sections:
- **lines 10–32**: `install_deps()` — auto pip install on startup
- **lines 140–193**: Language dicts (`LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`)
- **lines 643–782**: `WakeListener` — wake-word detection (Porcupine + Whisper fallback)
- **lines 784+**: `App(QWidget)` — main UI class
- **lines 2005+**: `open_settings_dialog()` — settings window

## Core Flow

1. Wake-word heard (Porcupine or Whisper VAD)
2. Record audio for `wake_command_seconds` seconds
3. Whisper API transcribes
4. `parse_voice_command()` — GPT-4.1-mini extracts target language + translates
5. TTS (Edge TTS / ElevenLabs / pyttsx3) plays to selected output devices

## Guidance

- Edit `ai_voice_app.py` unless the user explicitly requests a new file
- Keep UI responsive — all audio/API work runs in daemon threads
- Do not introduce unnecessary dependencies
- Flag icons: use ONLY `fillRect` in `create_flag_icon()` — PyQt6 strict-mode crashes on `setBrush`/`drawEllipse`
- Adding a language: update `LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`, and `create_flag_icon()` elif chain
- Multi-device playback: `play_wav_bytes()` handles threading automatically

## Settings (app_settings.json)

| Key | Default |
|---|---|
| `hotkey` | `ctrl+alt+space` |
| `wake_keyword` | `jarvis` |
| `wake_custom_ppn_path` | `""` |
| `picovoice_access_key` | `""` |
| `default_target_lang` | `Auto` |
| `default_tts_backend` | Edge TTS |
| `wake_command_seconds` | `6.0` |

## Supported Languages (21)

Auto, English, German, Swedish, Finnish, Russian, Italian,
Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian,
Japanese, Chinese, Hungarian, Polish, Czech, Catalan,
Belarusian, Spanish

## User Preferences

- Windows desktop only
- Reliable audio routing and user-friendly device selection
- Avoid unstable emoji rendering in PyQt6 controls
- Short, actionable answers — mention exact file changed
- No broad architectural changes unless asked

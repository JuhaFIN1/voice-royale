# Voice Royale — Claude Code context

## Projekti

Windows-työpöytäsovellus (PyQt6): mikrofoni → Whisper → käännös (Google/DeepL/OpenAI) → TTS.

```bat
python ai_voice_app.py          # kehitys
build_app.bat                   # PyInstaller + Inno Setup + signing → installer_output\
```

## Tiedostot

| Tiedosto | Kuvaus |
|---|---|
| `ai_voice_app.py` | Koko sovellus, ~4300 riviä |
| `credentials.env` | API-avaimet (OPENAI_API_KEY, ELEVEN_API_KEY, VOICE_ID) |
| `.env` | Signing-muuttujat (SIGN_CERT_PATH, SIGN_CERT_PASSWORD) — ei githubiin |
| `app_settings.json` | Käyttäjäasetukset |
| `speech_history.json` | Historia + suosikit |
| `build_app.bat` | PyInstaller + Inno Setup + signtool |
| `installer.iss` | Inno Setup -skripti |
| `certs/juha-signing.pfx` | Self-signed cert — ei githubiin |

## Arkkitehtuuri (ai_voice_app.py)

- `install_deps()` — automaattinen pip-asennus käynnistyksessä
- `LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`, `_GOOGLE_LANG_MAP`, `_DEEPL_LANG_MAP` — kielidictit
- `create_flag_icon(country_code)` — lippuikonit
- `WakeListener` — wake-word kuuntelija (Porcupine tai Whisper VAD fallback)
- `App(QWidget)` — pääluokka koko UI:lla
- `SoundboardButton` — soundboard-nappi, `_edit_mode` on luokkatason flag
- `translate_text(text, lang, backend, deepl_key)` — käännös, backend default "Google (free)"
- `open_settings_dialog()` — 4-välilehtinen asetusikkuna

## Kriittiset säännöt

**Lippuikonit:** `create_flag_icon()` käyttää VAIN `fillRect` — ei `setBrush/drawEllipse`. PyQt6 strict-mode kaatuu muuten.

**Thread-safety:** Ei suoria widget-kutsuja bg-threadista — käytä signaaleja.

**Uuden kielen lisääminen:** Päivitä kaikki viisi paikkaa: `LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`, `_GOOGLE_LANG_MAP`, `_DEEPL_LANG_MAP`, ja `create_flag_icon()` elif-ketju. Huom: Hebrew = `"iw"` Google-mapissa (ei `"he"`). Hindi/Hebrew/Croatian = `None` DeepL-mapissa (ei tueta).

**Soundboard:** `_sb_play_id` (int) counter estää concurrent play -kaatumisen. `SoundboardButton._edit_mode` on classmethod `set_edit_mode(bool)`.

## Tuetut kielet

28 built-in + käyttäjän omat (tallennetaan `app_settings.json` → `custom_languages`).

## Käyttäjäasetukset (app_settings.json)

`hotkey`, `wake_keyword`, `picovoice_access_key`, `default_target_lang`, `default_tts_backend`, `wake_command_seconds`, `translation_backend`, `deepl_api_key`, `custom_languages`.

## Code Signing

Self-signed cert kehityskäyttöön (ei luotettu SmartScreenissä).

- Paikallinen build: `build_app.bat` lukee `.env`:stä `SIGN_CERT_PATH` + `SIGN_CERT_PASSWORD`, ajaa signtool automaattisesti
- CI/GitHub Actions: secretit `SIGN_CERT_BASE64` + `SIGN_CERT_PASSWORD` GitHubin Settings → Secrets → Actions
- **Ei koskaan githubiin:** `.env`, `certs/`, `*.pfx`

## Releases

`.github/workflows/release.yml` — triggeröityy `v*`-tagista:
- Windows: PyInstaller → Inno Setup → signtool → release asset
- macOS: PyInstaller → DMG → ad-hoc sign → release asset

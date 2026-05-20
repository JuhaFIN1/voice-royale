# Voice Royale — Claude Code context

## Projekti lyhyesti

Windows-työpöytäsovellus (PyQt6) joka:
1. Tallentaa ääntä mikrofonista (sounddevice)
2. Transkriptoi Whisperillä (OpenAI Whisper API)
3. Kääntää GPT-4.1-mini:llä valittuun kieleen
4. Toistaa käännöksen TTS:llä (Edge TTS / ElevenLabs / pyttsx3)

## Käynnistys

```bat
cd /d "E:\CLOUDS\AI-SYSTEMS\ai-voice-router"
python ai_voice_app.py
```

Tai `build_app.bat` → PyInstaller EXE.

## Tiedostorakenne

| Tiedosto | Kuvaus |
|---|---|
| `ai_voice_app.py` | Koko sovellus, ~2100 riviä |
| `credentials.env` | API-avaimet (OPENAI_API_KEY, ELEVEN_API_KEY, VOICE_ID) |
| `app_settings.json` | Käyttäjäasetukset (hotkey, wake keyword, TTS backend) |
| `speech_history.json` | Historia + suosikit |
| `requirements.txt` / `requirements 2.txt` | Riippuvuudet |
| `build_app.bat` | PyInstaller-build |

## Arkkitehtuuri (ai_voice_app.py)

- **rivit 10–32**: `install_deps()` — automaattinen pip-asennus käynnistyksessä
- **rivit 76–111**: UI-tyylikionstantit (`METER_LABEL_STYLE`, `METER_STYLE_MIC`, jne.)
- **rivit 140–193**: Kielidictit (`LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`)
- **rivit 618–779**: `WakeListener` — wake-word kuuntelija
- **rivit 784+**: `App(QWidget)` — pääluokka koko UI:lla
- **rivit ~1990+**: `open_settings_dialog()` — asetusikkuna

## Tuetut kielet (15 kpl)

Auto, English, German, Swedish, Finnish, Russian, Italian,
Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian,
Japanese, Chinese, Hungarian

## Kriittiset tekniset huomiot

### Lippuikonit
`create_flag_icon(country_code)` käyttää VAIN `fillRect` — ei `setBrush/drawEllipse`.
PyQt6 strict-mode kaataa `build_language_icons()` jos käytetään ellipsiä.

### WakeListener
Kaksi moodia automaattisesti:
- **Porcupine** (jos `pvporcupine` asennettu JA Picovoice-avain asetettu Asetuksissa)
- **Whisper VAD fallback** (toimii ilman avainta — tallentaa 2.5s pätkiä, tarkistaa onko wake-sana)

### Uuden kielen lisääminen
Lisää kolmeen dict:iin (`LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`) ja `create_flag_icon()` elif-ketjuun. Käytä vain `fillRect`.

### Monilaitetoisto
`play_wav_bytes()` tukee useaa output-laitetta samanaikaisesti (threading).

## Käyttäjäasetukset

Tallennetaan `app_settings.json`:
- `hotkey` — globaali pikanäppäin (oletus: `ctrl+alt+space`)
- `wake_keyword` — wake-sana (oletus: `jarvis`)
- `picovoice_access_key` — Porcupine-avain (valinnainen)
- `default_target_lang` — oletuskohde
- `default_tts_backend` — Edge TTS (free) tai ElevenLabs
- `wake_command_seconds` — äänityspituus wake-sanan jälkeen (oletus: 6s)

## Viimeksi tehty (2026-05-12)

1. Iso UI-refaktorointi: per-device output-rivit checkboxeilla, tasomittarit, asetukset-dialogi
2. WakeListener korjattu — Whisper VAD fallback lisätty
3. Lisätty 9 uutta kieltä: Dutch, Norwegian, Danish, Romanian, Latvian, Lithuanian, Japanese, Chinese, Hungarian
4. Korjattu lippuikonit (JP/CN käyttivät setBrush/drawEllipse → korjattu fillRect:ksi)

## Code Signing Setup (Windows EXE Signing)

Project uses Windows Code Signing with a locally generated self-signed certificate for development/testing.

### Certificate location
- PFX file: `certs/juha-signing.pfx`

### Environment variables (.env)
- SIGN_CERT_PATH=certs/juha-signing.pfx
- SIGN_CERT_PASSWORD=The password used when exporting the PFX certificate

### Important rules
- NEVER commit `.env`, `.pfx` files, or the `certs/` folder to GitHub
- Signing certificate and password are local-only secrets
- If either the PFX or password changes, both must be updated together
- The certificate is used only for development/testing signing (not trusted by Windows SmartScreen globally)

### Build / Signing workflow (manual for now)
1. Build the application (no automation yet)
2. Load environment variables from `.env`
3. Use `signtool.exe` to sign the generated `.exe` using:
   - Certificate from `SIGN_CERT_PATH`
   - Password from `SIGN_CERT_PASSWORD`
4. Output is a signed executable ready for distribution/testing

### Security note
This setup is temporary and intended for development. For production releases, a trusted Code Signing Certificate (or EV Code Signing Certificate) is required to reduce Windows SmartScreen warnings.

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
| `ai_voice_app.py` | Koko sovellus, ~5600 riviä |
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
- `VoiceEffectProcessor` — real-time DSP, `set_monitor(device, enabled)` = Hear Myself
- `SetupWizard` — 4-vaiheinen: Welcome / API key / Enter key / VB-Cable / Devices
- `open_settings_dialog()` — 6-välilehtinen asetusikkuna (Käännös, Wake Word, Kielet, Pikavalinnat, Stream Deck, Asennukset)

## Stream Deck HTTP API (ai_voice_app.py — sessio 8)

`StreamDeckHttpServer` käynnistyy aina appin mukana, **port 17842**.

| Endpoint | Kuvaus |
|---|---|
| `GET /health` | `{"ok": true}` |
| `GET /state` | JSON: recording, listening, language, fx_preset, tts_backend, soundboard_page, soundboard_pages[].slots[].{name,has_file,has_image,image_path} |
| `GET /actions` | Lista kaikista toiminnoista |
| `POST /action/{name}` | Suorita toiminto (no body, no Content-Type) |
| `GET /soundboard/image/{page}/{slot}` | `{"image": "data:image/png;base64,..."}` tai `{"image": null}` |

**Thread-safety — kriittinen:** `QTimer.singleShot(0, cb)` bg-threadista EI toimi PyQt6:ssa. Käytä `queue.Queue`:

```python
self._sd_action_queue = queue.Queue()
self._sd_action_timer = QTimer(self)           # 50ms — nopea nappivaste
self._sd_action_timer.timeout.connect(self._drain_sd_action_queue)
self._sd_action_timer.start(50)
self._sd_state_timer = QTimer(self)            # 1500ms — tila-pollaus
self._sd_state_timer.timeout.connect(self._refresh_sd_state)
self._sd_state_timer.start(1500)
```

`do_POST` laittaa action-nimen jonoon; `_drain_sd_action_queue()` kutsuu `_handle_sd_action_impl()` pääthreadissa.

**CORS:** POST ilman bodya/Content-Typea = simple request, ei OPTIONS-preflight. Älä lisää headereita fetchiin.

## Stream Deck Plugin (streamdeck-plugin/)

`streamdeck-plugin/com.voiceroyale.sdPlugin/` — virallinen Elgato-plugin.

- `manifest.json` — v1.2.7, **`CategoryIcon` vaaditaan SD 7.x:ssä** (puuttuva → "unable to install")
- `plugin.html` — HTML-pohjainen plugin (native WebSocket + fetch, ei Node.js); `CodePath: "plugin.html"`
- `propertyinspector/soundboard.html` — SD WebSocket API: `getSettings`/`setSettings`/`didReceiveSettings`, lataa nimimuuttujat `/state`-endpointista
- `propertyinspector/lang.html`, `propertyinspector/fx.html` — vastaavat
- `icons/plugin.png` (72×72), `icons/plugin@2x.png` (144×144)
- `build-plugin.bat` — pakkaa `.streamDeckPlugin`-tiedostoksi

**Asennus (manuaalinen):** pura zip → `%APPDATA%\Elgato\StreamDeck\Plugins\com.voiceroyale.sdPlugin\`

**Action-nimet** (POST /action/{name}):
`record_toggle`, `wake_listen_toggle`, `speak`, `stop_recording`, `settings`, `tts_toggle`,
`sb_page_next`, `sb_page_prev`, `lang_{language}`, `fx_{preset}`, `soundboard_{page}_{slot}`

## Kriittiset säännöt

**Lippuikonit:** `create_flag_icon()` käyttää VAIN `fillRect` — ei `setBrush/drawEllipse`. PyQt6 strict-mode kaatuu muuten.

**Thread-safety:** Ei suoria widget-kutsuja bg-threadista — käytä signaaleja.

**Uuden kielen lisääminen:** Päivitä kaikki viisi paikkaa: `LANGS`, `LANG_FLAG_CODES`, `EDGE_VOICES`, `_GOOGLE_LANG_MAP`, `_DEEPL_LANG_MAP`, ja `create_flag_icon()` elif-ketju. Huom: Hebrew = `"iw"` Google-mapissa (ei `"he"`). Hindi/Hebrew/Croatian = `None` DeepL-mapissa (ei tueta).

**Soundboard:** `_sb_play_id` (int) counter estää concurrent play -kaatumisen. `SoundboardButton._edit_mode` on classmethod `set_edit_mode(bool)`.

## Tuetut kielet

28 built-in + käyttäjän omat (tallennetaan `app_settings.json` → `custom_languages`).

## Käyttäjäasetukset (app_settings.json)

`hotkey`, `wake_keyword`, `picovoice_access_key`, `default_target_lang`, `default_tts_backend`, `wake_command_seconds`, `translation_backend`, `deepl_api_key`, `custom_languages`, `voice_fx_output_device`, `voice_fx_monitor_device`, `voice_fx_hear_myself`.

## Kriittinen: Settings-ikkuna exe-tilassa

`_pkg_status()` asetusikkunan Asennukset-välilehdellä käyttää `sys.modules` frozen-tilassa (`getattr(sys, "frozen", False)`). ÄLÄ käytä `importlib.import_module` frozen-tilassa valinnaisten natiivi-kirjastojen (pvporcupine, pyrubberband) kanssa — ne voivat kaataa prosessin muulla kuin `ImportError`-poikkeuksella.

## Hear Myself — Voice FX -monitorointi

`VoiceEffectProcessor.set_monitor(device, enabled)` käynnistää/pysäyttää erillisen `_monitor_stream` OutputStream-virran. Prosessori kirjoittaa käsitellyn audion sekä FX-outputtiin (VB-Cable) että monitor-outputtiin (kuulokkeet) kun `_hear_myself=True`. Asetetaan myös `start()`:ssa jos `_monitor_device` on asetettu.

## Code Signing

Self-signed cert kehityskäyttöön (ei luotettu SmartScreenissä).

- Paikallinen build: `build_app.bat` lukee `.env`:stä `SIGN_CERT_PATH` + `SIGN_CERT_PASSWORD`, ajaa signtool automaattisesti
- CI/GitHub Actions: secretit `SIGN_CERT_BASE64` + `SIGN_CERT_PASSWORD` GitHubin Settings → Secrets → Actions
- **Ei koskaan githubiin:** `.env`, `certs/`, `*.pfx`

## Releases

`.github/workflows/release.yml` — triggeröityy `v*`-tagista:
- Windows: PyInstaller → Inno Setup → signtool → release asset
- macOS: PyInstaller → DMG → ad-hoc sign → release asset

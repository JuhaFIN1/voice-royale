# Copilot Instructions for AI Voice Router

This workspace contains a Windows desktop Python app for AI voice routing built with PyQt6.

## Project Focus
- Single-file app: `ai_voice_app.py`
- UI is a dark-themed PyQt6 desktop app
- Audio input/output routing using `sounddevice`
- Multiple TTS backends: Edge TTS, ElevenLabs, local fallback
- Persistent history/favorites in `speech_history.json`
- Global hotkey support and no console window when packaged

## Guidance for Copilot
- Prefer editing `ai_voice_app.py` unless the user explicitly requests a new file
- Keep the UI responsive and avoid blocking the main thread
- Do not introduce unnecessary dependencies
- Use `QListWidget` or `QComboBox` for selection controls, with clear visual styling
- For audio output, support selecting multiple devices when possible
- Preserve existing user data and history format when migrating
- Keep code concise and maintainable

## When responding
- Provide short, actionable answers
- Mention the exact file changed, if any
- Do not make broad architectural changes unless asked

## User Preferences
- The app is meant for Windows desktop use
- Prioritize reliable audio routing and user-friendly device selection
- Avoid using unstable emoji rendering in PyQt6 controls

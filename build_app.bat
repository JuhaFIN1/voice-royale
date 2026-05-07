@echo off
REM Build the AI Voice Router executable with PyInstaller
set PYINSTALLER_ARGS=--noconsole --onefile --name "AI Voice Router" --add-data "credentials.env;."
python -m PyInstaller %PYINSTALLER_ARGS% ai_voice_app.py
if errorlevel 1 (
    echo Build failed.
) else (
    echo Build complete. Check the dist folder.
)

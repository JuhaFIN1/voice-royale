@echo off
REM ============================================================
REM  AI Voice Router — PyInstaller build
REM  Output: dist\AI Voice Router\AI Voice Router.exe
REM
REM  After build, place credentials.env next to the .exe
REM ============================================================

set NAME=AI Voice Router
set SCRIPT=ai_voice_app.py
set VENV_PYTHON=.venv\Scripts\python.exe

REM Use venv python if available, else system python
if exist "%VENV_PYTHON%" (
    set PYTHON=%VENV_PYTHON%
) else (
    set PYTHON=python
)

echo Using Python: %PYTHON%
echo.

%PYTHON% -m PyInstaller ^
    --noconsole ^
    --onedir ^
    --name "%NAME%" ^
    --add-data "juhalempiainensoftware.png;." ^
    --hidden-import scipy.signal ^
    --hidden-import pyttsx3.drivers ^
    --hidden-import pyttsx3.drivers.sapi5 ^
    --hidden-import comtypes.stream ^
    --collect-all edge_tts ^
    --collect-all sounddevice ^
    --collect-all certifi ^
    --noconfirm ^
    %SCRIPT%

if errorlevel 1 (
    echo.
    echo *** BUILD FAILED — check errors above ***
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Build complete!
echo  Folder: dist\%NAME%\
echo.
echo  IMPORTANT: copy credentials.env into dist\%NAME%\
echo  before running the app.
echo ============================================================
pause

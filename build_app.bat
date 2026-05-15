@echo off
REM ============================================================
REM  AI Voice Router — Full build: PyInstaller + Windows Installer
REM
REM  Output: installer_output\AI_Voice_Router_Setup_%VERSION%.exe
REM ============================================================

set NAME=AI Voice Router
set SCRIPT=ai_voice_app.py
set VENV_PYTHON=.venv\Scripts\python.exe
set VERSION=1.0.1
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set INNO_INSTALLER_URL=https://files.jrsoftware.org/is/6/innosetup-6.3.3.exe
set INNO_TEMP=%TEMP%\innosetup_installer.exe

echo ============================================================
echo  Step 1/3 — PyInstaller
echo ============================================================

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
    echo *** PyInstaller FAILED — check errors above ***
    pause
    exit /b 1
)

echo.
echo PyInstaller build complete.

REM ============================================================
echo.
echo ============================================================
echo  Step 2/3 — Inno Setup (Windows Installer)
echo ============================================================

REM Check for Inno Setup; download and install if missing
if not exist %ISCC% (
    echo Inno Setup not found. Downloading...
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri '%INNO_INSTALLER_URL%' -OutFile '%INNO_TEMP%'" 2>nul
    if not exist "%INNO_TEMP%" (
        echo Download failed. Install Inno Setup manually from https://jrsoftware.org/isdl.php
        pause
        exit /b 1
    )
    echo Installing Inno Setup silently...
    "%INNO_TEMP%" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    del "%INNO_TEMP%"
    if not exist %ISCC% (
        echo Inno Setup install failed. Install it manually and re-run.
        pause
        exit /b 1
    )
    echo Inno Setup installed.
)

echo Building installer...
if not exist installer_output mkdir installer_output

%ISCC% installer.iss

if errorlevel 1 (
    echo.
    echo *** Installer build FAILED — check errors above ***
    pause
    exit /b 1
)

REM ============================================================
echo.
echo ============================================================
echo  Step 3/3 — Done!
echo.
echo  Installer: installer_output\AI_Voice_Router_Setup_%VERSION%.exe
echo.
echo  Distribute that single file.
echo  Users run it and follow the wizard.
echo  After install they must add their OPENAI_API_KEY
echo  to credentials.env in the installation folder.
echo ============================================================
pause

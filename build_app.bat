@echo off
REM ============================================================
REM  Voice Royale — Full build: PyInstaller + Windows Installer
REM
REM  Output: installer_output\Voice_Royale_Setup_%VERSION%.exe
REM ============================================================

set NAME=Voice Royale
set SCRIPT=ai_voice_app.py
set VENV_PYTHON=.venv\Scripts\python.exe
set VERSION=1.2.0
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
    --icon "iconimage.ico" ^
    --add-data "juhalempiainensoftware.png;." ^
    --add-data "iconimage.ico;." ^
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
echo  Step 3/4 — Code Signing
echo ============================================================

set SIGNTOOL="C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"
set INSTALLER=installer_output\Voice_Royale_Setup_%VERSION%.exe

REM Load signing variables from .env if present
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
        if "%%A"=="SIGN_CERT_PATH"     set SIGN_CERT_PATH=%%B
        if "%%A"=="SIGN_CERT_PASSWORD" set SIGN_CERT_PASSWORD=%%B
    )
)

if not defined SIGN_CERT_PATH (
    echo Skipping signing — SIGN_CERT_PATH not set in .env
    goto done
)
if not exist "%SIGN_CERT_PATH%" (
    echo Skipping signing — cert not found: %SIGN_CERT_PATH%
    goto done
)

echo Signing: %INSTALLER%
%SIGNTOOL% sign /f "%SIGN_CERT_PATH%" /p "%SIGN_CERT_PASSWORD%" /td sha256 /fd sha256 "%INSTALLER%"

if errorlevel 1 (
    echo *** Signing FAILED — check cert path and password in .env ***
    pause
    exit /b 1
)
echo Signing complete.

REM ============================================================
:done
echo.
echo ============================================================
echo  Step 4/4 — Done!
echo.
echo  Installer: %INSTALLER%
echo.
echo  Distribute that single file.
echo  Users run it and follow the wizard.
echo  After install they must add their OPENAI_API_KEY
echo  to credentials.env in the installation folder.
echo ============================================================
pause

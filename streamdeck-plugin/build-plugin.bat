@echo off
REM ============================================================
REM  Build com.voiceroyale.streamDeckPlugin
REM  Double-click the output file to install in Stream Deck.
REM ============================================================

set PLUGIN_DIR=com.voiceroyale.sdPlugin
set OUTPUT=com.voiceroyale.streamDeckPlugin

if exist "%OUTPUT%" del "%OUTPUT%"

echo Packing %PLUGIN_DIR% into %OUTPUT% ...
powershell -NoProfile -Command ^
    "Compress-Archive -Path '%PLUGIN_DIR%' -DestinationPath '%OUTPUT%.zip' -Force; Rename-Item '%OUTPUT%.zip' '%OUTPUT%'"

if exist "%OUTPUT%" (
    echo.
    echo Done: %OUTPUT%
    echo Double-click it to install in Elgato Stream Deck software.
) else (
    echo.
    echo *** Build FAILED — check errors above ***
)
pause

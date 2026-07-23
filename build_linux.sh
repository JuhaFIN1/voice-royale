#!/bin/bash
# Voice Royale - Fedora Linux build script
# Ajetaan Fedora Linuxilla (testattu Fedora Linux 44, myos WSL2:ssa).
# Tuottaa: dist/voice-royale/ (PyInstaller onedir) + RPM ~/rpmbuild/RPMS/x86_64/
set -e

NAME=voice-royale
SCRIPT=ai_voice_app.py
VERSION=$(grep -oP 'APP_VERSION = "\K[^"]+' ai_voice_app.py)
echo "Building Voice Royale $VERSION for Fedora Linux..."

# --- 1. Jarjestelmariippuvuudet (kertaalleen, dnf) ---
# sudo dnf install -y python3.12 python3.12-devel ffmpeg-free rpm-build gcc git \
#   portaudio-devel mesa-libEGL mesa-libGL libxkbcommon libxkbcommon-x11 \
#   xcb-util-cursor xcb-util-wm xcb-util-keysyms xcb-util xcb-util-image \
#   xcb-util-renderutil pipewire-pulseaudio espeak-ng

# --- 2. venv + pip-riippuvuudet ---
if [ ! -d .venv312 ]; then
    python3.12 -m venv .venv312
fi
source .venv312/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller -q

# --- 3. PyInstaller onedir-build (CLI-lippuina, sama malli kuin build_app.bat) ---
# HUOM: pyttsx3.drivers.espeak (ei sapi5/comtypes — ne ovat Windows-vain).
# .png-ikoni koska PyInstaller ei tue .ico/.icns-ikoneita Linuxilla ("Ignoring icon" -
# varoitus on odotettu ja harmiton, .desktop-tiedosto hoitaa sovellusikonin XDG-menussa.
python -m PyInstaller \
    --noconsole \
    --onedir \
    --name "$NAME" \
    --icon "iconimage.png" \
    --add-data "BluexDEV_logo.png:." \
    --add-data "iconimage.png:." \
    --hidden-import scipy.signal \
    --hidden-import stftpitchshift \
    --hidden-import pyttsx3.drivers \
    --hidden-import pyttsx3.drivers.espeak \
    --collect-all edge_tts \
    --collect-all sounddevice \
    --collect-all certifi \
    --noconfirm \
    "$SCRIPT"

# --- 4. RPM-paketointi ---
mkdir -p ~/rpmbuild/{SOURCES,SPECS,BUILD,RPMS,SRPMS,BUILDROOT}
tar czf ~/rpmbuild/SOURCES/${NAME}-${VERSION}-linux-x86_64.tar.gz -C dist "$NAME"
cp packaging/voice-royale.desktop ~/rpmbuild/SOURCES/
cp iconimage.png ~/rpmbuild/SOURCES/
sed "s/^Version:.*/Version:        ${VERSION}/" packaging/voice-royale.spec > ~/rpmbuild/SPECS/voice-royale.spec
rpmbuild -ba ~/rpmbuild/SPECS/voice-royale.spec

echo ""
echo "Valmis. RPM: ~/rpmbuild/RPMS/x86_64/${NAME}-${VERSION}-1.fc*.x86_64.rpm"
echo "Asennus: sudo dnf install ~/rpmbuild/RPMS/x86_64/${NAME}-${VERSION}-1.fc*.x86_64.rpm"
echo "Ajo: voice-royale  (tai Sovellukset-valikosta 'Voice Royale')"

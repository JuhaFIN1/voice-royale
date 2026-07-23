%global debug_package %{nil}
%global __os_install_post %{nil}
%global _build_id_links none

Name:           voice-royale
Version:        1.3.91
Release:        1%{?dist}
Summary:        Mikrofoni -> Whisper -> kaannos -> puhesynteesi -sovellus
License:        Proprietary
URL:            https://github.com/JuhaFIN1/voice-royale
Source0:        voice-royale-%{version}-linux-x86_64.tar.gz
Source1:        voice-royale.desktop
Source2:        iconimage.png
BuildArch:      x86_64
AutoReqProv:    no
Requires:       mesa-libEGL, mesa-libGL, xcb-util-cursor, xcb-util-wm, xcb-util-keysyms, xcb-util-image, xcb-util-renderutil, libxkbcommon-x11, pipewire-pulseaudio, espeak-ng, ffmpeg-free

%description
Voice Royale: mikrofonista puhe tekstiksi (Whisper), kaannos (Google/DeepL/OpenAI)
ja puhesynteesi (ElevenLabs/Edge TTS/OpenAI). Fedora Linux -kannettava paketti,
sisaltaa oman Python-runtimen (PyInstaller onedir-build), ei ulkoisia
pip-riippuvuuksia asennushetkella.

%prep
%setup -q -c -n voice-royale-src

%build
# no build step, binary is pre-built by PyInstaller

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/voice-royale
cp -a voice-royale/. %{buildroot}/opt/voice-royale/
mkdir -p %{buildroot}%{_datadir}/applications
install -m 644 %{SOURCE1} %{buildroot}%{_datadir}/applications/voice-royale.desktop
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps
install -m 644 %{SOURCE2} %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/voice-royale.png
mkdir -p %{buildroot}%{_bindir}
ln -sf /opt/voice-royale/voice-royale %{buildroot}%{_bindir}/voice-royale

%files
/opt/voice-royale
%{_bindir}/voice-royale
%{_datadir}/applications/voice-royale.desktop
%{_datadir}/icons/hicolor/256x256/apps/voice-royale.png

%post
/usr/bin/update-desktop-database &>/dev/null || :
/usr/bin/gtk-update-icon-cache %{_datadir}/icons/hicolor &>/dev/null || :

%postun
/usr/bin/update-desktop-database &>/dev/null || :

%changelog
* Thu Jul 23 2026 BluexDEV Softwares <asiakaspalvelu@selaa.fi> - 1.3.91-1
- Ensimmainen Fedora Linux -porttaus (PyInstaller onedir + RPM)

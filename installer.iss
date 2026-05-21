[Setup]
AppId={{F3A7C2E1-9B4D-4F8A-BC23-1E5D7A9F0C42}
AppName=Voice Royale
AppVersion=1.3.10
AppPublisher=Juha Lempiäinen
AppPublisherURL=https://github.com/JuhaFIN1/voice-royale
AppSupportURL=https://github.com/JuhaFIN1/voice-royale/issues
DefaultDirName={autopf}\Voice Royale
DefaultGroupName=Voice Royale
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=Voice_Royale_Setup_1.3.10
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\Voice Royale.exe
DisableProgramGroupPage=no
SetupIconFile=iconimage.ico
UninstallDisplayName=Voice Royale
; Close a running instance automatically before overwriting files
CloseApplications=yes
CloseApplicationsFilter=Voice Royale.exe
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\Voice Royale\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "credentials.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "iconimage.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "streamdeck-plugin\com.voiceroyale.streamDeckPlugin"; DestDir: "{app}\StreamDeck"; Flags: ignoreversion

[Icons]
Name: "{group}\Voice Royale"; Filename: "{app}\Voice Royale.exe"; IconFilename: "{app}\iconimage.ico"
Name: "{group}\Edit credentials (API keys)"; Filename: "notepad.exe"; Parameters: "{app}\credentials.env.example"
Name: "{group}\Install Stream Deck Plugin"; Filename: "{app}\StreamDeck\com.voiceroyale.streamDeckPlugin"
Name: "{group}\Uninstall Voice Royale"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Voice Royale"; Filename: "{app}\Voice Royale.exe"; IconFilename: "{app}\iconimage.ico"; Tasks: desktopicon

[Run]
; Rebuild Windows icon cache so the new shortcut icon appears immediately
Filename: "{cmd}"; Parameters: "/c ie4uinit.exe -show"; Flags: runhidden waituntilidle
Filename: "{app}\Voice Royale.exe"; Description: "Launch Voice Royale"; Flags: nowait postinstall skipifsilent

[Messages]
WelcomeLabel2=This will install Voice Royale on your computer.%n%nThe app includes a first-run setup wizard that guides you through%nconfiguring your OpenAI API key and audio devices.%n%nClick Next to continue.
FinishedLabel=Voice Royale has been installed successfully.%n%nClick Finish to launch the app. The setup wizard will guide you through the initial configuration.

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataDir: String;
  Answer: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    AppDataDir := ExpandConstant('{userappdata}\Voice Royale');
    if DirExists(AppDataDir) then
    begin
      Answer := MsgBox(
        'Do you want to delete your personal data?' + #13#10 + #13#10 +
        'This includes:' + #13#10 +
        '  - API keys (credentials.env)' + #13#10 +
        '  - Settings and hotkeys' + #13#10 +
        '  - Speech history and favorites' + #13#10 +
        '  - Soundboard files and images' + #13#10 + #13#10 +
        'Click YES to delete everything.' + #13#10 +
        'Click NO to keep your data (you can reinstall later and pick up where you left off).',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2
      );
      if Answer = IDYES then
        DelTree(AppDataDir, True, True, True);
    end;
  end;
end;

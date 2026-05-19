[Setup]
AppId={{F3A7C2E1-9B4D-4F8A-BC23-1E5D7A9F0C42}
AppName=AI Voice Router
AppVersion=1.1.0
AppPublisher=Juha Lempiäinen
AppPublisherURL=https://github.com/JuhaFIN1/ai-voice-router
AppSupportURL=https://github.com/JuhaFIN1/ai-voice-router/issues
DefaultDirName={autopf}\AI Voice Router
DefaultGroupName=AI Voice Router
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=AI_Voice_Router_Setup_1.1.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\AI Voice Router.exe
DisableProgramGroupPage=no
SetupIconFile=iconimage.ico
UninstallDisplayName=AI Voice Router
; Close a running instance automatically before overwriting files
CloseApplications=yes
CloseApplicationsFilter=AI Voice Router.exe
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\AI Voice Router\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "credentials.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "iconimage.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\AI Voice Router"; Filename: "{app}\AI Voice Router.exe"; IconFilename: "{app}\iconimage.ico"
Name: "{group}\Edit credentials (API keys)"; Filename: "notepad.exe"; Parameters: "{app}\credentials.env.example"
Name: "{group}\Uninstall AI Voice Router"; Filename: "{uninstallexe}"
Name: "{commondesktop}\AI Voice Router"; Filename: "{app}\AI Voice Router.exe"; IconFilename: "{app}\iconimage.ico"; Tasks: desktopicon

[Run]
; Rebuild Windows icon cache so the new shortcut icon appears immediately
Filename: "{cmd}"; Parameters: "/c ie4uinit.exe -show"; Flags: runhidden waituntilidle
Filename: "{app}\AI Voice Router.exe"; Description: "Launch AI Voice Router"; Flags: nowait postinstall skipifsilent

[Messages]
WelcomeLabel2=This will install AI Voice Router on your computer.%n%nThe app includes a first-run setup wizard that guides you through%nconfiguring your OpenAI API key and audio devices.%n%nClick Next to continue.
FinishedLabel=AI Voice Router has been installed successfully.%n%nClick Finish to launch the app. The setup wizard will guide you through the initial configuration.

[Setup]
AppId={{F3A7C2E1-9B4D-4F8A-BC23-1E5D7A9F0C42}
AppName=AI Voice Router
AppVersion=1.0.1
AppPublisher=Juha Lempiäinen
AppPublisherURL=https://github.com/JuhaFIN1/ai-voice-router
AppSupportURL=https://github.com/JuhaFIN1/ai-voice-router/issues
DefaultDirName={autopf}\AI Voice Router
DefaultGroupName=AI Voice Router
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=AI_Voice_Router_Setup_1.0.1
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\AI Voice Router.exe
DisableProgramGroupPage=no
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

[Icons]
Name: "{group}\AI Voice Router"; Filename: "{app}\AI Voice Router.exe"
Name: "{group}\Edit credentials (API keys)"; Filename: "notepad.exe"; Parameters: "{app}\credentials.env.example"
Name: "{group}\Uninstall AI Voice Router"; Filename: "{uninstallexe}"
Name: "{commondesktop}\AI Voice Router"; Filename: "{app}\AI Voice Router.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AI Voice Router.exe"; Description: "Launch AI Voice Router"; Flags: nowait postinstall skipifsilent

[Messages]
WelcomeLabel2=This will install AI Voice Router on your computer.%n%nThe app includes a first-run setup wizard that guides you through%nconfiguring your OpenAI API key and audio devices.%n%nClick Next to continue.
FinishedLabel=AI Voice Router has been installed successfully.%n%nClick Finish to launch the app. The setup wizard will guide you through the initial configuration.

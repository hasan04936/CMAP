[Setup]
; --- Basic App Info ---
AppName=C-MAP Enterprise
AppVersion=1.0
AppPublisher=Grow Green Trading Co.
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={autopf}\C-MAP Enterprise
DisableProgramGroupPage=yes

; --- Output Settings ---
; This creates the final Setup.exe inside a new "Output" folder in your project
OutputDir=.\Output
OutputBaseFilename=C-MAP_Setup
SetupIconFile=Logo.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Grabs the main EXE
Source: "dist\CMAP_Enterprise\CMAP_Enterprise.exe"; DestDir: "{app}"; Flags: ignoreversion

; Grabs everything else (internal folder, ngrok, database) BUT blocks test logs!
Source: "dist\CMAP_Enterprise\*"; DestDir: "{app}"; Excludes: "*.txt, *.log"; Flags: ignoreversion recursesubdirs createallsubdirs

; Copies the default clean SQLite database
Source: "db.sqlite3"; DestDir: "{app}"; Flags: ignoreversion

; Copies the dynamic card scenery preview image placeholder
Source: "media\default_card_preview.png"; DestDir: "{app}\media"; Flags: ignoreversion

[Dirs]
; --- Force Clean Folders ---
; This guarantees the system creates a perfectly clean media architecture for the client
Name: "{app}\media"
Name: "{app}\media\avatars"
Name: "{app}\media\company_logos"
Name: "{app}\media\documents"
Name: "{app}\media\custom_uploads"

[Icons]
; --- Desktop & Start Menu Shortcuts ---
Name: "{autodesktop}\C-MAP Enterprise"; Filename: "{app}\CMAP_Enterprise.exe"; Tasks: desktopicon
Name: "{autoprograms}\C-MAP Enterprise"; Filename: "{app}\CMAP_Enterprise.exe"

[Run]
; --- Auto-Launch after Install ---
Filename: "{app}\CMAP_Enterprise.exe"; Description: "{cm:LaunchProgram,C-MAP Enterprise}"; Flags: nowait postinstall skipifsilent

[Registry]
; Write the installation path to the registry
Root: HKA; Subkey: "Software\CMAPEnterprise"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
; Write the machine's unique hardware ID to the registry
Root: HKA; Subkey: "Software\CMAPEnterprise"; ValueType: string; ValueName: "MachineID"; ValueData: "{code:GetMachineGuid}"; Flags: uninsdeletekey

[Code]
// Helper function to read the Windows MachineGuid from HKLM
function GetMachineGuid(Param: String): String;
var
  MachineGuid: String;
begin
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Cryptography', 'MachineGuid', MachineGuid) then
  begin
    Result := MachineGuid;
  end
  else
  begin
    Result := '';
  end;
end;
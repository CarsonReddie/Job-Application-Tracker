; JobTracker Inno Setup Installer Script
; Compile with Inno Setup: https://jrsoftware.org/isdl.php
;
; Open this file in Inno Setup Compiler and click Build > Compile

[Setup]
AppName=JobTracker
AppVersion=1.0.0
AppPublisher=Carson Reddie
DefaultDirName={autopf}\JobTracker
DefaultGroupName=JobTracker
OutputDir=.
OutputBaseFilename=JobTracker-Setup-1.0.0
SetupIconFile=installer_icon.ico
UninstallDisplayIcon={app}\JobTracker.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\JobTracker.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\JobTracker"; Filename: "{app}\JobTracker.exe"
Name: "{group}\Uninstall JobTracker"; Filename: "{uninstallexe}"
Name: "{autodesktop}\JobTracker"; Filename: "{app}\JobTracker.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JobTracker.exe"; Description: "Launch JobTracker"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

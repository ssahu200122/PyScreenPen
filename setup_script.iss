[Setup]
; --- General Info ---
AppName=PyScreen Pen
AppVersion=1.0.0
AppPublisher=Saurav
DefaultDirName={autopf}\PyScreenPen
DefaultGroupName=PyScreenPen

; --- Output Settings ---
; This will place the final installer in a folder called "Output" next to your script
OutputDir=.\Output
OutputBaseFilename=PyScreenPen_Setup
Compression=lzma2
SolidCompression=yes

; --- Aesthetics ---
; Requires admin rights to install to Program Files
PrivilegesRequired=admin
SetupIconFile=logo.ico

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; --- Core Application Files ---
; This points to your PyInstaller output folder. 
; Make sure this script is saved in the same root folder as your 'dist' folder!
Source: "dist\main\main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
; --- Start Menu & Desktop Shortcuts ---
Name: "{group}\PyScreenPen"; Filename: "{app}\main.exe"; IconFilename: "{app}\main.exe"
Name: "{group}\{cm:UninstallProgram,PyScreenPen}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PyScreenPen"; Filename: "{app}\main.exe"; Tasks: desktopicon; IconFilename: "{app}\main.exe"

[Run]
; --- Launch After Install ---
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,PyScreenPen}"; Flags: nowait postinstall skipifsilent

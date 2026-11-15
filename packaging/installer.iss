; Inno Setup — oddiy "Keyingi > Keyingi > O'rnatish" o'rnatuvchisi
[Setup]
AppName=RMS AI
AppVersion=0.7.0
DefaultDirName={autopf}\AgentUmimiy
DefaultGroupName=RMS AI
OutputDir=..\dist
OutputBaseFilename=RMSAI-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\AgentUmimiy.exe
SetupIconFile=AgentUmimiy.ico

[Files]
Source: "..\dist\AgentUmimiy\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\RMS AI"; Filename: "{app}\AgentUmimiy.exe"; IconFilename: "{app}\AgentUmimiy.exe"; AppUserModelID: "AgentUmimiy.Desktop"
Name: "{autodesktop}\RMS AI"; Filename: "{app}\AgentUmimiy.exe"; IconFilename: "{app}\AgentUmimiy.exe"; AppUserModelID: "AgentUmimiy.Desktop"

[Run]
Filename: "{app}\AgentUmimiy.exe"; Description: "RMS AI ni ishga tushirish"; Flags: nowait postinstall skipifsilent

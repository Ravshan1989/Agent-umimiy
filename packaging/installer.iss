; Inno Setup — oddiy "Keyingi > Keyingi > O'rnatish" o'rnatuvchisi
[Setup]
AppName=Agent Umimiy
AppVersion=0.4.0
DefaultDirName={autopf}\AgentUmimiy
DefaultGroupName=Agent Umimiy
OutputDir=..\dist
OutputBaseFilename=AgentUmimiy-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\AgentUmimiy.exe
SetupIconFile=AgentUmimiy.ico

[Files]
Source: "..\dist\AgentUmimiy\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Agent Umimiy"; Filename: "{app}\AgentUmimiy.exe"; IconFilename: "{app}\AgentUmimiy.exe"; AppUserModelID: "AgentUmimiy.Desktop"
Name: "{autodesktop}\Agent Umimiy"; Filename: "{app}\AgentUmimiy.exe"; IconFilename: "{app}\AgentUmimiy.exe"; AppUserModelID: "AgentUmimiy.Desktop"

[Run]
Filename: "{app}\AgentUmimiy.exe"; Description: "Agent Umimiy ni ishga tushirish"; Flags: nowait postinstall skipifsilent

; Inno Setup — ofis xodimlari uchun yengil RMS AI Client o'rnatuvchisi
[Setup]
AppName=RMS AI Client
AppVersion=0.7.0
DefaultDirName={autopf}\AgentUmimiyClient
DefaultGroupName=RMS AI Client
OutputDir=..\dist
OutputBaseFilename=RMSAIClient-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\AgentUmimiyClient.exe
SetupIconFile=AgentUmimiy.ico

[Files]
Source: "..\dist\AgentUmimiyClient\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\RMS AI Client"; Filename: "{app}\AgentUmimiyClient.exe"; IconFilename: "{app}\AgentUmimiyClient.exe"; AppUserModelID: "AgentUmimiy.Client"
Name: "{autodesktop}\RMS AI Client"; Filename: "{app}\AgentUmimiyClient.exe"; IconFilename: "{app}\AgentUmimiyClient.exe"; AppUserModelID: "AgentUmimiy.Client"

[Run]
Filename: "{app}\AgentUmimiyClient.exe"; Description: "RMS AI Client ni ishga tushirish"; Flags: nowait postinstall skipifsilent

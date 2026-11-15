; Inno Setup — ofis xodimlari uchun yengil RMS AI Client o'rnatuvchisi
[Setup]
AppName=RMS AI Client
AppVersion=0.7.1
DefaultDirName={autopf}\RMSAIClient
DefaultGroupName=RMS AI Client
OutputDir=..\dist
OutputBaseFilename=RMSAIClient-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\RMSAIClient.exe
SetupIconFile=AgentUmimiy.ico

[Files]
Source: "..\dist\RMSAIClient\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\RMS AI Client"; Filename: "{app}\RMSAIClient.exe"; IconFilename: "{app}\RMSAIClient.exe"; AppUserModelID: "RMSAI.Client"
Name: "{autodesktop}\RMS AI Client"; Filename: "{app}\RMSAIClient.exe"; IconFilename: "{app}\RMSAIClient.exe"; AppUserModelID: "RMSAI.Client"

[Run]
Filename: "{app}\RMSAIClient.exe"; Description: "RMS AI Client ni ishga tushirish"; Flags: nowait postinstall skipifsilent

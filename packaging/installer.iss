; Inno Setup — oddiy "Keyingi > Keyingi > O'rnatish" o'rnatuvchisi
[Setup]
AppName=RMS AI
AppVersion=0.7.2
DefaultDirName={autopf}\RMSAI
DefaultGroupName=RMS AI
OutputDir=..\dist
OutputBaseFilename=RMSAI-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\RMSAI.exe
SetupIconFile=AgentUmimiy.ico

[Files]
Source: "..\dist\RMSAI\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\RMS AI"; Filename: "{app}\RMSAI.exe"; IconFilename: "{app}\RMSAI.exe"; AppUserModelID: "RMSAI.Desktop"
Name: "{group}\RMS AI ni o'chirish"; Filename: "{uninstallexe}"
Name: "{autodesktop}\RMS AI"; Filename: "{app}\RMSAI.exe"; IconFilename: "{app}\RMSAI.exe"; AppUserModelID: "RMSAI.Desktop"

[Run]
Filename: "{app}\RMSAI.exe"; Description: "RMS AI ni ishga tushirish"; Flags: nowait postinstall skipifsilent

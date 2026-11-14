; Bộ cài đặt Windows (Inno Setup 6) cho Ứng dụng Kế toán – Hocviendaotaoai
; Biên dịch sau khi đã chạy packaging\build_windows.bat:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss

#define AppName "Ung dung Ke toan - Hocviendaotaoai"
#define AppVersion "1.1.0-gd2"

[Setup]
AppId={{6E7B9A52-3C1D-4E8F-9A0B-2F6C8D4E1A37}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Hocviendaotaoai
DefaultDirName={autopf}\Hocviendaotaoai\UngDungKeToan
DefaultGroupName=Hocviendaotaoai
OutputDir=..\dist
OutputBaseFilename=CaiDat_UngDungKeToan_{#AppVersion}
SetupIconFile=app.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tao bieu tuong tren Desktop"; Flags: unchecked

[Files]
Source: "..\dist\UngDungKeToan\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Ung dung Ke toan"; Filename: "{app}\UngDungKeToan.exe"
Name: "{group}\Huong dan cai dat"; Filename: "{app}\HUONG_DAN_CAI_DAT.md"
Name: "{autodesktop}\Ung dung Ke toan"; Filename: "{app}\UngDungKeToan.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\UngDungKeToan.exe"; Description: "Chay Ung dung Ke toan"; Flags: nowait postinstall skipifsilent

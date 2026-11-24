; Polat PDF kurulumu (Inno Setup 6). derle.ps1 çalıştırır; sürüm /DSurum=... ile gelir.
#ifndef Surum
  #define Surum "0.0.0"
#endif

[Setup]
AppId={{96927368-C104-47FF-ADE3-5E7812FDC8A7}
AppName=Polat PDF
AppVersion={#Surum}
AppPublisher=Polat
DefaultDirName={localappdata}\Programs\Polat PDF
DefaultGroupName=Polat PDF
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ChangesAssociations=yes
CloseApplications=force
OutputDir=Output
OutputBaseFilename=PolatPDF-Kurulum-{#Surum}
SetupIconFile=polatpdf.ico
UninstallDisplayIcon={app}\PolatPDF.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "masaustu"; Description: "Masaüstüne kısayol oluştur"

[Files]
Source: "dist\PolatPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; eski sürümden kalan kütüphaneler karışmasın
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Polat PDF"; Filename: "{app}\PolatPDF.exe"
Name: "{autodesktop}\Polat PDF"; Filename: "{app}\PolatPDF.exe"; Tasks: masaustu

[Registry]
; "Birlikte aç" listesi ve Varsayılan uygulamalar için kayıt (Windows varsayılanı kullanıcıya seçtirir)
Root: HKCU; Subkey: "Software\Classes\PolatPDF.Belge"; ValueType: string; ValueData: "PDF Belgesi"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\PolatPDF.Belge\DefaultIcon"; ValueType: string; ValueData: "{app}\PolatPDF.exe,0"
Root: HKCU; Subkey: "Software\Classes\PolatPDF.Belge\shell\open\command"; ValueType: string; ValueData: """{app}\PolatPDF.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PolatPDF.Belge"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\Applications\PolatPDF.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Polat PDF"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\PolatPDF.exe\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\Applications\PolatPDF.exe\shell\open\command"; ValueType: string; ValueData: """{app}\PolatPDF.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Polat PDF"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Polat PDF\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Polat PDF"
Root: HKCU; Subkey: "Software\Polat PDF\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "PDF görüntüleyici ve düzenleyici"
Root: HKCU; Subkey: "Software\Polat PDF\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "PolatPDF.Belge"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Polat PDF"; ValueData: "Software\Polat PDF\Capabilities"; Flags: uninsdeletevalue

[Run]
; sessiz kurulumda (güncelleme) uygulama kendiliğinden yeniden açılsın
Filename: "{app}\PolatPDF.exe"; Flags: nowait skipifnotsilent
Filename: "{app}\PolatPDF.exe"; Description: "Polat PDF'i şimdi aç"; Flags: nowait postinstall skipifsilent
Filename: "ms-settings:defaultapps?registeredAppUser=Polat%20PDF"; Description: "Bütün PDF'leri Polat PDF ile açmak için Windows ayarını aç"; Flags: shellexec postinstall skipifsilent

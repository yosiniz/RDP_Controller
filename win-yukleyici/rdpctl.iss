; =====================================================================
;  rdpctl - Windows kurulum betigi (Inno Setup)
; ---------------------------------------------------------------------
;  Bu betik rdpctl-setup.exe adli bir kurulum programi uretir. Son
;  kullanici bu setup.exe'yi cift tiklayip "Ileri -> Ileri" ile rdpctl'i
;  Program Files altina kurar; Baslat menusune kisayol ve "Programlar ve
;  Ozellikler" (Add/Remove Programs) listesine kayit eklenir.
;
;  DERLEME:
;    - Otomatik: GitHub Actions "Installers" is akisi (build-installers.yml)
;      once PyInstaller ile dist\rdpctl.exe + dist\rdpctl-kaldir.exe uretir,
;      sonra bu betigi "iscc win-yukleyici\rdpctl.iss" ile derler.
;    - Elle (Windows'ta): Inno Setup Compiler'i kurun, once uygulamalari
;      "pyinstaller --noconfirm packaging\rdpctl.spec" vb. ile uretip
;      dist\ klasorunu doldurun, sonra bu dosyayi Inno Setup ile derleyin.
;
;  KAYNAK DOSYA YOLLARI:
;    Bu betik win-yukleyici\ icindedir. "..\dist\..." yollari depo kokundeki
;    dist\ klasorune bakar; PyInstaller ciktilari oraya gelir. Istenirse
;    derleyiciye farkli bir konum bildirmek icin:
;        iscc /DSourceDir=C:\yol\dist win-yukleyici\rdpctl.iss
;    seklinde SourceDir tanimi gecilebilir (varsayilan: ..\dist).
; =====================================================================

#ifndef SourceDir
  #define SourceDir "..\dist"
#endif

#define MyAppName "rdpctl"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "rdpctl"
#define MyAppExeName "rdpctl.exe"
#define MyUninstExeName "rdpctl-kaldir.exe"

[Setup]
; AppId uygulamanin tekil kimligidir. DEGISTIRMEYIN; guncellemelerin ayni
; kurulumu bulabilmesi ve "Programlar ve Ozellikler" kaydinin dogru
; eslesmesi icin sabit kalmalidir.
AppId={{B2F1C3A4-5D6E-47F8-9A0B-1C2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=.
OutputBaseFilename=rdpctl-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Program Files altina kurmak icin yonetici yetkisi gerekir.
; ALTERNATIF (kullanici basina, yoneticisiz kurulum) isteniyorsa asagidaki
; iki satiri yorumdan cikarip yukaridaki PrivilegesRequired=admin satirini
; ve DefaultDirName'i degistirin:
;     PrivilegesRequired=lowest
;     DefaultDirName={autopf} yerine {userpf}\{#MyAppName}
; (Boylece kurulum yoneticisiz, yalnizca o kullanici icin yapilir.)
PrivilegesRequired=admin
; "Programlar ve Ozellikler" listesinde gorunen ad ve simge:
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
; Not: Inno Setup, yukaridaki AppId sayesinde Add/Remove Programs (Programlar
; ve Ozellikler) kaydini OTOMATIK olusturur; ayrica kendi kaldirici
; (unins000.exe) uretir. Bizim rdpctl-kaldir.exe da yan yana kurulur.
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
; Varsayilan olarak Ingilizce arayuz kullaniyoruz; boylece her Inno Setup
; dagitiminda (ve GitHub Actions'ta) sorunsuz derlenir.
Name: "english"; MessagesFile: "compiler:Default.isl"
; TURKCE ARAYUZ (istege bagli): Inno Setup'in resmi dagitiminda Turkish.isl
; bulunur. Turkce sihirbaz istiyorsaniz asagidaki satiri yorumdan cikarin.
; CI ortaminda bu dosya olmayabilecegi icin varsayilan olarak kapalidir.
; Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
; Masaustu kisayolu istege baglidir; sihirbazda kullaniciya sorulur.
Name: "desktopicon"; Description: "Masaustune kisayol olustur"; GroupDescription: "Ek simgeler:"; Flags: unchecked

[Files]
; Ana uygulama ve bizim kaldiricimiz {app} (Program Files\rdpctl) icine kopyalanir.
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\{#MyUninstExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Baslat menusu kisayollari
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} Kaldir"; Filename: "{app}\{#MyUninstExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Istege bagli masaustu kisayolu (yukaridaki desktopicon gorevine bagli)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Kurulum bitince uygulamayi (istege bagli) baslat.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

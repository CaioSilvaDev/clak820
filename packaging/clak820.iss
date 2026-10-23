; Instalador do clak820 (Inno Setup 6).
; Compilar:  ISCC.exe /DAppVersion=0.2.0 packaging\clak820.iss
; Instala por usuário (sem admin) em %LOCALAPPDATA%\Programs\clak820.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B0E2B71-8C4D-4A51-9E1B-C1A6820C1A82}
AppName=clak820
AppVersion={#AppVersion}
AppVerName=clak820 {#AppVersion}
AppPublisher=Caio Silva
AppPublisherURL=https://github.com/CaioSilvaDev/clak820
AppSupportURL=https://github.com/CaioSilvaDev/clak820/issues
DefaultDirName={localappdata}\Programs\clak820
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=clak820-{#AppVersion}-setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\clak820.exe
UninstallDisplayName=clak820
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
ptbr.Plug=Antes de abrir: conecte o teclado pelo cabo USB, no modo com fio, e feche o app oficial da AJAZZ.
en.Plug=Before launching: connect the keyboard with the USB cable in wired mode and close the official AJAZZ app.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\clak820\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\clak820"; Filename: "{app}\clak820.exe"
Name: "{autodesktop}\clak820"; Filename: "{app}\clak820.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\clak820.exe"; Description: "{cm:LaunchProgram,clak820}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Fecha o app e remove o statusLine e a inicialização automática.
Filename: "{app}\clak820-cli.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "clak820-uninstall"

[Code]
// Fecha uma versão já instalada antes de trocar os arquivos (atualização).
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  if FileExists(ExpandConstant('{app}\clak820-cli.exe')) then
  begin
    Exec(ExpandConstant('{app}\clak820-cli.exe'), 'stop', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Sleep(500);
  end;
  Result := '';
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 + CustomMessage('Plug');
end;

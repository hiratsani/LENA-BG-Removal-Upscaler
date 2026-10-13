[Setup]
AppId=LENAEnhancedDesktopLocal
AppName=LENA
AppVerName=LENA
AppVersion=1.0.0
VersionInfoVersion=1.0.0.0
AppPublisher=Hiratsani
DefaultDirName={localappdata}\Programs\LENA
UsePreviousAppDir=no
DefaultGroupName=LENA
UsePreviousGroup=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0.18362
OutputDir=..\Installer
OutputBaseFilename=LENA
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\LENA.ico
UninstallDisplayIcon={app}\LENA.exe
DisableProgramGroupPage=yes

[Files]
Source: ".build\dist\LENA\LENA.exe"; DestDir: "{app}"; DestName: "LENA.exe"; Flags: ignoreversion
Source: ".build\dist\LENA\*"; DestDir: "{app}"; Excludes: "LENA.exe"; Flags: ignoreversion recursesubdirs createallsubdirs

; A true uninstall should reset onboarding/preferences so reinstall behaves like
; a fresh install. Keep the model cache intact unless the user explicitly
; chooses to remove downloaded models in the uninstall dialog.
[UninstallDelete]
Type: files; Name: "{localappdata}\LENA\settings.json"
Type: files; Name: "{localappdata}\LENA\settings.tmp"

[Run]
Filename: "{app}\LENA.exe"; Description: "Open LENA"; Flags: nowait postinstall skipifsilent

#include "uninstall_models.iss"

// Shortcuts are convenience only. Some hardened/debloated Windows builds,
// Controlled Folder Access policies, or broken Desktop ACLs can reject .lnk
// creation with 0x80070005. Never fail the whole LENA install for that.
procedure TryCreateLenaShortcut(const LinkFile: String);
var
  ParentDir: String;
begin
  try
    ParentDir := ExtractFileDir(LinkFile);
    if (ParentDir <> '') and (not DirExists(ParentDir)) then
      ForceDirectories(ParentDir);

    CreateShellLink(
      LinkFile,
      'LENA',
      ExpandConstant('{app}\LENA.exe'),
      '',
      ExpandConstant('{app}'),
      ExpandConstant('{app}\LENA.exe'),
      0,
      SW_SHOWNORMAL);
  except
    // Intentionally log only. A shortcut permission problem must never make
    // Setup look like the application itself failed to install.
    Log('LENA shortcut skipped: ' + LinkFile + ' - ' + GetExceptionMessage);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    TryCreateLenaShortcut(ExpandConstant('{group}\LENA.lnk'));
    TryCreateLenaShortcut(ExpandConstant('{userdesktop}\LENA.lnk'));
  end;
end;

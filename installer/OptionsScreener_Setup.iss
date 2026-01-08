; Inno Setup Script for Smart Options Screener v3.3
; 
; Prerequisites:
;   1. Install Inno Setup from: https://jrsoftware.org/isdl.php
;   2. Build the app first with: pyinstaller OptionsScreener.spec
;   3. Open this file in Inno Setup Compiler and click Build > Compile
;
; Output: Creates OptionsScreener_Setup.exe in the 'installer/output' folder

#define MyAppName "Smart Options Screener"
#define MyAppVersion "3.3"
#define MyAppPublisher "Your Company Name"
#define MyAppURL "https://github.com/yourusername/option_testing_qwen"
#define MyAppExeName "OptionsScreener.exe"
#define MyAppDescription "Smart Options Screener for NSE/BSE Options Trading"

[Setup]
; Application info
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation settings
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output settings
OutputDir=output
OutputBaseFilename=OptionsScreener_Setup_v{#MyAppVersion}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Visual settings
WizardStyle=modern
SetupIconFile=
; UninstallDisplayIcon={app}\{#MyAppExeName}

; Privileges - doesn't require admin rights
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Misc
DisableWelcomePage=no
DisableReadyPage=no
ShowLanguageDialog=auto

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main application files from PyInstaller output
Source: "..\dist\OptionsScreener\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Optional: Include sample config or data files
; Source: "..\example_screener_alert.json"; DestDir: "{app}\examples"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up log files and cache on uninstall
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\*.log"

[Code]
// Check if Microsoft Visual C++ Redistributable is installed (required by Python)
function VCRedistInstalled(): Boolean;
var
  RegKey: String;
begin
  RegKey := 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
  Result := RegKeyExists(HKLM, RegKey) or RegKeyExists(HKCU, RegKey);
  
  if not Result then
  begin
    RegKey := 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
    Result := RegKeyExists(HKLM, RegKey);
  end;
end;

procedure InitializeWizard;
begin
  // You can add custom initialization code here
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  
  // Warn if VC++ Redistributable might be missing
  if not VCRedistInstalled() then
  begin
    if MsgBox('Microsoft Visual C++ Redistributable may not be installed. ' +
              'The application might not work correctly without it.' + #13#10 + #13#10 +
              'Do you want to continue with the installation?', 
              mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := False;
    end;
  end;
end;


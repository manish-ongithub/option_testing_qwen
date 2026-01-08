; Inno Setup Script for Indian Options Paper Trading Application
; 
; Prerequisites:
;   1. Install Inno Setup from: https://jrsoftware.org/isdl.php
;   2. Build the app first with: pyinstaller PaperTradeApp.spec
;   3. Open this file in Inno Setup Compiler and click Build > Compile
;
; Output: Creates PaperTradeApp_Setup.exe in the 'installer/output' folder

#define MyAppName "Paper Trade App"
#define MyAppVersion "1.0"
#define MyAppPublisher "Your Company Name"
#define MyAppURL "https://github.com/yourusername/option_testing_qwen"
#define MyAppExeName "PaperTradeApp.exe"
#define MyAppDescription "Indian Options Paper Trading Simulator"

[Setup]
; Application info
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}
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
OutputBaseFilename=PaperTradeApp_Setup_v{#MyAppVersion}

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
Source: "..\dist\PaperTradeApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Create empty directories for runtime data
; These will be created on first run, but we ensure the structure exists

[Dirs]
; Create alerts_inbox directory for the user to place alert files
Name: "{app}\alerts_inbox"; Permissions: users-modify
; Create reports directory for generated reports
Name: "{app}\reports"; Permissions: users-modify
; Create data_cache directory for cached data
Name: "{app}\data_cache"; Permissions: users-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up generated files on uninstall
Type: filesandordirs; Name: "{app}\reports"
Type: filesandordirs; Name: "{app}\data_cache"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\*.log"
Type: files; Name: "{app}\*.db"

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
  // Custom initialization if needed
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

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Create a sample config file if it doesn't exist
    // Users should copy config_example.py to config.py and edit it
  end;
end;

